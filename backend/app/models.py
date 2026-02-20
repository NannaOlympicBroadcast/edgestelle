"""
SQLAlchemy 2.0 ORM 模型 — test_templates / test_reports / users / api_keys / system_configs。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """声明式基类。"""
    pass


class TestTemplate(Base):
    """测试模板表 — 存储 JSON Schema 格式的测试指标定义。"""

    __tablename__ = "test_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="模板名称")
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0", comment="版本号"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="模板描述"
    )
    schema_definition: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="测试指标及阈值定义 (JSON)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    # relationship
    reports: Mapped[list["TestReport"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TestTemplate {self.name} v{self.version}>"


class TestReport(Base):
    """测试报告表 — 存储设备上报的填充数据及 AI 分析结果。"""

    __tablename__ = "test_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_templates.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联模板 ID",
    )
    device_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="设备标识"
    )
    report_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="设备上报的测试数据 (JSON)"
    )
    ai_analysis: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI Agent 分析结果 (Markdown)"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", comment="pending / analyzed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="入库时间",
    )

    # relationship
    template: Mapped["TestTemplate"] = relationship(back_populates="reports")

    def __repr__(self) -> str:
        return f"<TestReport device={self.device_id} status={self.status}>"


# ────────────────────────── 用户与鉴权 ──────────────────────────


class User(Base):
    """用户表 — 通过飞书 OAuth 注册。"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    feishu_open_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, comment="飞书 open_id"
    )
    feishu_union_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="飞书 union_id"
    )
    nickname: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", comment="飞书昵称"
    )
    avatar_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="飞书头像 URL"
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否管理员"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="注册时间",
    )

    # relationships
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.nickname} ({self.feishu_open_id})>"


class ApiKey(Base):
    """API Key 表 — 存储哈希后的密钥，供设备端 SDK 鉴权。"""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户",
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="Default", comment="Key 别名"
    )
    key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="SHA-256 哈希"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(12), nullable=False, comment="明文前缀 (esk_xxxx) 用于展示"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否有效"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="上次使用时间"
    )

    # relationship
    user: Mapped["User"] = relationship(back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey {self.key_prefix}... user={self.user_id}>"


class SystemConfig(Base):
    """系统配置表 — 键值对形式存储运行时可修改的配置。"""

    __tablename__ = "system_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    key: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, comment="配置键"
    )
    value: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="配置值"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<SystemConfig {self.key}>"

