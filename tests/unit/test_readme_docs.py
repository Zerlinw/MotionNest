"""README 文档测试：相对链接有效，且不含会被 GitHub 渲染坏的原始 HTML。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
READMES = ("README.md", "README.en.md")

_FENCE = re.compile(r"```.*?```", re.S)
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_TAG = re.compile(r"<[a-zA-Z][^<>]*>")


def _body(name: str) -> str:
    """去掉围栏代码块，只保留真正会被渲染的正文。"""
    return _FENCE.sub("", (ROOT / name).read_text(encoding="utf-8"))


def _relative_links(body: str) -> list[str]:
    links = []
    for target in _LINK.findall(body):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        if path:
            links.append(path)
    return links


@pytest.mark.parametrize("name", READMES)
def test_readme_relative_links_exist(name: str) -> None:
    missing = sorted({path for path in _relative_links(_body(name)) if not (ROOT / path).exists()})
    assert not missing, f"{name} 存在失效相对链接: {missing}"


@pytest.mark.parametrize("name", READMES)
def test_readme_raw_html_attributes_are_quoted(name: str) -> None:
    """GitHub 的渲染管线按 `>` 截断标签，属性值里出现 `>` 会把整段徽章渲染成乱码。"""
    broken = [tag for tag in _TAG.findall(_body(name)) if tag.count('"') % 2]
    assert not broken, f"{name} 的 HTML 属性含 `>`, GitHub 会渲染错乱: {broken}"
