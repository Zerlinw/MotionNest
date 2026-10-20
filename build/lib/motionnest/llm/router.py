"""TaskRouter：任务 → 档位 → 模型 的路由与调用入口。

这是业务层与模型层之间唯一的一道门：
- agents/ 只调用 router.complete(task, messages)，不 import 任何 Provider；
- 路由规则集中在 config/router.yaml，改规则不改代码；
- 强模型缺失时按 fallback_tiers 降级；降级产出自动标记 requires_human_signoff；
- 规则允许人工兜底（human_review: true）且无任何可用模型时，抛出
  HumanReviewRequired，把任务交回给人，而不是静默失败。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..exceptions import (
    ConfigError,
    HumanReviewRequired,
    ModelUnavailableError,
    UnknownTaskError,
)
from .registry import ModelRegistry
from .types import Message, ModelTier


@dataclass(frozen=True, slots=True)
class RouteRule:
    """一个任务的路由规则（来自 router.yaml）。"""

    task: str
    preferred_tier: ModelTier
    candidates: tuple[str, ...]                 # 按优先级尝试的逻辑模型名
    fallback_tiers: tuple[ModelTier, ...] = ()  # 首选不可用时的档位回退顺序
    human_review: bool = False                  # 产出是否必须人工签发
    description: str = ""

    @classmethod
    def from_dict(cls, task: str, data: dict[str, Any]) -> RouteRule:
        try:
            preferred = ModelTier(str(data["preferred_tier"]).lower())
            candidates = tuple(str(c) for c in data.get("candidates", []))
            fallback = tuple(ModelTier(str(t).lower()) for t in data.get("fallback_tiers", []))
        except (KeyError, ValueError) as exc:
            raise ConfigError(f"router.yaml 中任务 {task!r} 规则非法：{exc}") from exc
        if not candidates:
            raise ConfigError(f"router.yaml 中任务 {task!r} 未声明 candidates")
        return cls(
            task=task,
            preferred_tier=preferred,
            candidates=candidates,
            fallback_tiers=fallback,
            human_review=bool(data.get("human_review", False)),
            description=str(data.get("description", "")),
        )


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """一次路由决策的结果（不含调用）。"""

    task: str
    model: str
    tier: ModelTier
    degraded: bool          # True 表示未落在首选档位（降级产出）
    rule: RouteRule


@dataclass(frozen=True, slots=True)
class RoutedResponse:
    """路由 + 调用完成后的归一化返回。"""

    text: str
    task: str
    model_used: str
    tier_used: ModelTier
    degraded: bool = False
    requires_human_signoff: bool = False
    latency_ms: int = 0
    usage: dict[str, int] = field(default_factory=dict)


class TaskRouter:
    """任务路由器：业务层唯一的模型调用入口。"""

    def __init__(
        self,
        registry: ModelRegistry,
        rules: dict[str, RouteRule],
        *,
        allow_human_review: bool = True,
        audit_trail: list[dict[str, Any]] | None = None,
    ) -> None:
        self.registry = registry
        self.rules = dict(rules)
        self.allow_human_review = allow_human_review
        self.audit_trail = audit_trail if audit_trail is not None else []

    # ---------------------------------------------------------------- 加载
    @classmethod
    def from_yaml(
        cls,
        registry: ModelRegistry,
        path: Path,
        **kwargs: Any,
    ) -> TaskRouter:
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"路由规则不存在：{path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        routes = raw.get("routes") or {}
        rules = {task: RouteRule.from_dict(task, data) for task, data in routes.items()}
        if not rules:
            raise ConfigError(f"{path} 中未定义任何路由规则")
        # 校验 candidates 都已在注册表中登记
        for rule in rules.values():
            for name in rule.candidates:
                registry.get_spec(name)  # 不存在会抛 ConfigError
        return cls(registry, rules, **kwargs)

    # ---------------------------------------------------------------- 路由
    def get_rule(self, task: str) -> RouteRule:
        rule = self.rules.get(task)
        if rule is None:
            raise UnknownTaskError(
                f"未登记的路由任务 {task!r}（可用：{', '.join(sorted(self.rules))}）"
            )
        return rule

    def _candidate_order(self, rule: RouteRule) -> list[tuple[str, ModelTier, bool]]:
        """展开候选顺序：首选 candidates → fallback 档位默认模型，去重。"""
        ordered: list[tuple[str, ModelTier, bool]] = []
        seen: set[str] = set()
        for name in rule.candidates:
            spec = self.registry.get_spec(name)
            ordered.append((name, spec.tier_enum, spec.tier_enum is not rule.preferred_tier))
            seen.add(name)
        for tier in rule.fallback_tiers:
            spec = self.registry.default_for_tier(tier)
            if spec is not None and spec.name not in seen:
                ordered.append((spec.name, tier, tier is not rule.preferred_tier))
                seen.add(spec.name)
        return ordered

    def resolve(self, task: str) -> RouteDecision:
        """决定用哪个模型；不做实际调用。"""
        rule = self.get_rule(task)
        for name, tier, degraded in self._candidate_order(rule):
            if self.registry.key_available(name):
                return RouteDecision(task=task, model=name, tier=tier, degraded=degraded, rule=rule)
        # 没有任何候选可用
        if rule.human_review and self.allow_human_review:
            raise HumanReviewRequired(
                task=task,
                reason="所有候选模型均不可用（密钥未配置或调用失败），按规则转人工兜底",
                rule=rule,
            )
        raise ModelUnavailableError(
            f"任务 {task!r} 无可用模型：候选 {list(rule.candidates)} 均缺少密钥"
        )

    # ---------------------------------------------------------------- 调用
    def complete(
        self,
        task: str,
        messages: Sequence[Message],
        **kwargs: Any,
    ) -> RoutedResponse:
        decision = self.resolve(task)
        provider = self.registry.provider(decision.model)
        response = provider.chat(messages, **kwargs)
        result = RoutedResponse(
            text=response.text,
            task=task,
            model_used=decision.model,
            tier_used=decision.tier,
            degraded=decision.degraded,
            requires_human_signoff=decision.rule.human_review,
            latency_ms=response.latency_ms,
            usage=response.usage,
        )
        self.audit_trail.append(
            {
                "task": task,
                "model": result.model_used,
                "tier": result.tier_used.value,
                "degraded": result.degraded,
                "requires_human_signoff": result.requires_human_signoff,
                "latency_ms": result.latency_ms,
                "usage": result.usage,
            }
        )
        return result

    def healthcheck(self) -> dict[str, tuple[bool, str]]:
        """对注册表中所有模型做真实探测。"""
        return {spec.name: self.registry.provider(spec.name).healthcheck() for spec in self.registry.specs()}

    def describe_routes(self) -> list[dict[str, Any]]:
        """供 CLI 打印的路由表。"""
        rows: list[dict[str, Any]] = []
        for task, rule in self.rules.items():
            try:
                decision = self.resolve(task)
                current = f"{decision.model}（{decision.tier.value}{'，降级' if decision.degraded else ''}）"
            except (ModelUnavailableError, HumanReviewRequired) as exc:
                current = f"不可用 → {type(exc).__name__}"
            rows.append(
                {
                    "task": task,
                    "preferred_tier": rule.preferred_tier.value,
                    "candidates": list(rule.candidates),
                    "fallback_tiers": [t.value for t in rule.fallback_tiers],
                    "human_review": rule.human_review,
                    "current": current,
                    "description": rule.description,
                }
            )
        return rows
