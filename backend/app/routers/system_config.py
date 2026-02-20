"""
系统配置管理路由 — 管理员专用。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_admin_user
from ..models import SystemConfig, User
from ..schemas import SystemConfigResponse, SystemConfigUpdate

router = APIRouter(prefix="/api/v1/system", tags=["System Config"])


@router.get(
    "/config",
    response_model=list[SystemConfigResponse],
    summary="获取所有系统配置",
)
async def list_system_configs(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """获取所有系统配置项 (管理员权限)。"""
    result = await db.execute(
        select(SystemConfig).order_by(SystemConfig.key)
    )
    return result.scalars().all()


@router.put(
    "/config",
    response_model=list[SystemConfigResponse],
    summary="批量更新系统配置",
)
async def update_system_configs(
    payload: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """批量更新或创建系统配置项 (管理员权限)。"""
    updated = []
    for item in payload.configs:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == item.key)
        )
        config = result.scalar_one_or_none()

        if config is None:
            config = SystemConfig(key=item.key, value=item.value)
            db.add(config)
        else:
            config.value = item.value

        await db.flush()
        await db.refresh(config)
        updated.append(config)

    return updated
