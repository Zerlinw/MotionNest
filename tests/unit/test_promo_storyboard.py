"""promo 阶段 3 测试：固定骨架、30 秒硬不变量、并轨与兜底文案。"""

from __future__ import annotations

import pytest

from motionnest.promo.schemas import PromoBrief, PromoDoc, PromoDocSection, PromoTable
from motionnest.promo.storyboard import (
    TOTAL_DURATION_MS,
    build_storyboard,
    template_storyboard,
)


def _doc() -> PromoDoc:
    return PromoDoc(
        title="XR-500 巡检机器人",
        sections=[
            PromoDocSection(kind="heading", text="XR-500 巡检机器人"),
            PromoDocSection(kind="paragraph", text="面向石化厂区的自主巡检设备。"),
        ],
        tables=[
            PromoTable(source="specs.csv", columns=["型号", "续航小时"], rows=2, summary="2 行 × 2 列\n续航小时: 12 ~ 18")
        ],
    )


def _brief(points: list[str]) -> PromoBrief:
    return PromoBrief(
        product_name="XR-500",
        tagline="厂区巡检专家",
        audience="采购决策者",
        selling_points=points,
        proof_numbers=["续航小时 12 ~ 18（specs.csv）"],
        cta="欢迎联系获取方案",
    )


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_total_duration_exact_for_any_point_count(count: int):
    brief = _brief([f"卖点{index}" for index in range(count)])
    storyboard = build_storyboard(brief, _doc(), None)
    assert storyboard.total_duration_ms == TOTAL_DURATION_MS == 30_000
    assert sum(shot.duration_ms for shot in storyboard.shots) == 30_000
    storyboard.assert_duration()  # 不抛异常


def test_skeleton_beats_with_three_points():
    storyboard = build_storyboard(_brief(["A", "B", "C"]), _doc(), None)
    beats = [(shot.beat, shot.duration_ms) for shot in storyboard.shots]
    assert beats == [
        ("hook", 3000),
        ("reveal", 5000),
        ("selling_point", 5000),
        ("selling_point", 5000),
        ("selling_point", 5000),
        ("proof", 4000),
        ("cta", 3000),
    ]


def test_two_points_merge_durations():
    storyboard = build_storyboard(_brief(["A", "B"]), _doc(), None)
    selling = [shot.duration_ms for shot in storyboard.shots if shot.beat == "selling_point"]
    assert selling == [7500, 7500]
    assert sum(shot.duration_ms for shot in storyboard.shots) == 30_000


def test_no_points_fallback_skeleton():
    storyboard = build_storyboard(_brief([]), _doc(), None)
    assert sum(shot.duration_ms for shot in storyboard.shots) == 30_000
    assert {shot.beat for shot in storyboard.shots} == {"hook", "reveal", "proof", "cta"}


def test_copy_fallback_without_model():
    storyboard = build_storyboard(_brief(["自主避障", "续航 12 小时"]), _doc(), None)
    assert all(shot.on_screen_text for shot in storyboard.shots)
    hook = storyboard.shots[0]
    assert "XR-500" in hook.on_screen_text
    assert all(shot.copy_source == "template" for shot in storyboard.shots)


def test_copy_from_model():
    reply = (
        '{"hook": {"text": "厂区巡检，一夜无忧", "narration": "XR-500 让夜间巡检无人化"}, '
        '"reveal": {"text": "为采购决策者而生"}, '
        '"selling_points": [{"text": "自主避障更安全"}, {"text": "12 小时长续航"}], '
        '"proof": {"text": "续航 12 ~ 18 小时"}, '
        '"cta": {"text": "欢迎联系获取方案"}}'
    )
    storyboard = build_storyboard(_brief(["占位", "占位"]), _doc(), lambda system, user: reply)
    all_texts = [shot.on_screen_text for shot in storyboard.shots]
    assert all_texts[0] == "厂区巡检，一夜无忧"
    assert "自主避障更安全" in all_texts
    assert all_texts[-1] == "欢迎联系获取方案"
    assert sum(shot.duration_ms for shot in storyboard.shots) == 30_000


def test_copy_model_failure_falls_back():
    def broken(system: str, user: str) -> str:
        raise RuntimeError("模型不可用")

    storyboard = build_storyboard(_brief(["A", "B"]), _doc(), broken)
    assert all(shot.copy_source == "template" for shot in storyboard.shots)
    assert sum(shot.duration_ms for shot in storyboard.shots) == 30_000


def test_proof_visual_uses_table():
    storyboard = build_storyboard(_brief(["A", "B"]), _doc(), None)
    proof = next(shot for shot in storyboard.shots if shot.beat == "proof")
    assert proof.visual["kind"] == "chart"
    assert proof.visual["table"] == "specs.csv"


def test_template_storyboard_matches():
    brief = _brief(["A", "B", "C"])
    doc = _doc()
    assert template_storyboard(brief, doc).model_dump() == build_storyboard(brief, doc, None).model_dump()
