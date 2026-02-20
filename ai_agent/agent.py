"""
AI Agent 分析引擎 — 数据驱动的 IoT 测试报告智能诊断系统。

核心特性:
  - 支持用户自定义 System Prompt (custom_system_prompt)
  - 支持用户自定义分析工作流 (workflow_steps)
  - 支持用户自定义重点关注领域 (focus_areas)
  - 指标业务语义 (description) 注入分析上下文
  - LLM 不可用时自动降级为规则引擎
"""

import asyncio
import logging
import uuid

from openai import AsyncOpenAI
from sqlalchemy import select, update

from backend.app.config import get_settings
from backend.app.database import async_session
from backend.app.models import TestReport, TestTemplate

logger = logging.getLogger("edgestelle.ai_agent")
settings = get_settings()


# ═══════════════════════════════════════════════════════════════
#  默认 System Prompt (当用户未自定义时使用)
# ═══════════════════════════════════════════════════════════════

DEFAULT_SYSTEM_PROMPT = """\
你是一位资深的嵌入式硬件测试专家，服务于 EdgeStelle IoT 设备自动化测试平台。

你的职责是：
1. **数据审查**：仔细审查设备上报的每一项测试指标值。
2. **阈值比对**：将实际数据与模板中定义的阈值进行逐项比对，判断是否超标。
3. **异常分析**：对超出阈值的指标进行深度分析，推断可能的硬件故障、固件缺陷或环境因素。
4. **综合评分**：给出 0~100 分的综合健康评分。
5. **修复建议**：提供具体、可操作的排查和修复建议。
"""

# 固定输出格式要求 (始终追加到 System Prompt 后)
OUTPUT_FORMAT_INSTRUCTION = """
## 输出格式要求

请严格按照以下 Markdown 格式输出诊断报告：

---

# 🔬 设备测试诊断报告

## 📊 综合评分: [XX]/100

## 📋 指标汇总

| 指标 | 实际值 | 阈值上限 | 阈值下限 | 状态 |
|------|--------|----------|----------|------|
| ... | ... | ... | ... | ✅ 正常 / ⚠️ 警告 / ❌ 异常 |

## ⚠️ 异常预警

[逐条列出发现的异常，说明严重程度]

## 🔍 原因分析

[对每个异常指标给出可能原因分析]

## 🛠️ 修复建议

[给出具体的排查步骤和修复方案]

## 📝 总结

[一段总结性文字]

---

## 注意事项
- 即使所有指标均正常，也要给出综合评价和预防性建议。
- 多个异常之间如有关联，应从系统层面综合分析。
- 评分参考: 90-100 优秀, 70-89 良好, 50-69 警告, 0-49 严重。
"""


# ═══════════════════════════════════════════════════════════════
#  动态 System Prompt 组装
# ═══════════════════════════════════════════════════════════════


def build_system_prompt(analysis_config: dict | None) -> str:
    """
    根据模板中的 analysis_config 动态组装 System Prompt。

    优先级: custom_system_prompt > DEFAULT_SYSTEM_PROMPT
    始终追加: 输出格式指令 + workflow_steps + focus_areas
    """
    config = analysis_config or {}

    # 1. 基础角色 Prompt
    base_prompt = config.get("custom_system_prompt") or DEFAULT_SYSTEM_PROMPT

    parts = [base_prompt.strip()]

    # 2. 追加工作流步骤
    workflow_steps = config.get("workflow_steps")
    if workflow_steps:
        parts.append("\n## 诊断工作流\n\n请严格按照以下步骤顺序执行诊断：\n")
        for step in workflow_steps:
            parts.append(f"- {step}")

    # 3. 追加重点关注领域
    focus_areas = config.get("focus_areas")
    if focus_areas:
        parts.append("\n## 重点关注领域\n\n请优先分析以下领域的相关指标：\n")
        for area in focus_areas:
            parts.append(f"- **{area}**")

    # 4. 始终追加输出格式指令
    parts.append(OUTPUT_FORMAT_INSTRUCTION)

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
#  上下文构建 (含指标语义)
# ═══════════════════════════════════════════════════════════════


