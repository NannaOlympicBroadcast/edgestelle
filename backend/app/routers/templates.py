"""
测试模板路由 — 从 main.py 提取并添加鉴权。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import TestTemplate, User
from ..schemas import TemplateCreate, TemplateListItem, TemplateResponse

router = APIRouter(prefix="/api/v1/templates", tags=["Templates"])


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建测试模板",
)
async def create_template(
    payload: TemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
):
    """
    创建一个测试模板。模板包含测试指标名称、单位、阈值、业务语义及 AI 分析配置。
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


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="获取测试模板详情",
)
async def get_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """根据模板 ID 获取完整模板定义，供设备端 SDK 下载使用。(无需鉴权)"""
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


@router.get(
    "",
    response_model=list[TemplateListItem],
    summary="获取模板列表",
)
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """分页获取模板列表（精简字段）。(无需鉴权)"""
    result = await db.execute(
        select(TestTemplate)
        .order_by(TestTemplate.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
