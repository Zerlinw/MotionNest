"""Agent 基类：业务逻辑与模型层的唯一连接点。

所有 Agent 只依赖 TaskRouter（构造函数注入），
不 import 任何 Provider——这就是"切换模型不改业务代码"的落点。
"""

from __future__ import annotations

from string import Template
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ..exceptions import SchemaValidationError
from ..llm.router import RoutedResponse, TaskRouter
from ..llm.types import Message
from ..utils.json import parse_json_loose
from . import prompts

T = TypeVar("T", bound=BaseModel)


class BaseAgent:
    """Agent 底座：任务名 + 提示词仓库 + JSON 输出契约。"""

    name: str = "agent"
    task: str = ""                # 对应 router.yaml 中的任务键
    temperature: float = 0.2

    def __init__(
        self,
        router: TaskRouter,
        *,
        system_prompt: str | None = None,
        user_prompt_template: str | None = None,
    ) -> None:
        self.router = router
        self._system_prompt = system_prompt
        self._user_prompt_template = user_prompt_template

    # ---------------------------------------------------------------- 提示词
    @property
    def system_prompt(self) -> str:
        """系统提示词：实例覆盖 > prompts 覆盖 > 默认值。"""
        return self._system_prompt or prompts.get(self.task, "system")

    def render_user(self, **fields: object) -> str:
        """渲染用户提示词模板（$name 占位符）。"""
        if self._user_prompt_template is not None:
            return Template(self._user_prompt_template).safe_substitute(**fields)
        return prompts.render(self.task, "user", **fields)

    # ---------------------------------------------------------------- 调用
    def complete(self, prompt: str, **kwargs: object) -> RoutedResponse:
        messages = [
            Message(role="system", content=self.system_prompt),
            Message(role="user", content=prompt),
        ]
        return self.router.complete(
            self.task, messages, temperature=kwargs.pop("temperature", self.temperature), **kwargs
        )

    def complete_json(
        self,
        prompt: str,
        schema: type[T],
        *,
        max_retries: int = 2,
    ) -> tuple[T, RoutedResponse]:
        """调用模型并解析为 schema；失败时把校验错误回喂重试。"""
        last_error = ""
        response: RoutedResponse | None = None
        for attempt in range(max_retries + 1):
            final_prompt = prompt
            if attempt > 0:
                final_prompt = (
                    f"{prompt}\n\n【第 {attempt} 次重试】上一次输出未通过结构校验，"
                    f"请只输出修正后的 JSON，不要任何解释：\n{last_error}"
                )
            response = self.complete(final_prompt)
            try:
                return schema.model_validate(parse_json_loose(response.text)), response
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)
        raise SchemaValidationError(
            f"{self.name} 的输出连续 {max_retries + 1} 次未通过 schema 校验：{last_error}"
        )
