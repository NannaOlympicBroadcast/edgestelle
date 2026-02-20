"""
飞书开放平台 API 封装 — Tenant Access Token · 云文档 · 消息卡片推送。
"""

import logging
import time

import httpx

from ..config import get_settings

logger = logging.getLogger("edgestelle.feishu")
settings = get_settings()


# ═══════════════════════════════════════════════════════════════
#  Tenant Access Token (缓存)
# ═══════════════════════════════════════════════════════════════

_token_cache: dict = {"token": "", "expire_at": 0}

FEISHU_TENANT_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


async def get_tenant_access_token() -> str:
    """
    获取飞书 tenant_access_token 并缓存 (有效期 2 小时，提前 5 分钟刷新)。
    """
    now = time.time()
    if _token_cache["token"] and _token_cache["expire_at"] > now:
        return _token_cache["token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            FEISHU_TENANT_TOKEN_URL,
            json={
                "app_id": settings.FEISHU_APP_ID,
                "app_secret": settings.FEISHU_APP_SECRET,
            },
            timeout=10,
        )
        data = resp.json()

    if data.get("code") != 0:
        logger.error("获取 tenant_access_token 失败: %s", data)
        raise RuntimeError(f"飞书 tenant_access_token 获取失败: {data.get('msg')}")

    token = data["tenant_access_token"]
    expire = data.get("expire", 7200)
    _token_cache["token"] = token
    _token_cache["expire_at"] = now + expire - 300  # 提前 5 分钟刷新

    logger.info("✅ tenant_access_token 已获取 (有效 %ds)", expire)
    return token


# ═══════════════════════════════════════════════════════════════
#  创建飞书文档
# ═══════════════════════════════════════════════════════════════

FEISHU_CREATE_DOC_URL = "https://open.feishu.cn/open-apis/docx/v1/documents"
FEISHU_CREATE_DOC_BLOCK_URL = "https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children"


async def create_feishu_doc(title: str, markdown_content: str) -> str:
    """
    创建飞书新版文档，写入 Markdown 内容，返回文档 URL。

    Parameters
    ----------
    title : str
        文档标题。
    markdown_content : str
        Markdown 格式的分析报告内容。

    Returns
    -------
    str
        飞书文档的 URL。
    """
    token = await get_tenant_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    async with httpx.AsyncClient() as client:
        # 1. 创建空文档
        resp = await client.post(
            FEISHU_CREATE_DOC_URL,
            json={"title": title, "folder_token": ""},
            headers=headers,
            timeout=15,
        )
        doc_data = resp.json()

    if doc_data.get("code") != 0:
        logger.error("创建飞书文档失败: %s", doc_data)
        raise RuntimeError(f"创建飞书文档失败: {doc_data.get('msg')}")

    document_id = doc_data["data"]["document"]["document_id"]
    doc_url = f"https://feishu.cn/docx/{document_id}"

    # 2. 向文档中追加文本块 (以纯文本方式写入 Markdown 内容)
    # 文档创建后 document_id 同时也是根 block_id
    block_url = FEISHU_CREATE_DOC_BLOCK_URL.format(
        document_id=document_id, block_id=document_id
    )

    # 将 Markdown 按段落拆分为多个文本块
    paragraphs = markdown_content.split("\n")
    children = []
    for para in paragraphs:
        if not para.strip():
            continue
        children.append({
            "block_type": 2,  # text block
            "text": {
                "elements": [
                    {
                        "text_run": {
                            "content": para,
                        }
                    }
                ],
                "style": {},
            },
        })

    if children:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                block_url,
                json={"children": children, "index": 0},
                headers=headers,
                timeout=30,
            )
            block_data = resp.json()
            if block_data.get("code") != 0:
                logger.warning("写入文档内容失败 (文档已创建): %s", block_data)

    logger.info("📄 飞书文档已创建: %s", doc_url)
    return doc_url


# ═══════════════════════════════════════════════════════════════
#  发送消息卡片
# ═══════════════════════════════════════════════════════════════


def build_alert_card(
    device_id: str,
    score: str,
    anomaly_summary: list[str],
    doc_url: str,
    webui_url: str,
) -> dict:
    """
    构建飞书消息卡片 JSON (Interactive Message Card)。

    Parameters
    ----------
    device_id : str
        设备 ID。
    score : str
        综合评分文本。
    anomaly_summary : list[str]
        异常指标摘要。
    doc_url : str
        飞书云文档 URL。
    webui_url : str
        WebUI 报告详情页 URL。
    """
    anomaly_text = "\n".join(f"• {a}" for a in anomaly_summary) if anomaly_summary else "✅ 所有指标正常"

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔔 EdgeStelle 设备测试报告 — {device_id}",
                },
                "template": "red" if anomaly_summary else "green",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📊 综合评分:** {score}\n\n**⚠️ 异常摘要:**\n{anomaly_text}",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "📄 查看飞书文档",
                            },
                            "url": doc_url,
                            "type": "primary",
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "🖥️ 查看 WebUI",
                            },
                            "url": webui_url,
                            "type": "default",
                        },
                    ],
                },
            ],
        },
    }


async def send_message_card(webhook_url: str, card: dict) -> bool:
    """
    通过飞书 Bot Webhook 发送消息卡片。

    Parameters
    ----------
    webhook_url : str
        飞书机器人 Webhook URL。
    card : dict
        消息卡片 JSON (由 build_alert_card 构建)。

    Returns
    -------
    bool
        是否发送成功。
    """
    if not webhook_url:
        logger.warning("飞书 Webhook URL 未配置，跳过推送")
        return False

    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=card, timeout=10)
        data = resp.json()

    if data.get("code") != 0 and data.get("StatusCode") != 0:
        logger.error("飞书消息卡片发送失败: %s", data)
        return False

    logger.info("✅ 飞书消息卡片已发送")
    return True
