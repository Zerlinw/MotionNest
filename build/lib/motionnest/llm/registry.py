"""ModelRegistry：从 config/models.yaml 加载模型声明并实例化 Provider。

新增一个模型 = 在 YAML 里加一段声明，注册表自动完成：
逻辑名 → ModelSpec → 对应格式的 LLMProvider（进程内缓存复用连接）。
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..exceptions import ConfigError
from .anthropic_provider import AnthropicProvider
from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .types import ModelTier, ProviderFormat


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """一个模型的静态声明（来自 models.yaml 的一段条目）。"""

    name: str                 # 逻辑名，路由规则只认这个名字
    model_id: str             # 提供方侧真实模型 ID
    provider_format: str      # openai | anthropic
    base_url: str
    api_key_env: str
    tier: str                 # low | strong
    description: str = ""
    max_output_tokens: int = 8192

    @property
    def tier_enum(self) -> ModelTier:
        return ModelTier(self.tier)

    @property
    def format_enum(self) -> ProviderFormat:
        return ProviderFormat(self.provider_format)


_PROVIDER_MAP = {
    ProviderFormat.OPENAI: OpenAIProvider,
    ProviderFormat.ANTHROPIC: AnthropicProvider,
}


class ModelRegistry:
    """模型注册表：声明 → Provider 实例的工厂与缓存。"""

    def __init__(self, specs: Iterable[ModelSpec]) -> None:
        self._specs: dict[str, ModelSpec] = {}
        for spec in specs:
            if spec.name in self._specs:
                raise ConfigError(f"models.yaml 中模型逻辑名重复：{spec.name}")
            self._specs[spec.name] = spec
        if not self._specs:
            raise ConfigError("models.yaml 中未定义任何模型")
        self._providers: dict[str, LLMProvider] = {}

    # ---------------------------------------------------------------- 加载
    @classmethod
    def from_yaml(cls, path: Path) -> ModelRegistry:
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"模型注册表不存在：{path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = raw.get("models") or []
        specs: list[ModelSpec] = []
        for entry in entries:
            try:
                specs.append(
                    ModelSpec(
                        name=str(entry["name"]),
                        model_id=str(entry["model_id"]),
                        provider_format=str(entry["provider_format"]).lower(),
                        base_url=str(entry["base_url"]).rstrip("/"),
                        api_key_env=str(entry["api_key_env"]),
                        tier=str(entry["tier"]).lower(),
                        description=str(entry.get("description", "")),
                        max_output_tokens=int(entry.get("max_output_tokens", 8192)),
                    )
                )
            except KeyError as exc:
                raise ConfigError(f"models.yaml 条目缺少必填字段 {exc}：{entry}") from exc
        return cls(specs)

    # ---------------------------------------------------------------- 查询
    def get_spec(self, name: str) -> ModelSpec:
        try:
            return self._specs[name]
        except KeyError as exc:
            raise ConfigError(f"未注册的模型逻辑名：{name!r}（可用：{', '.join(self._specs)}）") from exc

    def provider(self, name: str) -> LLMProvider:
        """按逻辑名取得 Provider 实例（首次创建，之后复用）。"""
        if name not in self._providers:
            spec = self.get_spec(name)
            try:
                provider_cls = _PROVIDER_MAP[spec.format_enum]
            except KeyError as exc:
                raise ConfigError(
                    f"模型 {name!r} 的 provider_format={spec.provider_format!r} 不受支持"
                    f"（可选：{[f.value for f in ProviderFormat]}）"
                ) from exc
            self._providers[name] = provider_cls(spec)
        return self._providers[name]

    def specs(self) -> list[ModelSpec]:
        return list(self._specs.values())

    def specs_for_tier(self, tier: ModelTier | str) -> list[ModelSpec]:
        wanted = ModelTier(tier)
        return [s for s in self._specs.values() if s.tier_enum is wanted]

    def default_for_tier(self, tier: ModelTier | str) -> ModelSpec | None:
        specs = self.specs_for_tier(tier)
        return specs[0] if specs else None

    def key_available(self, name: str) -> bool:
        spec = self.get_spec(name)
        return bool(os.environ.get(spec.api_key_env, "").strip())

    def close_all(self) -> None:
        for provider in self._providers.values():
            provider.close()
        self._providers.clear()
