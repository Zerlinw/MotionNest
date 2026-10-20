"""模型抽象层：Provider（双接口格式）+ Registry（注册表）+ Router（任务路由）。"""

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .registry import ModelRegistry, ModelSpec
from .router import RouteDecision, RoutedResponse, RouteRule, TaskRouter
from .types import LLMResponse, Message, ModelTier, ProviderFormat

__all__ = [
    "AnthropicProvider",
    "LLMProvider",
    "LLMResponse",
    "Message",
    "ModelRegistry",
    "ModelSpec",
    "ModelTier",
    "OpenAIProvider",
    "ProviderFormat",
    "RouteDecision",
    "RouteRule",
    "RoutedResponse",
    "TaskRouter",
]
