"""
FastAPI 应用入口 — 路由 + Lifespan (自动建表 + MQTT 监听 + AI Agent)。
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import engine, get_db
from .models import Base, TestReport, TestTemplate
from .schemas import (
    ReportResponse,
    TemplateCreate,
    TemplateListItem,
    TemplateResponse,
)


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
    version="0.1.0",
    lifespan=lifespan,
)


# ───────────────────────── Template Routes ─────────────────────────


@app.post(
    "/api/v1/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建测试模板",
    tags=["Templates"],
)
async def create_template(
    payload: TemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    创建一个测试模板。模板包含测试指标名称、单位、阈值、业务语义及 AI 分析配置。

    **示例请求体：**
    ```json
    {
      "name": "智能摄像头深度测试",
      "version": "2.0",
      "schema_definition": {
        "metrics": [
          {"name": "npu_temp", "unit": "°C", "threshold_max": 80,
           "description": "NPU 核心温度，决定了 AI 视觉算法的算力释放"},
          {"name": "packet_loss_rate", "unit": "%", "threshold_max": 2,
           "description": "网络丢包率，影响视频流的连续性"}
        ],
        "analysis_config": {
          "custom_system_prompt": "你是安防摄像头领域的资深排障专家...",
          "workflow_steps": [
            "1. 首先排查 npu_temp 是否与画面卡顿有关联。",
            "2. 如果温度过高，优先建议检查散热硅脂或外壳结构。"
          ],
          "focus_areas": ["散热系统", "网络稳定性"]
        }
      }
    }
    ```
    """
    template = TestTemplate(
        name=payload.name,
        version=payload.version,
        description=payload.description,
        schema_definition=payload.schema_definition.model_dump(exclude_none=True),
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@app.get(
    "/api/v1/templates/{template_id}",
    response_model=TemplateResponse,
    summary="获取测试模板详情",
    tags=["Templates"],
)
async def get_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """根据模板 ID 获取完整模板定义，供设备端 SDK 下载使用。"""
    result = await db.execute(
        select(TestTemplate).where(TestTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模板 {template_id} 不存在",
        )
    return template


@app.get(
    "/api/v1/templates",
    response_model=list[TemplateListItem],
    summary="获取模板列表",
    tags=["Templates"],
)
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """分页获取模板列表（精简字段）。"""
    result = await db.execute(
        select(TestTemplate)
        .order_by(TestTemplate.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


# ───────────────────────── Report Routes ─────────────────────────


@app.get(
    "/api/v1/reports",
    response_model=list[ReportResponse],
    summary="获取报告列表",
    tags=["Reports"],
)
async def list_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: str | None = Query(None, description="按设备 ID 过滤"),
    status_filter: str | None = Query(None, alias="status", description="按状态过滤 (pending/analyzed)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """分页获取测试报告列表，支持按设备和状态过滤。"""
    query = select(TestReport).order_by(TestReport.created_at.desc())
    if device_id:
        query = query.where(TestReport.device_id == device_id)
    if status_filter:
        query = query.where(TestReport.status == status_filter)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@app.get(
    "/api/v1/reports/{report_id}",
    response_model=ReportResponse,
    summary="获取报告详情（含 AI 分析）",
    tags=["Reports"],
)
async def get_report(
    report_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取单份报告详情及 AI 分析结果。"""
    result = await db.execute(
        select(TestReport).where(TestReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"报告 {report_id} 不存在",
        )
    return report


@app.post(
    "/api/v1/reports/{report_id}/analyze",
    response_model=ReportResponse,
    summary="手动触发 AI 分析",
    tags=["Reports"],
)
async def trigger_analysis(
    report_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """手动触发对某份报告的 AI 分析（重新分析）。"""
    result = await db.execute(
        select(TestReport).where(TestReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"报告 {report_id} 不存在",
        )

    try:
        from ai_agent.agent import analyze_report
        await analyze_report(report_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 分析失败: {str(e)}",
        )

    await db.refresh(report)
    return report


# ───────────────────────── Health ─────────────────────────


@app.get("/health", tags=["System"])
async def health_check():
    """健康检查端点。"""
    return {"status": "ok", "service": "edgestelle-backend"}
