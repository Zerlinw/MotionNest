"""宣传片管线数据结构：文档解析产物 → 要点 → 分镜。

设计约束：
- 所有字段可 JSON 序列化（工件即项目文件，见 core/project.py）；
- 时长字段一律毫秒 int，合计精确 30000（见 storyboard.py 的骨架）；
- degraded 列表记录"哪一环降级了"，最终写入审计清单。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PromoDocSection(BaseModel):
    """文档中的一个内容块。"""

    kind: str = Field(description="heading | paragraph | list | json")
    text: str


class PromoImage(BaseModel):
    """一张归一化后的图片素材（已复制到项目 assets/）。"""

    name: str = Field(description="assets/ 下的文件名")
    source: str = Field(description="来源：文档名 / asset-folder / generated")
    caption: str = ""


class PromoTable(BaseModel):
    """一张表（CSV/JSON）的摘要 + 少量样例行，供蒸馏与图表使用。"""

    source: str
    columns: list[str] = Field(default_factory=list)
    rows: int = 0
    summary: str = ""
    sample_records: list[dict] = Field(default_factory=list, description="最多 8 行样例")


class PromoDoc(BaseModel):
    """文档解析阶段的产出：全部文档蒸馏后的统一中间表示。"""

    title: str = ""
    sections: list[PromoDocSection] = Field(default_factory=list)
    images: list[PromoImage] = Field(default_factory=list)
    tables: list[PromoTable] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list, description="文档文件名清单")
    degraded: list[str] = Field(default_factory=list, description="解析/降级说明")


class PromoBrief(BaseModel):
    """要点蒸馏产出：宣传片叙事简报。"""

    product_name: str
    tagline: str = ""
    audience: str = ""
    selling_points: list[str] = Field(default_factory=list, description="2-5 条")
    proof_numbers: list[str] = Field(default_factory=list, description="带来源的佐证数字")
    cta: str = ""
    tone: str = "专业、克制"
    palette: list[str] = Field(default_factory=list, description="主色倾向，缺省内置企业蓝")
    source: str = Field(default="model", description="model | template（降级标记）")


class PromoShot(BaseModel):
    """一个镜头：节拍 + 确定性时长 + 文案 + 视觉规格。"""

    id: str = Field(pattern=r"^shot-\d+$")
    beat: str = Field(description="hook | reveal | selling_point | proof | cta")
    duration_ms: int = Field(gt=0)
    on_screen_text: str
    narration: str = ""
    visual: dict = Field(default_factory=dict)
    copy_source: str = Field(default="model", description="model | template")


class PromoStoryboard(BaseModel):
    """分镜脚本：Σduration_ms 必须精确等于 TOTAL_DURATION_MS。"""

    title: str
    total_duration_ms: int
    shots: list[PromoShot] = Field(min_length=1)

    def assert_duration(self) -> None:
        """硬不变量：总时长必须精确 30000ms，否则拒绝渲染。"""
        total = sum(shot.duration_ms for shot in self.shots)
        if total != self.total_duration_ms:
            raise ValueError(f"分镜总时长 {total} != {self.total_duration_ms}")
