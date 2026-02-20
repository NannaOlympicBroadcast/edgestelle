"""
测试报告路由 — 从 main.py 提取并添加鉴权。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import TestReport, User
from ..schemas import ReportResponse

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


@router.get(
    "",
    response_model=list[ReportResponse],
    summary="获取报告列表",
)
async def list_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
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


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="获取报告详情（含 AI 分析）",
)
async def get_report(
    report_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
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


@router.post(
    "/{report_id}/analyze",
    response_model=ReportResponse,
    summary="手动触发 AI 分析",
)
async def trigger_analysis(
    report_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
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
