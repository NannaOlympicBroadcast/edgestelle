"""
SQLAlchemy 2.0 ORM 模型 — test_templates / test_reports。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
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
