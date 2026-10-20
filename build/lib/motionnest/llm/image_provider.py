"""OpenAI 兼容生图提供方（/images/generations）。

用途：宣传片分镜中"既无用户素材、又无 pptx 内嵌图"的镜头补图。
边界：调用失败抛 MotionNestError，由 compose 决定降级为 SVG/CSS 兜底，
不阻塞管线；密钥由调用方注入（设置页 → bridge → 本类），不读环境变量。
"""

from __future__ import annotations

import base64
import time

import httpx

from ..exceptions import MotionNestError

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class ImageProvider:
    """最小可用的 OpenAI 兼容生图客户端。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=timeout)

    def generate(self, prompt: str, *, size: str = "1792x1024") -> bytes:
        """生成图片，返回 PNG 字节。失败抛 MotionNestError。"""
        if not self.api_key:
            raise MotionNestError("生图模型未配置 API Key")
        url = f"{self.base_url}/images/generations"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }
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
                data = response.json().get("data") or []
                if not data or "b64_json" not in data[0]:
                    raise MotionNestError(f"生图响应缺少 b64_json：{str(response.json())[:200]}")
                return base64.b64decode(data[0]["b64_json"])
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 8))
        raise MotionNestError(f"生图调用失败：{last_error}") from last_error

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ImageProvider:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
