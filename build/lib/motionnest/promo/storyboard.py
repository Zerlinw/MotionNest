"""阶段 3 · 固定骨架分镜（时长确定性，文案可模型生成）。

骨架（毫秒，合计精确 30000）：
    钩子 3000 + 产品亮相 5000 + 卖点合计 15000 + 数据佐证 4000 + CTA 3000
卖点条数决定并轨：1→15000 / 2→7500 / 3→5000 / 4→3750 / 5→3000；
无卖点时退化为 钩子 4000 + 亮相 8000 + 佐证 12000 + CTA 6000。

自动化边界：时长与节拍结构完全确定性（保证 30 秒完整性）；
on_screen_text / narration 由 copy_fn 生成，缺失或超长时用 brief 确定性兜底并截断。
"""

from __future__ import annotations

from collections.abc import Callable

from ..utils.json import parse_json_loose
from .schemas import PromoBrief, PromoDoc, PromoShot, PromoStoryboard

TOTAL_DURATION_MS = 30_000
_HOOK_MS = 3_000
_REVEAL_MS = 5_000
_PROOF_MS = 4_000
_CTA_MS = 3_000
_SELLING_TOTAL_MS = TOTAL_DURATION_MS - _HOOK_MS - _REVEAL_MS - _PROOF_MS - _CTA_MS  # 15000
_NO_POINT_DURATIONS = {"hook": 4_000, "reveal": 8_000, "proof": 12_000, "cta": 6_000}

COPY_SYSTEM = """你是宣传片文案。为给定节拍写屏幕字幕与旁白。
规则：字幕口语化、不超过字数上限；旁白一句话讲清价值；只输出 JSON。"""


def build_storyboard(
    brief: PromoBrief,
    doc: PromoDoc,
    copy_fn: Callable[[str, str], str] | None = None,
) -> PromoStoryboard:
    """brief → 分镜（Σduration_ms 精确 30000）。"""
    plan = _beat_plan(brief)
    copy = _beat_copy(brief, doc, copy_fn) if copy_fn else {}
    shots: list[PromoShot] = []
    point_index = 0
    for beat, duration_ms in plan:
        if beat == "selling_point":
            text, narration, source = _point_copy(brief, copy, point_index)
            point_index += 1
            visual = {"kind": "image", "keywords": text[:20]}
        elif beat == "proof":
            text, narration, source = _proof_copy(brief, copy)
            visual = {"kind": "chart", "table": _first_table_name(doc)}
        elif beat == "cta":
            text, narration, source = _cta_copy(brief, copy)
            visual = {"kind": "text"}
        elif beat == "hook":
            text, narration, source = _hook_copy(brief, copy)
            visual = {"kind": "image", "keywords": brief.product_name}
        else:  # reveal
            text, narration, source = _reveal_copy(brief, copy)
            visual = {"kind": "image", "keywords": brief.product_name}
        shots.append(
            PromoShot(
                id=f"shot-{len(shots) + 1}",
                beat=beat,
                duration_ms=duration_ms,
                on_screen_text=text,
                narration=narration,
                visual=visual,
                copy_source=source,
            )
        )
    storyboard = PromoStoryboard(
        title=f"{brief.product_name} · 30 秒宣传片",
        total_duration_ms=TOTAL_DURATION_MS,
        shots=shots,
    )
    storyboard.assert_duration()
    return storyboard


def template_storyboard(brief: PromoBrief, doc: PromoDoc) -> PromoStoryboard:
    """无模型时的确定性分镜（离线/测试基线）。"""
    return build_storyboard(brief, doc, copy_fn=None)


