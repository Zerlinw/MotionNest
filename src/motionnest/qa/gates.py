"""四道质量门禁：数据门 → 逻辑门 → 视觉门 → 发布门。

每道门输出**可操作的错误**，而不是模糊警告；
任一门禁失败不得自动导出正式版本（发布门强制检查人工签批）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..composition.scenes import DATA_BEARING_PROPS
from ..core.schemas import Composition, DataDictionary, DataInsight, DataSummary
from ..data.validate import check_data

# 需要人工签批才能发布工件（对应 router.yaml 中 human_review: true 的任务）
HUMAN_SIGNOFF_ARTIFACTS = ("reviews/music-plan.json", "reviews/camera-moves.json", "reviews/review-report.json")

MAX_ON_SCREEN_CHARS = 40


@dataclass(slots=True)
class GateResult:
    gate: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def data_gate(summary: DataSummary, dictionary: DataDictionary) -> GateResult:
    errors, warnings = check_data(summary, dictionary)
    return GateResult(gate="data", passed=not errors, errors=errors, warnings=warnings)


def logic_gate(insight: DataInsight, summary: DataSummary) -> GateResult:
    """逻辑门：断言可复算、证据可追溯、结论与证据一致。"""
    errors: list[str] = []
    warnings: list[str] = []

    if len(insight.candidates) < 1:
        errors.append("未生成任何叙事候选")
    for candidate in insight.candidates:
        if not candidate.evidence_ids:
            errors.append(f"叙事候选 {candidate.id!r} 未绑定任何证据 ID")
        if not candidate.key_numbers:
            warnings.append(f"叙事候选 {candidate.id!r} 未列出关键数字")
        if not candidate.ignored_info:
            warnings.append(f"叙事候选 {candidate.id!r} 未声明忽略了哪些信息（叙事非唯一解释）")
    for metric in insight.metrics:
        if not metric.evidence_id:
            errors.append(f"指标 {metric.name!r} 未绑定证据 ID")
        elif metric.evidence_id not in {c.id for c in insight.candidates} and not metric.evidence_id.startswith("metric:"):
            warnings.append(f"指标 {metric.name!r} 的证据 {metric.evidence_id!r} 未对应任何叙事候选")
    if summary.rows < 2:
        errors.append("数据行数不足，无法复算任何断言")
    return GateResult(gate="logic", passed=not errors, errors=errors, warnings=warnings)


def visual_gate(composition: Composition) -> GateResult:
    """视觉门：文字溢出、图层结构、时间码连续性（启发式）。"""
    errors: list[str] = []
    warnings: list[str] = []

    if not composition.scenes:
        errors.append("合成中没有场景")
    seen_layers: set[str] = set()
    cursor = 0
    for scene in composition.scenes:
        if scene.duration_ms <= 0:
            errors.append(f"场景 {scene.id} 时长非正")
        if not scene.layers:
            warnings.append(f"场景 {scene.id} 没有任何图层（可能为空镜）")
        for layer in scene.layers:
            if layer.id in seen_layers:
                errors.append(f"图层 ID 重复：{layer.id}（破坏定点改稿定位）")
            seen_layers.add(layer.id)
            if layer.type == "chart" and "chart_type" not in layer.props:
                errors.append(f"图表图层 {layer.id} 缺少 chart_type")
            text = str(layer.props.get("text") or layer.props.get("title") or "")
            if len(text) > MAX_ON_SCREEN_CHARS:
                warnings.append(
                    f"图层 {layer.id} 文字 {len(text)} 字符超过 {MAX_ON_SCREEN_CHARS}，注意安全区溢出"
                )
        cursor += scene.duration_ms
    if cursor > 600_000:
        warnings.append(f"总时长 {cursor}ms 超过 10 分钟，注意认知负荷")
    return GateResult(gate="visual", passed=not errors, errors=errors, warnings=warnings)


def release_gate(
    approvals: dict[str, str],
    *,
    required: tuple[str, ...] = HUMAN_SIGNOFF_ARTIFACTS,
) -> GateResult:
    """发布门：人工签批齐全 + 数据层改动已复算（由调用方传入 approvals）。"""
    errors: list[str] = []
    missing = [artifact for artifact in required if artifact not in approvals]
    if missing:
        errors.append("缺少人工签批：" + "、".join(missing))
    return GateResult(gate="release", passed=not errors, errors=errors, warnings=[])


def run_all_gates(
    *,
    summary: DataSummary,
    dictionary: DataDictionary,
    insight: DataInsight,
    composition: Composition,
    approvals: dict[str, str],
) -> list[GateResult]:
    return [
        data_gate(summary, dictionary),
        logic_gate(insight, summary),
        visual_gate(composition),
        release_gate(approvals),
    ]


def blocking_errors(results: list[GateResult]) -> list[str]:
    return [f"[{result.gate}] {error}" for result in results for error in result.errors]


def data_bearing_props() -> set[str]:
    return set(DATA_BEARING_PROPS)
