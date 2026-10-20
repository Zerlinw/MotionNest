"""初稿动画生成 Agent（低成本档）。

职责：把分镜脚本转成可序列化的场景树（Composition JSON）。
硬规则：图层类型白名单、动画原语白名单、稳定 ID 规则；
模型只产出"声明式状态"，不直接写最终 HTML/视频。
"""

from __future__ import annotations

import json

from ..core.schemas import Composition, Storyboard
from ..llm.router import RoutedResponse
from .base import BaseAgent


class Animator(BaseAgent):
    name = "animator"
    task = "draft_animation"
    temperature = 0.3

    def run(
        self,
        storyboard: Storyboard,
        *,
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
    ) -> tuple[Composition, RoutedResponse]:
        prompt = self.render_user(
            storyboard_json=json.dumps(storyboard.model_dump(mode="json"), ensure_ascii=False, indent=2),
            fps=fps,
            width=width,
            height=height,
        )
        return self.complete_json(prompt, Composition)