# ---------------------------------------------------------------- 节拍规划
def _beat_plan(brief: PromoBrief) -> list[tuple[str, int]]:
    points = [p for p in brief.selling_points if p.strip()]
    if not points:
        return [
            ("hook", _NO_POINT_DURATIONS["hook"]),
            ("reveal", _NO_POINT_DURATIONS["reveal"]),
            ("proof", _NO_POINT_DURATIONS["proof"]),
            ("cta", _NO_POINT_DURATIONS["cta"]),
        ]
    per_point, remainder = divmod(_SELLING_TOTAL_MS, len(points))
    plan: list[tuple[str, int]] = [("hook", _HOOK_MS), ("reveal", _REVEAL_MS)]
    for index in range(len(points)):
        duration = per_point + (1 if index < remainder else 0)
        plan.append(("selling_point", duration))
    plan.append(("proof", _PROOF_MS))
    plan.append(("cta", _CTA_MS))
    return plan


# ---------------------------------------------------------------- 文案
def _beat_copy(
    brief: PromoBrief, doc: PromoDoc, copy_fn: Callable[[str, str], str] | None
) -> dict:
    if copy_fn is None:
        return {}
    prompt = (
        f"产品：{brief.product_name}\n标语：{brief.tagline}\n受众：{brief.audience}\n"
        f"卖点：{'；'.join(brief.selling_points)}\n佐证：{'；'.join(brief.proof_numbers)}\n"
        f"CTA：{brief.cta}\n文档标题：{doc.title}\n\n"
        '输出 JSON：{"hook": {"text", "narration"}, "reveal": {"text", "narration"}, '
        '"selling_points": [{"text", "narration"}], "proof": {"text", "narration"}, '
        '"cta": {"text", "narration"}}；hook 字幕 ≤24 字，卖点字幕 ≤28 字，CTA ≤16 字。'
    )
    try:
        payload = parse_json_loose(copy_fn(COPY_SYSTEM, prompt))
        return payload if isinstance(payload, dict) else {}
    except Exception:  # noqa: BLE001 - 文案失败不影响时长结构，走兜底
        return {}


def _pick(copy: dict, key: str, index: int | None = None) -> tuple[str, str, str]:
    node = copy.get(key)
    if index is not None:
        items = node if isinstance(node, list) else []
        node = items[index] if index < len(items) else None
    if isinstance(node, dict):
        text = str(node.get("text", "")).strip()
        narration = str(node.get("narration", "")).strip()
        if text:
            return text, narration, "model"
    return "", "", "template"


def _hook_copy(brief: PromoBrief, copy: dict) -> tuple[str, str, str]:
    text, narration, source = _pick(copy, "hook")
    if not text:
        text = f"{brief.product_name}\n{brief.tagline}" if brief.tagline else brief.product_name
    return text[:48], narration[:80], source


def _reveal_copy(brief: PromoBrief, copy: dict) -> tuple[str, str, str]:
    text, narration, source = _pick(copy, "reveal")
    if not text:
        text = f"为{brief.audience or '客户'}而生" if brief.audience else "专业设备 · 全新亮相"
    return text[:48], narration[:80], source


def _point_copy(brief: PromoBrief, copy: dict, index: int) -> tuple[str, str, str]:
    text, narration, source = _pick(copy, "selling_points", index)
    if not text:
        points = [p for p in brief.selling_points if p.strip()]
        text = points[index] if index < len(points) else "稳定可靠"
    return text[:32], narration[:80], source


def _proof_copy(brief: PromoBrief, copy: dict) -> tuple[str, str, str]:
    text, narration, source = _pick(copy, "proof")
    if not text:
        text = " · ".join(brief.proof_numbers[:2]) if brief.proof_numbers else "用数据说话"
    return text[:48], narration[:80], source


def _cta_copy(brief: PromoBrief, copy: dict) -> tuple[str, str, str]:
    text, narration, source = _pick(copy, "cta")
    if not text:
        text = f"{brief.cta}\n{brief.product_name}" if brief.cta else brief.product_name
    return text[:32], narration[:80], source


def _first_table_name(doc: PromoDoc) -> str:
    return doc.tables[0].source if doc.tables else ""
