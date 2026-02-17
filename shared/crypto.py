"""
EdgeStelle — AES-256-GCM 加密/解密工具
用于在 MQTT Payload 上额外加密敏感数据（如脚本内容）
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_aes_key(hex_key: str) -> bytes:
    """将 64 位 hex 字符串转为 32 字节密钥"""
    key_bytes = bytes.fromhex(hex_key)
    if len(key_bytes) != 32:
        raise ValueError(f"AES 密钥长度必须为 32 字节，当前为 {len(key_bytes)} 字节")
    return key_bytes


def encrypt_payload(plaintext: str, hex_key: str) -> str:
    """
    AES-256-GCM 加密
    返回 base64 编码的 nonce + 密文（便于 JSON 传输）
    """
    key = _get_aes_key(hex_key)
    nonce = os.urandom(12)  # GCM 推荐 96-bit nonce
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # nonce(12B) + ciphertext 拼接后 base64 编码
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_payload(token: str, hex_key: str) -> str:
    """
    AES-256-GCM 解密
    输入 base64 编码的 nonce + 密文
    """
    key = _get_aes_key(hex_key)
    raw = base64.b64decode(token)
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
