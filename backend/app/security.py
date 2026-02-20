"""
JWT 签发/验证 + API Key 工具函数。
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from .config import get_settings

settings = get_settings()


# ────────────────────────── JWT ──────────────────────────


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """签发 JWT — 默认有效期取 ``JWT_EXPIRE_MINUTES``。"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    验证并解码 JWT。

    Raises
    ------
    JWTError
        令牌无效或已过期。
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ────────────────────────── API Key ──────────────────────────


API_KEY_PREFIX = "esk_"


def generate_api_key() -> str:
    """生成 ``esk_`` 前缀的随机 API Key (48 字符随机 hex)。"""
    return f"{API_KEY_PREFIX}{secrets.token_hex(24)}"


def hash_api_key(raw_key: str) -> str:
    """SHA-256 哈希 API Key 用于持久化存储。"""
    return hashlib.sha256(raw_key.encode()).hexdigest()
