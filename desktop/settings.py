"""桌面端设置持久化（极致减法版）。

只有四类配置：
  theme            主题（darcula / light）
  chat             对话模型：api_key / base_url / model_id（要点蒸馏与文案）
  image            生图模型：api_key / base_url / model_id（留空则素材 + SVG 兜底）
  last_output_dir  上次成片输出目录

其余参数（超时/重试/帧率/分辨率/时长）全部内置默认值，不在界面暴露。
存储位置（按优先级）：
  1. 环境变量 MNEST_DESKTOP_SETTINGS 指定的路径
  2. 可执行文件同级目录（免安装绿色模式，可 U 盘携带）
  3. %APPDATA%/MotionNest/settings.json

安全提示：密钥以明文 JSON 存储在本机；工具仅在本地使用，请勿共享该文件。
旧版设置文件通过深合并迁移：未知键保留但不生效。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SETTINGS: dict = {
    "theme": "darcula",
    "chat": {
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model_id": "deepseek-chat",
    },
    "image": {
        "api_key": "",
        "base_url": "",
        "model_id": "",
    },
    "last_output_dir": "",
}

CHAT_KEY_ENV = "MOTIONNEST_CHAT_API_KEY"
IMAGE_KEY_ENV = "MOTIONNEST_IMAGE_API_KEY"


def settings_path() -> Path:
    """解析设置文件路径。"""
    override = os.environ.get("MNEST_DESKTOP_SETTINGS")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        local = Path(sys.executable).parent / "motionnest-settings.json"
        try:
            local.touch(exist_ok=True)
            return local
        except OSError:
            pass
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) / "MotionNest" if appdata else Path.home() / ".motionnest"
    base.mkdir(parents=True, exist_ok=True)
    return base / "settings.json"


@dataclass
class SettingsStore:
    """设置的读写与合并（深合并，保留未知键以兼容历史版本）。"""

    path: Path = field(default_factory=settings_path)
    data: dict = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_SETTINGS)))

    def __post_init__(self) -> None:
        self.load()

    # ---------------------------------------------------------------- 读写
    def load(self) -> None:
        if self.path.is_file():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                stored = {}
            self.data = _deep_merge(json.loads(json.dumps(DEFAULT_SETTINGS)), stored)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---------------------------------------------------------------- 字段
    @property
    def theme(self) -> str:
        return self.data.get("theme", "darcula")

    @theme.setter
    def theme(self, value: str) -> None:
        self.data["theme"] = value

    @property
    def chat(self) -> dict:
        return self.data.setdefault("chat", dict(DEFAULT_SETTINGS["chat"]))

    @property
    def image(self) -> dict:
        return self.data.setdefault("image", dict(DEFAULT_SETTINGS["image"]))

    @property
    def last_output_dir(self) -> str:
        return self.data.get("last_output_dir", "")

    @last_output_dir.setter
    def last_output_dir(self, value: str) -> None:
        self.data["last_output_dir"] = value

    # ---------------------------------------------------------------- 派生
    def chat_ready(self) -> bool:
        cfg = self.chat
        return bool(cfg.get("api_key", "").strip() and cfg.get("base_url", "").strip())

    def image_ready(self) -> bool:
        cfg = self.image
        return bool(cfg.get("api_key", "").strip() and cfg.get("base_url", "").strip())


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并：override 覆盖 base，base 中 override 没有的键保留。"""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
