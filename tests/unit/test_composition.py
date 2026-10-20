"""合成层与门禁测试：模板合成、定点补丁、视觉/逻辑/发布门禁。"""

from __future__ import annotations

from motionnest.agents.data_interpreter import template_insight
from motionnest.agents.storyboard import template_storyboard
from motionnest.composition.scenes import apply_patch, template_composition
from motionnest.composition.timeline import Timeline
from motionnest.core.schemas import RevisionPatch
from motionnest.data.loader import dictionary_from_summary, summarize
from motionnest.qa.gates import logic_gate, release_gate, visual_gate

RECORDS = [
    {"month": "2026-01", "new_users": "1200", "retained_d30": "402"},
    {"month": "2026-02", "new_users": "1350", "retained_d30": "480"},
    {"month": "2026-03", "new_users": "1180", "retained_d30": "398"},
]


def _pipeline():
    summary = summarize(RECORDS)
    insight = template_insight(summary, dictionary_from_summary(summary, source="test"))
    storyboard = template_storyboard(insight, "cand-1", duration_ms=24000)
    composition = template_composition(storyboard)
    return summary, insight, storyboard, composition


def test_template_storyboard_timecodes_are_continuous():
    _, _, storyboard, _ = _pipeline()
    cursor = 0
    for shot in storyboard.normalized_shots():
        assert shot.start_ms == cursor
        cursor += shot.duration_ms
    assert cursor == storyboard.total_duration_ms


def test_timeline_lookup_and_timecode():
    _, _, storyboard, _ = _pipeline()
    timeline = Timeline(30, tuple(storyboard.normalized_shots()))
    assert timeline.total_ms == storyboard.total_duration_ms
    assert Timeline.timecode(0) == "00:00.000"
    assert Timeline.timecode(65_500) == "01:05.500"
    assert timeline.shot_at(0).id == "shot-1"


def test_template_composition_ids_are_stable_and_unique():
    _, _, _, composition = _pipeline()
    ids = [layer.id for scene in composition.scenes for layer in scene.layers]
    assert len(ids) == len(set(ids))
    assert all(scene.id.startswith("scene-") for scene in composition.scenes)


def test_apply_patch_only_touches_target_layer():
    _, _, _, composition = _pipeline()
    scene_id = composition.scenes[1].id
    layer_id = composition.scenes[1].layers[0].id
    before = composition.model_copy(deep=True)
    patch = RevisionPatch(
        scene_id=scene_id,
        layer_id=layer_id,
        changes={"title": "新标题"},
        reason="评论要求",
    )
    updated, touches_data = apply_patch(composition, patch)
    assert touches_data is False
    assert updated.find_layer(scene_id, layer_id).props["title"] == "新标题"
    # 其他场景原样不动
    assert updated.scenes[0] == before.scenes[0]
    # 原对象不被修改
    assert composition.find_layer(scene_id, layer_id).props["title"] != "新标题"


def test_apply_patch_detects_data_bearing_change():
    _, _, _, composition = _pipeline()
    scene_id = composition.scenes[1].id
    layer_id = composition.scenes[1].layers[0].id
    patch = RevisionPatch(
        scene_id=scene_id,
        layer_id=layer_id,
        changes={"value": 999},
        reason="改数",
    )
    _, touches_data = apply_patch(composition, patch)
    assert touches_data is True


def test_visual_gate_flags_duplicate_layer_ids():
    _, _, _, composition = _pipeline()
    composition.scenes[1].layers[0].id = composition.scenes[0].layers[0].id
    gate = visual_gate(composition)
    assert gate.passed is False
    assert any("重复" in error for error in gate.errors)


def test_logic_gate_flags_candidate_without_evidence():
    _, insight, _, _ = _pipeline()
    insight.candidates[0].evidence_ids = []
    gate = logic_gate(insight, summarize(RECORDS))
    assert gate.passed is False


def test_release_gate_requires_signoffs():
    gate = release_gate({})
    assert gate.passed is False
    gate = release_gate({"reviews/music-plan.json": "x", "reviews/camera-moves.json": "x", "reviews/review-report.json": "x"})
    assert gate.passed is True
