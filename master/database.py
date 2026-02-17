"""
EdgeStelle — Master 数据库模型与会话管理
使用 SQLAlchemy 2.0 async + aiosqlite
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import String, Float, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ============================================================
# 基类
# ============================================================

class Base(DeclarativeBase):
    pass


# ============================================================
# 节点表
# ============================================================

class Node(Base):
    """边缘节点"""
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)            # Master 分配的唯一 ID
    name: Mapped[str] = mapped_column(String(128), default="")               # 节点自报名称
    ip: Mapped[str] = mapped_column(String(45), default="")                  # 节点 IP
    status: Mapped[str] = mapped_column(String(16), default="offline")       # online / offline / busy
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    mem_percent: Mapped[float] = mapped_column(Float, default=0.0)
    last_heartbeat: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    registered_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # 关系
    executions: Mapped[list["Execution"]] = relationship(back_populates="node", cascade="all, delete-orphan")


# ============================================================
# 执行记录表
# ============================================================

class Execution(Base):
    """一次命令执行的记录"""
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)            # UUID
    node_id: Mapped[str] = mapped_column(String(64), ForeignKey("nodes.id"))
    command: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="running")       # running / success / failed
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # 关系
    node: Mapped["Node"] = relationship(back_populates="executions")
    logs: Mapped[list["LogLine"]] = relationship(back_populates="execution", cascade="all, delete-orphan")


# ============================================================
# 日志行表
# ============================================================

class LogLine(Base):
    """单行日志"""
    __tablename__ = "log_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), ForeignKey("executions.id"))
    stream: Mapped[str] = mapped_column(String(8), default="stdout")         # stdout / stderr
    content: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[float] = mapped_column(Float, default=0.0)

    # 关系
    execution: Mapped["Execution"] = relationship(back_populates="logs")


# ============================================================
# 引擎与会话工厂（延迟初始化）
# ============================================================

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str) -> None:
    """初始化数据库引擎并创建所有表"""
    global _engine, _session_factory
    _engine = create_async_engine(database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库引擎"""
    global _engine
    if _engine:
        await _engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的上下文管理器"""
    if _session_factory is None:
        raise RuntimeError("数据库尚未初始化，请先调用 init_db()")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
