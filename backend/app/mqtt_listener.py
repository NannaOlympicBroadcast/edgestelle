"""
MQTT 监听服务 — 订阅设备上报的测试报告，校验并入库。

可通过两种方式运行:
  1. 独立进程: python -m backend.app.mqtt_listener
  2. FastAPI 生命周期集成 (在 main.py 中启动后台任务)
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import async_session
from .models import TestReport, TestTemplate

logger = logging.getLogger("edgestelle.mqtt_listener")
settings = get_settings()


# ═══════════════════════════════════════════════════════════════
#  报告校验与入库
# ═══════════════════════════════════════════════════════════════

REQUIRED_FIELDS = {"template_id", "device_id", "results"}


def validate_report_payload(payload: dict) -> tuple[bool, str]:
    """
    校验上报的 JSON 格式。

    Returns
    -------
    (is_valid, error_message)
    """
    missing = REQUIRED_FIELDS - set(payload.keys())
    if missing:
        return False, f"缺少必要字段: {missing}"

    if not isinstance(payload["results"], list) or len(payload["results"]) == 0:
        return False, "results 须为非空数组"

    try:
        uuid.UUID(str(payload["template_id"]))
    except ValueError:
        return False, f"template_id 格式无效: {payload['template_id']}"

    return True, ""


async def persist_report(payload: dict) -> uuid.UUID | None:
    """
    将校验通过的报告写入 PostgreSQL 并返回 report_id。
    """
    async with async_session() as session:
        async with session.begin():
            # 检查模板是否存在
            template_id = uuid.UUID(str(payload["template_id"]))
            result = await session.execute(
                select(TestTemplate).where(TestTemplate.id == template_id)
            )
            template = result.scalar_one_or_none()
            if template is None:
                logger.warning("⚠️  模板不存在: %s — 仍然入库，但标记 template 未知",
                               template_id)

            report = TestReport(
                template_id=template_id,
                device_id=payload["device_id"],
                report_data=payload,
                status="pending",
            )
            session.add(report)
            await session.flush()
            report_id = report.id
            logger.info("💾 报告已入库 — id=%s device=%s",
                        report_id, payload["device_id"])
            return report_id


# ═══════════════════════════════════════════════════════════════
#  MQTT 回调
# ═══════════════════════════════════════════════════════════════

# 新报告入库后的回调列表 (供 AI Agent 步骤四注册)
_on_report_saved_callbacks: list = []


def register_on_report_saved(callback):
    """注册新报告入库后的回调函数。callback(report_id, payload)"""
    _on_report_saved_callbacks.append(callback)


def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        topic = "iot/test/report/#"
        client.subscribe(topic, qos=1)
        logger.info("✅ MQTT 已连接并订阅 %s", topic)
    else:
        logger.error("❌ MQTT 连接失败 — rc=%d", rc)


def _on_message(client, userdata, msg):
    """收到消息后：校验 → 入库 → 触发回调。"""
    topic = msg.topic
    logger.info("📩 收到消息 — topic=%s size=%d", topic, len(msg.payload))

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error("❌ JSON 解析失败: %s", e)
        return

    is_valid, err = validate_report_payload(payload)
    if not is_valid:
        logger.error("❌ 报告校验失败: %s", err)
        return

    # 在事件循环中执行异步入库
    loop = userdata.get("loop")
    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(
            _handle_report(payload), loop
        )
        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error("❌ 入库失败: %s", e, exc_info=True)
    else:
        # 没有运行中的事件循环时，创建新的
        asyncio.run(_handle_report(payload))


async def _handle_report(payload: dict):
    report_id = await persist_report(payload)
    if report_id:
        for cb in _on_report_saved_callbacks:
            try:
                result = cb(report_id, payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("❌ 回调执行失败: %s", e, exc_info=True)


# ═══════════════════════════════════════════════════════════════
#  MQTT 客户端启动
# ═══════════════════════════════════════════════════════════════


def create_mqtt_client(loop: asyncio.AbstractEventLoop | None = None) -> mqtt.Client:
    """
    创建并配置 MQTT 客户端 (尚未连接)。

    Parameters
    ----------
    loop : asyncio.AbstractEventLoop, optional
        传入运行中的事件循环，使入库操作在该循环上执行。

    Returns
    -------
    mqtt.Client
    """
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.MQTT_CLIENT_ID,
        protocol=mqtt.MQTTv5,
        userdata={"loop": loop},
    )

    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

    client.on_connect = _on_connect
    client.on_message = _on_message

    return client


def start_mqtt_listener(loop: asyncio.AbstractEventLoop | None = None) -> mqtt.Client:
    """
    连接 Broker 并启动后台网络循环。返回客户端实例以便管理生命周期。
    """
    client = create_mqtt_client(loop)
    client.connect(
        settings.MQTT_BROKER_HOST,
        settings.MQTT_BROKER_PORT,
        keepalive=60,
    )
    client.loop_start()
    logger.info("🚀 MQTT 监听已启动 — %s:%d",
                settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT)
    return client


# ═══════════════════════════════════════════════════════════════
#  独立运行入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    )
    logger.info("EdgeStelle MQTT Listener — 独立模式启动")
    loop = asyncio.new_event_loop()
    client = start_mqtt_listener(loop)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("🛑 收到中断信号，正在停止…")
    finally:
        client.loop_stop()
        client.disconnect()
        loop.close()
