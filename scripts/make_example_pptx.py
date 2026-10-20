"""生成 examples/equipment-promo 示例素材（stdlib 实现，零第三方依赖）。

产物：
  examples/equipment-promo/product.md            产品文档（如已存在则跳过）
  examples/equipment-promo/specs.csv             设备参数表（如已存在则跳过）
  examples/equipment-promo/assets/hero.png       主视觉（渐变 + 设备剪影）
  examples/equipment-promo/assets/detail.png     细节图
  examples/equipment-promo/docs/product-deck.pptx  三页迷你演示文稿（含内嵌图片）

用法：python scripts/make_example_pptx.py
pptx 结构为最小合法集（[Content_Types].xml / _rels / presentation.xml /
ppt/slides/slideN.xml / ppt/media/*），用于验证 intake 的文本与图片提取链路。
"""

from __future__ import annotations

import struct
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "equipment-promo"
WIDTH, HEIGHT = 640, 360

SLIDES = [
    ("XR-500 工业巡检机器人 · 产品介绍", ["面向石化厂区的自主巡检设备", "IP66 防护 · 耐酸碱外壳", "已服务 30+ 行业客户"]),
    ("核心能力", ["多传感器融合避障，巡检路径自主规划", "夜间红外热成像，异常温升实时告警", "云端报表自动生成，运维数据可追溯"]),
    ("关键参数", ["续航 12 小时（Pro 版 18 小时）", "防护等级 IP66（Pro 版 IP67）", "单机覆盖 5 公里管廊"]),
]


# ---------------------------------------------------------------- PNG 写入
def write_png(path: Path, width: int, height: int, shade) -> None:
    """纯 stdlib PNG 编码（truecolor，无滤镜）。"""

    def rows() -> bytes:
        raw = bytearray()
        for y in range(height):
            raw.append(0)  # filter type: none
            for x in range(width):
                raw.extend(shade(x, y))
        return bytes(raw)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows(), 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def hero_shade(x: int, y: int) -> tuple[int, int, int]:
    """深蓝渐变 + 中部设备剪影（圆角矩形 + 顶部传感器）。"""
    base = int(30 + 60 * (y / HEIGHT))
    color = (14, base // 2, base + 40)
    cx, cy = WIDTH // 2, int(HEIGHT * 0.62)
    if abs(x - cx) < 200 and abs(y - cy) < 90:  # 机身
        color = (74, 136, 199)
    if abs(x - cx) < 26 and abs(y - (cy - 110)) < 26:  # 传感器
        color = (247, 201, 72)
    if abs(x - cx) < 200 and abs(y - (cy + 90)) < 8:  # 底盘阴影
        color = (11, 14, 20)
    return color


def detail_shade(x: int, y: int) -> tuple[int, int, int]:
    """暖色细节图：同心圆纹理。"""
    dx, dy = x - WIDTH // 2, y - HEIGHT // 2
    ring = int((dx * dx + dy * dy) ** 0.5) % 40
    base = 180 + (30 if ring < 20 else 0)
    return (base, int(base * 0.6), int(base * 0.4))


# ---------------------------------------------------------------- PPTX 构造
_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
{overrides}
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""

_PRESENTATION = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<p:sldIdLst>{slide_ids}</p:sldIdLst>
</p:presentation>"""

_PRESENTATION_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{slide_rels}
</Relationships>"""

_SLIDE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<p:cSld><p:spTree>
<p:pic><p:nvPicPr/><p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr/></p:pic>
{shapes}
</p:spTree></p:cSld>
</p:sld>"""

_SLIDE_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>"""


def _text_shape(text: str, top: int, size: int, bold: bool) -> str:
    bold_attr = ' b="1"' if bold else ""
    return (
        "<p:sp><p:nvSpPr/><p:spPr/>"
        f'<p:txBody><a:bodyPr/><a:p><a:r><a:rPr lang="zh-CN" sz="{size}"{bold_attr}/>'
        f"<a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>"
    )


def build_pptx(path: Path, image_bytes: bytes) -> None:
    slide_ids = "".join(f'<p:sldId id="{256 + index}"/>' for index in range(len(SLIDES)))
    slide_rels = "".join(
        f'<Relationship Id="rId{index + 1}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{index + 1}.xml"/>'
        for index in range(len(SLIDES))
    )
    overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{index + 1}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(len(SLIDES))
    )
    slides = []
    for title, bullets in SLIDES:
        shapes = _text_shape(title, 0, 3200, True)
        shapes += "".join(_text_shape(bullet, 0, 1600, False) for bullet in bullets)
        slides.append(_SLIDE.format(shapes=shapes))
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES.format(overrides=overrides))
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("ppt/presentation.xml", _PRESENTATION.format(slide_ids=slide_ids))
        archive.writestr("ppt/_rels/presentation.xml.rels", _PRESENTATION_RELS.format(slide_rels=slide_rels))
        for index, slide_xml in enumerate(slides, start=1):
            archive.writestr(f"ppt/slides/slide{index}.xml", slide_xml)
            archive.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", _SLIDE_RELS)
        archive.writestr("ppt/media/image1.png", image_bytes)


