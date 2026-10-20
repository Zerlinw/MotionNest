"""promo 全链路测试：StubProvider 文案 + 假生图 + 渲染/探测打桩，无网络无 ffmpeg 依赖。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionnest.promo.pipeline import run_promo

BRIEF_REPLY = json.dumps(
    {
        "product_name": "XR-500 巡检机器人",
        "tagline": "厂区巡检专家",
        "audience": "采购决策者",
        "selling_points": ["自主避障", "12 小时续航", "IP66 防护"],
        "proof_numbers": ["续航 12 ~ 18 小时"],
        "cta": "欢迎联系获取方案",
        "tone": "专业、克制",
        "palette": ["#4A88C7"],
    },
    ensure_ascii=False,
)


@pytest.fixture()
def docs(tmp_path: Path) -> list[Path]:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "product.md").write_text(
        "# XR-500 巡检机器人\n## 核心优势\n- 自主避障\n- 12 小时续航\n- IP66 防护\n",
        encoding="utf-8",
    )
    (folder / "specs.csv").write_text("型号,续航小时\nXR-500,12\nXR-500 Pro,18\n", encoding="utf-8")
    return [folder / "product.md", folder / "specs.csv"]


@pytest.fixture()
def stubbed(monkeypatch):
    """把逐帧渲染与 ffprobe 打桩，使测试不依赖 playwright/ffmpeg。"""
    from motionnest.promo import pipeline as pipeline_module
    from motionnest.runtime.renderer import Renderer, RenderResult

    def fake_render_video(self, composition, *, fps=None, quality="preview", strict=False):
        frames = self.output_dir / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        count = 150 if quality == "preview" else 900
        for index in range(count):
            (frames / f"frame-{index + 1:04d}.png").write_bytes(b"")
        video = self.output_dir / f"motionnest-{quality}.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"fake-mp4")
        return RenderResult(status="video", outputs=[video])

    monkeypatch.setattr(Renderer, "render_video", fake_render_video)
    monkeypatch.setattr(pipeline_module, "probe_duration", lambda path: 30.0)


def test_full_pipeline_with_model(stubbed, docs, tmp_path: Path):
    calls: list[tuple[str, str]] = []

    def chat_fn(system: str, user: str) -> str:
        calls.append((system, user))
        return BRIEF_REPLY

    def image_fn(prompt: str) -> bytes:
        return b"\x89PNG\r\n\x1a\ngenerated"

    result = run_promo(
        tmp_path / "out",
        docs,
        note="突出续航",
        chat_fn=chat_fn,
        image_fn=image_fn,
        chat_model="deepseek-chat",
        image_model="img-model",
        quality="final",
        logger=lambda level, message: None,
    )
    # 两次模型调用：要点蒸馏 + 分镜文案
    assert len(calls) == 2
    video = Path(result["video"])
    assert video.name == "promo.mp4"
    assert video.is_file()
    assert result["duration_s"] == 30.0
    assert result["frames"] == 900
    assert result["shots"] == 7  # 3 卖点 → 完整七拍
    assert result["degraded"] == []

    audit = json.loads(Path(result["audit"]).read_text(encoding="utf-8"))
    assert audit["duration_ms"] == 30_000
    assert audit["brief_source"] == "model"
    assert audit["chat_model"] == "deepseek-chat"
    assert audit["sources"] == ["product.md", "specs.csv"]
    assert any(source.startswith("generated:") for source in audit["assets"].values())
    generated = list((Path(result["project"]) / "assets" / "generated").glob("*.png"))
    assert len(generated) >= 1


def test_pipeline_template_degradation_without_model(stubbed, docs, tmp_path: Path):
    result = run_promo(tmp_path / "out", docs, quality="preview", logger=lambda level, message: None)
    assert result["shots"] >= 4
    audit = json.loads(Path(result["audit"]).read_text(encoding="utf-8"))
    assert audit["brief_source"] == "template"
    assert audit["fps"] == 5  # preview 档
    assert any("未配置对话模型" in note for note in audit["degraded"])


def test_duration_validation_failure(stubbed, monkeypatch, docs, tmp_path: Path):
    from motionnest.promo import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "probe_duration", lambda path: 24.0)
    with pytest.raises(RuntimeError, match="超出"):
        run_promo(tmp_path / "out", docs, quality="preview", logger=lambda level, message: None)


def test_frame_count_failure(stubbed, monkeypatch, docs, tmp_path: Path):
    from motionnest.promo import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "_count_frames", lambda frames_dir: 100)
    with pytest.raises(RuntimeError, match="帧数不达标"):
        run_promo(tmp_path / "out", docs, quality="preview", logger=lambda level, message: None)


def test_image_failure_does_not_block(stubbed, docs, tmp_path: Path):
    def chat_fn(system: str, user: str) -> str:
        return BRIEF_REPLY

    def image_fn(prompt: str) -> bytes:
        raise RuntimeError("生图服务不可用")

    result = run_promo(
        tmp_path / "out",
        docs,
        chat_fn=chat_fn,
        image_fn=image_fn,
        quality="preview",
        logger=lambda level, message: None,
    )
    audit = json.loads(Path(result["audit"]).read_text(encoding="utf-8"))
    assert any(source == "svg-fallback" for source in audit["assets"].values())
    assert Path(result["video"]).is_file()


def test_requires_at_least_one_input(stubbed, tmp_path: Path):
    with pytest.raises(Exception, match="请至少提供"):
        run_promo(tmp_path / "out", [], quality="preview", logger=lambda level, message: None)
