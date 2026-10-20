"""最终成片校对 Agent（强模型档 + 人工兜底）。

职责：在导出前对整片做终审——数字一致性、节奏、披露完整性，
结合四道门禁结果给出 blocking/warning/suggestion 三级问题单。
passed = 无 blocking 问题；报告始终需要人工签发。
"""

from __future__ import annotations

import json

from ..core.schemas import Composition, DataInsight, ReviewReport
from ..llm.router import RoutedResponse
from ..qa.gates import GateResult
from .base import BaseAgent


class FinalReviewer(BaseAgent):
    name = "final-reviewer"
    task = "final_review"
    temperature = 0.2

    def run(
        self,
        composition: Composition,
        insight: DataInsight,
        gate_results: list[GateResult],
    ) -> tuple[ReviewReport, RoutedResponse]:
        gate_summary = {result.gate: result.passed for result in gate_results}
        prompt = self.render_user(
            insight_json=json.dumps(insight.model_dump(mode="json"), ensure_ascii=False, indent=2),
            composition_json=json.dumps(composition.model_dump(mode="json"), ensure_ascii=False, indent=2),
            gate_summary_json=json.dumps(gate_summary, ensure_ascii=False),
        )
        report, response = self.complete_json(prompt, ReviewReport)
        report.gates_summary = gate_summary or report.gates_summary
        report.signoff_required = True
        return report, response
