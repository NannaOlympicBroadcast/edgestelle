"""
EdgeStelle — Master FastAPI 路由
提供 REST API 和 WebSocket 端点
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc

from master.database import Node, Execution, LogLine, get_session
from master.mqtt_service import dispatch_command
from master.ws_manager import ws_manager

logger = logging.getLogger("edgestelle.master.api")

router = APIRouter(prefix="/api")


# ============================================================
# 请求 / 响应 模型
# ============================================================

class ExecuteRequest(BaseModel):
    """执行命令请求"""
    node_id: str
    command: str


class ExecuteResponse(BaseModel):
    """执行命令响应"""
    exec_id: str
    message: str = "命令已下发"


# ============================================================
# 节点 API
# ============================================================

@router.get("/nodes")
async def list_nodes() -> list[dict[str, Any]]:
    """获取所有节点列表"""
    async with get_session() as session:
        result = await session.execute(
            select(Node).order_by(desc(Node.last_heartbeat))
        )
        nodes = result.scalars().all()
        return [
            {
                "id": n.id,
                "name": n.name,
                "ip": n.ip,
                "status": n.status,
                "cpu_percent": n.cpu_percent,
                "mem_percent": n.mem_percent,
                "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
                "registered_at": n.registered_at.isoformat() if n.registered_at else None,
            }
            for n in nodes
        ]


@router.get("/nodes/{node_id}")
async def get_node(node_id: str) -> dict[str, Any]:
    """获取单个节点详情"""
    async with get_session() as session:
        result = await session.execute(select(Node).where(Node.id == node_id))
        node = result.scalar_one_or_none()
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")
        return {
            "id": node.id,
            "name": node.name,
            "ip": node.ip,
            "status": node.status,
            "cpu_percent": node.cpu_percent,
            "mem_percent": node.mem_percent,
            "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None,
            "registered_at": node.registered_at.isoformat() if node.registered_at else None,
        }


# ============================================================
# 执行 API
# ============================================================

@router.post("/execute", response_model=ExecuteResponse)
async def execute_command(req: ExecuteRequest) -> ExecuteResponse:
    """向指定节点下发命令"""
    # 验证节点是否存在且在线
    async with get_session() as session:
        result = await session.execute(select(Node).where(Node.id == req.node_id))
        node = result.scalar_one_or_none()
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")
        if node.status == "offline":
            raise HTTPException(status_code=400, detail="节点离线，无法执行")

    exec_id = await dispatch_command(req.node_id, req.command)
    return ExecuteResponse(exec_id=exec_id)


@router.get("/executions")
async def list_executions(node_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """获取执行记录列表，可按 node_id 过滤"""
    async with get_session() as session:
        query = select(Execution).order_by(desc(Execution.created_at)).limit(limit)
        if node_id:
            query = query.where(Execution.node_id == node_id)
        result = await session.execute(query)
        execs = result.scalars().all()
        return [
            {
                "id": e.id,
                "node_id": e.node_id,
                "command": e.command,
                "status": e.status,
                "exit_code": e.exit_code,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "finished_at": e.finished_at.isoformat() if e.finished_at else None,
            }
            for e in execs
        ]


@router.get("/executions/{exec_id}/logs")
async def get_execution_logs(exec_id: str) -> list[dict[str, Any]]:
    """获取某次执行的全部日志行"""
    async with get_session() as session:
        result = await session.execute(
            select(LogLine)
            .where(LogLine.execution_id == exec_id)
            .order_by(LogLine.timestamp)
        )
        logs = result.scalars().all()
        return [
            {
                "stream": l.stream,
                "content": l.content,
                "timestamp": l.timestamp,
            }
            for l in logs
        ]


# ============================================================
# WebSocket 端点
# ============================================================

# 此文件中不直接定义 WS 路由，而是在 app.py 中挂载
# 见 app.py: @app.websocket("/ws/logs/{node_id}")
