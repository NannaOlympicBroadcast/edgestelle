"""
FastAPI 应用入口 — Router 注册 + Lifespan (自动建表 + MQTT 监听 + AI Agent) + CORS。
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import engine
from .models import Base

settings = get_settings()


# ───────────────────────── Lifespan ─────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时自动建表 + 启动 MQTT 监听，关闭时清理。"""
    # 1. 自动建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 启动 MQTT 监听 (后台线程)
    mqtt_client = None
    try:
        from .mqtt_listener import start_mqtt_listener, register_on_report_saved
        from ai_agent.agent import on_new_report

        loop = asyncio.get_running_loop()
        mqtt_client = start_mqtt_listener(loop)

        # 3. 注册 AI Agent 回调
        register_on_report_saved(on_new_report)
    except Exception as e:
        import logging
        logging.getLogger("edgestelle").warning(
            "⚠️  MQTT/AI Agent 初始化跳过 (可能 Broker 未就绪): %s", e
        )

    yield

    # 清理
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    await engine.dispose()


# ───────────────────────── App ─────────────────────────


app = FastAPI(
    title="EdgeStelle — IoT 测试管理平台",
    description="IoT 设备自动化测试模板管理、报告收集与 AI 智能分析 API",
    version="0.2.0",
    lifespan=lifespan,
)

# ───────────────────────── CORS ─────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────── Routers ─────────────────────────

from .routers import auth, api_keys, templates, reports, system_config  # noqa: E402

app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(templates.router)
app.include_router(reports.router)
app.include_router(system_config.router)


# ───────────────────────── Health ─────────────────────────


@app.get("/health", tags=["System"])
async def health_check():
    """健康检查端点。"""
    return {"status": "ok", "service": "edgestelle-backend"}
