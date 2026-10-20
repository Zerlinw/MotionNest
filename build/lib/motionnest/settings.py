"""配置加载：定位 config 目录，构建 Registry 与 Router。

查找顺序：环境变量 MNEST_CONFIG_DIR → 当前目录 ./config → PyInstaller 冻结目录
（sys._MEIPASS，随 exe 打包）→ 仓库内 config/。
密钥一律从环境变量读取（支持 .env），不落库、不进配置。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .llm.registry import ModelRegistry
from .llm.router import TaskRouter


@dataclass(frozen=True, slots=True)
class Settings:
    config_dir: Path
    models_path: Path
    router_path: Path

    @classmethod
    def resolve(cls, config_dir: str | None = None) -> Settings:
        candidates: list[Path] = []
        if config_dir:
            candidates.append(Path(config_dir))
        env_dir = os.environ.get("MNEST_CONFIG_DIR")
        if env_dir:
            candidates.append(Path(env_dir))
        candidates.append(Path.cwd() / "config")
        if getattr(sys, "frozen", False):  # PyInstaller onefile 的解包目录
            candidates.append(Path(sys._MEIPASS) / "config")  # type: ignore[attr-defined]
        candidates.append(Path(__file__).resolve().parent.parent.parent / "config")
        for candidate in candidates:
            if (candidate / "models.yaml").is_file():
                return cls(
                    config_dir=candidate,
                    models_path=candidate / "models.yaml",
                    router_path=candidate / "router.yaml",
                )
        searched = "\n  ".join(str(c) for c in candidates)
        raise FileNotFoundError(f"未找到配置文件，已搜索：\n  {searched}")


def load_environment() -> None:
    """加载 .env（不覆盖已有环境变量）。"""
    load_dotenv(override=False)


def build_registry(settings: Settings) -> ModelRegistry:
    return ModelRegistry.from_yaml(settings.models_path)


def build_router(settings: Settings, registry: ModelRegistry) -> TaskRouter:
    allow_human_review = os.environ.get("MNEST_ALLOW_HUMAN_REVIEW", "true").lower() not in ("0", "false", "no")
    return TaskRouter.from_yaml(registry, settings.router_path, allow_human_review=allow_human_review)


def build_stack(config_dir: str | None = None) -> tuple[Settings, ModelRegistry, TaskRouter]:
    """一键构建 配置 + 注册表 + 路由器。"""
    load_environment()
    settings = Settings.resolve(config_dir)
    registry = build_registry(settings)
    router = build_router(settings, registry)
    return settings, registry, router
