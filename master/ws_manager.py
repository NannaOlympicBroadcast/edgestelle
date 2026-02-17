"""
EdgeStelle — WebSocket 连接管理器
管理前端 WebSocket 连接，支持按 node_id 分组推送实时日志
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("edgestelle.ws")


class WebSocketManager:
    """
    管理 WebSocket 连接，支持：
    1. 全局广播（节点状态变更）
    2. 按 node_id 定向推送（实时日志）
    """

    def __init__(self):
        # node_id → set[WebSocket]:  关注特定节点日志的连接
        self._log_subscribers: dict[str, set[WebSocket]] = {}
        # 全局连接列表（接收节点状态等广播）
        self._global_connections: set[WebSocket] = set()

    async def connect_global(self, ws: WebSocket) -> None:
        """接受全局连接（Dashboard 状态推送）"""
        await ws.accept()
        self._global_connections.add(ws)
        logger.info("全局 WS 连接建立，当前 %d 个", len(self._global_connections))

    async def connect_log(self, ws: WebSocket, node_id: str) -> None:
        """接受日志连接（Terminal View 实时日志）"""
        await ws.accept()
        if node_id not in self._log_subscribers:
            self._log_subscribers[node_id] = set()
        self._log_subscribers[node_id].add(ws)
        logger.info("日志 WS 连接建立: node=%s，当前 %d 个", node_id, len(self._log_subscribers[node_id]))

    def disconnect_global(self, ws: WebSocket) -> None:
        """移除全局连接"""
        self._global_connections.discard(ws)

    def disconnect_log(self, ws: WebSocket, node_id: str) -> None:
        """移除日志连接"""
        if node_id in self._log_subscribers:
            self._log_subscribers[node_id].discard(ws)
            if not self._log_subscribers[node_id]:
                del self._log_subscribers[node_id]

    async def broadcast_global(self, data: dict[str, Any]) -> None:
        """向所有全局连接广播消息"""
        dead: list[WebSocket] = []
        message = json.dumps(data, ensure_ascii=False)
        for ws in self._global_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._global_connections.discard(ws)

    async def push_log(self, node_id: str, data: dict[str, Any]) -> None:
        """向关注指定节点的连接推送日志"""
        subscribers = self._log_subscribers.get(node_id, set())
        if not subscribers:
            return
        dead: list[WebSocket] = []
        message = json.dumps(data, ensure_ascii=False)
        for ws in subscribers:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            subscribers.discard(ws)


# 全局单例
ws_manager = WebSocketManager()
