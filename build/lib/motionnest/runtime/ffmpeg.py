"""FFmpeg 子进程封装（受控调用，不拼接用户输入到 shell）。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def encode_frames(frames_dir: Path, output: Path, *, fps: int = 30) -> Path:
    """把帧目录（frame-%04d.png）编码为 MP4。"""
    if not ffmpeg_available():
        raise RuntimeError("未找到 ffmpeg，请先安装并加入 PATH")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(Path(frames_dir) / "frame-%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 编码失败：{result.stderr[-500:]}")
    return output


def probe_duration(path: Path) -> float | None:
    """读取媒体时长（秒）。"""
    if not ffmpeg_available():
        return None
    command = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None