def build_analysis_context(template: dict, report: dict) -> str:
    """
    将模板阈值、指标语义和设备实测数据整理为结构化上下文文本。

    新增: 每个指标的 description (业务语义) 会作为独立列注入上下文。
    """
    lines = []
    lines.append("## 测试模板信息")
    lines.append(f"- 模板名称: {template.get('name', '未知')}")
    lines.append(f"- 版本: {template.get('version', '未知')}")
    lines.append("")

    # 模板中的指标定义 (含 description)
    schema_def = template.get("schema_definition", {})
    template_metrics = {m["name"]: m for m in schema_def.get("metrics", [])}

    lines.append("## 设备上报数据")
    lines.append(f"- 设备 ID: {report.get('device_id', '未知')}")
    lines.append(f"- 上报时间: {report.get('timestamp', '未知')}")
    lines.append("")

    # ── 指标详情表 (新增 "业务含义" 列) ──
    lines.append("## 指标详情")
    lines.append("")
    lines.append("| 指标 | 业务含义 | 单位 | 实际值 | 阈值上限 | 阈值下限 | 是否超标 |")
    lines.append("|------|----------|------|--------|----------|----------|----------|")

    results = report.get("results", [])
    for r in results:
        name = r.get("name", "?")
        unit = r.get("unit", "")
        value = r.get("value", "N/A")

        # 从模板定义中获取 description
        tmpl_metric = template_metrics.get(name, {})
        desc = tmpl_metric.get("description", "—")

        t_max = r.get("threshold_max", tmpl_metric.get("threshold_max", "—"))
        t_min = r.get("threshold_min", tmpl_metric.get("threshold_min", "—"))

        exceeded = "否"
        if t_max not in (None, "—") and isinstance(value, (int, float)):
            if value > float(t_max):
                exceeded = "⚠️ 超上限"
        if t_min not in (None, "—") and isinstance(value, (int, float)):
            if value < float(t_min):
                exceeded = "⚠️ 低于下限"

        lines.append(f"| {name} | {desc} | {unit} | {value} | {t_max} | {t_min} | {exceeded} |")

    # 异常摘要
    anomaly_summary = report.get("anomaly_summary", [])
    if anomaly_summary:
        lines.append("")
        lines.append("## 设备端异常摘要")
        for a in anomaly_summary:
            lines.append(f"- {a}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  LLM 调用 (动态 Prompt)
# ═══════════════════════════════════════════════════════════════


async def call_llm(system_prompt: str, context: str) -> str:
    """
    调用大语言模型 API 进行分析。

    Parameters
    ----------
    system_prompt : str
        动态组装的 System Prompt (基于模板 analysis_config)。
    context : str
        结构化的测试数据上下文。

    Returns
    -------
    str
        LLM 返回的 Markdown 诊断报告。
    """
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    user_message = f"请分析以下 IoT 设备的测试数据，并按格式输出诊断报告：\n\n{context}"

    logger.info("🤖 正在调用 LLM (%s) 进行分析…", settings.OPENAI_MODEL)
    logger.debug("📝 System Prompt 长度: %d 字符", len(system_prompt))

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    analysis = response.choices[0].message.content
    logger.info("✅ LLM 分析完成 — 输出 %d 字符", len(analysis))
    return analysis


# ═══════════════════════════════════════════════════════════════
#  核心工作流
# ═══════════════════════════════════════════════════════════════


async def analyze_report(report_id: uuid.UUID) -> str | None:
    """
    AI Agent 主流程：读取报告 → 构建上下文 → 动态组装 Prompt → LLM 分析 → 结果存库。

    Parameters
    ----------
    report_id : uuid.UUID
        待分析的报告 ID。

    Returns
    -------
    str | None
        分析结果 Markdown 文本，失败返回 None。
    """
    logger.info("🔄 开始分析报告 — id=%s", report_id)

    async with async_session() as session:
        # 读取报告
        result = await session.execute(
            select(TestReport).where(TestReport.id == report_id)
        )
        report_obj = result.scalar_one_or_none()
        if report_obj is None:
            logger.error("❌ 报告不存在: %s", report_id)
            return None

        # 读取关联模板
        result = await session.execute(
            select(TestTemplate).where(TestTemplate.id == report_obj.template_id)
        )
        template_obj = result.scalar_one_or_none()

        # 构建模板数据
        template_data = {
            "name": template_obj.name if template_obj else "未知模板",
            "version": template_obj.version if template_obj else "?",
            "schema_definition": template_obj.schema_definition if template_obj else {},
        }
        report_data = report_obj.report_data

        # ── 提取 analysis_config ──
        schema_def = template_data.get("schema_definition", {})
        analysis_config = schema_def.get("analysis_config")

        # ── 动态组装 System Prompt ──
        system_prompt = build_system_prompt(analysis_config)

        # ── 构建分析上下文 (含指标语义) ──
        context = build_analysis_context(template_data, report_data)

        logger.info("📋 analysis_config: %s",
                     "用户自定义" if analysis_config else "使用默认")

        # 调用 LLM
        try:
            analysis = await call_llm(system_prompt, context)
        except Exception as e:
            logger.error("❌ LLM 调用失败: %s", e, exc_info=True)
            analysis = _fallback_analysis(template_data, report_data)

        # 结果存库
        await session.execute(
            update(TestReport)
            .where(TestReport.id == report_id)
            .values(ai_analysis=analysis, status="analyzed")
        )
        await session.commit()
        logger.info("💾 分析结果已保存 — report_id=%s", report_id)

        # ── 飞书集成 (可选) ──
        try:
            await _push_to_feishu(
                report_id=report_id,
                device_id=report_data.get("device_id", "unknown"),
                analysis=analysis,
                anomaly_summary=report_data.get("anomaly_summary", []),
            )
        except Exception as e:
            logger.warning("⚠️ 飞书推送失败 (不影响主流程): %s", e)

        return analysis


def _fallback_analysis(template: dict, report: dict) -> str:
    """
    LLM 不可用时的简单规则分析（降级方案）。
    """
    lines = ["# 🔬 设备测试诊断报告 (规则引擎)", ""]
    lines.append("> ⚠️ LLM 服务不可用，以下为基于阈值的自动分析。\n")

    schema_def = template.get("schema_definition", {})
    template_metrics = {m["name"]: m for m in schema_def.get("metrics", [])}

    results = report.get("results", [])
    anomalies = []
    total = len(results)
    normal_count = 0

    for r in results:
        name = r.get("name", "?")
        value = r.get("value")
        tmpl = template_metrics.get(name, {})
        t_max = r.get("threshold_max", tmpl.get("threshold_max"))
        t_min = r.get("threshold_min", tmpl.get("threshold_min"))
        desc = tmpl.get("description", "")

        desc_hint = f" ({desc})" if desc else ""

        if t_max is not None and isinstance(value, (int, float)) and value > float(t_max):
            anomalies.append(f"- **{name}**{desc_hint} = {value}{r.get('unit', '')} — 超出上限 {t_max}")
        elif t_min is not None and isinstance(value, (int, float)) and value < float(t_min):
            anomalies.append(f"- **{name}**{desc_hint} = {value}{r.get('unit', '')} — 低于下限 {t_min}")
        else:
            normal_count += 1

    score = int((normal_count / max(total, 1)) * 100)
    lines.append(f"## 📊 综合评分: {score}/100\n")

    if anomalies:
        lines.append("## ⚠️ 异常指标\n")
        lines.extend(anomalies)
    else:
        lines.append("## ✅ 所有指标均在正常范围\n")

    lines.append("\n## 📝 总结\n")
    lines.append(f"共检测 {total} 项指标，{normal_count} 项正常，{len(anomalies)} 项异常。")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  飞书推送
# ═══════════════════════════════════════════════════════════════

import re


async def _push_to_feishu(
    report_id: uuid.UUID,
    device_id: str,
    analysis: str,
    anomaly_summary: list,
) -> None:
    """
    将分析结果推送到飞书 (创建文档 + 发送卡片)。

    仅在飞书配置完整时执行，否则静默跳过。
    """
    if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
        logger.debug("飞书未配置，跳过推送")
        return

    from backend.app.integrations.feishu import (
        create_feishu_doc,
        build_alert_card,
        send_message_card,
    )

    # 提取综合评分
    score_match = re.search(r"综合评分[:\s]*(\d+)/100", analysis)
    score = score_match.group(0) if score_match else "N/A"

    # 1. 创建飞书文档
    title = f"EdgeStelle 诊断报告 — {device_id}"
    doc_url = await create_feishu_doc(title, analysis)

    # 2. 构建并发送消息卡片
    webui_url = f"{settings.OPENAI_BASE_URL.replace('/v1', '')}"  # fallback
    try:
        from backend.app.config import get_settings as _get_settings
        _s = _get_settings()
        webui_url = f"{_s.FRONTEND_URL}/reports/{report_id}"
    except Exception:
        webui_url = f"http://localhost:5173/reports/{report_id}"

    webhook_url = settings.FEISHU_BOT_WEBHOOK_URL

    # 也尝试从数据库 SystemConfig 读取
    if not webhook_url:
        try:
            from backend.app.database import async_session as _async_session
            from backend.app.models import SystemConfig
            from sqlalchemy import select as _select

            async with _async_session() as session:
                result = await session.execute(
                    _select(SystemConfig).where(SystemConfig.key == "feishu_bot_webhook_url")
                )
                config = result.scalar_one_or_none()
                if config:
                    webhook_url = config.value
        except Exception:
            pass

    if not webhook_url:
        logger.info("📄 飞书文档已创建: %s (未配置 Webhook，跳过卡片推送)", doc_url)
        return

    card = build_alert_card(
        device_id=device_id,
        score=score,
        anomaly_summary=anomaly_summary,
        doc_url=doc_url,
        webui_url=webui_url,
    )
    await send_message_card(webhook_url, card)
    logger.info("✅ 飞书推送完成 — device=%s doc=%s", device_id, doc_url)


# ═══════════════════════════════════════════════════════════════
#  MQTT 触发回调
# ═══════════════════════════════════════════════════════════════


async def on_new_report(report_id: uuid.UUID, payload: dict):
    """
    供 mqtt_listener 注册的回调 — 新报告入库后触发分析。
    """
    logger.info("🔔 触发 AI 分析 — report_id=%s device=%s",
                report_id, payload.get("device_id", "?"))
    try:
        analysis = await analyze_report(report_id)
        if analysis:
            logger.info("📄 分析完成，前 100 字符:\n%s", analysis[:100])
    except Exception as e:
        logger.error("❌ AI 分析流程异常: %s", e, exc_info=True)

