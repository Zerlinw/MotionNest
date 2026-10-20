"""全链路 Pydantic 数据模型。

设计约束：LLM 的一切产出都必须先落入这些 schema 才能进入管线，
schema 是"模型提议区"与"确定性执行区"之间的闸门。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ================================================================ 数据层
class ColumnSpec(BaseModel):
    """数据字典中的一列。"""

    name: str
    dtype: str = Field(description="number | date | text | category")
    unit: str | None = None
    description: str = ""
    required: bool = True


class DataDictionary(BaseModel):
    """数据字典：口径、单位、来源的一等公民。"""

    columns: list[ColumnSpec]
    timezone: str = "local"
    source: str = Field(default="", description="来源说明（URL/系统/负责人）")
    metric_definitions: dict[str, str] = Field(default_factory=dict)


class ColumnSummary(BaseModel):
    name: str
    dtype: str
    nulls: int
    unique: int
    min: float | None = None
    max: float | None = None
    sample: list[str] = Field(default_factory=list)


class DataSummary(BaseModel):
    """数据摘要：给模型看的"目录"，而不是整表原文。"""

    rows: int
    columns: list[ColumnSummary]
    date_range: str = ""


class KeyMetric(BaseModel):
    name: str
    display_value: str = Field(description="展示值（含单位的字符串）")
    delta: str | None = None
    evidence_id: str = Field(description="必须绑定一个可复算的数据断言 ID")
    risk: str | None = None


class NarrativeCandidate(BaseModel):
    """一个叙事方向：论点 + 证据 + 明确声明忽略了什么。"""

    id: str
    title: str
    thesis: str
    audience: str
    key_numbers: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    ignored_info: list[str] = Field(default_factory=list, description="本方向刻意忽略的信息")
    risks: list[str] = Field(default_factory=list)


class DataInsight(BaseModel):
    """数据解读 Agent 的产出。"""

    summary: str
    metrics: list[KeyMetric] = Field(default_factory=list)
    candidates: list[NarrativeCandidate] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)


# ================================================================ 脚本层
class Shot(BaseModel):
    """一个镜头：时间码 + 数据断言 + 证据绑定 + 画面规格。"""

    id: str = Field(pattern=r"^shot-\d+$")
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    scene_type: str = Field(description="chart | text | transition | title | outro")
    assertion: str = Field(description="本镜头承载的数据断言（可复算）")
    evidence_ids: list[str] = Field(default_factory=list)
    visual: dict = Field(default_factory=dict, description="图表类型/系列/高亮等")
    narration: str | None = None
    on_screen_text: str | None = None


class Storyboard(BaseModel):
    """分镜脚本 Agent 的产出。"""

    title: str
    total_duration_ms: int = Field(gt=0)
    shots: list[Shot] = Field(min_length=1)

    def normalized_shots(self) -> list[Shot]:
        """按 start_ms 排序并补齐 end（供时间轴与门禁使用）。"""
        return sorted(self.shots, key=lambda s: s.start_ms)


# ================================================================ 合成层
class Layer(BaseModel):
    """场景内图层：稳定 ID 是"指着画面改"的定位锚点。"""

    id: str
    type: str = Field(description="chart | text | shape | image")
    props: dict = Field(default_factory=dict)
    animation: dict = Field(default_factory=dict, description="enter/exit 动画原语")
    evidence_ids: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    id: str = Field(pattern=r"^scene-\d+$")
    shot_id: str
    duration_ms: int = Field(gt=0)
    layers: list[Layer] = Field(default_factory=list)
    camera: dict | None = None


class Composition(BaseModel):
    """可序列化的整片合成（JSON 即工程文件）。"""

    fps: int = Field(default=30, ge=1, le=120)
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    background: str = Field(default="", description="画面背景色，空 = 渲染默认 #0b0e14")
    scenes: list[Scene] = Field(default_factory=list)

    def find_scene(self, scene_id: str) -> Scene:
        for scene in self.scenes:
            if scene.id == scene_id:
                return scene
        raise KeyError(scene_id)

    def find_layer(self, scene_id: str, layer_id: str) -> Layer:
        for layer in self.find_scene(scene_id).layers:
            if layer.id == layer_id:
                return layer
        raise KeyError(layer_id)


# ================================================================ 声音层
class MusicSection(BaseModel):
    label: str
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    energy: float = Field(ge=0.0, le=1.0)


class SfxEvent(BaseModel):
    at_ms: int = Field(ge=0)
    kind: str
    note: str = ""


class MusicPlan(BaseModel):
    """配乐规划：节拍/能量/触发点的结构化中间表示（模型无听觉，终审靠人）。"""

    tempo_bpm: int = Field(ge=40, le=240)
    sections: list[MusicSection] = Field(default_factory=list)
    sfx_events: list[SfxEvent] = Field(default_factory=list)
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    abc_score: str | None = Field(default=None, description="ABC 文本谱（可选交换格式）")
    requires_human_listening: bool = True


# ================================================================ 运镜层
class CameraKeyframe(BaseModel):
    t_ms: int = Field(ge=0)
    position: list[float] = Field(min_length=3, max_length=3)
    target: list[float] = Field(min_length=3, max_length=3)
    fov: float = Field(default=50.0, gt=0, lt=120)


class CameraMove(BaseModel):
    """一次三维运镜设计。"""

    shot_id: str
    move_type: str = Field(description="static | dolly | pan | orbit | crane")
    easing: str = "ease-in-out"
    keyframes: list[CameraKeyframe] = Field(default_factory=list)
    rationale: str = ""
    generated_by: str = Field(default="strong-model", description="strong-model | template | human")


# ================================================================ 审片层
class ReviewIssue(BaseModel):
    severity: str = Field(description="blocking | warning | suggestion")
    target: str = Field(description="scene/layer/断言 ID")
    message: str
    suggestion: str = ""


class ReviewReport(BaseModel):
    """最终成片校对报告。"""

    passed: bool = False
    issues: list[ReviewIssue] = Field(default_factory=list)
    gates_summary: dict[str, bool] = Field(default_factory=dict)
    signoff_required: bool = True
    reviewer: str = ""


# ================================================================ 改稿层
class RevisionPatch(BaseModel):
    """一次定点修改：只动一个图层的一个/几个属性。"""

    scene_id: str
    layer_id: str
    changes: dict = Field(description="prop -> 新值")
    reason: str
    evidence_check: str | None = None
    needs_recompute: bool = Field(
        default=False,
        description="改动是否触及数据层（值/单位/口径）——是则必须重算并再过数据门",
    )


# ============================================================ 工程元信息
class ProjectManifest(BaseModel):
    """project.json：项目身份、版本与审批状态。"""

    name: str
    schema_version: str = "0.1.0"
    created_at: str
    template: str | None = None
    current_version: str | None = None
    approvals: dict[str, str] = Field(default_factory=dict, description="artifact -> 审批人/时间")
