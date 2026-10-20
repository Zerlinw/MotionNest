import tempfile
from pathlib import Path

from motionnest.core.project import Project
from motionnest.promo import parse_documents, distill_brief, build_storyboard, compose

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
print("title:", doc.title)
print("sections:", len(doc.sections), "tables:", len(doc.tables), "images:", len(doc.images))
brief = distill_brief(doc, "突出续航与防护", None)
print("brief:", brief.product_name, "|", brief.selling_points, "|", brief.proof_numbers, "|", brief.source)
sb = build_storyboard(brief, doc, None)
print("total:", sb.total_duration_ms, "shots:", [(s.beat, s.duration_ms) for s in sb.shots])
print("sum:", sum(s.duration_ms for s in sb.shots))
comp, usage = compose(sb, doc, brief)
print("scenes:", len(comp.scenes), "bg:", comp.background)
for sc in comp.scenes:
    print(" ", sc.id, sc.duration_ms, [l.type for l in sc.layers])
print("usage:", usage)
