"""Provider 双接口格式测试：用 MockTransport 验证线协议与归一化解析。"""

from __future__ import annotations

import httpx
import pytest

from motionnest.llm.anthropic_provider import AnthropicProvider
from motionnest.llm.openai_provider import OpenAIProvider
from motionnest.llm.registry import ModelSpec
from motionnest.llm.types import Message

OPENAI_SPEC = ModelSpec(
    name="t-openai",
    model_id="deepseek-flash",
    provider_format="openai",
    base_url="https://api.deepseek.com",
    api_key_env="TEST_KEY_LOW",
    tier="low",
)

ANTHROPIC_SPEC = ModelSpec(
    name="t-anthropic",
    model_id="deepseek-flash",
    provider_format="anthropic",
    base_url="https://api.deepseek.com/anthropic",
    api_key_env="TEST_KEY_LOW",
    tier="low",
)


def _client_with(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_wire_format(monkeypatch):
    monkeypatch.setenv("TEST_KEY_LOW", "sk-test")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [{"message": {"role": "assistant", "content": "你好，世界"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16},
            },
        )

    provider = OpenAIProvider(OPENAI_SPEC)
    provider._client = _client_with(handler)
    response = provider.chat([Message("system", "s"), Message("user", "u")])

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer sk-test"
    assert '"model":"deepseek-flash"' in captured["body"]
    assert '"role":"system"' in captured["body"]
    assert response.text == "你好，世界"
    assert response.provider_format == "openai"
    assert response.usage["total_tokens"] == 16


def test_anthropic_wire_format(monkeypatch):
    monkeypatch.setenv("TEST_KEY_LOW", "sk-test")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "content": [{"type": "text", "text": "片段一"}, {"type": "text", "text": "片段二"}],
                "usage": {"input_tokens": 9, "output_tokens": 4},
            },
        )

    provider = AnthropicProvider(ANTHROPIC_SPEC)
    provider._client = _client_with(handler)
    response = provider.chat([Message("system", "s"), Message("user", "u1"), Message("assistant", "a1"), Message("user", "u2")])

    assert captured["url"] == "https://api.deepseek.com/anthropic/v1/messages"
    assert captured["headers"]["x-api-key"] == "sk-test"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert '"system":"s"' in captured["body"]  # system 是顶层字段而非角色
    assert '"role":"system"' not in captured["body"]
    assert response.text == "片段一片段二"
    assert response.provider_format == "anthropic"
    assert response.usage["prompt_tokens"] == 9


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("TEST_KEY_LOW", raising=False)
    from motionnest.exceptions import MissingApiKeyError

    provider = OpenAIProvider(OPENAI_SPEC)
    with pytest.raises(MissingApiKeyError):
        provider.chat([Message("user", "hi")])


def test_retry_then_success(monkeypatch):
    monkeypatch.setenv("TEST_KEY_LOW", "sk-test")
    state = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["count"] += 1
        if state["count"] < 3:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "model": "m"})

    provider = OpenAIProvider(OPENAI_SPEC)
    provider._client = _client_with(handler)
    response = provider.chat([Message("user", "hi")])
    assert response.text == "ok"
    assert state["count"] == 3
