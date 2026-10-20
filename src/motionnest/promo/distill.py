"""阶段 2 · 要点蒸馏（单次模型调用，失败确定性降级）。

输入：PromoDoc + 用户一句话补充说明 + chat_fn(system, user) -> str。
输出：PromoBrief（产品名 / 标语 / 受众 / 卖点 2-5 条 / 佐证数字 / CTA / 语气 / 配色）。

自动化边界：chat_fn 缺失或调用/解析失败 → template_brief 确定性降级，
brief.source = "template" 并记入 degraded；不猜测文档中没有的事实，
佐证数字必须来自表格/正文中出现的数值。
"""

from __future__ import annotations

import re
from collections.abc import Callable

from ..utils.json import parse_json_loose
from .schemas import PromoBrief, PromoDoc

MAX_PROMPT_CHARS = 8000
DEFAULT_PALETTE = ["#4A88C7", "#3574F0", "#38C6A4", "#F7724F", "#F7C948"]

DISTILL_SYSTEM = """你是企业设备宣传片的叙事策划。根据给定文档蒸馏出一支 30 秒宣传片的简报。
硬规则：
1. 只使用文档中明确出现的信息，不得编造产品能力、参数或客户；
2. selling_points 输出 2-5 条，每条不超过 30 字，面向采购决策者讲价值；
3. proof_numbers 只收录文档中出现过的数字（含口径），没有就留空；
4. cta 是片尾行动号召，不超过 20 字；
5. 只输出 JSON，不要任何解释。"""


def distill_brief(
    doc: PromoDoc,
    note: str,
    chat_fn: Callable[[str, str], str] | None = None,
) -> PromoBrief:
    """文档 → 宣传片简报。模型不可用时降级为模板。"""
    if chat_fn is None:
        return _degraded(doc, "未配置对话模型，使用模板降级")
    prompt = _build_prompt(doc, note)
    try:
        raw = chat_fn(DISTILL_SYSTEM, prompt)
        brief = _normalize(PromoBrief.model_validate(parse_json_loose(raw)))
        if not brief.product_name:
            raise ValueError("product_name 为空")
        return brief
    except Exception as exc:  # noqa: BLE001 - 任何模型侧失败都走确定性降级
        return _degraded(doc, f"要点蒸馏失败（{type(exc).__name__}），使用模板降级")


def template_brief(doc: PromoDoc) -> PromoBrief:
    """确定性模板简报：标题 + 小节标题 + 表格数值列，不构成叙事建议。"""
    headings = [s.text for s in doc.sections if s.kind == "heading"]
    paragraphs = [s.text for s in doc.sections if s.kind in ("paragraph", "list")]
    selling = [h for h in headings[1:] if not _is_generic_heading(h)][:3]
    if not selling:
        selling = [p[:30] for p in paragraphs[:3]]
    if not selling:
        selling = ["稳定可靠的工业设计"]
    numbers: list[str] = []
    for table in doc.tables:
        for line in table.summary.splitlines()[1:]:
            name, _, value = line.partition(":")
            if " ~ " in value:  # 仅收录数值列的范围行（样例行可能是型号等文本）
                numbers.append(f"{name.strip()} {value.strip()}（{table.source}）")
    return PromoBrief(
        product_name=doc.title or "企业设备",
        tagline=next((p[:40] for p in paragraphs if p), "专业设备 · 稳定之选"),
        audience="采购与运维决策者",
        selling_points=selling[:5],
        proof_numbers=numbers[:3],
        cta="欢迎联系获取详细方案",
        source="template",
    )


_GENERIC_HEADINGS = {"概述", "介绍", "简介", "关于", "关于我们", "目录", "总结", "联系方式", "产品概述"}


def _is_generic_heading(text: str) -> bool:
    return text.strip() in _GENERIC_HEADINGS


def _degraded(doc: PromoDoc, reason: str) -> PromoBrief:
    brief = template_brief(doc)
    brief.source = "template"
    doc.degraded.append(reason)
    return brief


def _build_prompt(doc: PromoDoc, note: str) -> str:
    parts: list[str] = [f"文档标题：{doc.title}"]
    for section in doc.sections:
        parts.append(f"[{section.kind}] {section.text}")
    for table in doc.tables:
        parts.append(f"[table {table.source}] {table.summary}")
    for image in doc.images:
        parts.append(f"[image] {image.name}（来自 {image.source}）")
    body = "\n".join(parts)[:MAX_PROMPT_CHARS]
    instruction = (
        "\n\n请输出 JSON：{product_name, tagline, audience, selling_points[], "
        "proof_numbers[], cta, tone, palette[]}"
    )
    if note.strip():
        instruction += f"\n用户补充要求（优先满足）：{note.strip()}"
    return body + instruction


def _normalize(brief: PromoBrief) -> PromoBrief:
    """裁剪到 schema 约定：卖点 2-5 条、各字段长度上限。"""
    brief.selling_points = [p.strip()[:60] for p in brief.selling_points if p.strip()][:5]
    brief.proof_numbers = [n.strip()[:60] for n in brief.proof_numbers if n.strip()][:3]
    brief.tagline = brief.tagline.strip()[:60]
    brief.audience = brief.audience.strip()[:40]
    brief.cta = brief.cta.strip()[:40] or "欢迎联系获取详细方案"
    brief.tone = brief.tone.strip()[:20] or "专业、克制"
    brief.palette = [c for c in brief.palette if re.match(r"^#[0-9a-fA-F]{6}$", c)][:5] or list(DEFAULT_PALETTE)
    return brief
