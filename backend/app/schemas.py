"""
Pydantic v2 请求/响应 Schema — 用于 FastAPI 接口数据校验。
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ────────────────────────── Template ──────────────────────────


class MetricDefinition(BaseModel):
    """单个测试指标定义。"""

    name: str = Field(..., examples=["cpu_temperature"], description="指标名称")
    unit: str = Field(..., examples=["°C"], description="度量单位")
    threshold_max: float | None = Field(
        None, examples=[60.0], description="上限阈值（超过即异常）"
    )
    threshold_min: float | None = Field(
        None, examples=[0.0], description="下限阈值（低于即异常）"
    )


class SchemaDefinition(BaseModel):
    """模板中的 JSON Schema 定义。"""

    metrics: list[MetricDefinition] = Field(
        ..., min_length=1, description="至少包含一个测试指标"
    )


class TemplateCreate(BaseModel):
    """创建模板请求体。"""

    name: str = Field(
        ..., max_length=255, examples=["边缘设备标准测试"], description="模板名称"
    )
    version: str = Field(
        default="1.0", max_length=32, examples=["1.0"], description="版本号"
    )
    description: str | None = Field(
        default=None, examples=["涵盖 CPU、内存、网络等基础指标"], description="模板描述"
    )
    schema_definition: SchemaDefinition = Field(
        ..., description="测试指标及阈值定义"
    )


class TemplateResponse(BaseModel):
    """模板响应体。"""

    id: uuid.UUID
    name: str
    version: str
    description: str | None
    schema_definition: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListItem(BaseModel):
    """模板列表项（精简）。"""

    id: uuid.UUID
    name: str
    version: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ────────────────────────── Report ──────────────────────────


class ReportResponse(BaseModel):
    """测试报告响应体。"""

    id: uuid.UUID
    template_id: uuid.UUID
    device_id: str
    report_data: dict[str, Any]
    ai_analysis: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ────────────────────────── 通用 ──────────────────────────


class MessageResponse(BaseModel):
    """通用消息响应。"""

    message: str
    detail: str | None = None
