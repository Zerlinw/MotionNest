"""promo 渲染测试：image 图层进入 HTML、背景色注入、assets 相对路径。"""

from __future__ import annotations

import json
import re

import pytest

from motionnest.core.project import Project
from motionnest.core.schemas import Composition, Scene
from motionnest.promo.compose import compose
from motionnest.promo.schemas import PromoBrief, PromoDoc, PromoDocSection
from motionnest.promo.storyboard import build_storyboard
from motionnest.runtime.renderer import Renderer, scene_frame_counts


def _brief() -> PromoBrief:
    return PromoBrief(
        product_name="XR-500",
        tagline="厂区巡检专家",
        audience="采购",
        selling_points=["自主避障", "12 小时续航", "IP66 防护"],
        cta="欢迎联系",
    )


def _doc_with_image(project: Project) -> PromoDoc:
    asset = project.path("assets", "user-hero.png")
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    return PromoDoc(
        title="XR-500",
        sections=[PromoDocSection(kind="heading", text="XR-500")],
        images=[],
    )


def _patch_doc_image(doc: PromoDoc, project: Project) -> PromoDoc:
    from motionnest.promo.schemas import PromoImage

    doc.images.append(PromoImage(name="assets/user-hero.png", source="asset-folder"))
    return doc


@pytest.fixture()
def project(tmp_path) -> Project:
    return Project.create(tmp_path / "ws", "t")


def test_image_layer_rendered_in_html(project):
    doc = _patch_doc_image(_doc_with_image(project), project)
    storyboard = build_storyboard(_brief(), doc, None)
    composition, usage = compose(storyboard, doc, _brief())

    # hook/卖点镜头应命中素材
    assert any(source.startswith("asset:") for source in usage.values())

    renderer = Renderer(project.path("composition", "html"))
    html_path = renderer.write_scene(composition.scenes[0], composition)
    html = html_path.read_text(encoding="utf-8")
    assert "#0B0E14" in html  # 背景注入
    assert 'type === "image"' in html  # JS 渲染分支存在
    assert 'object-fit' in html
    # 图层 JSON 内嵌且 src 为 assets/ 相对路径
    match = re.search(r"const SCENE = (\{.*?\});\nconst COMP", html, re.S)
    scene = json.loads(match.group(1))
    image_layers = [layer for layer in scene["layers"] if layer["type"] == "image"]
    assert image_layers, "hook 场景应包含 image 图层"
    assert image_layers[0]["props"]["src"].startswith("assets/")


def test_background_default_when_empty(project):
    composition = Composition(
        scenes=[Scene(id="scene-01", shot_id="shot-1", duration_ms=1000, layers=[])]
    )
    renderer = Renderer(project.path("composition", "html"))
    html_path = renderer.write_scene(composition.scenes[0], composition)
    html = html_path.read_text(encoding="utf-8")
    assert "#0b0e14" in html  # 空 background → 渲染默认


def test_strict_mode_raises_without_ffmpeg(project, monkeypatch):
    composition = Composition(
        scenes=[Scene(id="scene-01", shot_id="shot-1", duration_ms=1000, layers=[])]
    )
    monkeypatch.setattr("motionnest.runtime.ffmpeg.ffmpeg_available", lambda: False)
    renderer = Renderer(project.path("composition", "html"))
    with pytest.raises(RuntimeError, match="ffmpeg"):
        renderer.render_video(composition, strict=True)


def test_non_strict_degrades_without_ffmpeg(project, monkeypatch):
    monkeypatch.setattr("motionnest.runtime.ffmpeg.ffmpeg_available", lambda: False)
    composition = Composition(
        scenes=[Scene(id="scene-01", shot_id="shot-1", duration_ms=1000, layers=[])]
    )
    renderer = Renderer(project.path("composition", "html"))
    result = renderer.render_video(composition, strict=False)
    assert result.status == "html-only"
    assert len(result.outputs) == 1


def test_bare_asset_name_normalized_to_assets_prefix(project):
    """intake 存裸文件名（user-hero.png），compose 必须归一化为 assets/ 相对路径。"""
    from motionnest.promo.schemas import PromoImage

    doc = _doc_with_image(project)
    doc.images.append(PromoImage(name="user-hero.png", source="asset-folder"))
    storyboard = build_storyboard(_brief(), doc, None)
    composition, _usage = compose(storyboard, doc, _brief())
    image_srcs = [
        layer.props["src"]
        for scene in composition.scenes
        for layer in scene.layers
        if layer.type == "image"
    ]
    assert image_srcs
    assert all(src.startswith("assets/") for src in image_srcs)
    assert not any("assets/assets/" in src for src in image_srcs)


@pytest.mark.parametrize("fps", [30, 5])
@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_scene_frame_counts_sum_exact(fps: int, count: int):
    """4 卖点（3750ms/镜头）等非整帧时长下，累计取整仍严格 900/150 帧。"""
    from motionnest.promo.schemas import PromoBrief, PromoDoc
    from motionnest.promo.storyboard import TOTAL_DURATION_MS, build_storyboard

    brief = PromoBrief(
        product_name="XR-500",
        selling_points=[f"卖点{index}" for index in range(count)],
    )
    storyboard = build_storyboard(brief, PromoDoc(title="XR-500"), None)
    counts = scene_frame_counts([shot.duration_ms for shot in storyboard.shots], fps)
    assert sum(counts) == round(TOTAL_DURATION_MS * fps / 1000)
    assert all(value > 0 for value in counts)
