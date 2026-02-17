"""
EdgeStelle — MQTT 客户端封装
基于 paho-mqtt，提供 TLS 配置、自动重连、JSON 发布等便捷方法
"""

from __future__ import annotations

import json
import logging
import ssl
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt
from pydantic import BaseModel

from shared.config import MQTTSettings

logger = logging.getLogger("edgestelle.mqtt")


class MQTTClientWrapper:
    """
    paho-mqtt 的高层封装，统一 TLS / 重连 / JSON 序列化
    """

    def __init__(
        self,
        client_id: str,
        settings: MQTTSettings,
        *,
        clean_session: bool = True,
    ):
        self._settings = settings
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=clean_session,
        )

        # ---------- TLS ----------
        if settings.mqtt_use_tls:
            ca = Path(settings.mqtt_ca_cert)
            cert = Path(settings.mqtt_client_cert)
            key = Path(settings.mqtt_client_key)
            if not ca.exists():
                raise FileNotFoundError(f"CA 证书不存在: {ca}")
            self._client.tls_set(
                ca_certs=str(ca),
                certfile=str(cert) if cert.exists() else None,
                keyfile=str(key) if key.exists() else None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            logger.info("MQTT TLS 已启用")

        # ---------- 回调 ----------
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # 用户注册的 topic → callback 映射
        self._topic_handlers: dict[str, Callable] = {}
        # 待订阅列表（连接后自动订阅）
        self._subscriptions: list[tuple[str, int]] = []

        # 重连控制
        self._reconnect_delay = 1  # 指数退避初始值（秒）
        self._max_reconnect_delay = 60

    # ============================================================
    # 连接管理
    # ============================================================

    def connect(self) -> None:
        """连接到 MQTT Broker（同步阻塞直到连接成功或失败）"""
        broker = self._settings.mqtt_broker
        port = self._settings.mqtt_port
        logger.info("正在连接 MQTT Broker %s:%d ...", broker, port)
        self._client.connect(broker, port, keepalive=60)

    def loop_start(self) -> None:
        """在后台线程中启动网络循环"""
        self._client.loop_start()

    def loop_stop(self) -> None:
        """停止网络循环"""
        self._client.loop_stop()

    def disconnect(self) -> None:
        """断开连接"""
        self._client.disconnect()

    # ============================================================
    # 发布 / 订阅
    # ============================================================

    def publish_json(self, topic: str, payload: BaseModel | dict, qos: int = 1) -> None:
        """将 Pydantic 模型或 dict 序列化为 JSON 并发布"""
        if isinstance(payload, BaseModel):
            data = payload.model_dump_json()
        else:
            data = json.dumps(payload, ensure_ascii=False)
        self._client.publish(topic, data, qos=qos)
        logger.debug("PUB → %s : %s", topic, data[:200])

    def subscribe(self, topic: str, qos: int = 1, handler: Optional[Callable] = None) -> None:
        """
        订阅 Topic 并（可选）注册消息处理函数
        handler 签名: handler(topic: str, payload: dict) -> None
        """
        self._subscriptions.append((topic, qos))
        if handler:
            self._topic_handlers[topic] = handler
        # 如果已经连接，立即订阅
        if self._client.is_connected():
            self._client.subscribe(topic, qos)
            logger.info("SUB ← %s (qos=%d)", topic, qos)

    # ============================================================
    # 内部回调
    # ============================================================

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """连接成功回调 — 自动重新订阅所有 Topic"""
        if rc == 0:
            logger.info("✅ MQTT 连接成功")
            self._reconnect_delay = 1  # 重置退避
            # 重新订阅
            for topic, qos in self._subscriptions:
                client.subscribe(topic, qos)
                logger.info("SUB ← %s (qos=%d)", topic, qos)
        else:
            logger.error("❌ MQTT 连接失败, rc=%d", rc)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """断连回调 — 如果非主动断开，启动指数退避重连"""
        if rc != 0:
            logger.warning("⚠️ MQTT 意外断连 (rc=%d)，%d 秒后重连...", rc, self._reconnect_delay)
            time.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
            try:
                client.reconnect()
            except Exception as e:
                logger.error("重连失败: %s", e)

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        """收到消息 — 解析 JSON 并分发给对应的 handler"""
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("消息解析失败 [%s]: %s", topic, e)
            return

        logger.debug("MSG ← %s : %s", topic, str(payload)[:200])

        # 精确匹配
        if topic in self._topic_handlers:
            try:
                self._topic_handlers[topic](topic, payload)
            except Exception:
                logger.exception("处理消息异常 [%s]", topic)
            return

        # 通配符匹配：遍历已注册的通配 topic
        for pattern, handler in self._topic_handlers.items():
            if mqtt.topic_matches_sub(pattern, topic):
                try:
                    handler(topic, payload)
                except Exception:
                    logger.exception("处理消息异常 [%s]", topic)
                return

        logger.debug("未找到 handler: %s", topic)
