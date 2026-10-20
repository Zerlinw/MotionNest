"""promo 阶段 1 测试：md/csv/pptx 解析、素材扫描、归一化。"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from motionnest.core.project import Project
from motionnest.exceptions import ConfigError
from motionnest.promo.intake import parse_documents


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return Project.create(tmp_path / "workspace", "t")


def _write_md(path: Path) -> None:
    path.write_text(
        "# XR-500 工业巡检机器人\n"
        "\n"
        "面向石化厂区的自主巡检设备。\n"
        "\n"
        "## 核心优势\n"
        "- 自主避障，夜间红外巡检\n"
        "- 单次充电续航 12 小时\n"
        "\n"
        "```python\n"
        "# 代码块应被忽略\n"
        "```\n",
        encoding="utf-8",
    )


def _write_csv(path: Path) -> None:
    path.write_text("型号,续航小时\nXR-500,12\nXR-500 Pro,18\n", encoding="utf-8")


def _write_pptx(path: Path, media: dict[str, bytes] | None = None) -> None:
    """用 zipfile 造一个最小合法 pptx：两页幻灯片 + 一张 media 图片。"""
    slide1 = (
        '<?xml version="1.0"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
        ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<p:cSld><p:spTree><a:p><a:r><a:t>XR-500 产品介绍</a:t></a:r></a:p>"
        "<a:p><a:r><a:t>IP66 防护等级</a:t></a:r></a:p></p:spTree></p:cSld></p:sld>"
    )
    slide2 = (
        '<?xml version="1.0"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
        ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<p:cSld><p:spTree><a:p><a:r><a:t>续航 12 小时</a:t></a:r></a:p></p:spTree></p:cSld></p:sld>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", slide1)
        archive.writestr("ppt/slides/slide2.xml", slide2)
        for name, payload in (media or {"ppt/media/image1.png": b"\x89PNG\r\n\x1a\nfake"}).items():
            archive.writestr(name, payload)


def test_markdown_parsing(project, tmp_path: Path):
    md = tmp_path / "product.md"
    _write_md(md)
    doc = parse_documents([md], project)
    assert doc.title == "XR-500 工业巡检机器人"
    headings = [s.text for s in doc.sections if s.kind == "heading"]
    assert "核心优势" in headings
    joined = "\n".join(s.text for s in doc.sections)
    assert "自主避障" in joined
    assert "代码块应被忽略" not in joined  # 围栏代码块跳过
    assert doc.sources == ["product.md"]
    # 原文进入 sources/ 供追溯
    assert (project.root / "sources" / "product.md").is_file()


def test_csv_table_summary(project, tmp_path: Path):
    csv = tmp_path / "specs.csv"
    _write_csv(csv)
    doc = parse_documents([csv], project)
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert table.columns == ["型号", "续航小时"]
    assert table.rows == 2
    assert " ~ " in table.summary  # 数值列输出范围
    assert len(table.sample_records) == 2


def test_pptx_text_and_media(project, tmp_path: Path):
    pptx = tmp_path / "deck.pptx"
    _write_pptx(pptx)
    doc = parse_documents([pptx], project)
    joined = "\n".join(s.text for s in doc.sections)
    assert "XR-500 产品介绍" in joined
    assert "IP66 防护等级" in joined
    assert "续航 12 小时" in joined
    assert len(doc.images) == 1
    assert doc.images[0].name.startswith("pptx-deck-")
    assert (project.root / "assets" / doc.images[0].name).is_file()


def test_pptx_oversized_media_skipped(project, tmp_path: Path):
    pptx = tmp_path / "deck.pptx"
    _write_pptx(pptx, media={"ppt/media/big.png": b"x" * (10 * 1024 * 1024 + 1)})
    doc = parse_documents([pptx], project)
    assert doc.images == []
    assert any("超过 10MB" in note for note in doc.degraded)


def test_asset_folder_scan(project, tmp_path: Path):
    assets = tmp_path / "assets-src"
    assets.mkdir()
    (assets / "hero.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (assets / "logo.svg").write_text("<svg/>", encoding="utf-8")
    (assets / "notes.txt").write_text("ignore", encoding="utf-8")
    doc = parse_documents([], project, asset_dir=assets)
    names = {image.name for image in doc.images}
    assert names == {"user-hero.png", "user-logo.svg"}


def test_missing_file_raises(project, tmp_path: Path):
    with pytest.raises(ConfigError, match="文档不存在"):
        parse_documents([tmp_path / "nope.md"], project)


def test_unsupported_suffix_raises(project, tmp_path: Path):
    txt = tmp_path / "a.txt"
    txt.write_text("x", encoding="utf-8")
    with pytest.raises(ConfigError, match="不支持的文档格式"):
        parse_documents([txt], project)


def test_bad_zip_raises(project, tmp_path: Path):
    fake = tmp_path / "bad.pptx"
    fake.write_bytes(b"not a zip")
    with pytest.raises(ConfigError, match="pptx 文件损坏"):
        parse_documents([fake], project)


def test_empty_input_raises(project):
    with pytest.raises(ConfigError, match="没有解析到任何内容"):
        parse_documents([], project)


def test_json_docs(project, tmp_path: Path):
    data = tmp_path / "table.json"
    data.write_text(json.dumps([{"a": 1}, {"a": 2}]), encoding="utf-8")
    doc = parse_documents([data], project)
    assert len(doc.tables) == 1
    assert doc.tables[0].rows == 2
