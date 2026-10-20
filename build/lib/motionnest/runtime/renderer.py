"""本机渲染层：Composition JSON → HTML 场景 → （可选）截帧 → MP4。

渲染哲学：
- 场景树是唯一事实源，HTML/帧/MP4 都是它的投影；
- 图层带稳定 data-mn-id，供 studio 坐标命中与定点改稿；
- 动画全部走 CSS/Web Animations，可被 JS 暂停并 seek 到任意时刻
  （这是帧级复现与"关键帧自查"的基础）；
- 未安装 playwright 时自动降级：只产出 HTML 与渲染清单，不报错。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from ..core.schemas import Composition, Scene

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: __BG__; overflow: hidden; }
  #stage { position: relative; width: __WIDTH__px; height: __HEIGHT__px; overflow: hidden;
           font-family: "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
  .mn-layer { position: absolute; will-change: transform, opacity; }
  .mn-text { color: #f5f7fa; font-weight: 600; text-shadow: 0 2px 12px rgba(0,0,0,.45); }
  .mn-caption { background: rgba(11,14,20,.55); padding: .4em .8em; border-radius: .3em; }
  @keyframes mn-fade { from { opacity: 0 } to { opacity: 1 } }
  @keyframes mn-slide-up { from { opacity: 0; transform: translateY(60px) } to { opacity: 1; transform: none } }
  @keyframes mn-slide-down { from { opacity: 0; transform: translateY(-60px) } to { opacity: 1; transform: none } }
  @keyframes mn-scale { from { opacity: 0; transform: scale(.8) } to { opacity: 1; transform: none } }
  @keyframes mn-draw { from { clip-path: inset(0 100% 0 0) } to { clip-path: inset(0 0 0 0) } }
  @keyframes mn-count-up { from { opacity: 0; transform: translateY(24px) } to { opacity: 1; transform: none } }
</style>
</head>
<body>
<div id="stage"></div>
<script>
const SCENE = __SCENE_JSON__;
const COMP = __COMP_JSON__;
const PALETTE = ["#4f8ef7", "#f7724f", "#38c6a4", "#b478f0", "#f7c948"];
function chartSVG(p) {
  const series = (p.series || []).map(s => ({ name: String(s.name), value: Number(s.value) || 0 }));
  if (!series.length) return '<svg width="100%" height="100%"></svg>';
  const W = COMP.width, H = COMP.height, pad = 120;
  const max = Math.max(...series.map(s => Math.abs(s.value)), 1);
  const bw = (W - pad * 2) / series.length;
  let bars = "";
  series.forEach((s, i) => {
    const h = (Math.abs(s.value) / max) * (H - pad * 2);
    const x = pad + i * bw + bw * 0.15, y = H - pad - h;
    bars += `<rect x="${x}" y="${y}" width="${bw * 0.7}" height="${h}" rx="8" fill="${PALETTE[i % PALETTE.length]}"/>`;
    bars += `<text x="${x + bw * 0.35}" y="${H - pad + 36}" fill="#cdd6e4" font-size="26" text-anchor="middle">${s.name}</text>`;
    bars += `<text x="${x + bw * 0.35}" y="${y - 14}" fill="#f5f7fa" font-size="28" text-anchor="middle">${s.value}</text>`;
  });
  return `<svg width="${W}" height="${H}">${bars}</svg>`;
}
function applyAnimation(el, anim) {
  const type = (anim && anim.enter) || "fade";
  const dur = (anim && anim.duration_ms) || 600;
  const name = { fade: "mn-fade", "slide-up": "mn-slide-up", "slide-down": "mn-slide-down",
                 scale: "mn-scale", draw: "mn-draw", "count-up": "mn-count-up" }[type] || "mn-fade";
  el.style.animation = `${name} ${dur}ms cubic-bezier(.22,.61,.36,1) both`;
}
function renderScene(stage, scene) {
  stage.innerHTML = "";
  (scene.layers || []).forEach(layer => {
    const el = document.createElement("div");
    el.className = "mn-layer";
    el.id = layer.id;
    el.dataset.mnId = layer.id;
    const p = layer.props || {};
    if (layer.type === "chart") {
      el.innerHTML = chartSVG(p);
      el.style.inset = "0";
    } else if (layer.type === "image") {
      const fit = p.fit || "cover";
      el.innerHTML = `<img src="${p.src}" alt="" style="width:100%;height:100%;`
        + `object-fit:${fit};border-radius:${p.radius || 12}px;display:block">`;
      el.style.left = (p.x || 0) + "px";
      el.style.top = (p.y || 0) + "px";
      el.style.width = (p.w || 400) + "px";
      el.style.height = (p.h || 300) + "px";
    } else if (layer.type === "text") {
      el.classList.add("mn-text");
      if (p.caption !== false) el.classList.add("mn-caption");
      el.textContent = p.text || "";
      el.style.left = (p.x || 0) + "px";
      el.style.top = (p.y || 0) + "px";
      el.style.fontSize = (p.size || 36) + "px";
      if (p.color) el.style.color = p.color;
      if (p.width) el.style.width = p.width + "px";
      if (p.align === "center") { el.style.left = "0"; el.style.textAlign = "center"; }
      el.style.whiteSpace = "pre-line";
    } else {
      el.style.left = (p.x || 0) + "px";
      el.style.top = (p.y || 0) + "px";
      el.style.width = (p.w || 200) + "px";
      el.style.height = (p.h || 200) + "px";
      el.style.background = p.color || "#4f8ef7";
      el.style.borderRadius = (p.radius || 12) + "px";
    }
    applyAnimation(el, layer.animation || {});
    stage.appendChild(el);
  });
}
renderScene(document.getElementById("stage"), SCENE);
</script>
</body>
</html>
"""


