"""分镜脚本 Agent（低成本档）。

职责：把批准的叙事方向转成带时间码的逐镜头脚本。
硬规则：每镜头必须承载一个可复算的数据断言并绑定证据 ID；
时间码连续不重叠；口播文字与画面文字分离。
"""

from __future__ import annotations

import json

from ..core.schemas import DataInsight, Shot, Storyboard
from ..llm.router import RoutedResponse
from .base import BaseAgent


class StoryboardAgent(BaseAgent):
    name = "storyboard-agent"
    task = "storyboard_generation"
    temperature = 0.3

    def run(
        self,
        insight: DataInsight,
        candidate_id: str,
        constraints: dict,
    ) -> tuple[Storyboard, RoutedResponse]:
        candidate = next((c for c in insight.candidates if c.id == candidate_id), None)
        if candidate is None:
            raise ValueError(f"叙事候选不存在：{candidate_id}")
        prompt = self.render_user(
            insight_json=json.dumps(insight.model_dump(mode="json"), ensure_ascii=False, indent=2),
            candidate_json=json.dumps(candidate.model_dump(mode="json"), ensure_ascii=False, indent=2),
            constraints_json=json.dumps(constraints, ensure_ascii=False, indent=2),
        )
        return self.complete_json(prompt, Storyboard)


def template_storyboard(
    insight: DataInsight,
    candidate_id: str,
    *,
    duration_ms: int = 30000,
) -> Storyboard:
    """确定性模板分镜（--offline 用，不调用模型）。

    结构：片名 → 每个关键数字一个图表镜头 → 收尾，
    时长按目标总时长等比分配，时间码连续。
    """
    candidate = next((c for c in insight.candidates if c.id == candidate_id), None)
    if candidate is None:
        raise ValueError(f"叙事候选不存在：{candidate_id}")
    key_numbers = candidate.key_numbers or ["关键结论"]
    shots: list[Shot] = []
    head_ms, tail_ms = 2500, 2500
    body_ms = max(3000 * len(key_numbers), duration_ms - head_ms - tail_ms)
    per_shot = body_ms // len(key_numbers)

    shots.append(
        Shot(
            id="shot-1",
            start_ms=0,
            duration_ms=head_ms,
            scene_type="title",
            assertion=candidate.thesis,
            evidence_ids=list(candidate.evidence_ids),
            visual={},
            on_screen_text=candidate.title[:30],
        )
    )
    cursor = head_ms
    for index, number in enumerate(key_numbers, start=2):
        shots.append(
            Shot(
                id=f"shot-{index}",
                start_ms=cursor,
                duration_ms=per_shot,
                scene_type="chart",
                assertion=f"关键数字：{number}",
                evidence_ids=list(candidate.evidence_ids),
                visual={"chart_type": "bar", "series": [{"name": candidate.title, "value": 0}], "highlight": []},
                narration=f"如图，{number}。",
                on_screen_text=str(number)[:30],
            )
        )
        cursor += per_shot
    shots.append(
        Shot(
            id=f"shot-{len(shots) + 1}",
            start_ms=cursor,
            duration_ms=tail_ms,
            scene_type="outro",
            assertion=candidate.thesis,
            evidence_ids=list(candidate.evidence_ids),
            visual={},
            on_screen_text="数据来源见引用页",
        )
    )
    return Storyboard(title=candidate.title, total_duration_ms=cursor + tail_ms, shots=shots)
