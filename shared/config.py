"""
EdgeStelle — 共享配置加载模块
使用 pydantic-settings 从 .env 文件读取配置
"""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录（pyproject.toml 所在位置）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MQTTSettings(BaseSettings):
    """MQTT 连接相关配置"""
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_use_tls: bool = False
    mqtt_ca_cert: str = "deploy/certs/ca.crt"
    mqtt_client_cert: str = "deploy/certs/client.crt"
    mqtt_client_key: str = "deploy/certs/client.key"

    # 安全
    secret_key: str = "change-me"
    aes_key: str = "0" * 64  # 32 字节 hex


class MasterSettings(MQTTSettings):
    """Master 独有配置（继承 MQTT 配置）"""
    master_host: str = "0.0.0.0"
    master_port: int = 8000
    database_url: str = f"sqlite+aiosqlite:///{_PROJECT_ROOT / 'edgestelle.db'}"


class AgentSettings(MQTTSettings):
    """Agent 独有配置（继承 MQTT 配置）"""
    node_name: str = "edge-node-01"
    # node_id 由 Master 分配，注册后持久化到本地文件
    node_id_file: str = str(_PROJECT_ROOT / ".node_id")
