"""阶段 1 · 文档解析（纯确定性，无模型调用）。

输入：markdown / csv / json / pptx 文档列表 + 可选素材文件夹 + 项目工作区。
输出：PromoDoc（文本块 / 表格摘要 / 归一化图片清单），原始文档复制到 sources/，
图片统一复制到 assets/（白名单扩展名 + 大小上限），路径全部相对项目根。

自动化边界：解析失败即抛 ConfigError 并指明文件；不做任何内容猜测。
pptx 用 stdlib zipfile + ElementTree 提取 slideN.xml 的 <a:t> 文本与 ppt/media 图片，
不引入 python-pptx 依赖；母版/图表对象内文本不在提取范围（正文已覆盖）。
"""

from __future__ import annotations

import json
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from ..core.project import Project
from ..data.loader import load_table
from ..exceptions import ConfigError
from .schemas import PromoDoc, PromoDocSection, PromoImage, PromoTable

DOC_SUFFIXES = {".md", ".markdown", ".csv", ".json", ".pptx"}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
MAX_ASSET_BYTES = 10 * 1024 * 1024  # 10MB
MAX_SAMPLE_RECORDS = 8

_A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_LIST_RE = re.compile(r"^([-*+]|\d+[.)])\s+")


# ---------------------------------------------------------------- 入口
def parse_documents(
    doc_paths: list[str | Path],
    project: Project,
    *,
    asset_dir: str | Path | None = None,
) -> PromoDoc:
    """解析全部文档与素材文件夹，归一化进项目工作区。"""
    doc = PromoDoc()
    used_names: dict[str, int] = {}

    for raw in doc_paths:
        path = Path(raw)
        if not path.is_file():
            raise ConfigError(f"文档不存在：{path}")
        suffix = path.suffix.lower()
        if suffix not in DOC_SUFFIXES:
            raise ConfigError(
                f"不支持的文档格式：{path.name}（支持 {', '.join(sorted(DOC_SUFFIXES))}）"
            )
        _copy_to_sources(project, path)
        doc.sources.append(path.name)
        if suffix in (".md", ".markdown"):
            _parse_markdown(path, doc)
        elif suffix in (".csv", ".json"):
            _parse_table(path, doc)
        elif suffix == ".pptx":
            _parse_pptx(path, doc, project, used_names)

    if asset_dir:
        _scan_asset_folder(Path(asset_dir), doc, project, used_names)

    if not doc.sources and not doc.images:
        raise ConfigError("没有解析到任何内容：请至少提供一个文档或素材文件夹")
    if not doc.title:
        doc.title = doc.sources[0] if doc.sources else "产品宣传片"
    return doc


# ---------------------------------------------------------------- markdown
def _parse_markdown(path: Path, doc: PromoDoc) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    sections: list[PromoDocSection] = []
    buffer: list[str] = []
    buffer_kind = "paragraph"

    def flush() -> None:
        nonlocal buffer, buffer_kind
        if buffer:
            content = "\n".join(buffer).strip()
            if content:
                sections.append(PromoDocSection(kind=buffer_kind, text=content))
        buffer = []

    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped:
            flush()
            continue
        if stripped.startswith("#"):
            flush()
            heading = stripped.lstrip("#").strip()
            if heading:
                sections.append(PromoDocSection(kind="heading", text=heading))
            continue
        if _LIST_RE.match(stripped):
            if buffer_kind != "list":
                flush()
                buffer_kind = "list"
            buffer.append(_LIST_RE.sub("", stripped))
            continue
        if buffer_kind != "paragraph":
            flush()
            buffer_kind = "paragraph"
        buffer.append(stripped)
    flush()

    doc.sections.extend(sections)
    for section in sections:
        if section.kind == "heading" and not doc.title:
            doc.title = section.text


