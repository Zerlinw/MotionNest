"""评论收件箱：位置 → 时间 → 图层 → 证据 的可逆映射。

这是"指着画面改"的工程化：
- 用户在预览界面上点击并留评论，评论携带 时间点/坐标/命中图层；
- hit_test 按层序做几何命中（后生成的图层在上，命中优先）；
- Agent 侧 claim_next 领取评论 → 定位 → 改稿 → resolve 回报。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.schemas import Layer


@dataclass(slots=True)
class Comment:
    id: str
    created_at: str
    scene_id: str
    time_ms: int
    x: float
    y: float
    element_id: str | None      # 命中图层 ID（可由 hit_test 推导，也可由编辑器直接给出）
    text: str
    status: str = "open"        # open | claimed | resolved | rejected
    note: str = ""              # agent 的回报说明


class Inbox:
    """基于 JSONL 的评论收件箱（append-only，可审计）。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- 读写
    def _read_all(self) -> list[Comment]:
        if not self.path.is_file():
            return []
        comments: list[Comment] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                comments.append(Comment(**json.loads(line)))
        return comments

    def _rewrite(self, comments: list[Comment]) -> None:
        self.path.write_text(
            "".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in comments),
            encoding="utf-8",
        )

    # ---------------------------------------------------------------- 操作
    def post(
        self,
        text: str,
        *,
        scene_id: str,
        time_ms: int,
        x: float,
        y: float,
        element_id: str | None = None,
    ) -> Comment:
        comment = Comment(
            id=f"comment-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc).isoformat(),
            scene_id=scene_id,
            time_ms=time_ms,
            x=x,
            y=y,
            element_id=element_id,
            text=text,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(comment), ensure_ascii=False) + "\n")
        return comment

    def list(self, status: str | None = None) -> list[Comment]:
        comments = self._read_all()
        return [c for c in comments if status is None or c.status == status]

    def claim_next(self) -> Comment | None:
        comments = self._read_all()
        for comment in comments:
            if comment.status == "open":
                comment.status = "claimed"
                self._rewrite(comments)
                return comment
        return None

    def resolve(self, comment_id: str, *, status: str = "resolved", note: str = "") -> Comment:
        comments = self._read_all()
        for comment in comments:
            if comment.id == comment_id:
                comment.status = status
                comment.note = note
                self._rewrite(comments)
                return comment
        raise KeyError(f"评论不存在：{comment_id}")


def hit_test(
    layers: list[Layer],
    x: float,
    y: float,
    *,
    viewport_width: float,
    viewport_height: float,
) -> str | None:
    """屏幕坐标 → 图层 ID。坐标以视口左上为原点，归一化到 0~1 后按层序倒序命中。"""
    nx, ny = x / viewport_width, y / viewport_height
    for layer in reversed(layers):
        props: dict[str, Any] = layer.props
        left = float(props.get("x", 0)) / viewport_width
        top = float(props.get("y", 0)) / viewport_height
        width = float(props.get("w", props.get("width", 0.2))) / viewport_width
        height = float(props.get("h", props.get("height", 0.1))) / viewport_height
        if left <= nx <= left + width and top <= ny <= top + height:
            return layer.id
    return None
