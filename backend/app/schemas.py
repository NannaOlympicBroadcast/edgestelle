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
    description: str | None = Field(
        None,
        examples=["NPU 核心温度，决定了 AI 视觉算法的算力释放"],
        description="指标的业务语义描述，告知 AI Agent 该指标的含义和影响",
    )


class AnalysisConfig(BaseModel):
    """用户自定义的 AI 分析配置 — 驱动 Agent 行为。"""

    custom_system_prompt: str | None = Field(
        None,
        description="自定义系统提示词，覆盖默认的专家角色设定",
        examples=["你是安防摄像头领域的资深排障专家，语气要严厉、专业，直接指出致命缺陷。"],
    )
    workflow_steps: list[str] | None = Field(
        None,
        description="自定义分析工作流步骤，Agent 将严格按此顺序执行诊断",
        examples=[["1. 首先排查 npu_temp 是否与画面卡顿有关联。", "2. 如果温度过高，优先建议检查散热硅脂或外壳结构。"]],
    )
    focus_areas: list[str] | None = Field(
        None,
        description="重点关注的异常领域，Agent 会优先分析这些方面",
        examples=[["散热系统", "网络稳定性", "固件兼容性"]],
    )


class SchemaDefinition(BaseModel):
    """模板中的 JSON Schema 定义。"""

    metrics: list[MetricDefinition] = Field(
        ..., min_length=1, description="至少包含一个测试指标"
    )
    analysis_config: AnalysisConfig | None = Field(
        None, description="AI 分析配置 — 自定义提示词、工作流和重点关注领域"
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


# ────────────────────────── User / Auth ──────────────────────────


class UserResponse(BaseModel):
    """用户信息响应。"""

    id: uuid.UUID
    feishu_open_id: str
    nickname: str
    avatar_url: str | None
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT 令牌响应。"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ────────────────────────── API Key ──────────────────────────


class ApiKeyCreate(BaseModel):
    """创建 API Key 请求体。"""

    name: str = Field(default="Default", max_length=128, description="Key 别名")


class ApiKeyResponse(BaseModel):
    """API Key 列表项 (不含密钥明文)。"""

    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    """创建 API Key 后一次性返回的响应 (含明文)。"""

    id: uuid.UUID
    name: str
    key_prefix: str
    raw_key: str = Field(..., description="明文密钥 — 仅此一次展示，请妥善保存")
    created_at: datetime


# ────────────────────────── System Config ──────────────────────────


class SystemConfigItem(BaseModel):
    """单项配置。"""

    key: str
    value: str


class SystemConfigResponse(BaseModel):
    """系统配置响应。"""

    key: str
    value: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemConfigUpdate(BaseModel):
    """批量更新系统配置请求体。"""

    configs: list[SystemConfigItem]