# ---------------------------------------------------------------- 表格
def _parse_table(path: Path, doc: PromoDoc) -> None:
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"JSON 解析失败：{path.name}（{exc}）") from exc
        if not (isinstance(payload, list) and payload and all(isinstance(r, dict) for r in payload)):
            doc.sections.append(
                PromoDocSection(kind="json", text=json.dumps(payload, ensure_ascii=False)[:4000])
            )
            return
    records, summary = load_table(path)
    doc.tables.append(
        PromoTable(
            source=path.name,
            columns=[column.name for column in summary.columns],
            rows=summary.rows,
            summary=_table_summary_text(summary),
            sample_records=[{k: str(v) for k, v in record.items()} for record in records[:MAX_SAMPLE_RECORDS]],
        )
    )
    doc.sections.append(
        PromoDocSection(kind="paragraph", text=f"数据表 {path.name}：{summary.rows} 行 × {len(summary.columns)} 列")
    )


def _table_summary_text(summary: Any) -> str:
    """数值列输出范围（min ~ max），其余列输出样例值。"""
    lines = [f"{summary.rows} 行 × {len(summary.columns)} 列"]
    for column in summary.columns:
        if column.dtype == "number" and column.min is not None:
            lines.append(f"{column.name}: {column.min:g} ~ {column.max:g}")
        else:
            lines.append(f"{column.name}: {column.sample[0] if column.sample else '-'}")
    return "\n".join(lines)


# ---------------------------------------------------------------- pptx
def _parse_pptx(path: Path, doc: PromoDoc, project: Project, used_names: dict[str, int]) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            slide_names = sorted(
                (name for name in archive.namelist() if _SLIDE_RE.match(name)),
                key=lambda name: int(_SLIDE_RE.match(name).group(1)),  # type: ignore[union-attr]
            )
            if not slide_names:
                raise ConfigError(f"pptx 内没有幻灯片：{path.name}")
            for slide_name in slide_names:
                root = ET.fromstring(archive.read(slide_name))
                texts = [
                    node.text.strip()
                    for node in root.iter(f"{_A_NS}t")
                    if node.text and node.text.strip()
                ]
                if texts:
                    doc.sections.append(
                        PromoDocSection(kind="paragraph", text=f"[{path.name}] " + " / ".join(texts))
                    )
            for media_name in archive.namelist():
                if not media_name.startswith("ppt/media/"):
                    continue
                if Path(media_name).suffix.lower() not in ASSET_SUFFIXES:
                    continue
                info = archive.getinfo(media_name)
                if info.file_size > MAX_ASSET_BYTES:
                    doc.degraded.append(f"{media_name} 超过 10MB，已跳过")
                    continue
                target = _unique_name(f"pptx-{path.stem}-{Path(media_name).name}", used_names)
                destination = project.path("assets", target)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(media_name))
                doc.images.append(PromoImage(name=target, source=path.name))
    except zipfile.BadZipFile as exc:
        raise ConfigError(f"pptx 文件损坏或不是有效 ZIP：{path.name}（{exc}）") from exc


# ---------------------------------------------------------------- 素材文件夹
def _scan_asset_folder(
    folder: Path, doc: PromoDoc, project: Project, used_names: dict[str, int]
) -> None:
    if not folder.is_dir():
        raise ConfigError(f"素材文件夹不存在：{folder}")
    found = 0
    for image_path in sorted(folder.rglob("*")):
        if not image_path.is_file():
            continue
        if image_path.suffix.lower() not in ASSET_SUFFIXES:
            continue
        if image_path.stat().st_size > MAX_ASSET_BYTES:
            doc.degraded.append(f"{image_path.name} 超过 10MB，已跳过")
            continue
        target = _unique_name(f"user-{image_path.name}", used_names)
        destination = project.path("assets", target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_path, destination)
        doc.images.append(PromoImage(name=target, source="asset-folder"))
        found += 1
    if found == 0:
        doc.degraded.append(f"素材文件夹 {folder} 中没有可用图片（{', '.join(sorted(ASSET_SUFFIXES))}）")


# ---------------------------------------------------------------- 工具
def _copy_to_sources(project: Project, path: Path) -> None:
    destination = project.path("sources", path.name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.resolve() != path.resolve():
        shutil.copy2(path, destination)


def _unique_name(name: str, used_names: dict[str, int]) -> str:
    count = used_names.get(name, 0)
    used_names[name] = count + 1
    if count == 0:
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    return f"{stem}-{count + 1}{suffix}"
