"""版本快照：可回滚的单位是完整项目状态，而非命令历史。

每次"批准"都生成一个内容寻址快照（versions/<hash>/），
记录 data/plan/script/composition/reviews/sources 的全量状态；
restore 整体还原，diff 列出文件级差异。
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_DIRS = ("data", "plan", "script", "composition", "reviews", "sources", "studio")


@dataclass(frozen=True, slots=True)
class SnapshotInfo:
    id: str
    label: str
    created_at: str
    path: Path


def _dir_digest(root: Path, directories: tuple[str, ...]) -> str:
    hasher = hashlib.sha256()
    for name in directories:
        base = root / name
        if not base.is_dir():
            continue
        for file_path in sorted(base.rglob("*")):
            if file_path.is_file():
                rel = file_path.relative_to(root).as_posix()
                hasher.update(rel.encode("utf-8"))
                hasher.update(file_path.read_bytes())
    return hasher.hexdigest()[:16]


def snapshot_project(root: Path, label: str) -> str:
    """把当前状态拷贝进 versions/<hash>/，返回快照 ID。"""
    root = Path(root)
    state_hash = _dir_digest(root, SNAPSHOT_DIRS)
    versions_dir = root / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{state_hash}"
    target = versions_dir / snapshot_id
    if target.exists():
        return snapshot_id  # 状态未变化，复用同一快照
    for name in SNAPSHOT_DIRS:
        source = root / name
        if source.is_dir():
            shutil.copytree(source, target / name)
    (target / "snapshot.json").write_text(
        json.dumps(
            {"id": snapshot_id, "label": label, "created_at": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return snapshot_id


def list_snapshots(root: Path) -> list[SnapshotInfo]:
    versions_dir = Path(root) / "versions"
    if not versions_dir.is_dir():
        return []
    snapshots: list[SnapshotInfo] = []
    for entry in sorted(versions_dir.iterdir()):
        meta_path = entry / "snapshot.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        snapshots.append(
            SnapshotInfo(
                id=meta["id"], label=meta.get("label", ""), created_at=meta.get("created_at", ""), path=entry
            )
        )
    # 按创建时间排序（ID 含秒级时间戳，同一秒内需靠 created_at 的微秒精度保证次序）
    snapshots.sort(key=lambda s: (s.created_at, s.id))
    return snapshots


def restore_snapshot(root: Path, snapshot_id: str) -> None:
    """整库还原到指定快照（先清空后拷回）。"""
    root = Path(root)
    source = root / "versions" / snapshot_id
    if not source.is_dir():
        raise FileNotFoundError(f"快照不存在：{snapshot_id}")
    for name in SNAPSHOT_DIRS:
        target = root / name
        if target.is_dir():
            shutil.rmtree(target)
        snap_dir = source / name
        if snap_dir.is_dir():
            shutil.copytree(snap_dir, target)


def diff_snapshots(root: Path, id_a: str, id_b: str) -> dict[str, list[str]]:
    """文件级 diff：added / removed / changed。"""
    root = Path(root)
    dir_a, dir_b = root / "versions" / id_a, root / "versions" / id_b

    def files_of(base: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for name in SNAPSHOT_DIRS:
            snap = base / name
            if not snap.is_dir():
                continue
            for file_path in sorted(snap.rglob("*")):
                if file_path.is_file() and file_path.name != "snapshot.json":
                    rel = file_path.relative_to(base).as_posix()
                    result[rel] = hashlib.sha256(file_path.read_bytes()).hexdigest()
        return result

    files_a, files_b = files_of(dir_a), files_of(dir_b)
    return {
        "added": sorted(set(files_b) - set(files_a)),
        "removed": sorted(set(files_a) - set(files_b)),
        "changed": sorted(k for k in set(files_a) & set(files_b) if files_a[k] != files_b[k]),
    }
