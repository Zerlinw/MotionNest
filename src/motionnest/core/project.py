"""Project：MotionNest 工作区（项目状态的一等公民）。

一个项目目录 = 一份可审、可改、可复现的工程文件：
    project.json       身份、版本与审批状态
    data/              数据快照、字典、摘要
    plan/              数据解读与叙事方向
    script/            分镜脚本与字幕
    composition/       合成 JSON 与 HTML 预览
    reviews/           配乐/运镜/审片报告与人工签批
    sources/           引用与许可清单
    assets/            用户授权素材
    exports/           成片与审计报告
    versions/          快照（可回滚的单位是完整项目状态，不是命令历史）
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from ..exceptions import ConfigError
from .schemas import ProjectManifest
from .versions import list_snapshots, restore_snapshot, snapshot_project

STATE_DIRS = (
    "data",
    "plan",
    "script",
    "composition",
    "reviews",
    "sources",
    "assets",
    "exports",
    "studio",
    "versions",
)


class Project:
    """项目工作区。"""

    SCHEMA_VERSION = "0.1.0"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # ---------------------------------------------------------------- 创建/加载
    @classmethod
    def create(cls, root: Path, name: str, *, template: str | None = None) -> Project:
        root = Path(root)
        if root.exists() and any(root.iterdir()):
            raise ConfigError(f"目标目录非空：{root}")
        project = cls(root)
        for directory in STATE_DIRS:
            (root / directory).mkdir(parents=True, exist_ok=True)
        manifest = ProjectManifest(
            name=name,
            schema_version=cls.SCHEMA_VERSION,
            created_at=datetime.now(timezone.utc).isoformat(),
            template=template,
        )
        project.save_manifest(manifest)
        return project

    @classmethod
    def load(cls, root: Path) -> Project:
        root = Path(root)
        manifest_path = root / "project.json"
        if not manifest_path.is_file():
            raise ConfigError(f"{root} 不是 MotionNest 项目（缺少 project.json）")
        project = cls(root)
        manifest = project.manifest  # 触发校验
        if manifest.schema_version != cls.SCHEMA_VERSION:
            raise ConfigError(
                f"项目 schema 版本不匹配：{manifest.schema_version} != {cls.SCHEMA_VERSION}"
            )
        return project

    # ---------------------------------------------------------------- 清单
    @property
    def manifest(self) -> ProjectManifest:
        try:
            return ProjectManifest.model_validate_json(
                (self.root / "project.json").read_text(encoding="utf-8")
            )
        except ValidationError as exc:
            raise ConfigError(f"project.json 非法：{exc}") from exc

    def save_manifest(self, manifest: ProjectManifest) -> None:
        (self.root / "project.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_manifest(self, **changes: object) -> ProjectManifest:
        manifest = self.manifest.model_copy(update=changes)
        self.save_manifest(manifest)
        return manifest

    # ---------------------------------------------------------------- 路径
    def path(self, *parts: str) -> Path:
        target = self.root.joinpath(*parts)
        resolved = target.resolve()
        if not str(resolved).startswith(str(self.root.resolve())):
            raise ConfigError(f"路径越出工作区：{target}")
        return target

    def artifact_path(self, artifact: str) -> Path:
        """按工件名取得惯用路径（data/plan/script/...）。"""
        return self.path(artifact)

    def write_json(self, relpath: str, payload: object) -> Path:
        target = self.path(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return target

    def read_json(self, relpath: str) -> object:
        return json.loads(self.path(relpath).read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- 版本
    def snapshot(self, label: str) -> str:
        version_id = snapshot_project(self.root, label)
        self.update_manifest(current_version=version_id)
        return version_id

    def undo(self) -> str | None:
        snapshots = list_snapshots(self.root)
        if len(snapshots) < 2:
            return None  # 至少保留一个快照，无法继续回退
        target = snapshots[-2]
        restore_snapshot(self.root, target.id)
        self.update_manifest(current_version=target.id)
        return target.id

    def snapshots(self) -> list:
        return list_snapshots(self.root)

    # ---------------------------------------------------------------- 审批
    def approve(self, artifact: str, note: str = "") -> None:
        """人工签批一个工件（配乐/运镜/终审报告等）。"""
        manifest = self.manifest
        approvals = dict(manifest.approvals)
        approvals[artifact] = f"{note} @ {datetime.now(timezone.utc).isoformat()}"
        self.update_manifest(approvals=approvals)

    def is_approved(self, artifact: str) -> bool:
        return artifact in self.manifest.approvals


def _jsonable(payload: object) -> object:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")  # type: ignore[attr-defined]
    return payload
