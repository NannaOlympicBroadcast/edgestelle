"""
飞书 OAuth 登录路由。

流程:
  1. GET /login  → 返回飞书授权跳转 URL
  2. GET /callback?code=... → 用 code 换取 user_access_token → 获取用户信息 → 签发 JWT
  3. GET /me → 返回当前登录用户信息
"""

import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import TokenResponse, UserResponse
from ..security import create_access_token

logger = logging.getLogger("edgestelle.auth")
settings = get_settings()

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


# ────────────────────────── 飞书 OAuth ──────────────────────────


FEISHU_AUTHORIZE_URL = "https://open.feishu.cn/open-apis/authen/v1/authorize"
FEISHU_ACCESS_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token"
FEISHU_USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"
FEISHU_APP_ACCESS_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"


async def _get_app_access_token() -> str:
    """获取飞书 app_access_token (用于换取 user_access_token)。"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            FEISHU_APP_ACCESS_TOKEN_URL,
            json={
                "app_id": settings.FEISHU_APP_ID,
                "app_secret": settings.FEISHU_APP_SECRET,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.error("获取 app_access_token 失败: %s", data)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"飞书 app_access_token 获取失败: {data.get('msg')}",
            )
        return data["app_access_token"]


@router.get("/feishu/login", summary="飞书 OAuth 授权跳转")
async def feishu_login():
    """返回飞书 OAuth 授权页面的跳转 URL。"""
    if not settings.FEISHU_APP_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="飞书 App ID 未配置",
        )

    params = urlencode({
        "app_id": settings.FEISHU_APP_ID,
        "redirect_uri": settings.FEISHU_REDIRECT_URI,
        "response_type": "code",
        "state": "edgestelle",
    })
    authorize_url = f"{FEISHU_AUTHORIZE_URL}?{params}"
    return {"authorize_url": authorize_url}


@router.get("/feishu/callback", summary="飞书 OAuth 回调")
async def feishu_callback(
    code: str = Query(..., description="飞书授权码"),
    db: AsyncSession = Depends(get_db),
):
    """
    接收飞书回调 code，换取 user_access_token，获取用户信息。
    用户不存在则自动注册。签发系统 JWT 后重定向至前端。
    """
    # 1. 用 code 换 user_access_token
    app_access_token = await _get_app_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            FEISHU_ACCESS_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "code": code,
            },
            headers={"Authorization": f"Bearer {app_access_token}"},
            timeout=10,
        )
        token_data = resp.json()

    if token_data.get("code") != 0:
        logger.error("飞书 code 换 token 失败: %s", token_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"飞书授权失败: {token_data.get('msg', '未知错误')}",
        )

    user_access_token = token_data["data"]["access_token"]

    # 2. 获取用户信息
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            FEISHU_USER_INFO_URL,
            headers={"Authorization": f"Bearer {user_access_token}"},
            timeout=10,
        )
        user_info = resp.json()

    if user_info.get("code") != 0:
        logger.error("获取飞书用户信息失败: %s", user_info)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="获取飞书用户信息失败",
        )

    info = user_info["data"]
    open_id = info["open_id"]
    union_id = info.get("union_id")
    nickname = info.get("name", "")
    avatar_url = info.get("avatar_url") or info.get("avatar", {}).get("avatar_origin")

    # 3. 查找或创建用户
    result = await db.execute(select(User).where(User.feishu_open_id == open_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            feishu_open_id=open_id,
            feishu_union_id=union_id,
            nickname=nickname,
            avatar_url=avatar_url,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info("✅ 新用户注册: %s (%s)", nickname, open_id)
    else:
        # 更新用户信息
        user.nickname = nickname
        user.avatar_url = avatar_url
        if union_id:
            user.feishu_union_id = union_id
        logger.info("🔄 用户登录: %s (%s)", nickname, open_id)

    # 4. 签发 JWT
    jwt_token = create_access_token({"sub": str(user.id)})

    # 5. 重定向到前端
    redirect_url = f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}"
    return RedirectResponse(url=redirect_url)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户信息",
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """获取当前已登录用户的信息。"""
    return current_user
