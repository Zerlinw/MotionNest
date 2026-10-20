"""promo CLI 接线测试：mnest promo 把参数正确透传给 run_promo（不发网络、不渲染）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import motionnest.cli as cli
import motionnest.promo as promo_module
from motionnest.exceptions import ConfigError

runner = CliRunner()


@pytest.fixture()
def doc(tmp_path: Path) -> Path:
    path = tmp_path / "product.md"
    path.write_text("# XR-500 巡检机器人\n## 核心优势\n- 续航 12 小时\n", encoding="utf-8")
    return path


@pytest.fixture()
def offline(monkeypatch):
    """屏蔽 .env 与全局模型栈，避免测试受本机密钥/配置影响。"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MOTIONNEST_IMAGE_API_KEY", raising=False)
    monkeypatch.setattr(cli, "load_environment", lambda: None)
    monkeypatch.setattr(cli, "build_stack", lambda config: (None, None, None))


def test_promo_cli_wires_pipeline(doc: Path, tmp_path: Path, offline, monkeypatch):
    captured: dict = {}

    def fake_run_promo(output_dir, doc_paths, **kwargs):
        captured["output_dir"] = output_dir
        captured["doc_paths"] = doc_paths
        captured.update(kwargs)
        return {"video": str(tmp_path / "promo.mp4"), "audit": str(tmp_path / "audit.json")}

    monkeypatch.setattr(promo_module, "run_promo", fake_run_promo)
    result = runner.invoke(
        cli.app,
        ["promo", str(doc), "-o", str(tmp_path / "out"), "--quality", "preview", "--note", "突出续航"],
    )
    assert result.exit_code == 0, result.output
    assert captured["doc_paths"] == [doc]
    assert captured["output_dir"] == tmp_path / "out"
    assert captured["quality"] == "preview"
    assert captured["note"] == "突出续航"
    assert captured["chat_fn"] is None  # 无密钥 → 模板降级
    assert captured["image_fn"] is None


def test_promo_cli_defaults_to_final(doc: Path, tmp_path: Path, offline, monkeypatch):
    captured: dict = {}

    def fake_run_promo(output_dir, doc_paths, **kwargs):
        captured.update(kwargs)
        return {"video": "v.mp4", "audit": "a.json"}

    monkeypatch.setattr(promo_module, "run_promo", fake_run_promo)
    result = runner.invoke(cli.app, ["promo", str(doc)])
    assert result.exit_code == 0, result.output
    assert captured["quality"] == "final"
    assert captured["note"] == ""


def test_promo_cli_reports_pipeline_error(doc: Path, tmp_path: Path, offline, monkeypatch):
    def boom(output_dir, doc_paths, **kwargs):
        raise ConfigError("文档格式不支持")

    monkeypatch.setattr(promo_module, "run_promo", boom)
    result = runner.invoke(cli.app, ["promo", str(doc)])
    assert result.exit_code == 1
    assert "文档格式不支持" in result.output


def test_promo_help_lists_docs_argument():
    result = runner.invoke(cli.app, ["promo", "--help"])
    assert result.exit_code == 0
    assert "docs" in result.output
