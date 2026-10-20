"""Anthropic Messages 接口实现（POST {base_url}/v1/messages）。

适用于 Anthropic Claude，以及 DeepSeek 的 /anthropic 兼容端点
（base_url 配 https://api.deepseek.com/anthropic 即可）。
注意 Anthropic 格式的 system 是顶层字段而非消息角色。
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from .base import LLMProvider
from .types import LLMResponse, Message


class AnthropicProvider(LLMProvider):
    """Anthropic Messages 兼容提供方。"""

    format_name = "anthropic"
    ANTHROPIC_VERSION = "2023-06-01"

    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        system = "\n\n".join(m.content for m in messages if m.role == "system").strip() or None
        turns = [m.to_dict() for m in messages if m.role != "system"]
        payload: dict = {
            "model": self.spec.model_id,
            "messages": turns,
            "max_tokens": max_tokens or self.spec.max_output_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        started = time.perf_counter()
        data = self._post_json(
            f"{self.spec.base_url.rstrip('/')}/v1/messages",
            headers={
                "x-api-key": self._api_key(),
                "anthropic-version": self.ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
        usage_raw = data.get("usage") or {}
        usage = {
            "prompt_tokens": usage_raw.get("input_tokens", 0),
            "completion_tokens": usage_raw.get("output_tokens", 0),
            "total_tokens": usage_raw.get("input_tokens", 0) + usage_raw.get("output_tokens", 0),
        }
        return LLMResponse(
            text=text,
            model=data.get("model", self.spec.model_id),
            provider_format=self.format_name,
            usage=usage,
            latency_ms=latency_ms,
            raw=data,
        )
