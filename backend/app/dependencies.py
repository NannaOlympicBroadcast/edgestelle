"""
FastAPI 依赖注入 — 双重鉴权 (Bearer JWT / X-API-Key)。
"""

import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import ApiKey, User
from .security import decode_access_token, hash_api_key

# HTTPBearer 设 auto_error=False，让我们可以退而检查 X-API-Key
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> User:
    """
    双重鉴权依赖：

    1. 优先检查 ``Authorization: Bearer <JWT>``
    2. 若无 Bearer 则检查 ``X-API-Key`` 头
    3. 两者都不存在则 401
    """
    # ── 路径 A: Bearer JWT ──
    if credentials is not None:
        try:
            payload = decode_access_token(credentials.credentials)
            user_id = uuid.UUID(payload.get("sub", ""))
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT 令牌无效或已过期",
                headers={"WWW-Authenticate": "Bearer"},
            )

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )
        return user

    # ── 路径 B: X-API-Key ──
    if x_api_key is not None:
        key_hash = hash_api_key(x_api_key)
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active.is_(True),
            )
        )
        api_key_obj = result.scalar_one_or_none()
        if api_key_obj is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key 无效或已撤销",
            )

        # 更新 last_used_at
        from datetime import datetime, timezone
        api_key_obj.last_used_at = datetime.now(timezone.utc)

        # 返回关联用户
        result = await db.execute(select(User).where(User.id == api_key_obj.user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key 关联用户不存在",
            )
        return user

    # ── 两者都不存在 ──
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="缺少鉴权凭证 (Bearer Token 或 X-API-Key)",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求管理员权限。"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
