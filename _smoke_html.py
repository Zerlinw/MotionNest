import tempfile
from pathlib import Path

from motionnest.core.project import Project
from motionnest.promo import parse_documents, build_storyboard, compose, template_brief
from motionnest.runtime.renderer import Renderer

tmp = Path(tempfile.mkdtemp())
docs = tmp / "docs"
docs.mkdir()
(docs / "product.md").write_text(
    "# XR-500 工业巡检机器人\n"
    "## 产品概述\n"
    "XR-500 面向石化厂区巡检，耐酸碱外壳，IP66 防护。\n"
    "## 核心优势\n"
    "- 自主避障，夜间红外巡检\n"
    "- 单次充电续航 12 小时\n"
    "- 云端报表自动生成\n",
    encoding="utf-8",
)
(docs / "specs.csv").write_text(
    "型号,续航小时,防护等级\nXR-500,12,IP66\nXR-500 Pro,18,IP67\n", encoding="utf-8"
)

project = Project.create(tmp / "out" / "p", "p")
doc = parse_documents([docs / "product.md", docs / "specs.csv"], project)
brief = template_brief(doc)
sb = build_storyboard(brief, doc, None)
comp, usage = compose(sb, doc, brief)

renderer = Renderer(project.path("composition", "html"))
paths = renderer.write_all(comp)
print("html files:", [p.name for p in paths])
html = paths[0].read_text(encoding="utf-8")
assert "#0B0E14" in html, "background not applied"
assert "mn-text" in html
scene5 = paths[4].read_text(encoding="utf-8")
assert '"chart"' in scene5, "chart layer missing in proof scene"
# 校验 JSON 内嵌可解析
import re, json
m = re.search(r"const SCENE = (\{.*?\});\nconst COMP", html, re.S)
scene = json.loads(m.group(1))
print("scene-01 layers:", [(l["id"], l["type"]) for l in scene["layers"]])
print("OK")
