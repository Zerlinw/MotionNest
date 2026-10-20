"""MotionNest 宣传片管线：文档进、30 秒 MP4 出。

公开入口：
- run_promo()：六阶段全自动编排（桌面端与 CLI 共用）；
- 各阶段函数（parse_documents / distill_brief / build_storyboard / compose）可单独调用。
"""

from .compose import compose
from .distill import distill_brief, template_brief
from .intake import parse_documents
from .pipeline import run_promo
from .schemas import PromoBrief, PromoDoc, PromoDocSection, PromoImage, PromoShot, PromoStoryboard, PromoTable
from .storyboard import TOTAL_DURATION_MS, build_storyboard, template_storyboard

__all__ = [
    "run_promo",
    "parse_documents",
    "distill_brief",
    "template_brief",
    "build_storyboard",
    "template_storyboard",
    "compose",
    "TOTAL_DURATION_MS",
    "PromoDoc",
    "PromoDocSection",
    "PromoImage",
    "PromoTable",
    "PromoBrief",
    "PromoShot",
    "PromoStoryboard",
]
