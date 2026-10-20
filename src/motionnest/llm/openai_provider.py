"""OpenAI 兼容接口实现（POST {base_url}/chat/completions）。

适用于 OpenAI、DeepSeek、Moonshot、智谱、本地 vLLM/Ollama 等一切
OpenAI 兼容端点。业务层不直接 import 本类——由 ModelRegistry 按
models.yaml 的 provider_format 字段实例化。
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from .base import LLMProvider
from .types import LLMResponse, Message


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions 兼容提供方。"""

    format_name = "openai"

    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        payload = {
            "model": self.spec.model_id,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens or self.spec.max_output_tokens,
        }
        started = time.perf_counter()
        data = self._post_json(
            f"{self.spec.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        choices = data.get("choices") or [{}]
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        usage_raw = data.get("usage") or {}
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens", 0),
            "completion_tokens": usage_raw.get("completion_tokens", 0),
            "total_tokens": usage_raw.get("total_tokens", 0),
        }
        return LLMResponse(
            text=text,
            model=data.get("model", self.spec.model_id),
            provider_format=self.format_name,
            usage=usage,
            latency_ms=latency_ms,
            raw=data,
        )
