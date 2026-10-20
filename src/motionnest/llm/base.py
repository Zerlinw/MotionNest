"""LLMProvider 抽象基类：所有提供方只实现一个 chat() 方法。

业务层（agents/）永远通过 TaskRouter 调用，拿到的都是归一化 LLMResponse；
切换提供方 = 换一个 LLMProvider 实现 + 一条 models.yaml 声明。
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import httpx

from ..exceptions import MissingApiKeyError, MotionNestError
from .types import LLMResponse, Message

if TYPE_CHECKING:  # 避免循环导入：registry 依赖本模块
    from .registry import ModelSpec

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class LLMProvider(ABC):
    """模型提供方抽象基类。"""

    format_name: str = "abstract"

    def __init__(self, spec: ModelSpec, *, timeout: float = 60.0, max_retries: int = 3) -> None:
        self.spec = spec
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=timeout)

    # ---------------------------------------------------------------- 子类实现
    @abstractmethod
    def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """发送对话，返回归一化结果。"""
        raise NotImplementedError

    # ---------------------------------------------------------------- 公共能力
    def _api_key(self) -> str:
        key = os.environ.get(self.spec.api_key_env, "").strip()
        if not key:
            raise MissingApiKeyError(
                f"模型 {self.spec.name!r} 需要环境变量 {self.spec.api_key_env}（见 .env.example）"
            )
        return key

    def _post_json(self, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        """带指数退避重试的 JSON POST（仅对 429/5xx 与网络错误重试）。"""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.post(url, headers=headers, json=payload)
                if response.status_code in RETRY_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}: {response.text[:200]}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:  # pragma: no cover - 网络分支
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 8))
        raise MotionNestError(f"模型 {self.spec.name!r} 调用失败：{last_error}") from last_error

    def healthcheck(self) -> tuple[bool, str]:
        """最小调用探测。返回 (是否可用, 说明)。"""
        try:
            response = self.chat(
                [Message(role="user", content="ping：请只回复 ok")],
                temperature=0.0,
                max_tokens=16,
            )
            return True, f"{self.spec.model_id} 可用（{response.latency_ms}ms）"
        except Exception as exc:
            return False, f"{self.spec.model_id} 不可用：{exc}"

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> LLMProvider:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
