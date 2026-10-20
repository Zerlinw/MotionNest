"""配乐审美 Agent（强模型档 + 人工兜底）。

职责：把节奏单/能量曲线转成结构化配乐规划（tempo、段落能量、
音效触发点、淡入淡出、可选 ABC 文本谱）。
认知边界：**模型没有听觉**。它只规划节拍与能量的结构，
不对"好不好听"下结论；最终听感必须人工确认（requires_human_listening）。
"""

from __future__ import annotations

import json

from ..core.schemas import MusicPlan, Storyboard
from ..llm.router import RoutedResponse
from .base import BaseAgent


class MusicDirector(BaseAgent):
    name = "music-director"
    task = "music_aesthetics"
    temperature = 0.4

    def run(self, storyboard: Storyboard, brief: dict) -> tuple[MusicPlan, RoutedResponse]:
        rhythm = [
            {
                "shot_id": shot.id,
                "start_ms": shot.start_ms,
                "duration_ms": shot.duration_ms,
                "scene_type": shot.scene_type,
                "assertion": shot.assertion,
            }
            for shot in storyboard.normalized_shots()
        ]
        prompt = self.render_user(
            brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
            rhythm_json=json.dumps(rhythm, ensure_ascii=False, indent=2),
        )
        return self.complete_json(prompt, MusicPlan)