@dataclass(slots=True)
class RenderResult:
    status: str                       # video | html-only | manifest
    outputs: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def scene_frame_counts(durations_ms: list[int], fps: int) -> list[int]:
    """按累计时间分配场景帧数，保证总计 == round(总时长 * fps / 1000)。

    逐场景 int(ms/1000*fps) 截断会在 3750ms 等时长上丢帧（30fps 下 112.5→112），
    累计取整把零头分摊到相邻场景，30s@30fps 严格 900 帧、30s@5fps 严格 150 帧。
    """
    counts: list[int] = []
    previous = 0
    cumulative = 0
    for duration_ms in durations_ms:
        cumulative += int(duration_ms)
        boundary = round(cumulative * fps / 1000)
        counts.append(boundary - previous)
        previous = boundary
    return counts


def _clear_frames(frames_dir: Path) -> None:
    """清掉上一轮残留的帧，避免帧数校验把旧帧算进来。"""
    if frames_dir.is_dir():
        for stale in frames_dir.glob("frame-*.png"):
            stale.unlink(missing_ok=True)


def _launch_browser(playwright):
    """优先用 Playwright 自带 Chromium；缺失时回退系统 Edge/Chrome（免下载浏览器）。

    打包版（PyInstaller onefile）通常不带 Chromium 浏览器二进制，但 Windows 自带 Edge，
    因此 channel 回退可让 exe 直接工作；也可用 MNEST_BROWSER_CHANNEL 显式指定。
    """
    channel = os.environ.get("MNEST_BROWSER_CHANNEL", "").strip()
    attempts: list[str | None] = ([channel] if channel else []) + [None, "msedge", "chrome"]
    last_error: Exception | None = None
    for candidate in attempts:
        try:
            if candidate:
                return playwright.chromium.launch(channel=candidate)
            return playwright.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - 逐个回退，最终统一报错
            last_error = exc
    raise RuntimeError(
        "无法启动浏览器：请执行 playwright install chromium，或安装 Edge/Chrome，"
        "或设置 MNEST_BROWSER_CHANNEL=msedge"
    ) from last_error


