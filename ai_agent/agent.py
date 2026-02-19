"""
AI Agent 分析引擎 — 基于 LLM 的 IoT 测试报告智能诊断系统。

核心工作流:
  1. 接收新报告触发 (由 mqtt_listener 的回调机制调用)
  2. 从数据库读取 test_report + test_template
  3. 对比阈值与实际数据，构建上下文
  4. 调用 LLM 进行深度分析
  5. 输出 Markdown 诊断报告，保存回数据库
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import select, update

from backend.app.config import get_settings
from backend.app.database import async_session
from backend.app.models import TestReport, TestTemplate

logger = logging.getLogger("edgestelle.ai_agent")
settings = get_settings()

# ═══════════════════════════════════════════════════════════════
#  System Prompt
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """你是一位资深的嵌入式硬件测试专家，服务于 EdgeStelle IoT 设备自动化测试平台。

你的职责是：
1. **数据审查**：仔细审查设备上报的每一项测试指标值。
2. **阈值比对**：将实际数据与模板中定义的阈值进行逐项比对，判断是否超标。
3. **异常分析**：对超出阈值的指标进行深度分析，推断可能的硬件故障、固件缺陷或环境因素。
4. **综合评分**：给出 0~100 分的综合健康评分。
5. **修复建议**：提供具体、可操作的排查和修复建议。

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
- 多个异常之间如有关联，应从系统层面综合分析（如 CPU 温度高+内存占用高 → 可能存在进程泄漏）。
- 评分参考: 90-100 优秀, 70-89 良好, 50-69 警告, 0-49 严重。
"""

# ═══════════════════════════════════════════════════════════════
#  上下文构建
# ═══════════════════════════════════════════════════════════════


def build_analysis_context(template: dict, report: dict) -> str:
    """
    将模板阈值和设备实测数据整理为结构化上下文文本。
    """
    lines = []
    lines.append(f"## 测试模板信息")
    lines.append(f"- 模板名称: {template.get('name', '未知')}")
    lines.append(f"- 版本: {template.get('version', '未知')}")
    lines.append("")

    # 模板中的指标定义
    schema_def = template.get("schema_definition", {})
    template_metrics = {m["name"]: m for m in schema_def.get("metrics", [])}

    lines.append(f"## 设备上报数据")
    lines.append(f"- 设备 ID: {report.get('device_id', '未知')}")
    lines.append(f"- 上报时间: {report.get('timestamp', '未知')}")
    lines.append("")

    lines.append("## 指标详情")
    lines.append("")
    lines.append("| 指标 | 单位 | 实际值 | 阈值上限 | 阈值下限 | 是否超标 |")
    lines.append("|------|------|--------|----------|----------|----------|")

    results = report.get("results", [])
    for r in results:
        name = r.get("name", "?")
        unit = r.get("unit", "")
        value = r.get("value", "N/A")
        t_max = r.get("threshold_max", template_metrics.get(name, {}).get("threshold_max", "—"))
        t_min = r.get("threshold_min", template_metrics.get(name, {}).get("threshold_min", "—"))

        exceeded = "否"
        if t_max not in (None, "—") and isinstance(value, (int, float)):
            if value > float(t_max):
                exceeded = "⚠️ 超上限"
        if t_min not in (None, "—") and isinstance(value, (int, float)):
            if value < float(t_min):
                exceeded = "⚠️ 低于下限"

        lines.append(f"| {name} | {unit} | {value} | {t_max} | {t_min} | {exceeded} |")

    # 异常摘要
    anomaly_summary = report.get("anomaly_summary", [])
    if anomaly_summary:
        lines.append("")
        lines.append("## 设备端异常摘要")
        for a in anomaly_summary:
            lines.append(f"- {a}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  LLM 调用
# ═══════════════════════════════════════════════════════════════


async def call_llm(context: str) -> str:
    """
    调用大语言模型 API 进行分析。

    Parameters
    ----------
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

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
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
    AI Agent 主流程：读取报告 → 构建上下文 → LLM 分析 → 结果存库。

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

        # 构建上下文
        template_data = {
            "name": template_obj.name if template_obj else "未知模板",
            "version": template_obj.version if template_obj else "?",
            "schema_definition": template_obj.schema_definition if template_obj else {},
        }
        report_data = report_obj.report_data

        context = build_analysis_context(template_data, report_data)

        # 调用 LLM
        try:
            analysis = await call_llm(context)
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
        t_max = r.get("threshold_max", template_metrics.get(name, {}).get("threshold_max"))
        t_min = r.get("threshold_min", template_metrics.get(name, {}).get("threshold_min"))

        if t_max is not None and isinstance(value, (int, float)) and value > float(t_max):
            anomalies.append(f"- **{name}** = {value}{r.get('unit', '')} — 超出上限 {t_max}")
        elif t_min is not None and isinstance(value, (int, float)) and value < float(t_min):
            anomalies.append(f"- **{name}** = {value}{r.get('unit', '')} — 低于下限 {t_min}")
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
