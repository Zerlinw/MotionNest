"""测试公共工具：StubProvider 与配置工厂。"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from motionnest.llm.base import LLMProvider
from motionnest.llm.registry import ModelRegistry, ModelSpec
from motionnest.llm.router import TaskRouter
from motionnest.llm.types import LLMResponse, Message

MODELS_YAML = """
models:
  - name: low-stub
    model_id: deepseek-flash
    provider_format: openai
    base_url: https://api.deepseek.com
    api_key_env: TEST_KEY_LOW
    tier: low
    max_output_tokens: 4096
  - name: strong-stub
    model_id: deepseek-v4-pro
    provider_format: anthropic
    base_url: https://api.deepseek.com/anthropic
    api_key_env: TEST_KEY_STRONG
    tier: strong
    max_output_tokens: 4096
"""

ROUTER_YAML = """
routes:
  data_interpretation:
    preferred_tier: low
    candidates: [low-stub]
    fallback_tiers: []
    human_review: false
  storyboard_generation:
    preferred_tier: low
    candidates: [low-stub]
    fallback_tiers: [strong]
    human_review: false
  draft_animation:
    preferred_tier: low
    candidates: [low-stub]
    fallback_tiers: [strong]
    human_review: false
  animation_revision:
    preferred_tier: low
    candidates: [low-stub]
    fallback_tiers: [strong]
    human_review: false
  music_aesthetics:
    preferred_tier: strong
    candidates: [strong-stub]
    fallback_tiers: [low]
    human_review: true
  camera_3d_design:
    preferred_tier: strong
    candidates: [strong-stub]
    fallback_tiers: [low]
    human_review: true
  final_review:
    preferred_tier: strong
    candidates: [strong-stub]
    fallback_tiers: [low]
    human_review: true
"""


class StubProvider(LLMProvider):
    """可编程桩 Provider：按队列返回文本，记录调用。"""

    def __init__(self, spec: ModelSpec, replies: list[str] | None = None, error: Exception | None = None) -> None:
        super().__init__(spec, timeout=5.0)
        self.replies = list(replies or [])
        self.error = error
        self.calls: list[list[Message]] = []

    def chat(self, messages, *, temperature: float = 0.2, max_tokens: int | None = None) -> LLMResponse:
        self.calls.append(list(messages))
        if self.error is not None:
            raise self.error
        text = self.replies.pop(0) if self.replies else "{}"
        return LLMResponse(
            text=text,
            model=self.spec.model_id,
            provider_format=self.spec.provider_format,
            latency_ms=7,
        )


def write_configs(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "models.yaml").write_text(MODELS_YAML, encoding="utf-8")
    (tmp_path / "router.yaml").write_text(ROUTER_YAML, encoding="utf-8")
    return tmp_path / "models.yaml", tmp_path / "router.yaml"


@pytest.fixture()
def registry(tmp_path: Path) -> ModelRegistry:
    models_path, _ = write_configs(tmp_path)
    return ModelRegistry.from_yaml(models_path)


@pytest.fixture()
def config_paths(tmp_path: Path) -> tuple[Path, Path]:
    return write_configs(tmp_path)


@pytest.fixture()
def router(registry: ModelRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TaskRouter:
    _, router_path = write_configs(tmp_path)
    monkeypatch.setenv("TEST_KEY_LOW", "k-low")
    monkeypatch.setenv("TEST_KEY_STRONG", "k-strong")
    return TaskRouter.from_yaml(registry, router_path)


@pytest.fixture()
def stub_router(registry: ModelRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TaskRouter:
    """带 StubProvider 的路由器（不发真实网络请求）。"""
    _, router_path = write_configs(tmp_path)
    monkeypatch.setenv("TEST_KEY_LOW", "k-low")
    monkeypatch.setenv("TEST_KEY_STRONG", "k-strong")
    task_router = TaskRouter.from_yaml(registry, router_path)
    registry._providers["low-stub"] = StubProvider(registry.get_spec("low-stub"))
    registry._providers["strong-stub"] = StubProvider(registry.get_spec("strong-stub"))
    return task_router


def mock_transport(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler)
