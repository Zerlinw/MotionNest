"""提示词仓库测试：默认值、覆盖、模板渲染。"""

from __future__ import annotations

from motionnest.agents import prompts


def test_all_seven_tasks_have_defaults():
    tasks = prompts.tasks()
    assert len(tasks) == 7
    for task in tasks:
        assert prompts.get(task, "system")
        assert prompts.get(task, "user")


def test_override_and_reset():
    task = "data_interpretation"
    original = prompts.get(task, "system")
    prompts.set_override(task, "system", "覆盖后的系统提示")
    assert prompts.get(task, "system") == "覆盖后的系统提示"
    prompts.set_override(task, "system", "")  # 空字符串 = 恢复默认
    assert prompts.get(task, "system") == original


def test_reset_all():
    prompts.set_override("storyboard_generation", "user", "x")
    prompts.reset_override()
    assert prompts.get("storyboard_generation", "user") == prompts.DEFAULTS["storyboard_generation"]["user"]


def test_render_substitutes_fields():
    text = prompts.render("data_interpretation", "user", brief_json="{}", summary_json="[]", dictionary_json="{}")
    assert "$brief_json" not in text
    assert "## 用户需求（brief）" in text


def test_render_tolerates_stray_dollar():
    """safe_substitute：模板外的 $ 不会抛错。"""
    text = prompts.render("storyboard_generation", "user", insight_json="{}", candidate_json="{}", constraints_json="{}")
    assert text


def test_invalid_kind_rejected():
    import pytest

    with pytest.raises(ValueError):
        prompts.set_override("data_interpretation", "middle", "x")
