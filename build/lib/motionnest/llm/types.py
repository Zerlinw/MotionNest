"""模型层公共数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

Role = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class Message:
    """与提供方无关的对话消息。"""

    role: Role
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class LLMResponse:
    """一次模型调用的归一化返回。"""

    text: str
    model: str
    provider_format: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    raw: dict[str, Any] | None = None


class ModelTier(str, Enum):
    """模型档位。"""

    LOW = "low"      # 低成本档：高频、结构化、可校验
    STRONG = "strong"  # 强模型档：审美、复杂推理、终审


class ProviderFormat(str, Enum):
    """接口格式。"""

    OPENAI = "openai"        # POST {base_url}/chat/completions
    ANTHROPIC = "anthropic"  # POST {base_url}/v1/messages
