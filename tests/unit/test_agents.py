"""Agent 层测试：schema 契约、校验重试、强模型/人工边界。"""

from __future__ import annotations

import json

import pytest

from motionnest.agents import CameraDesigner, DataInterpreter, MusicDirector
from motionnest.core.schemas import CameraMove, DataInsight, MusicPlan, Scene
from motionnest.exceptions import HumanReviewRequired, SchemaValidationError

GOOD_INSIGHT = {
    "summary": "增长由激活驱动",
    "metrics": [
        {"name": "retained_d30", "display_value": "398 ~ 948", "evidence_id": "metric:retained_d30"}
    ],
    "candidates": [
        {
            "id": "cand-1",
            "title": "留存改善",
            "thesis": "新用户激活改善带来留存提升",
            "audience": "管理层",
            "key_numbers": ["948"],
            "evidence_ids": ["metric:retained_d30"],
            "ignored_info": ["渠道结构"],
            "risks": ["样本期短"],
        }
    ],
    "data_quality_notes": [],
}


def _summary():
    from motionnest.data.loader import summarize

    records = [
        {"month": "2026-01", "retained_d30": "402"},
        {"month": "2026-02", "retained_d30": "480"},
        {"month": "2026-03", "retained_d30": "398"},
    ]
    return summarize(records)


def _dictionary():
    from motionnest.data.loader import dictionary_from_summary

    return dictionary_from_summary(_summary(), source="test")


def test_data_interpreter_parses_valid_output(stub_router):
    stub_router.registry.provider("low-stub").replies.append(json.dumps(GOOD_INSIGHT, ensure_ascii=False))
    insight, response = DataInterpreter(stub_router).run(_summary(), _dictionary(), {"goal": "测试"})
    assert isinstance(insight, DataInsight)
    assert insight.candidates[0].id == "cand-1"
    assert response.tier_used.value == "low"


def test_data_interpreter_retries_on_bad_json(stub_router):
    low = stub_router.registry.provider("low-stub")
    low.replies.append("这不是 JSON")
    low.replies.append(json.dumps(GOOD_INSIGHT, ensure_ascii=False))
    insight, _ = DataInterpreter(stub_router).run(_summary(), _dictionary(), {})
    assert insight.summary == "增长由激活驱动"
    assert len(low.calls) == 2  # 第一次失败被回喂纠错


def test_data_interpreter_raises_after_max_retries(stub_router):
    low = stub_router.registry.provider("low-stub")
    low.replies.extend(["坏输出", "还是坏输出", "依然坏输出"])
    with pytest.raises(SchemaValidationError):
        DataInterpreter(stub_router).run(_summary(), _dictionary(), {})


def test_parse_json_loose_handles_fences():
    from motionnest.utils.json import parse_json_loose

    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_loose('前言废话 {"a": [1, 2]} 后记') == {"a": [1, 2]}
    with pytest.raises(ValueError):
        parse_json_loose("完全没有 JSON")


def test_music_director_requires_signoff(stub_router):
    plan = {
        "tempo_bpm": 96,
        "sections": [{"label": "intro", "start_ms": 0, "duration_ms": 5000, "energy": 0.3}],
        "sfx_events": [],
        "fade_in_ms": 400,
        "fade_out_ms": 1200,
    }
    stub_router.registry.provider("strong-stub").replies.append(json.dumps(plan, ensure_ascii=False))
    from motionnest.core.schemas import Shot, Storyboard

    storyboard = Storyboard(
        title="t",
        total_duration_ms=5000,
        shots=[Shot(id="shot-1", start_ms=0, duration_ms=5000, scene_type="title", assertion="a")],
    )
    result, response = MusicDirector(stub_router).run(storyboard, {})
    assert isinstance(result, MusicPlan)
    assert result.tempo_bpm == 96
    assert response.requires_human_signoff is True


def test_music_director_human_fallback_when_strong_missing(stub_router, monkeypatch):
    monkeypatch.delenv("TEST_KEY_STRONG", raising=False)
    monkeypatch.delenv("TEST_KEY_LOW", raising=False)
    from motionnest.core.schemas import Shot, Storyboard

    storyboard = Storyboard(
        title="t",
        total_duration_ms=5000,
        shots=[Shot(id="shot-1", start_ms=0, duration_ms=5000, scene_type="title", assertion="a")],
    )
    with pytest.raises(HumanReviewRequired):
        MusicDirector(stub_router).run(storyboard, {})


def test_camera_simple_uses_template_without_model(stub_router):
    scene = Scene(id="scene-01", shot_id="shot-1", duration_ms=4000, layers=[])
    move, response = CameraDesigner(stub_router).run(scene, {"complexity": "simple"})
    assert isinstance(move, CameraMove)
    assert move.generated_by == "template"
    assert response is None  # 未调用任何模型


def test_camera_complex_uses_strong_model(stub_router):
    scene = Scene(id="scene-01", shot_id="shot-1", duration_ms=4000, layers=[])
    payload = {
        "shot_id": "shot-1",
        "move_type": "orbit",
        "easing": "ease-in-out",
        "keyframes": [
            {"t_ms": 0, "position": [0, 0, 10], "target": [0, 0, 0], "fov": 50},
            {"t_ms": 4000, "position": [3, 1, 9], "target": [0, 0, 0], "fov": 50},
        ],
        "rationale": "环绕展示",
    }
    stub_router.registry.provider("strong-stub").replies.append(json.dumps(payload, ensure_ascii=False))
    move, response = CameraDesigner(stub_router).run(scene, {"complexity": "complex"})
    assert move.move_type == "orbit"
    assert response.tier_used.value == "strong"
