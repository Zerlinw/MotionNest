"""三维运镜设计 Agent（强模型档 + 人工兜底）。

分工策略：
- 简单运镜（static / 轻微 dolly）走**确定性模板**，不消耗模型调用；
- 复杂运镜（orbit / crane / 多关键帧）才路由到强模型档，
  产出需人工签发（camera-moves.json）。
"""

from __future__ import annotations

import json

from ..core.schemas import CameraMove, Scene
from ..llm.router import RoutedResponse
from .base import BaseAgent

SIMPLE_MOVES = {"static", "dolly"}


class CameraDesigner(BaseAgent):
    name = "camera-designer"
    task = "camera_3d_design"
    temperature = 0.4

    def run(self, scene: Scene, brief: dict) -> tuple[CameraMove, RoutedResponse | None]:
        """复杂运镜 → 强模型；简单运镜 → 确定性模板（不调用模型）。"""
        if brief.get("complexity", "complex") == "simple":
            return self._template_move(scene, brief), None

        prompt = self.render_user(
            scene_json=json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2),
            brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
            shot_id=scene.shot_id,
        )
        return self.complete_json(prompt, CameraMove)

    @staticmethod
    def _template_move(scene: Scene, brief: dict) -> CameraMove:
        """确定性模板：简单运镜不花模型调用。"""
        return CameraMove(
            shot_id=scene.shot_id,
            move_type="static" if scene.duration_ms < 3000 else "dolly",
            easing="ease-in-out",
            keyframes=[
                {
                    "t_ms": 0,
                    "position": [0.0, 0.0, 10.0],
                    "target": [0.0, 0.0, 0.0],
                    "fov": 50.0,
                },
                {
                    "t_ms": scene.duration_ms,
                    "position": [0.0, 0.0, 9.2],
                    "target": [0.0, 0.0, 0.0],
                    "fov": 50.0,
                },
            ],
            rationale="简单运镜：确定性模板，未启用强模型",
            generated_by="template",
        )
