"""
EdgeStelle — Agent 主逻辑
1. 连接 MQTT Broker
2. 发送注册请求 → 等待 ACK → 保存 node_id
3. 订阅 cmd/{node_id}
4. 定时发送心跳
5. 收到命令 → 调用 executor → 流式回传日志
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from typing import Optional

from shared.config import AgentSettings
from shared.mqtt_wrapper import MQTTClientWrapper
from shared.protocol import (
    TOPIC_REGISTER,
    TOPIC_HEARTBEAT,
    MsgType,
    RegisterRequest,
    HeartbeatPayload,
    topic_cmd,
)
from agent.config import load_node_id, save_node_id
from agent.executor import execute_command

logger = logging.getLogger("edgestelle.agent")

# ---------- 全局状态 ----------
_node_id: Optional[str] = None         # Master 分配的唯一 ID
_status: str = "idle"                   # idle / busy
_mqtt: Optional[MQTTClientWrapper] = None
_settings: Optional[AgentSettings] = None
_register_event: Optional[asyncio.Event] = None
_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_local_ip() -> str:
    """获取本机 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_system_stats() -> tuple[float, float]:
    """获取 CPU / 内存使用率（尽量使用 psutil，不可用则返回 0）"""
    try:
        import psutil
        return psutil.cpu_percent(interval=0), psutil.virtual_memory().percent
    except ImportError:
        return 0.0, 0.0


# ============================================================
# MQTT 消息处理
# ============================================================

def _handle_register_response(topic: str, payload: dict) -> None:
    """处理注册响应（ACK / NAK）"""
    global _node_id
    msg_type = payload.get("type")

    if msg_type == MsgType.REGISTER_ACK:
        _node_id = payload.get("node_id", "")
        if _settings:
            save_node_id(_settings, _node_id)
        logger.info("✅ 注册成功! node_id = %s, 消息: %s", _node_id, payload.get("message"))
        # 通知主事件循环注册完成
        if _register_event and _loop:
            _loop.call_soon_threadsafe(_register_event.set)
    elif msg_type == MsgType.REGISTER_NAK:
        logger.error("❌ 注册被拒绝: %s", payload.get("reason"))


def _handle_command(topic: str, payload: dict) -> None:
    """收到命令 → 调度到异步执行器"""
    msg_type = payload.get("type")
    if msg_type != MsgType.CMD:
        return

    exec_id = payload.get("exec_id", "")
    command = payload.get("command", "")
    logger.info("收到命令 [exec=%s]: %s", exec_id, command[:200])

    # 在事件循环中调度异步任务
    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(
            _async_execute(exec_id, command), _loop
        )


async def _async_execute(exec_id: str, command: str) -> None:
    """异步执行命令并更新状态"""
    global _status
    _status = "busy"

    try:
        await execute_command(command, exec_id, _node_id or "", _mqtt)
    except Exception:
        logger.exception("命令执行异常 [exec=%s]", exec_id)
    finally:
        _status = "idle"


# ============================================================
# 注册与心跳
# ============================================================

async def _do_register(settings: AgentSettings) -> None:
    """发送注册请求并等待 ACK"""
    global _register_event
    _register_event = asyncio.Event()

    logger.info("正在向 Master 注册 (node_name=%s)...", settings.node_name)
    _mqtt.publish_json(
        TOPIC_REGISTER,
        RegisterRequest(
            node_name=settings.node_name,
            secret_key=settings.secret_key,
            ip=_get_local_ip(),
        ),
    )

    # 最多等待 30 秒
    try:
        await asyncio.wait_for(_register_event.wait(), timeout=30)
    except asyncio.TimeoutError:
        logger.error("注册超时（30 秒无响应）")
        raise


async def _heartbeat_loop() -> None:
    """每 15 秒发送一次心跳"""
    while True:
        try:
            if _node_id:
                cpu, mem = _get_system_stats()
                _mqtt.publish_json(
                    TOPIC_HEARTBEAT,
                    HeartbeatPayload(
                        node_id=_node_id,
                        status=_status,
                        cpu_percent=cpu,
                        mem_percent=mem,
                    ),
                )
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("心跳发送异常")
            await asyncio.sleep(5)


# ============================================================
# Agent 主入口
# ============================================================

async def run_agent() -> None:
    """Agent 主循环"""
    global _mqtt, _settings, _node_id, _loop

    _settings = AgentSettings()
    _loop = asyncio.get_running_loop()

    # ---------- 初始化 MQTT ----------
    _mqtt = MQTTClientWrapper(
        client_id=f"agent-{_settings.node_name}",
        settings=_settings,
    )

    # 先订阅注册通道
    _mqtt.subscribe(TOPIC_REGISTER, qos=1, handler=_handle_register_response)

    # 连接并启动网络循环
    _mqtt.connect()
    _mqtt.loop_start()

    # ---------- 注册流程 ----------
    # 检查是否已有 node_id
    _node_id = load_node_id(_settings)
    if _node_id:
        logger.info("使用已有 node_id: %s，发送重新注册请求...", _node_id)

    # 无论是否有旧 ID，都发注册请求以同步状态
    await _do_register(_settings)

    if not _node_id:
        logger.error("注册失败，Agent 退出")
        _mqtt.loop_stop()
        _mqtt.disconnect()
        return

    # ---------- 订阅命令通道 ----------
    cmd_topic = topic_cmd(_node_id)
    _mqtt.subscribe(cmd_topic, qos=1, handler=_handle_command)
    logger.info("已订阅命令通道: %s", cmd_topic)

    # ---------- 启动心跳 ----------
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    logger.info("🚀 Agent 已就绪，等待命令...")

    # ---------- 保持运行 ----------
    try:
        # 无限等待，直到被信号或 Ctrl+C 中断
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Agent 正在关闭...")
    finally:
        heartbeat_task.cancel()
        _mqtt.loop_stop()
        _mqtt.disconnect()
        logger.info("Agent 已关闭")
