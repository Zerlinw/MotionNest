"""阶段 4 · 画面合成（素材匹配确定性，无模型参与匹配决策）。

输入：PromoStoryboard + PromoDoc + PromoBrief + 可选生图回调。
输出：Composition（场景树，Layer.type 支持 image）+ 素材使用清单（供审计）。

视觉优先级（每个镜头）：用户/pptx 素材（关键词匹配）> AI 生图回调 > SVG/CSS 兜底。
配色/字体/背景全局统一（brief.palette + 固定深色底），保证 30 秒连贯性。
"""

from __future__ import annotations

from collections.abc import Callable

from ..core.schemas import Composition, Layer, Scene
from .schemas import PromoBrief, PromoDoc, PromoShot, PromoStoryboard

WIDTH, HEIGHT, FPS = 1920, 1080, 30
BACKGROUND = "#0B0E14"
TEXT_COLOR = "#F5F7FA"
DIM_COLOR = "#CDD6E4"

ImageGenerator = Callable[[str, str], "str | None"]  # (shot_id, prompt) -> assets/ 下的文件名或 None


def compose(
    storyboard: PromoStoryboard,
    doc: PromoDoc,
    brief: PromoBrief,
    *,
    generate_image: ImageGenerator | None = None,
    fps: int = FPS,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> tuple[Composition, dict[str, str]]:
    """分镜 → 场景树。返回 (composition, shot_id -> 素材来源说明)。"""
    palette = brief.palette or ["#4A88C7"]
    accent = palette[0]
    usage: dict[str, str] = {}
    used_images: set[str] = set()
    scenes: list[Scene] = []

    for index, shot in enumerate(storyboard.shots, start=1):
        image = _resolve_image(shot, doc, used_images, generate_image, usage, brief)
        layers: list[Layer] = []
        if shot.beat == "hook":
            layers += _hook_layers(index, shot, accent, image)
        elif shot.beat == "reveal":
            layers += _reveal_layers(index, shot, accent, image)
        elif shot.beat == "selling_point":
            layers += _point_layers(index, shot, accent, image)
        elif shot.beat == "proof":
            layers += _proof_layers(index, shot, accent, doc)
        else:  # cta
            layers += _cta_layers(index, shot, accent)
        layers.append(_brand_layer(index, brief.product_name))
        scenes.append(
            Scene(
                id=f"scene-{index:02d}",
                shot_id=shot.id,
                duration_ms=shot.duration_ms,
                layers=layers,
            )
        )

    composition = Composition(
        fps=fps, width=width, height=height, scenes=scenes, background=BACKGROUND
    )
    _assert_unique_layer_ids(composition)
    return composition, usage


# ---------------------------------------------------------------- 各节拍图层
def _hook_layers(index: int, shot: PromoShot, accent: str, image: str | None) -> list[Layer]:
    name, _, tagline = shot.on_screen_text.partition("\n")
    layers = [
        Layer(
            id=f"layer-{index:02d}-title",
            type="text",
            props={
                "text": name or shot.on_screen_text,
                "size": 68,
                "x": 120,
                "y": 400,
                "width": 860,
                "align": "left",
                "color": TEXT_COLOR,
                "caption": False,
            },
            animation={"enter": "slide-up", "duration_ms": _anim_ms(shot)},
        ),
        Layer(
            id=f"layer-{index:02d}-bar",
            type="shape",
            props={"x": 120, "y": 540, "w": 120, "h": 8, "color": accent, "radius": 4},
            animation={"enter": "fade", "duration_ms": 500},
        ),
    ]
    if tagline:
        layers.append(
            Layer(
                id=f"layer-{index:02d}-tagline",
                type="text",
                props={
                    "text": tagline,
                    "size": 34,
                    "x": 120,
                    "y": 580,
                    "width": 860,
                    "align": "left",
                    "color": DIM_COLOR,
                    "caption": False,
                },
                animation={"enter": "fade", "duration_ms": 600},
            )
        )
    if image:
        layers.append(
            Layer(
                id=f"layer-{index:02d}-image",
                type="image",
                props={"src": image, "x": 1040, "y": 200, "w": 760, "h": 680, "fit": "cover", "radius": 20},
                animation={"enter": "scale", "duration_ms": _anim_ms(shot)},
            )
        )
    return layers


def _reveal_layers(index: int, shot: PromoShot, accent: str, image: str | None) -> list[Layer]:
    layers: list[Layer] = []
    if image:
        layers.append(
            Layer(
                id=f"layer-{index:02d}-bg",
                type="image",
                props={"src": image, "x": 0, "y": 0, "w": WIDTH, "h": HEIGHT, "fit": "cover", "radius": 0},
                animation={"enter": "fade", "duration_ms": _anim_ms(shot)},
            )
        )
    layers += [
        Layer(
            id=f"layer-{index:02d}-text",
            type="text",
            props={
                "text": shot.on_screen_text,
                "size": 56,
                "x": 0,
                "y": 760,
                "width": WIDTH,
                "align": "center",
                "color": TEXT_COLOR,
                "caption": True,
            },
            animation={"enter": "slide-up", "duration_ms": _anim_ms(shot)},
        ),
        Layer(
            id=f"layer-{index:02d}-bar",
            type="shape",
            props={"x": WIDTH // 2 - 60, "y": 700, "w": 120, "h": 8, "color": accent, "radius": 4},
            animation={"enter": "fade", "duration_ms": 500},
        ),
    ]
    return layers


def _point_layers(index: int, shot: PromoShot, accent: str, image: str | None) -> list[Layer]:
    layers = [
        Layer(
            id=f"layer-{index:02d}-bar",
            type="shape",
            props={"x": 140, "y": 460, "w": 10, "h": 160, "color": accent, "radius": 5},
            animation={"enter": "fade", "duration_ms": 400},
        ),
        Layer(
            id=f"layer-{index:02d}-text",
            type="text",
            props={
                "text": shot.on_screen_text,
                "size": 52,
                "x": 190,
                "y": 460,
                "width": 1000,
                "align": "left",
                "color": TEXT_COLOR,
                "caption": False,
            },
            animation={"enter": "slide-up", "duration_ms": _anim_ms(shot)},
        ),
    ]
    if image:
        layers.append(
            Layer(
                id=f"layer-{index:02d}-image",
                type="image",
                props={
                    "src": image,
                    "x": 1250,
                    "y": 300,
                    "w": 560,
                    "h": 480,
                    "fit": "cover",
                    "radius": 20,
                },
                animation={"enter": "scale", "duration_ms": _anim_ms(shot)},
            )
        )
    return layers


def _proof_layers(index: int, shot: PromoShot, accent: str, doc: PromoDoc) -> list[Layer]:
    series = _chart_series(doc)
    if series:
        return [
            Layer(
                id=f"layer-{index:02d}-chart",
                type="chart",
                props={"chart_type": "bar", "series": series, "title": shot.on_screen_text[:40]},
                animation={"enter": "draw", "duration_ms": _anim_ms(shot)},
            )
        ]
    lines = [line.strip() for line in shot.on_screen_text.split("·") if line.strip()][:3]
    layers: list[Layer] = []
    for position, line in enumerate(lines):
        layers.append(
            Layer(
                id=f"layer-{index:02d}-num{position}",
                type="text",
                props={
                    "text": line.strip(),
                    "size": 64,
                    "x": 0,
                    "y": 320 + position * 160,
                    "width": WIDTH,
                    "align": "center",
                    "color": accent if position == 0 else TEXT_COLOR,
                    "caption": False,
                },
                animation={"enter": "count-up", "duration_ms": _anim_ms(shot)},
            )
        )
    if not layers:
        layers.append(
            Layer(
                id=f"layer-{index:02d}-text",
                type="text",
                props={
                    "text": shot.on_screen_text,
                    "size": 56,
                    "x": 0,
                    "y": 460,
                    "width": WIDTH,
                    "align": "center",
                    "color": TEXT_COLOR,
                    "caption": False,
                },
                animation={"enter": "fade", "duration_ms": _anim_ms(shot)},
            )
        )
    return layers


def _cta_layers(index: int, shot: PromoShot, accent: str) -> list[Layer]:
    cta, _, product = shot.on_screen_text.partition("\n")
    layers = [
        Layer(
            id=f"layer-{index:02d}-cta",
            type="text",
            props={
                "text": cta or shot.on_screen_text,
                "size": 64,
                "x": 0,
                "y": 420,
                "width": WIDTH,
                "align": "center",
                "color": accent,
                "caption": False,
            },
            animation={"enter": "scale", "duration_ms": _anim_ms(shot)},
        ),
        Layer(
            id=f"layer-{index:02d}-bar",
            type="shape",
            props={"x": WIDTH // 2 - 60, "y": 560, "w": 120, "h": 8, "color": accent, "radius": 4},
            animation={"enter": "fade", "duration_ms": 500},
        ),
    ]
    if product:
        layers.append(
            Layer(
                id=f"layer-{index:02d}-product",
                type="text",
                props={
                    "text": product,
                    "size": 36,
                    "x": 0,
                    "y": 600,
                    "width": WIDTH,
                    "align": "center",
                    "color": DIM_COLOR,
                    "caption": False,
                },
                animation={"enter": "fade", "duration_ms": 600},
            )
        )
    return layers


def _brand_layer(index: int, product_name: str) -> Layer:
    return Layer(
        id=f"layer-{index:02d}-brand",
        type="text",
        props={
            "text": product_name,
            "size": 24,
            "x": 60,
            "y": HEIGHT - 60,
            "width": 600,
            "align": "left",
            "color": DIM_COLOR,
            "caption": False,
        },
        animation={"enter": "fade", "duration_ms": 600},
    )


# ---------------------------------------------------------------- 素材解析
def _resolve_image(
    shot: PromoShot,
    doc: PromoDoc,
    used_images: set[str],
    generate_image: ImageGenerator | None,
    usage: dict[str, str],
    brief: PromoBrief,
) -> str | None:
    """返回 assets/ 相对路径；无素材且无生图时返回 None（SVG 兜底）。"""
    matched = _match_image(shot, doc, used_images)
    if matched:
        used_images.add(matched.name)
        # intake 存裸文件名（pptx-...png / user-...png），HTML 以 composition/html/ 为根，
        # 因此统一归一化为 assets/ 相对路径；已带前缀的（测试/自定义）不重复添加。
        src = matched.name if matched.name.startswith("assets/") else f"assets/{matched.name}"
        usage[shot.id] = f"asset:{matched.name}"
        return src
    if generate_image is not None:
        prompt = (
            f"企业设备宣传片画面：{brief.product_name}，{shot.on_screen_text[:40]}，"
            f"{brief.tone}，深色背景，产品摄影风格，无文字"
        )
        name = generate_image(shot.id, prompt)
        if name:
            usage[shot.id] = f"generated:{name}"
            return name
    usage[shot.id] = "svg-fallback"
    return None


def _match_image(shot: PromoShot, doc: PromoDoc, used_images: set[str]):
    """确定性匹配：文件名/说明含关键词优先，否则取第一张未用图。"""
    keywords = [k for k in str(shot.visual.get("keywords", "")).lower().split() if k]
    keywords += [word for word in shot.on_screen_text.lower().split() if len(word) >= 2]
    for image in doc.images:
        if image.name in used_images:
            continue
        haystack = f"{image.name} {image.caption}".lower()
        if any(keyword and keyword in haystack for keyword in keywords):
            return image
    for image in doc.images:
        if image.name not in used_images:
            return image
    return None


# ---------------------------------------------------------------- 图表数据
def _chart_series(doc: PromoDoc) -> list[dict] | None:
    """从第一个含数值列的表中取最多 6 行 {name, value}。"""
    for table in doc.tables:
        if not table.sample_records:
            continue
        numeric = [
            column
            for column in table.columns
            if all(_to_number(record.get(column)) is not None for record in table.sample_records if record.get(column))
        ]
        if not numeric:
            continue
        label_column = next((c for c in table.columns if c not in numeric), None)
        value_column = numeric[0]
        series: list[dict] = []
        for record in table.sample_records[:6]:
            value = _to_number(record.get(value_column))
            if value is None:
                continue
            name = str(record.get(label_column, "")) if label_column else value_column
            series.append({"name": name or value_column, "value": value})
        if series:
            return series
    return None


def _to_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# ---------------------------------------------------------------- 工具
def _anim_ms(shot: PromoShot) -> int:
    return min(800, max(300, shot.duration_ms // 3))


def _assert_unique_layer_ids(composition: Composition) -> None:
    for scene in composition.scenes:
        ids = [layer.id for layer in scene.layers]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{scene.id} 图层 ID 重复：{ids}")
