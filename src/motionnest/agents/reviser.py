"""动画改稿 Agent（低成本档）。

职责：接收评论（含定位到的元素/数据点 ID），产出**定点补丁**：
只改一个图层的几个属性，并判断是否触及数据层（触及则必须重算再过门禁）。
"""

from __future__ import annotations

import json

from ..core.schemas import Composition, RevisionPatch
from ..llm.router import RoutedResponse
from .base import BaseAgent


class Reviser(BaseAgent):
    name = "reviser"
    task = "animation_revision"
    temperature = 0.2

    def run(
        self,
        comment_text: str,
        composition: Composition,
        *,
        scene_id: str,
        layer_id: str,
    ) -> tuple[RevisionPatch, RoutedResponse]:
        scene = composition.find_scene(scene_id)
        layer = composition.find_layer(scene_id, layer_id)
        prompt = self.render_user(
            comment_text=comment_text,
            scene_json=json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2),
            layer_json=json.dumps(layer.model_dump(mode="json"), ensure_ascii=False, indent=2),
            scene_id=scene_id,
            layer_id=layer_id,
        )
        return self.complete_json(prompt, RevisionPatch)
