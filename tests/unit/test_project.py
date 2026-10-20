"""评论收件箱与版本管理测试。"""

from __future__ import annotations

import pytest

from motionnest.core.project import Project
from motionnest.core.schemas import Layer, Scene
from motionnest.core.versions import diff_snapshots
from motionnest.studio.inbox import Inbox, hit_test


def _scene():
    return Scene(
        id="scene-01",
        shot_id="shot-1",
        duration_ms=3000,
        layers=[
            Layer(id="layer-a", type="text", props={"text": "A", "x": 0, "y": 0, "w": 400, "h": 100}),
            Layer(id="layer-b", type="chart", props={"chart_type": "bar", "series": []}),
        ],
    )


def test_inbox_post_claim_resolve(tmp_path):
    inbox = Inbox(tmp_path / "inbox.jsonl")
    comment = inbox.post("改标题", scene_id="scene-01", time_ms=100, x=10, y=10, element_id="layer-a")
    assert comment.status == "open"
    assert len(inbox.list("open")) == 1

    claimed = inbox.claim_next()
    assert claimed.id == comment.id
    assert claimed.status == "claimed"
    assert inbox.claim_next() is None

    resolved = inbox.resolve(comment.id, note="已改")
    assert resolved.status == "resolved"
    assert resolved.note == "已改"
    # append-only：文件保留全部历史行
    assert len(inbox.list()) == 1


def test_hit_test_topmost_wins():
    scene = _scene()
    assert hit_test(scene.layers, 100, 50, viewport_width=1920, viewport_height=1080) == "layer-a"
    assert hit_test(scene.layers, 1800, 1000, viewport_width=1920, viewport_height=1080) is None


def test_hit_test_overlap_prefers_later_layer():
    layers = [
        Layer(id="bottom", type="text", props={"x": 0, "y": 0, "w": 800, "h": 800}),
        Layer(id="top", type="text", props={"x": 0, "y": 0, "w": 800, "h": 800}),
    ]
    assert hit_test(layers, 100, 100, viewport_width=1920, viewport_height=1080) == "top"


def test_project_snapshot_and_undo(tmp_path):
    project = Project.create(tmp_path / "proj", "demo")
    project.write_json("data/summary.json", {"rows": 1})
    version_a = project.snapshot("v1")
    project.write_json("data/summary.json", {"rows": 2})
    version_b = project.snapshot("v2")
    assert project.read_json("data/summary.json") == {"rows": 2}

    restored = project.undo()
    assert restored == version_a
    assert project.read_json("data/summary.json") == {"rows": 1}

    diff = diff_snapshots(project.root, version_a, version_b)
    assert "data/summary.json" in diff["changed"]


def test_project_approvals(tmp_path):
    project = Project.create(tmp_path / "proj", "demo")
    assert project.is_approved("reviews/music-plan.json") is False
    project.write_json("reviews/music-plan.json", {"tempo_bpm": 90})
    project.approve("reviews/music-plan.json", "listened")
    assert project.is_approved("reviews/music-plan.json") is True


def test_project_path_escape_blocked(tmp_path):
    project = Project.create(tmp_path / "proj", "demo")
    from motionnest.exceptions import ConfigError

    with pytest.raises(ConfigError):
        project.path("..", "outside.txt")
