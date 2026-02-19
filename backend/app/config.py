"""
应用配置 — 使用 pydantic-settings 从 .env 文件加载环境变量。
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，自动读取 .env 或环境变量。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── PostgreSQL ──
    POSTGRES_USER: str = "edgestelle"
    POSTGRES_PASSWORD: str = "edgestelle_secret"
    POSTGRES_DB: str = "edgestelle"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = (
        "postgresql+asyncpg://edgestelle:edgestelle_secret@localhost:5432/edgestelle"
    )

    # ── MQTT ──
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_CLIENT_ID: str = "edgestelle-backend"
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""

    # ── AI Agent (步骤四预留) ──
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"


@lru_cache
def get_settings() -> Settings:
    """单例获取配置实例。"""
    return Settings()
