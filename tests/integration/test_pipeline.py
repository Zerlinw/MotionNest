"""集成测试：离线全链路（不依赖任何模型密钥）。

覆盖：项目创建 → 数据门禁 → 离线洞察 → 离线分镜/合成 → 视觉门禁 →
评论收件箱 → 定点改稿 → 快照/回滚 → 发布门禁拦截。
"""

from __future__ import annotations

import json

import pytest

from motionnest.agents.data_interpreter import template_insight
from motionnest.agents.reviser import Reviser
from motionnest.agents.storyboard import template_storyboard
from motionnest.composition.scenes import apply_patch, template_composition
from motionnest.core.project import Project
from motionnest.core.schemas import Composition
from motionnest.data.loader import dictionary_from_summary, load_table
from motionnest.qa.gates import blocking_errors, run_all_gates, visual_gate


@pytest.fixture()
def csv_file(tmp_path):
    path = tmp_path / "q3.csv"
    path.write_text(
        "month,new_users,activated_users,retained_d30,revenue_cny\n"
        "2026-01,1200,780,402,186000\n"
        "2026-02,1350,910,480,212000\n"
        "2026-03,1180,760,398,174000\n"
        "2026-04,1520,1080,612,268000\n",
        encoding="utf-8",
    )
    return path


def test_full_offline_pipeline(tmp_path, csv_file, stub_router):
    # 1. 项目创建
    project = Project.create(tmp_path / "story", "q3-story")
    assert (project.root / "project.json").is_file()

    # 2. 数据导入与门禁
    records, summary = load_table(csv_file)
    dictionary = dictionary_from_summary(summary, source="local:q3.csv")
    from motionnest.qa.gates import data_gate

    assert data_gate(summary, dictionary).passed is True
    project.write_json("data/summary.json", summary)
    project.write_json("data/dictionary.json", dictionary)
    project.snapshot("data")

    # 3. 离线洞察 + 批准方向
    insight = template_insight(summary, dictionary)
    project.write_json("plan/insights.json", insight)
    project.write_json("plan/approved.json", {"candidate_id": "cand-1"})

    # 4. 离线分镜 + 合成
    storyboard = template_storyboard(insight, "cand-1", duration_ms=20000)
    project.write_json("script/storyboard.json", storyboard)
    composition = template_composition(storyboard)
    assert visual_gate(composition).passed is True
    project.write_json("composition/composition.json", composition)
    project.snapshot("compose")

    # 5. 评论 → 定点改稿（桩模型产出补丁）
    scene_id = composition.scenes[1].id
    layer_id = composition.scenes[1].layers[0].id
    patch_payload = {
        "scene_id": scene_id,
        "layer_id": layer_id,
        "changes": {"title": "修正后的标题"},
        "reason": "原标题超出安全区",
        "evidence_check": None,
        "needs_recompute": False,
    }
    stub_router.registry.provider("low-stub").replies.append(json.dumps(patch_payload, ensure_ascii=False))
    patch, _ = Reviser(stub_router).run("标题太长了", composition, scene_id=scene_id, layer_id=layer_id)
    updated, touches = apply_patch(composition, patch)
    assert touches is False
    assert updated.find_layer(scene_id, layer_id).props["title"] == "修正后的标题"
    project.write_json("composition/composition.json", updated)
    project.snapshot("revise")

    # 6. 回滚到改稿前
    project.undo()
    restored = Composition.model_validate(project.read_json("composition/composition.json"))
    assert restored.find_layer(scene_id, layer_id).props["title"] != "修正后的标题"

    # 7. 发布门禁：未签批 → 拦截
    gates = run_all_gates(
        summary=summary,
        dictionary=dictionary,
        insight=insight,
        composition=restored,
        approvals=project.manifest.approvals,
    )
    errors = blocking_errors(gates)
    assert any("人工签批" in error for error in errors)

    # 8. 三项人工签批后放行
    for artifact in ("reviews/music-plan.json", "reviews/camera-moves.json", "reviews/review-report.json"):
        project.write_json(artifact, {"signed": True})
        project.approve(artifact, "人工确认")
    gates = run_all_gates(
        summary=summary,
        dictionary=dictionary,
        insight=insight,
        composition=restored,
        approvals=project.manifest.approvals,
    )
    assert blocking_errors(gates) == []
