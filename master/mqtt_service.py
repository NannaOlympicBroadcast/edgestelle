"""
EdgeStelle — Master 端 MQTT 服务
处理节点注册、心跳、日志接收，并将日志推送给 WebSocket 前端
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import Any

from sqlalchemy import select, update

from shared.config import MasterSettings
from shared.mqtt_wrapper import MQTTClientWrapper
from shared.protocol import (
    TOPIC_REGISTER,
    TOPIC_HEARTBEAT,
    MsgType,
    RegisterAck,
    RegisterNak,
    topic_cmd,
    CommandPayload,
)
from master.database import Node, Execution, LogLine, get_session
from master.ws_manager import ws_manager

logger = logging.getLogger("edgestelle.master.mqtt")

# 全局 MQTT 客户端实例（延迟初始化）
_mqtt: MQTTClientWrapper | None = None
# asyncio 事件循环引用（用于在 paho 回调线程中调度协程）
_loop: asyncio.AbstractEventLoop | None = None


def get_mqtt_client() -> MQTTClientWrapper:
    """获取全局 MQTT 客户端"""
    if _mqtt is None:
        raise RuntimeError("MQTT 服务尚未初始化")
    return _mqtt


async def start_mqtt_service(settings: MasterSettings) -> None:
    """启动 Master MQTT 服务：连接 Broker 并注册回调"""
    global _mqtt, _loop
    _loop = asyncio.get_running_loop()

    _mqtt = MQTTClientWrapper(
        client_id=f"master-{uuid.uuid4().hex[:8]}",
        settings=settings,
    )

    # 注册消息处理器
    _mqtt.subscribe(TOPIC_REGISTER, qos=1, handler=_handle_register)
    _mqtt.subscribe(TOPIC_HEARTBEAT, qos=1, handler=_handle_heartbeat)
    _mqtt.subscribe("log/+", qos=1, handler=_handle_log)  # 通配符订阅所有节点日志

    _mqtt.connect()
    _mqtt.loop_start()
    logger.info("Master MQTT 服务已启动")


async def stop_mqtt_service() -> None:
    """停止 MQTT 服务"""
    global _mqtt
    if _mqtt:
        _mqtt.loop_stop()
        _mqtt.disconnect()
        _mqtt = None
        logger.info("Master MQTT 服务已停止")


# ============================================================
# 辅助函数：在 paho 回调线程中安全调度异步任务
# ============================================================

def _schedule_async(coro):
    """将协程调度到主事件循环中执行"""
    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _loop)


# ============================================================
# 消息处理器（运行在 paho 线程，通过 _schedule_async 桥接到异步）
# ============================================================

def _handle_register(topic: str, payload: dict) -> None:
    """处理节点注册请求"""
    _schedule_async(_async_handle_register(payload))


def _handle_heartbeat(topic: str, payload: dict) -> None:
    """处理节点心跳"""
    _schedule_async(_async_handle_heartbeat(payload))


def _handle_log(topic: str, payload: dict) -> None:
    """处理日志消息"""
    _schedule_async(_async_handle_log(topic, payload))


# ============================================================
# 异步消息处理实现
# ============================================================

async def _async_handle_register(payload: dict) -> None:
    """验证密钥 → 分配 node_id → 存库 → 回复 ACK"""
    msg_type = payload.get("type")
    if msg_type != MsgType.REGISTER_REQ:
        return

    from shared.config import MasterSettings
    settings = MasterSettings()

    # 验证预共享密钥
    if payload.get("secret_key") != settings.secret_key:
        logger.warning("节点注册失败：密钥不匹配 (name=%s)", payload.get("node_name"))
        if _mqtt:
            _mqtt.publish_json(TOPIC_REGISTER, RegisterNak(reason="密钥错误"))
        return

    node_name = payload.get("node_name", "unknown")
    node_ip = payload.get("ip", "")

    # 检查是否已注册（同名节点重新上线）
    async with get_session() as session:
        result = await session.execute(
            select(Node).where(Node.name == node_name)
        )
        existing = result.scalar_one_or_none()

        if existing:
            node_id = existing.id
            existing.ip = node_ip
            existing.status = "online"
            existing.last_heartbeat = datetime.datetime.utcnow()
            logger.info("节点重新上线: %s (%s)", node_name, node_id)
        else:
            node_id = uuid.uuid4().hex[:12]
            node = Node(
                id=node_id,
                name=node_name,
                ip=node_ip,
                status="online",
                last_heartbeat=datetime.datetime.utcnow(),
            )
            session.add(node)
            logger.info("新节点注册: %s → %s", node_name, node_id)

    # 回复 ACK
    if _mqtt:
        _mqtt.publish_json(
            TOPIC_REGISTER,
            RegisterAck(node_id=node_id, message=f"欢迎, {node_name}!"),
        )

    # 广播节点状态变更到前端
    await ws_manager.broadcast_global({
        "event": "node_update",
        "node_id": node_id,
        "name": node_name,
        "status": "online",
    })


async def _async_handle_heartbeat(payload: dict) -> None:
    """更新节点心跳时间和资源状态"""
    node_id = payload.get("node_id")
    if not node_id:
        return

    async with get_session() as session:
        await session.execute(
            update(Node)
            .where(Node.id == node_id)
            .values(
                status=payload.get("status", "idle"),
                cpu_percent=payload.get("cpu_percent", 0.0),
                mem_percent=payload.get("mem_percent", 0.0),
                last_heartbeat=datetime.datetime.utcnow(),
            )
        )

    # 广播到前端
    await ws_manager.broadcast_global({
        "event": "heartbeat",
        "node_id": node_id,
        "status": payload.get("status", "idle"),
        "cpu_percent": payload.get("cpu_percent", 0.0),
        "mem_percent": payload.get("mem_percent", 0.0),
        "timestamp": payload.get("timestamp"),
    })


async def _async_handle_log(topic: str, payload: dict) -> None:
    """接收日志行 / 命令完成通知 → 存库 + 推送前端"""
    msg_type = payload.get("type")
    node_id = payload.get("node_id", "")
    exec_id = payload.get("exec_id", "")

    if msg_type == MsgType.LOG_LINE:
        # 存入数据库
        async with get_session() as session:
            log = LogLine(
                execution_id=exec_id,
                stream=payload.get("stream", "stdout"),
                content=payload.get("line", ""),
                timestamp=payload.get("timestamp", 0.0),
            )
            session.add(log)

        # 推送到前端 WebSocket
        await ws_manager.push_log(node_id, {
            "event": "log_line",
            "exec_id": exec_id,
            "stream": payload.get("stream", "stdout"),
            "line": payload.get("line", ""),
            "timestamp": payload.get("timestamp"),
        })

    elif msg_type == MsgType.CMD_DONE:
        exit_code = payload.get("exit_code", -1)
        status = "success" if exit_code == 0 else "failed"

        # 更新执行记录状态
        async with get_session() as session:
            await session.execute(
                update(Execution)
                .where(Execution.id == exec_id)
                .values(
                    status=status,
                    exit_code=exit_code,
                    finished_at=datetime.datetime.utcnow(),
                )
            )

        # 更新节点状态为空闲
        async with get_session() as session:
            await session.execute(
                update(Node)
                .where(Node.id == node_id)
                .values(status="idle")
            )

        # 推送到前端
        await ws_manager.push_log(node_id, {
            "event": "cmd_done",
            "exec_id": exec_id,
            "exit_code": exit_code,
            "status": status,
        })
        await ws_manager.broadcast_global({
            "event": "node_update",
            "node_id": node_id,
            "status": "idle",
        })


# ============================================================
# 对外接口：下发命令
# ============================================================

async def dispatch_command(node_id: str, command: str) -> str:
    """
    向指定节点下发命令
    返回 exec_id
    """
    if not _mqtt:
        raise RuntimeError("MQTT 服务未启动")

    exec_id = uuid.uuid4().hex[:12]

    # 创建执行记录
    async with get_session() as session:
        execution = Execution(
            id=exec_id,
            node_id=node_id,
            command=command,
            status="running",
        )
        session.add(execution)

    # 更新节点状态为 busy
    async with get_session() as session:
        await session.execute(
            update(Node)
            .where(Node.id == node_id)
            .values(status="busy")
        )

    # 通过 MQTT 发送命令
    _mqtt.publish_json(
        topic_cmd(node_id),
        CommandPayload(exec_id=exec_id, command=command),
    )

    logger.info("命令已下发: node=%s, exec=%s, cmd=%s", node_id, exec_id, command[:100])

    # 通知前端节点变忙
    await ws_manager.broadcast_global({
        "event": "node_update",
        "node_id": node_id,
        "status": "busy",
    })

    return exec_id
