"""Bridge：桌面界面 → 宣传片管线的薄封装。

只有一个业务入口 generate_promo()：文档 + 素材 + 一句话补充 → 30 秒 MP4。
模型回调（chat_fn / image_fn）由设置页配置构造；密钥经环境变量注入
（OpenAIProvider 从 api_key_env 读取），调用时即建即用。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject

from .settings import CHAT_KEY_ENV, SettingsStore

DEFAULT_OUTPUT_DIRNAME = "MotionNest 宣传片"


class Bridge(QObject):
    """把 promo 管线封装为带 logger 的调用。"""

    def __init__(self, settings_store: SettingsStore) -> None:
        super().__init__()
        self.settings_store = settings_store

    # ---------------------------------------------------------------- 模型回调
    def chat_fn(self, logger=None):
        """构造 chat_fn(system, user) -> str；未配置密钥时返回 None（管线自动降级模板）。"""
        cfg = self.settings_store.chat
        if not cfg.get("api_key", "").strip():
            if logger:
                logger("warn", "未配置对话模型密钥：要点蒸馏与文案将使用模板降级")
            return None
        from motionnest.llm.openai_provider import OpenAIProvider
        from motionnest.llm.registry import ModelSpec
        from motionnest.llm.types import Message

        os.environ[CHAT_KEY_ENV] = cfg["api_key"].strip()
        spec = ModelSpec(
            name="promo-chat",
            model_id=cfg.get("model_id", "").strip() or "deepseek-chat",
            provider_format="openai",
            base_url=cfg.get("base_url", "").strip() or "https://api.deepseek.com",
            api_key_env=CHAT_KEY_ENV,
            tier="low",
            max_output_tokens=4096,
        )
        provider = OpenAIProvider(spec, timeout=120.0, max_retries=2)

        def call(system: str, user: str) -> str:
            response = provider.chat(
                [Message(role="system", content=system), Message(role="user", content=user)],
                temperature=0.3,
            )
            return response.text

        return call

    def image_fn(self, logger=None):
        """构造 image_fn(prompt) -> bytes；未配置生图模型时返回 None（素材 + SVG 兜底）。"""
        cfg = self.settings_store.image
        if not (cfg.get("api_key", "").strip() and cfg.get("base_url", "").strip()):
            return None
        from motionnest.llm.image_provider import ImageProvider

        provider = ImageProvider(
            base_url=cfg["base_url"].strip(),
            api_key=cfg["api_key"].strip(),
            model=cfg.get("model_id", "").strip(),
            timeout=180.0,
        )

        def call(prompt: str) -> bytes:
            return provider.generate(prompt, size="1792x1024")

        return call

    # ---------------------------------------------------------------- 主入口
    def generate_promo(
        self,
        logger,
        doc_paths: list[str],
        asset_dir: str,
        note: str,
        quality: str = "final",
    ) -> dict:
        """文档 → 30 秒宣传片 MP4（全自动，无签批）。"""
        from motionnest.promo import run_promo

        output_dir = self.settings_store.last_output_dir or str(
            Path.home() / "Videos" / DEFAULT_OUTPUT_DIRNAME
        )
        chat_fn = self.chat_fn(logger)
        image_fn = self.image_fn(logger)
        result = run_promo(
            output_dir,
            [Path(path) for path in doc_paths],
            asset_dir=asset_dir or None,
            note=note,
            chat_fn=chat_fn,
            image_fn=image_fn,
            chat_model=self.settings_store.chat.get("model_id", ""),
            image_model=self.settings_store.image.get("model_id", ""),
            quality=quality,
            logger=logger,
        )
        self.settings_store.last_output_dir = output_dir
        self.settings_store.save()
        return result

    # ---------------------------------------------------------------- 工具
    @staticmethod
    def open_path(path: str) -> None:
        """用系统默认方式打开文件或其所在文件夹。"""
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"路径不存在：{path}")
        if sys.platform.startswith("win"):
            os.startfile(target)  # noqa: S606 - 用户主动触发的打开操作
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)], check=False)
        else:
            subprocess.run(["xdg-open", str(target)], check=False)

    @staticmethod
    def reveal_in_folder(path: str) -> None:
        """打开文件所在文件夹（Windows 资源管理器选中文件）。"""
        target = Path(path)
        if sys.platform.startswith("win") and target.is_file():
            subprocess.run(["explorer", "/select,", str(target)], check=False)
        else:
            Bridge.open_path(str(target.parent))
