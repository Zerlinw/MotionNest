import tempfile
from pathlib import Path

from motionnest.promo import run_promo

tmp = Path(tempfile.mkdtemp())
docs = tmp / "docs"
docs.mkdir()
(docs / "product.md").write_text(
    "# XR-500 工业巡检机器人\n"
    "## 产品概述\n"
    "XR-500 面向石化厂区巡检，耐酸碱外壳，IP66 防护。\n"
    "## 核心优势\n"
    "- 自主避碍，夜间红外巡检\n"
    "- 单次充电续航 12 小时\n"
    "- 云端报表自动生成\n",
    encoding="utf-8",
)
(docs / "specs.csv").write_text(
    "型号,续航小时,防护等级\nXR-500,12,IP66\nXR-500 Pro,18,IP67\n", encoding="utf-8"
)

result = run_promo(
    tmp / "out",
    [docs / "product.md", docs / "specs.csv"],
    note="突出续航与防护",
    quality="preview",
    logger=lambda level, msg: print(f"[{level}] {msg}"),
)
print("video:", result["video"])
print("duration_s:", result["duration_s"], "frames:", result["frames"], "shots:", result["shots"])
