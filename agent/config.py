"""
EdgeStelle — Agent 配置
独立于 Master 的配置加载，包含节点 ID 的持久化逻辑
"""

from __future__ import annotations

import logging
from pathlib import Path

from shared.config import AgentSettings

logger = logging.getLogger("edgestelle.agent.config")


def load_node_id(settings: AgentSettings) -> str | None:
    """从本地文件加载已分配的 node_id，不存在则返回 None"""
    path = Path(settings.node_id_file)
    if path.exists():
        node_id = path.read_text().strip()
        if node_id:
            logger.info("已加载本地 node_id: %s", node_id)
            return node_id
    return None


def save_node_id(settings: AgentSettings, node_id: str) -> None:
    """将 Master 分配的 node_id 持久化到本地文件"""
    path = Path(settings.node_id_file)
    path.write_text(node_id)
    logger.info("node_id 已保存到 %s", path)