class Renderer:
    """场景渲染器。"""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)

    # ---------------------------------------------------------------- HTML
    def write_scene(self, scene: Scene, composition: Composition) -> Path:
        html = (
            _PAGE_TEMPLATE.replace("__TITLE__", scene.id)
            .replace("__WIDTH__", str(composition.width))
            .replace("__HEIGHT__", str(composition.height))
            .replace("__BG__", composition.background or "#0b0e14")
            .replace("__SCENE_JSON__", json.dumps(scene.model_dump(mode="json"), ensure_ascii=False))
            .replace("__COMP_JSON__", json.dumps(composition.model_dump(mode="json"), ensure_ascii=False))
        )
        path = self.output_dir / f"{scene.id}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return path

    def write_all(self, composition: Composition) -> list[Path]:
        return [self.write_scene(scene, composition) for scene in composition.scenes]

    # ---------------------------------------------------------------- 截帧
    def capture_frames(
        self,
        scene_html: Path,
        frames_dir: Path,
        *,
        fps: int,
        frame_count: int | None = None,
        duration_ms: int = 0,
        width: int,
        height: int,
        frame_offset: int = 0,
        max_frames: int = 900,
    ) -> int:
        """用无头浏览器逐帧截取（暂停 CSS 动画并 seek 到目标时刻）。

        frame_count 由调用方按累计时间精确分配；仅传 duration_ms 时保留旧的截断语义。
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("未安装 playwright（pip install motionnest[render] 且 playwright install chromium）") from exc

        frames_dir = Path(frames_dir)
        frames_dir.mkdir(parents=True, exist_ok=True)
        total = frame_count if frame_count is not None else min(int(duration_ms / 1000 * fps), max_frames)
        with sync_playwright() as playwright:
            browser = _launch_browser(playwright)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(Path(scene_html).resolve().as_uri())
            page.wait_for_timeout(200)
            for index in range(total):
                t_ms = int(index * 1000 / fps)
                page.evaluate(
                    "(t) => { document.getAnimations().forEach(a => { try { a.pause(); a.currentTime = t; } catch (e) {} }); }",
                    t_ms,
                )
                page.wait_for_timeout(30)
                page.screenshot(path=str(frames_dir / f"frame-{index + frame_offset:04d}.png"))
            browser.close()
        return total

    # ---------------------------------------------------------------- 成片
    def render_video(
        self,
        composition: Composition,
        *,
        fps: int | None = None,
        quality: str = "preview",
        strict: bool = False,
    ) -> RenderResult:
        """HTML →（可选逐帧）→ MP4。缺工具时默认降级为 HTML + 清单；strict=True 时抛错。"""
        from .ffmpeg import encode_frames, ffmpeg_available

        fps = fps or composition.fps
        html_paths = self.write_all(composition)
        result = RenderResult(status="html-only", outputs=html_paths)
        if not ffmpeg_available():
            message = "未检测到 ffmpeg：请安装 FFmpeg 并加入 PATH（https://ffmpeg.org/download.html）"
            if strict:
                raise RuntimeError(message)
            result.notes.append(message + "，仅输出 HTML 场景")
            return result
        try:
            import playwright  # noqa: F401
        except ImportError:
            message = "未安装 playwright：请执行 pip install motionnest[render] 且 playwright install chromium"
            if strict:
                raise RuntimeError(message) from None
            result.notes.append(message + "，仅输出 HTML 场景")
            return result

        frames_dir = self.output_dir / "frames"
        _clear_frames(frames_dir)
        offset = 0
        effective_fps = 5 if quality == "preview" else fps
        counts = scene_frame_counts([scene.duration_ms for scene in composition.scenes], effective_fps)
        for html_path, count in zip(html_paths, counts, strict=True):
            offset += self.capture_frames(
                html_path,
                frames_dir,
                fps=effective_fps,
                frame_count=count,
                width=composition.width,
                height=composition.height,
                frame_offset=offset,
            )
        if offset == 0:
            result.notes.append("没有可渲染的帧")
            return result
        video_path = self.output_dir / f"motionnest-{quality}.mp4"
        encode_frames(frames_dir, video_path, fps=effective_fps)
        result.status = "video"
        result.outputs.append(video_path)
        result.notes.append(f"逐帧渲染 {offset} 帧 @ {effective_fps}fps（quality={quality}）")
        return result
