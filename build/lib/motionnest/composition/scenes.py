"""场景树纯函数：确定性模板合成 + 定点补丁。

- template_composition：不调用任何模型，把分镜转成可渲染场景树
  （离线兜底与测试基线）；
- apply_patch：只改目标图层的目标属性，无关场景原样返回——
  "单属性改动不重建无关场景"的工程实现。
"""

from __future__ import annotations

from ..core.schemas import Composition, Layer, RevisionPatch, Scene, Storyboard

# 触及这些属性的改动视为"改数"，必须重算并再过数据门
DATA_BEARING_PROPS = {"value", "series", "unit", "total", "baseline"}


def template_composition(
    storyboard: Storyboard,
    *,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
) -> Composition:
    """确定性模板：分镜 → 场景树（无 LLM 参与）。"""
    scenes: list[Scene] = []
    for index, shot in enumerate(storyboard.normalized_shots(), start=1):
        layers: list[Layer] = []
        if shot.scene_type in ("chart", "title", "outro", "text"):
            layers.append(
                Layer(
                    id=f"layer-{index:02d}-chart",
                    type="chart" if shot.scene_type == "chart" else "text",
                    props={
                        "chart_type": shot.visual.get("chart_type", "bar"),
                        "series": shot.visual.get("series", []),
                        "title": shot.on_screen_text or shot.assertion,
                        "highlight": shot.visual.get("highlight", []),
                    },
                    animation={"enter": "draw", "duration_ms": min(800, shot.duration_ms // 2)},
                    evidence_ids=list(shot.evidence_ids),
                )
            )
        if shot.on_screen_text and shot.scene_type == "chart":
            layers.append(
                Layer(
                    id=f"layer-{index:02d}-caption",
                    type="text",
                    props={"text": shot.on_screen_text, "size": 36, "x": 80, "y": 120},
                    animation={"enter": "fade", "duration_ms": 400},
                )
            )
        scenes.append(
            Scene(
                id=f"scene-{index:02d}",
                shot_id=shot.id,
                duration_ms=shot.duration_ms,
                layers=layers,
            )
        )
    return Composition(fps=fps, width=width, height=height, scenes=scenes)


def apply_patch(composition: Composition, patch: RevisionPatch) -> tuple[Composition, bool]:
    """应用定点补丁，返回 (新 Composition, 是否触及数据层)。"""
    updated = composition.model_copy(deep=True)
    layer = updated.find_layer(patch.scene_id, patch.layer_id)
    touches_data = patch.needs_recompute or any(key in DATA_BEARING_PROPS for key in patch.changes)
    layer.props.update(patch.changes)
    return updated, touches_data


def scene_layer_ids(scene: Scene) -> list[str]:
    return [layer.id for layer in scene.layers]
