"""数据解读 Agent（低成本档）。

职责：把数据摘要 + 数据字典 + 用户 brief 转成结构化洞察：
关键指标（带证据 ID）、多个叙事候选（每个声明忽略了什么、风险是什么）。
硬规则：不得臆测数据；每个结论必须能回到一个证据 ID。
"""

from __future__ import annotations

import json

from ..core.schemas import (
    DataDictionary,
    DataInsight,
    DataSummary,
    KeyMetric,
    NarrativeCandidate,
)
from ..llm.router import RoutedResponse
from .base import BaseAgent


class DataInterpreter(BaseAgent):
    name = "data-interpreter"
    task = "data_interpretation"
    temperature = 0.2

    def run(
        self,
        summary: DataSummary,
        dictionary: DataDictionary,
        brief: dict,
    ) -> tuple[DataInsight, RoutedResponse]:
        prompt = self.render_user(
            brief_json=json.dumps(brief, ensure_ascii=False, indent=2),
            summary_json=json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2),
            dictionary_json=json.dumps(dictionary.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )
        return self.complete_json(prompt, DataInsight)


def template_insight(summary: DataSummary, dictionary: DataDictionary) -> DataInsight:
    """确定性模板洞察（--offline 用，不调用模型）。

    只做纯机械汇总：数值列 → 关键指标；两个固定候选方向（结构/变化）。
    用于离线跑通链路与测试基线，不构成叙事建议。
    """
    numeric = [c for c in summary.columns if c.dtype == "number"]
    metrics = [
        KeyMetric(
            name=column.name,
            display_value=f"{column.min:g} ~ {column.max:g}" if column.min is not None else "-",
            delta=None,
            evidence_id=f"metric:{column.name}",
            risk=f"{column.nulls} 个空值" if column.nulls else None,
        )
        for column in numeric
    ]
    primary = numeric[0].name if numeric else "数据"
    candidates = [
        NarrativeCandidate(
            id="cand-1",
            title=f"{primary} 的结构分布",
            thesis=f"以 {primary} 为主线展示数据结构",
            audience="general",
            key_numbers=[m.display_value for m in metrics[:3]],
            evidence_ids=[m.evidence_id for m in metrics[:3]],
            ignored_info=["未展开的维度与细分切片"],
            risks=["模板产出，需人工确认叙事"],
        ),
        NarrativeCandidate(
            id="cand-2",
            title=f"{primary} 的变化趋势",
            thesis=f"以 {primary} 的变化为主线展示趋势",
            audience="general",
            key_numbers=[m.display_value for m in metrics[:3]],
            evidence_ids=[m.evidence_id for m in metrics[:3]],
            ignored_info=["结构性归因与外部因素"],
            risks=["模板产出，需人工确认叙事"],
        ),
    ]
    return DataInsight(
        summary=f"离线模板：{summary.rows} 行 × {len(summary.columns)} 列，数值列 {len(numeric)} 个",
        metrics=metrics,
        candidates=candidates,
        data_quality_notes=["该洞察由确定性模板生成，未经模型解读"],
    )
