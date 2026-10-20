"""阶段 5-6 · 管线编排与全自动导出。

run_promo() 是桌面端与 CLI 的唯一入口：
    文档解析 → 要点蒸馏 → 固定骨架分镜 → 画面合成 → 逐帧渲染 → 校验导出

契约：
- 输入：文档列表 + 可选素材文件夹/补充说明 + 两个可注入的模型回调
  （chat_fn(system, user) -> str；image_fn(prompt) -> bytes | None）；
- 输出：exports/promo.mp4（单文件成片）+ exports/audit.json（审计清单）；
- 无人工签批；时长硬校验（帧数 + ffprobe），不达标即报错，不静默降级。
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from ..core.project import Project
from ..exceptions import ConfigError
from ..runtime.ffmpeg import probe_duration
from ..runtime.renderer import Renderer
from .compose import FPS, HEIGHT, WIDTH, compose
from .distill import distill_brief
from .intake import parse_documents
from .schemas import PromoBrief, PromoDoc, PromoStoryboard
from .storyboard import TOTAL_DURATION_MS, build_storyboard

MIN_DURATION_S = 29.5
MAX_DURATION_S = 30.5

ChatFn = Callable[[str, str], str]
ImageFn = Callable[[str], "bytes | None"]


def run_promo(
    output_dir: str | Path,
    doc_paths: list[str | Path],
    *,
    asset_dir: str | Path | None = None,
    note: str = "",
    chat_fn: ChatFn | None = None,
    image_fn: ImageFn | None = None,
    chat_model: str = "",
    image_model: str = "",
    quality: str = "final",
    project_name: str = "",
    logger: Callable[[str, str], None] | None = None,
) -> dict:
    """文档 → 30 秒宣传片 MP4。返回结果摘要（含成片与审计路径）。"""
    log = logger or (lambda level, message: None)
    if not doc_paths and not asset_dir:
        raise ConfigError("请至少提供一个文档或素材文件夹")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    project = _create_project(output_root, project_name)
    log("info", f"项目工作区：{project.root}")

    # ---- 1 文档解析（确定性） ----
    doc = parse_documents(doc_paths, project, asset_dir=asset_dir)
    project.write_json("data/docs.json", doc)
    for warning in doc.degraded:
        log("warn", warning)
    log("ok", f"解析完成：{len(doc.sources)} 个文档 / {len(doc.sections)} 个内容块 / {len(doc.images)} 张图片")

    # ---- 2 要点蒸馏（模型，失败降级模板） ----
    brief = distill_brief(doc, note, chat_fn)
    project.write_json("plan/brief.json", brief)
    if brief.source == "template":
        log("warn", "要点蒸馏不可用，已用模板降级（审计中注明）")
    else:
        log("ok", f"要点蒸馏：{brief.product_name}，卖点 {len(brief.selling_points)} 条")

    # ---- 3 固定骨架分镜（时长确定性） ----
    storyboard = build_storyboard(brief, doc, chat_fn)
    storyboard.assert_duration()
    project.write_json("script/promo-storyboard.json", storyboard)
    log("ok", f"分镜：{len(storyboard.shots)} 个镜头，总时长 {storyboard.total_duration_ms}ms")

    # ---- 4 画面合成（匹配确定性 + 可选生图） ----
    saver = _make_image_saver(project, image_fn, log) if image_fn else None
    composition, asset_usage = compose(storyboard, doc, brief, generate_image=saver)
    project.write_json("composition/composition.json", composition)
    renderer = Renderer(project.path("composition", "html"))
    renderer.write_all(composition)
    _stage_assets(project, composition)
    project.snapshot("promo compose")
    matched = sum(1 for v in asset_usage.values() if not v.endswith("svg-fallback"))
    log("ok", f"场景树：{len(composition.scenes)} 个场景，素材命中 {matched} 个镜头")

    # ---- 5 逐帧渲染（缺依赖报错，不降级） ----
    log("info", f"逐帧渲染中（quality={quality}，{WIDTH}×{HEIGHT}）…")
    result = renderer.render_video(composition, quality=quality, strict=True)
    if result.status != "video":
        raise RuntimeError("渲染未产出视频：" + "；".join(result.notes))
    video = result.outputs[-1]
    log("ok", f"渲染完成：{video}")

    # ---- 6 校验导出（全自动） ----
    effective_fps = 5 if quality == "preview" else FPS
    expected_frames = round(TOTAL_DURATION_MS * effective_fps / 1000)
    frames_dir = project.path("composition", "html", "frames")
    actual_frames = _count_frames(frames_dir)
    if actual_frames != expected_frames:
        raise RuntimeError(f"帧数不达标：{actual_frames} != {expected_frames}（30 秒完整性校验失败）")
    duration_s = probe_duration(video)
    if duration_s is not None and not (MIN_DURATION_S <= duration_s <= MAX_DURATION_S):
        raise RuntimeError(f"成片时长 {duration_s:.2f}s 超出 [{MIN_DURATION_S}, {MAX_DURATION_S}]s")

    exports = project.path("exports")
    exports.mkdir(parents=True, exist_ok=True)
    final_mp4 = exports / "promo.mp4"
    shutil.copy2(video, final_mp4)
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": project.manifest.name,
        "output": str(final_mp4),
        "duration_ms": TOTAL_DURATION_MS,
        "duration_s": duration_s,
        "frames": actual_frames,
        "fps": effective_fps,
        "quality": quality,
        "resolution": f"{WIDTH}x{HEIGHT}",
        "sources": doc.sources,
        "assets": asset_usage,
        "brief_source": brief.source,
        "copy_sources": sorted({shot.copy_source for shot in storyboard.shots}),
        "degraded": doc.degraded,
        "chat_model": chat_model,
        "image_model": image_model,
    }
    project.write_json("exports/audit.json", audit)
    project.snapshot("promo export")
    log("ok", f"导出完成：{final_mp4}（{duration_s:.2f}s，{actual_frames} 帧）")

    return {
        "project": str(project.root),
        "video": str(final_mp4),
        "audit": str(project.path("exports", "audit.json")),
        "duration_s": duration_s,
        "frames": actual_frames,
        "shots": len(storyboard.shots),
        "brief": brief.model_dump(mode="json"),
        "degraded": doc.degraded,
    }


# ---------------------------------------------------------------- 内部
def _count_frames(frames_dir: Path) -> int:
    return len(list(Path(frames_dir).glob("frame-*.png")))


def _create_project(output_root: Path, project_name: str) -> Project:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = project_name or f"promo-{stamp}"
    root = output_root / name
    suffix = 1
    while root.exists() and any(root.iterdir()):
        suffix += 1
        root = output_root / f"{name}-{suffix}"
    return Project.create(root, root.name)


def _make_image_saver(
    project: Project, image_fn: ImageFn, log: Callable[[str, str], None]
) -> Callable[[str, str], str | None]:
    """把 image_fn(prompt)->bytes 包装为 compose 需要的 (shot_id, prompt)->assets 名。"""

    def generate(shot_id: str, prompt: str) -> str | None:
        try:
            payload = image_fn(prompt)
        except Exception as exc:  # noqa: BLE001 - 生图失败不阻塞管线
            log("warn", f"{shot_id} 生图失败（{type(exc).__name__}），改用图形兜底")
            return None
        if not payload:
            return None
        name = f"generated/{shot_id}.png"
        destination = project.path("assets", name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return f"assets/{name}"

    return generate


def _stage_assets(project: Project, composition) -> None:
    """把 composition 引用的 assets/ 图片复制到 composition/html/assets/（HTML 相对路径）。"""
    html_dir = project.path("composition", "html")
    for scene in composition.scenes:
        for layer in scene.layers:
            if layer.type != "image":
                continue
            src = str(layer.props.get("src", ""))
            if not src.startswith("assets/"):
                continue
            source = project.root / src
            if not source.is_file():
                raise ConfigError(f"素材缺失：{src}")
            destination = html_dir / src
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def write_brief(path: str | Path, brief: PromoBrief) -> None:
    """工具：单独落盘 brief（CLI 调试用）。"""
    Path(path).write_text(brief.model_dump_json(indent=2), encoding="utf-8")


__all__ = [
    "run_promo",
    "PromoBrief",
    "PromoDoc",
    "PromoStoryboard",
]