# ---------------------------------------------------------------- 文档
PRODUCT_MD = """# XR-500 工业巡检机器人

面向石化厂区的自主巡检设备：多传感器融合避障、夜间红外热成像、云端报表自动生成。
已服务 30+ 行业客户，覆盖管廊、罐区、装卸台等复杂场景。

## 核心优势

- 多传感器融合避障，巡检路径自主规划，无需人工示教
- 夜间红外热成像，异常温升实时告警
- 单次充电续航 12 小时，覆盖 5 公里管廊
- IP66 防护等级，耐酸碱外壳，适应户外严苛环境
- 云端报表自动生成，运维数据可追溯

## 客户价值

- 人工巡检频次下降 70%，高危区域零暴露
- 异常发现从"按班"提升到"实时"
- 报表自动生成，运维合规审计有据可查

## 服务承诺

整机质保 2 年，4 小时响应，备件 48 小时到场。
"""

SPECS_CSV = """型号,续航小时,防护等级,覆盖距离公里,客户数
XR-500,12,IP66,5,30
XR-500 Pro,18,IP67,8,12
XR-500 Lite,8,IP65,3,45
"""

README_MD = """# 示例：XR-500 工业巡检机器人 · 30 秒宣传片

自造合成素材（文档 + 参数表 + 迷你 pptx + 两张图片），用于跑通 MotionNest
宣传片管线。不包含任何真实业务数据。

## 一键跑通（CLI）

```bash
cd <仓库根目录>

# 重新生成素材（可选，仓库已附带生成结果）
python scripts/make_example_pptx.py

# 文档 → 30 秒 MP4（未配置模型时自动模板降级，仍可出片）
mnest promo examples/equipment-promo/product.md examples/equipment-promo/specs.csv \\
  examples/equipment-promo/docs/product-deck.pptx \\
  --assets examples/equipment-promo/assets \\
  --note "突出续航与防护，面向海外采购客户" \\
  -o out
```

产物：`out/promo-*/exports/promo.mp4`（1920×1080@30fps，30.00s）
与 `exports/audit.json`（数据来源 / 素材命中 / 时长校验）。

## 桌面端

启动 MotionNestDesktop.exe，把 `product.md`、`specs.csv`、
`docs/product-deck.pptx` 与 `assets/` 文件夹一起拖入工作台，
点击"生成 30 秒宣传片"。

## 质量说明

- 未配置对话模型：要点蒸馏与文案走确定性模板（审计中注明 template）；
- 配置 DeepSeek 密钥后自动切换模型链路（蒸馏 + 文案两次调用）；
- 未配置生图模型：缺图镜头以 SVG/CSS 图形兜底；配置后按需补图。
"""


def main() -> int:
    hero = EXAMPLE / "assets" / "hero.png"
    detail = EXAMPLE / "assets" / "detail.png"
    write_png(hero, WIDTH, HEIGHT, hero_shade)
    write_png(detail, WIDTH, HEIGHT, detail_shade)
    print(f"==> {hero}")
    print(f"==> {detail}")

    build_pptx(EXAMPLE / "docs" / "product-deck.pptx", hero.read_bytes())
    print(f"==> {EXAMPLE / 'docs' / 'product-deck.pptx'}")

    for path, content in (
        (EXAMPLE / "product.md", PRODUCT_MD),
        (EXAMPLE / "specs.csv", SPECS_CSV),
        (EXAMPLE / "README.md", README_MD),
    ):
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"==> {path}")
    print("示例素材就绪。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
