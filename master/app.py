"""
EdgeStelle — Master FastAPI 应用入口
组装路由、MQTT 服务、数据库、静态文件
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from shared.config import MasterSettings
from master.database import init_db, close_db
from master.mqtt_service import start_mqtt_service, stop_mqtt_service
from master.ws_manager import ws_manager
from master.api import router as api_router

# ---------- 日志配置 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("edgestelle.master")


# ============================================================
# 应用生命周期
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的初始化与清理"""
    settings = MasterSettings()

    # 启动数据库
    logger.info("正在初始化数据库: %s", settings.database_url)
    await init_db(settings.database_url)

    # 启动 MQTT 服务
    await start_mqtt_service(settings)

    # 启动节点健康检查后台任务
    health_task = asyncio.create_task(_node_health_checker())

    yield

    # 关闭
    health_task.cancel()
    await stop_mqtt_service()
    await close_db()
    logger.info("Master 已关闭")


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="EdgeStelle Master",
    description="MQTT 多节点脚本执行管理平台",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 REST API 路由
app.include_router(api_router)

# 挂载前端静态文件
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


# ============================================================
# WebSocket 路由
# ============================================================

@app.websocket("/ws/logs/{node_id}")
async def ws_logs(websocket: WebSocket, node_id: str):
    """实时日志 WebSocket — 前端订阅特定节点的日志流"""
    await ws_manager.connect_log(websocket, node_id)
    try:
        while True:
            # 保持连接，接收前端心跳或忽略
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_log(websocket, node_id)
        logger.info("日志 WS 断开: node=%s", node_id)


@app.websocket("/ws/global")
async def ws_global(websocket: WebSocket):
    """全局状态 WebSocket — Dashboard 实时更新"""
    await ws_manager.connect_global(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_global(websocket)
        logger.info("全局 WS 断开")


# ============================================================
# 节点健康检查后台任务
# ============================================================

async def _node_health_checker():
    """
    每 30 秒检查一次：若节点超过 60 秒未发心跳，标记为 offline
    """
    import datetime
    from sqlalchemy import select, update
    from master.database import Node, get_session

    while True:
        try:
            await asyncio.sleep(30)
            threshold = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
            async with get_session() as session:
                result = await session.execute(
                    select(Node).where(
                        Node.status != "offline",
                        Node.last_heartbeat < threshold,
                    )
                )
                stale_nodes = result.scalars().all()
                for node in stale_nodes:
                    node.status = "offline"
                    logger.warning("节点离线（心跳超时）: %s (%s)", node.name, node.id)
                    await ws_manager.broadcast_global({
                        "event": "node_update",
                        "node_id": node.id,
                        "name": node.name,
                        "status": "offline",
                    })
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("健康检查异常")
