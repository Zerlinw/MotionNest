"""时间轴：把镜头序列变成可复算的时间码。"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.schemas import Shot


@dataclass(frozen=True, slots=True)
class Timeline:
    """固定帧时钟的时间轴。给定 fps 与镜头序列，任何帧号可稳定复现。"""

    fps: int
    shots: tuple[Shot, ...]

    @property
    def total_ms(self) -> int:
        return sum(shot.duration_ms for shot in self.shots)

    @property
    def frame_count(self) -> int:
        return int(self.total_ms / 1000 * self.fps)

    def shot_at(self, time_ms: int) -> Shot | None:
        cursor = 0
        for shot in self.shots:
            if cursor <= time_ms < cursor + shot.duration_ms:
                return shot
            cursor += shot.duration_ms
        return None

    @staticmethod
    def timecode(time_ms: int) -> str:
        minutes, remainder = divmod(max(0, int(time_ms)), 60_000)
        seconds, millis = divmod(remainder, 1000)
        return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
