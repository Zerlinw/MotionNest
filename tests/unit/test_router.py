"""TaskRouter 路由规则测试：档位选择、降级、人工兜底。"""

from __future__ import annotations

import pytest

from motionnest.exceptions import HumanReviewRequired, ModelUnavailableError
from motionnest.llm.types import Message


class TestRouting:
    def test_low_task_prefers_low_tier(self, router):
        decision = router.resolve("data_interpretation")
        assert decision.model == "low-stub"
        assert decision.tier.value == "low"
        assert decision.degraded is False

    def test_low_task_falls_back_to_strong(self, router, monkeypatch):
        monkeypatch.delenv("TEST_KEY_LOW", raising=False)
        decision = router.resolve("storyboard_generation")
        assert decision.model == "strong-stub"
        assert decision.degraded is True

    def test_low_task_without_fallback_raises(self, router, monkeypatch):
        monkeypatch.delenv("TEST_KEY_LOW", raising=False)
        with pytest.raises(ModelUnavailableError):
            router.resolve("data_interpretation")

    def test_strong_task_prefers_strong(self, router):
        decision = router.resolve("music_aesthetics")
        assert decision.model == "strong-stub"
        assert decision.tier.value == "strong"
        assert decision.degraded is False

    def test_strong_task_human_review_when_unavailable(self, router, monkeypatch):
        monkeypatch.delenv("TEST_KEY_STRONG", raising=False)
        monkeypatch.delenv("TEST_KEY_LOW", raising=False)
        with pytest.raises(HumanReviewRequired):
            router.resolve("music_aesthetics")

    def test_strong_task_human_review_disabled(self, registry, config_paths, monkeypatch):
        from motionnest.llm.router import TaskRouter

        _, router_path = config_paths
        monkeypatch.delenv("TEST_KEY_STRONG", raising=False)
        monkeypatch.delenv("TEST_KEY_LOW", raising=False)
        strict = TaskRouter.from_yaml(registry, router_path, allow_human_review=False)
        with pytest.raises(ModelUnavailableError):
            strict.resolve("music_aesthetics")

    def test_unknown_task(self, router):
        from motionnest.exceptions import UnknownTaskError

        with pytest.raises(UnknownTaskError):
            router.resolve("not_a_task")

    def test_complete_returns_routed_response(self, stub_router):
        stub_router.registry.provider("low-stub").replies.append("你好")
        result = stub_router.complete("data_interpretation", [Message("user", "hi")])
        assert result.text == "你好"
        assert result.model_used == "low-stub"
        assert result.tier_used.value == "low"
        assert result.requires_human_signoff is False
        assert stub_router.audit_trail[-1]["task"] == "data_interpretation"

    def test_strong_task_marks_signoff(self, stub_router):
        stub_router.registry.provider("strong-stub").replies.append("{}")
        result = stub_router.complete("music_aesthetics", [Message("user", "hi")])
        assert result.requires_human_signoff is True
        assert result.tier_used.value == "strong"

    def test_describe_routes(self, router):
        rows = {row["task"]: row for row in router.describe_routes()}
        assert rows["data_interpretation"]["preferred_tier"] == "low"
        assert rows["music_aesthetics"]["human_review"] is True
        assert "strong-stub" in rows["music_aesthetics"]["candidates"]
        assert rows["music_aesthetics"]["fallback_tiers"] == ["low"]
