"""
设备端 SDK 配置 — 从环境变量或命令行参数加载。
"""

import os
from dataclasses import dataclass, field


@dataclass
class DeviceConfig:
    """设备 SDK 运行时配置。"""

    # 设备标识
    device_id: str = field(default_factory=lambda: os.getenv("DEVICE_ID", "edge-dev-001"))

    # 云端 API
    api_base_url: str = field(
        default_factory=lambda: os.getenv("API_BASE_URL", "http://localhost:8000")
    )

    # MQTT Broker
    mqtt_broker_host: str = field(
        default_factory=lambda: os.getenv("MQTT_BROKER_HOST", "localhost")
    )
    mqtt_broker_port: int = field(
        default_factory=lambda: int(os.getenv("MQTT_BROKER_PORT", "1883"))
    )
    mqtt_username: str = field(
        default_factory=lambda: os.getenv("MQTT_USERNAME", "")
    )
    mqtt_password: str = field(
        default_factory=lambda: os.getenv("MQTT_PASSWORD", "")
    )

    # MQTT Topic 前缀
    mqtt_report_topic_prefix: str = "iot/test/report"

    @property
    def mqtt_report_topic(self) -> str:
        """该设备的报告发布 Topic。"""
        return f"{self.mqtt_report_topic_prefix}/{self.device_id}"
