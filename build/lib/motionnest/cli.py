"""mnest 命令行：把 Agent 编排、门禁、渲染、版本串成可审计工作流。

命令总览：
  mnest doctor / models list|check|routes   环境与模型层自检
  mnest new / data add|verify               项目创建与数据门禁
  mnest plan [--approve ID]                 数据解读 → 叙事方向（低成本档）
  mnest compose [--offline]                 分镜 + 初稿动画（低成本档）
  mnest revise "评论" [--scene --layer]     定点改稿（低成本档）
  mnest music / camera / review             强模型档任务（人工签发）
  mnest render / export                     本机渲染与带审计的导出
  mnest inbox post|list|next|done           评论收件箱（指着画面改）
  mnest undo / audit                        回滚与审计
  mnest promo 文档... [--assets DIR]        宣传片管线：文档 → 30 秒 MP4（全自动）
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .agents import (
    Animator,
    CameraDesigner,
    DataInterpreter,
    FinalReviewer,
    MusicDirector,
    Reviser,
    StoryboardAgent,
)
from .agents.storyboard import template_storyboard
from .composition.scenes import apply_patch, template_composition
from .composition.timeline import Timeline
from .core.project import Project
from .core.schemas import (
    Composition,
    DataDictionary,
    DataInsight,
    DataSummary,
    Storyboard,
)
from .data.loader import dictionary_from_summary, load_dictionary, load_table
from .exceptions import HumanReviewRequired, MotionNestError
from .llm.registry import ModelRegistry
from .llm.router import TaskRouter
from .qa.gates import (
    blocking_errors,
    data_gate,
    run_all_gates,
    visual_gate,
)
from .runtime.renderer import Renderer
from .settings import build_stack, load_environment
from .studio.inbox import Inbox

app = typer.Typer(
    name="mnest",
    help="MotionNest（动巢）—— Agent 驱动的动画生成工作台",
    no_args_is_help=True,
    add_completion=False,
)
model_app = typer.Typer(no_args_is_help=True, help="模型层：注册表 / 探测 / 路由")
data_app = typer.Typer(no_args_is_help=True, help="数据：导入 / 校验")
inbox_app = typer.Typer(no_args_is_help=True, help="评论收件箱")
review_app = typer.Typer(no_args_is_help=True, help="终审与人工签批")
app.add_typer(model_app, name="models")
app.add_typer(data_app, name="data")
app.add_typer(inbox_app, name="inbox")
app.add_typer(review_app, name="review")

console = Console()
PROJECT_OPTION = typer.Option(..., "--project", "-p", help="项目目录")


# ================================================================ 全局上下文
@app.callback()
def main(ctx: typer.Context, config: str = typer.Option(None, "--config", help="配置目录（默认自动查找）")) -> None:
    """加载配置，构建 模型注册表 + 任务路由器。"""
    load_environment()
    ctx.obj = build_stack(config)


def _router(ctx: typer.Context) -> TaskRouter:
    return ctx.obj[2]


def _registry(ctx: typer.Context) -> ModelRegistry:
    return ctx.obj[1]


def _project(path: Path) -> Project:
    return Project.load(path)


def _fail(exc: Exception, code: int = 1) -> None:
    console.print(f"[red]错误：{exc}[/red]")
    raise typer.Exit(code)


def _print_response_info(response: object, *, label: str = "调用") -> None:
    if response is None:
        return
    tier = getattr(response, "tier_used", None)
    degraded = getattr(response, "degraded", False)
    signoff = getattr(response, "requires_human_signoff", False)
    model = getattr(response, "model_used", "?")
    latency = getattr(response, "latency_ms", 0)
    line = f"[dim]{label}：模型 {model}（档位 {getattr(tier, 'value', tier)}，{latency}ms）[/dim]"
    if degraded:
        line += " [yellow]! 非首选档位（降级产出）[/yellow]"
    if signoff:
        line += " [yellow]! 需人工签发后才能导出[/yellow]"
    console.print(line)


def _queue_human_review(project: Project, exc: HumanReviewRequired) -> None:
    """强模型不可用：写入人工兜底队列并提示（人工兜底是机制，不是失败）。"""
    project.write_json(
        "reviews/human-queue.json",
        {"task": exc.task, "reason": exc.reason, "at": datetime.now(timezone.utc).isoformat()},
    )
    console.print(f"[yellow]!! {exc}[/yellow]")
    console.print("已写入 reviews/human-queue.json：配置强模型密钥，或由人工完成该环节")


# ================================================================ 环境自检
@app.command()
def doctor(ctx: typer.Context) -> None:
    """环境检查：Python / FFmpeg / Playwright / 配置 / 密钥。"""
    import sys

    from .runtime.ffmpeg import ffmpeg_available

    rows: list[tuple[str, str, str]] = []
    rows.append(("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "OK"))
    has_ffmpeg = ffmpeg_available()
    rows.append(("FFmpeg", "已安装" if has_ffmpeg else "未安装（渲染降级为 HTML）", "OK" if has_ffmpeg else "!"))
    try:
        import playwright  # noqa: F401

        rows.append(("Playwright", "已安装（可逐帧渲染）", "OK"))
    except ImportError:
        rows.append(("Playwright", "未安装（pip install motionnest[render]）", "!"))
    try:
        settings, registry, _ = ctx.obj
        rows.append(("配置", str(settings.config_dir), "OK"))
        for spec in registry.specs():
            ok = registry.key_available(spec.name)
            rows.append((f"密钥 {spec.api_key_env}", f"{spec.name}（{spec.tier}）", "OK" if ok else "X"))
    except Exception as exc:
        rows.append(("配置", str(exc), "X"))

    table = Table("检查项", "状态", "结果")
    for item, detail, mark in rows:
        table.add_row(item, detail, mark)
    console.print(table)
    if any(mark == "X" for _, _, mark in rows):
        raise typer.Exit(1)


# ================================================================ 模型层
@model_app.command("list")
def models_list(ctx: typer.Context) -> None:
    """列出注册表中的全部模型。"""
    registry = _registry(ctx)
    table = Table("逻辑名", "模型 ID", "接口格式", "档位", "密钥", "说明")
    for spec in registry.specs():
        key = "OK" if registry.key_available(spec.name) else "X 未配置"
        table.add_row(spec.name, spec.model_id, spec.provider_format, spec.tier, key, spec.description)
    console.print(table)


@model_app.command("check")
def models_check(ctx: typer.Context, name: str = typer.Argument(None, help="只探测指定逻辑名")) -> None:
    """真实调用探测模型可用性（会消耗少量额度）。"""
    registry = _registry(ctx)
    targets = [name] if name else [spec.name for spec in registry.specs()]
    failed = 0
    for target in targets:
        ok, message = registry.provider(target).healthcheck()
        console.print(f"{'OK' if ok else 'X'} {message}")
        failed += 0 if ok else 1
    if failed:
        raise typer.Exit(1)


@model_app.command("routes")
def models_routes(ctx: typer.Context) -> None:
    """展示任务路由规则与当前生效决策。"""
    router = _router(ctx)
    table = Table("任务", "首选档位", "候选模型", "回退档位", "人工签发", "当前决策")
    for row in router.describe_routes():
        table.add_row(
            row["task"],
            row["preferred_tier"],
            " → ".join(row["candidates"]),
            " → ".join(row["fallback_tiers"]) or "-",
            "是" if row["human_review"] else "否",
            row["current"],
        )
    console.print(table)


# ================================================================ 项目与数据
@app.command()
def new(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="项目名"),
    path: Path = typer.Option(Path("."), "--path", help="父目录"),
    template: str = typer.Option(None, "--template", help="模板（trend/comparison/scorecard/explainer）"),
) -> None:
    """创建新项目工作区。"""
    try:
        project = Project.create(path / name, name, template=template)
    except MotionNestError as exc:
        _fail(exc)
        return
    console.print(f"[green]OK[/green] 已创建项目：{project.root}")
    console.print("下一步：mnest data add <csv> --project " + str(project.root))


@data_app.command("add")
def data_add(
    ctx: typer.Context,
    csv_path: Path = typer.Argument(..., help="CSV/JSON 数据文件"),
    project: Path = PROJECT_OPTION,
    dictionary: Path = typer.Option(None, "--dictionary", help="数据字典 JSON（缺省自动生成）"),
) -> None:
    """导入数据并跑数据门禁（不过门禁不允许进入后续流程）。"""
    proj = _project(project)
    try:
        records, summary = load_table(csv_path)
        if dictionary:
            data_dict = load_dictionary(dictionary)
        else:
            data_dict = dictionary_from_summary(summary, source=f"local:{csv_path.name}")
        gate = data_gate(summary, data_dict)
    except MotionNestError as exc:
        _fail(exc)
        return

    for warning in gate.warnings:
        console.print(f"[yellow]! {warning}[/yellow]")
    if not gate.passed:
        for error in gate.errors:
            console.print(f"[red]X {error}[/red]")
        raise typer.Exit(1)

    snapshot_dir = proj.path("data", "snapshot")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(csv_path, snapshot_dir / csv_path.name)
    proj.write_json("data/summary.json", summary)
    proj.write_json("data/dictionary.json", data_dict)
    proj.snapshot(f"data add {csv_path.name}")
    console.print(f"[green]OK[/green] 数据门禁通过：{summary.rows} 行 × {len(summary.columns)} 列")


@data_app.command("verify")
def data_verify(ctx: typer.Context, project: Path = PROJECT_OPTION) -> None:
    """对已导入数据重跑数据门禁。"""
    proj = _project(project)
    summary = DataSummary.model_validate(proj.read_json("data/summary.json"))
    data_dict = DataDictionary.model_validate_json((proj.root / "data" / "dictionary.json").read_text(encoding="utf-8"))
    gate = data_gate(summary, data_dict)
    for warning in gate.warnings:
        console.print(f"[yellow]! {warning}[/yellow]")
    if not gate.passed:
        for error in gate.errors:
            console.print(f"[red]X {error}[/red]")
        raise typer.Exit(1)
    console.print("[green]OK 数据门禁通过[/green]")


# ================================================================ 叙事与合成
@app.command()
def plan(
    ctx: typer.Context,
    project: Path = PROJECT_OPTION,
    approve: str = typer.Option(None, "--approve", help="批准某个候选 ID（如 cand-1）"),
    offline: bool = typer.Option(False, "--offline", help="不调用模型，用确定性模板直出"),
) -> None:
    """数据解读 → 多个叙事候选（低成本档，全自动）。"""
    proj = _project(project)
    router = _router(ctx)
    summary = DataSummary.model_validate(proj.read_json("data/summary.json"))
    data_dict = DataDictionary.model_validate_json((proj.root / "data" / "dictionary.json").read_text(encoding="utf-8"))
    brief_path = proj.root / "plan" / "brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.is_file() else {
        "goal": "把关键数据结论讲清楚",
        "audience": "general",
        "platform": "16:9",
    }
    if offline:
        from .agents.data_interpreter import template_insight

        insight = template_insight(summary, data_dict)
        response = None
        console.print("[dim]plan：--offline 确定性模板（未调用模型）[/dim]")
    else:
        agent = DataInterpreter(router)
        try:
            insight, response = agent.run(summary, data_dict, brief)
        except MotionNestError as exc:
            _fail(exc)
            return
        _print_response_info(response, label="数据解读")
    proj.write_json("plan/insights.json", insight)
    proj.write_json("plan/brief.json", brief)
    _print_response_info(response, label="数据解读")
    console.print(f"\n[bold]总体解读[/bold]：{insight.summary}\n")
    for candidate in insight.candidates:
        console.print(f"[bold cyan]{candidate.id}[/bold cyan] {candidate.title}")
        console.print(f"  论点：{candidate.thesis}")
        console.print(f"  受众：{candidate.audience}｜关键数字：{'、'.join(candidate.key_numbers) or '-'}")
        ignored = "、".join(candidate.ignored_info) or "-"
        risks = "、".join(candidate.risks) or "-"
        console.print(f"  刻意忽略：{ignored}｜风险：{risks}")
    proj.snapshot("plan")
    if approve:
        if approve not in {c.id for c in insight.candidates}:
            _fail(f"候选不存在：{approve}")
            return
        proj.write_json("plan/approved.json", {"candidate_id": approve})
        proj.snapshot(f"approve {approve}")
        console.print(f"[green]OK 已批准方向 {approve}，可运行 mnest compose[/green]")


@app.command()
def compose(
    ctx: typer.Context,
    project: Path = PROJECT_OPTION,
    duration: int = typer.Option(30000, "--duration", help="目标时长（毫秒）"),
    fps: int = typer.Option(30, "--fps"),
    width: int = typer.Option(1920, "--width"),
    height: int = typer.Option(1080, "--height"),
    offline: bool = typer.Option(False, "--offline", help="不调用模型，用确定性模板直出"),
) -> None:
    """分镜脚本 → 初稿动画场景树（低成本档；--offline 走确定性模板）。"""
    proj = _project(project)
    router = _router(ctx)
    approved_path = proj.root / "plan" / "approved.json"
    if not approved_path.is_file():
        _fail("尚未批准叙事方向：先运行 mnest plan --approve <id>")
        return
    candidate_id = json.loads(approved_path.read_text(encoding="utf-8"))["candidate_id"]
    insight = DataInsight.model_validate(proj.read_json("plan/insights.json"))

    constraints = {"target_duration_ms": duration, "platform": f"{width}:{height}", "fps": fps}
    if offline:
        storyboard = template_storyboard(insight, candidate_id, duration_ms=duration)
        console.print("[dim]compose：--offline 确定性模板（未调用模型）[/dim]")
    else:
        try:
            storyboard, response = StoryboardAgent(router).run(insight, candidate_id, constraints)
            _print_response_info(response, label="分镜脚本")
        except MotionNestError as exc:
            _fail(exc)
            return
    proj.write_json("script/storyboard.json", storyboard)

    if offline:
        composition = template_composition(storyboard, fps=fps, width=width, height=height)
    else:
        try:
            composition, response = Animator(router).run(storyboard, fps=fps, width=width, height=height)
            _print_response_info(response, label="初稿动画")
        except MotionNestError as exc:
            _fail(exc)
            return
    gate = visual_gate(composition)
    for warning in gate.warnings:
        console.print(f"[yellow]! {warning}[/yellow]")
    if not gate.passed:
        for error in gate.errors:
            console.print(f"[red]X {error}[/red]")
        raise typer.Exit(1)

    proj.write_json("composition/composition.json", composition)
    html_paths = Renderer(proj.path("composition", "html")).write_all(composition)
    proj.snapshot("compose")
    timeline = Timeline(fps, tuple(storyboard.normalized_shots()))
    console.print(
        f"[green]OK[/green] 初稿完成：{len(storyboard.shots)} 镜头 / "
        f"{Timeline.timecode(timeline.total_ms)} / {len(composition.scenes)} 场景，"
        f"HTML 预览 {len(html_paths)} 个（composition/html/）"
    )


@app.command()
def revise(
    ctx: typer.Context,
    text: str = typer.Argument(..., help="评论内容，如：标题里的百分比和数据不一致"),
    project: Path = PROJECT_OPTION,
    scene: str = typer.Option(None, "--scene", help="目标场景 ID"),
    layer: str = typer.Option(None, "--layer", help="目标图层 ID"),
    element: str = typer.Option(None, "--element", help="元素 ID（等价于 --layer，自动推导 --scene）"),
) -> None:
    """定点改稿：评论 → 只改目标图层（低成本档）。"""
    proj = _project(project)
    router = _router(ctx)
    composition = Composition.model_validate(proj.read_json("composition/composition.json"))
    layer_id = layer or element
    scene_id = scene
    if layer_id and not scene_id:
        for candidate_scene in composition.scenes:
            if any(item.id == layer_id for item in candidate_scene.layers):
                scene_id = candidate_scene.id
                break
    if not (scene_id and layer_id):
        _fail("请通过 --scene/--layer 或 --element 指定修改目标")
        return
    try:
        patch, response = Reviser(router).run(text, composition, scene_id=scene_id, layer_id=layer_id)
    except MotionNestError as exc:
        _fail(exc)
        return
    updated, touches_data = apply_patch(composition, patch)
    proj.write_json("composition/composition.json", updated)
    proj.snapshot(f"revise {scene_id}/{layer_id}")
    _print_response_info(response, label="动画改稿")
    changes = json.dumps(patch.changes, ensure_ascii=False)
    console.print(f"[green]OK[/green] 已应用补丁：{patch.scene_id}/{patch.layer_id} → {changes}")
    console.print(f"  理由：{patch.reason}")
    if touches_data:
        console.print("[yellow]! 改动触及数据层：请先 mnest data verify，再 mnest review，[/yellow]")
        console.print("[yellow]  通过后才能导出[/yellow]")


# ================================================================ 强模型档任务
@app.command()
def music(
    ctx: typer.Context,
    project: Path = PROJECT_OPTION,
    brief: str = typer.Option("{}", "--brief", help="JSON 创作约束"),
) -> None:
    """配乐审美规划（强模型档；模型无听觉，产出必须人工签发）。"""
    proj = _project(project)
    router = _router(ctx)
    storyboard = Storyboard.model_validate(proj.read_json("script/storyboard.json"))
    try:
        plan, response = MusicDirector(router).run(storyboard, json.loads(brief))
    except HumanReviewRequired as exc:
        _queue_human_review(proj, exc)
        raise typer.Exit(2) from exc
    except MotionNestError as exc:
        _fail(exc)
        return
    proj.write_json("reviews/music-plan.json", plan)
    _print_response_info(response, label="配乐审美")
    console.print(
        f"[green]OK[/green] 配乐规划已生成：tempo={plan.tempo_bpm}，"
        f"{len(plan.sections)} 个段落，{len(plan.sfx_events)} 个音效点"
    )
    console.print("[yellow]! 模型没有听觉：请人工试听确认后[/yellow]")
    console.print("[yellow]  执行 mnest review approve reviews/music-plan.json[/yellow]")


@app.command()
def camera(
    ctx: typer.Context,
    project: Path = PROJECT_OPTION,
    scene_id: str = typer.Option(..., "--scene", help="场景 ID"),
    complexity: str = typer.Option("complex", "--complexity", help="simple=确定性模板 / complex=强模型"),
) -> None:
    """三维运镜设计（简单走模板，复杂走强模型 + 人工签发）。"""
    proj = _project(project)
    router = _router(ctx)
    composition = Composition.model_validate(proj.read_json("composition/composition.json"))
    scene = composition.find_scene(scene_id)
    try:
        move, response = CameraDesigner(router).run(scene, {"complexity": complexity, "subject": "chart"})
    except HumanReviewRequired as exc:
        _queue_human_review(proj, exc)
        raise typer.Exit(2) from exc
    except MotionNestError as exc:
        _fail(exc)
        return
    moves_path = proj.root / "reviews" / "camera-moves.json"
    moves = json.loads(moves_path.read_text(encoding="utf-8")) if moves_path.is_file() else []
    moves.append(move.model_dump(mode="json"))
    proj.write_json("reviews/camera-moves.json", moves)
    _print_response_info(response, label="三维运镜")
    console.print(f"[green]OK[/green] 运镜已生成：{move.shot_id} {move.move_type}（{move.generated_by}）")
    if move.generated_by == "strong-model":
        console.print("[yellow]! 复杂运镜需人工确认：mnest review approve reviews/camera-moves.json[/yellow]")


@review_app.command("report")
def review_report(ctx: typer.Context, project: Path = PROJECT_OPTION) -> None:
    """最终成片校对（强模型档 + 门禁汇总；报告需人工签发）。"""
    proj = _project(project)
    router = _router(ctx)
    composition = Composition.model_validate(proj.read_json("composition/composition.json"))
    insight = DataInsight.model_validate(proj.read_json("plan/insights.json"))
    summary = DataSummary.model_validate(proj.read_json("data/summary.json"))
    data_dict = DataDictionary.model_validate_json((proj.root / "data" / "dictionary.json").read_text(encoding="utf-8"))
    approvals = proj.manifest.approvals
    gates = run_all_gates(summary=summary, dictionary=data_dict, insight=insight, composition=composition, approvals=approvals)
    try:
        report, response = FinalReviewer(router).run(composition, insight, gates)
    except HumanReviewRequired as exc:
        _queue_human_review(proj, exc)
        raise typer.Exit(2) from exc
    except MotionNestError as exc:
        _fail(exc)
        return
    proj.write_json("reviews/review-report.json", report)
    _print_response_info(response, label="成片终审")
    for issue in report.issues:
        color = {"blocking": "red", "warning": "yellow", "suggestion": "dim"}.get(issue.severity, "dim")
        console.print(f"[{color}]● {issue.severity} {issue.target}：{issue.message}[/{color}]")
        if issue.suggestion:
            console.print(f"    建议：{issue.suggestion}")
    if report.passed:
        console.print("[green]OK 终审通过（仍需人工签发）：mnest review approve reviews/review-report.json[/green]")
    else:
        console.print("[red]X 存在 blocking 问题，修复前不得导出[/red]")


@review_app.command("approve")
def review_approve(
    ctx: typer.Context,
    project: Path = PROJECT_OPTION,
    artifact: str = typer.Argument(..., help="工件路径，如 reviews/music-plan.json"),
    note: str = typer.Option("", "--note"),
) -> None:
    """人工签批工件（配乐 / 运镜 / 终审报告）。"""
    proj = _project(project)
    if not (proj.root / artifact).is_file():
        _fail(f"工件不存在：{artifact}")
        return
    proj.approve(artifact, note or "approved")
    console.print(f"[green]OK 已签批 {artifact}[/green]")


# ================================================================ 渲染与导出
@app.command()
def render(
    ctx: typer.Context,
    project: Path = PROJECT_OPTION,
    quality: str = typer.Option("preview", "--quality", help="preview=5fps 关键帧 / final=全帧率"),
) -> None:
    """本机渲染：HTML 场景 →（可选逐帧）→ MP4。"""
    proj = _project(project)
    composition = Composition.model_validate(proj.read_json("composition/composition.json"))
    renderer = Renderer(proj.path("composition", "html"))
    result = renderer.render_video(composition, quality=quality)
    for note in result.notes:
        console.print(f"[yellow]! {note}[/yellow]")
    for output in result.outputs:
        console.print(f"[green]OK[/green] {output}")
    if result.status != "video":
        console.print("[dim]提示：pip install motionnest[render] 并安装 Chromium 后可逐帧渲染出 MP4[/dim]")


@app.command()
def export(ctx: typer.Context, project: Path = PROJECT_OPTION) -> None:
    """导出正式成片：四道门禁 + 人工签批 + 审计清单，缺一不可。"""
    proj = _project(project)
    composition = Composition.model_validate(proj.read_json("composition/composition.json"))
    insight = DataInsight.model_validate(proj.read_json("plan/insights.json"))
    summary = DataSummary.model_validate(proj.read_json("data/summary.json"))
    data_dict = DataDictionary.model_validate_json((proj.root / "data" / "dictionary.json").read_text(encoding="utf-8"))
    approvals = proj.manifest.approvals
    gates = run_all_gates(summary=summary, dictionary=data_dict, insight=insight, composition=composition, approvals=approvals)
    for gate in gates:
        mark = "OK" if gate.passed else "X"
        console.print(f"{mark} {gate.gate} 门禁" + (f"：{gate.errors[0]}" if gate.errors else ""))
    errors = blocking_errors(gates)
    if errors:
        console.print("[red]导出被拦截：[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)

    exports = proj.path("exports")
    exports.mkdir(parents=True, exist_ok=True)
    video = proj.root / "composition" / "html" / "motionnest-final.mp4"
    preview = proj.root / "composition" / "html" / "motionnest-preview.mp4"
    source_video = video if video.is_file() else preview if preview.is_file() else None
    if source_video:
        shutil.copy2(source_video, exports / "final.mp4")
    audit = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "project": proj.manifest.name,
        "version": proj.manifest.current_version,
        "data_source": data_dict.source,
        "gates": {gate.gate: gate.passed for gate in gates},
        "approvals": approvals,
        "shots": len(composition.scenes),
    }
    proj.write_json("exports/audit.json", audit)
    proj.snapshot("export")
    console.print(f"[green]OK 导出完成[/green]：{exports}（含 audit.json 审计清单）")


# ================================================================ 评论收件箱
@inbox_app.command("post")
def inbox_post(
    ctx: typer.Context,
    text: str = typer.Argument(...),
    project: Path = PROJECT_OPTION,
    scene: str = typer.Option(..., "--scene"),
    time_ms: int = typer.Option(0, "--time-ms"),
    x: float = typer.Option(0, "--x", help="画布横坐标（px）"),
    y: float = typer.Option(0, "--y", help="画布纵坐标（px）"),
    element: str = typer.Option(None, "--element"),
) -> None:
    """在画面上留评论（携带时间点与坐标）。"""
    proj = _project(project)
    comment = Inbox(proj.path("studio", "inbox.jsonl")).post(
        text, scene_id=scene, time_ms=time_ms, x=x, y=y, element_id=element
    )
    console.print(f"[green]OK[/green] 已记录 {comment.id}（scene={scene}, t={time_ms}ms, x={x}, y={y}）")


@inbox_app.command("list")
def inbox_list(ctx: typer.Context, project: Path = PROJECT_OPTION, status: str = typer.Option(None, "--status")) -> None:
    """查看评论列表。"""
    proj = _project(project)
    comments = Inbox(proj.path("studio", "inbox.jsonl")).list(status)
    if not comments:
        console.print("（无评论）")
        return
    table = Table("ID", "状态", "场景", "时间", "坐标", "元素", "内容")
    for comment in comments:
        table.add_row(comment.id, comment.status, comment.scene_id, f"{comment.time_ms}ms",
                      f"({comment.x:.0f},{comment.y:.0f})", comment.element_id or "-", comment.text)
    console.print(table)


@inbox_app.command("next")
def inbox_next(ctx: typer.Context, project: Path = PROJECT_OPTION) -> None:
    """Agent 侧：领取下一条待处理评论。"""
    proj = _project(project)
    comment = Inbox(proj.path("studio", "inbox.jsonl")).claim_next()
    if comment is None:
        console.print("（没有待处理评论）")
        return
    console.print(json.dumps(comment.__dict__, ensure_ascii=False, indent=2))
    console.print("[dim]定位后执行 mnest revise ... 改稿，再用 mnest inbox done 回报[/dim]")


@inbox_app.command("done")
def inbox_done(ctx: typer.Context, comment_id: str = typer.Argument(...), project: Path = PROJECT_OPTION,
               note: str = typer.Option("", "--note"), reject: bool = typer.Option(False, "--reject")) -> None:
    """回报评论处理结果。"""
    proj = _project(project)
    comment = Inbox(proj.path("studio", "inbox.jsonl")).resolve(
        comment_id, status="rejected" if reject else "resolved", note=note
    )
    console.print(f"[green]OK[/green] {comment.id} → {comment.status}")


# ================================================================ 版本与审计
@app.command()
def undo(ctx: typer.Context, project: Path = PROJECT_OPTION) -> None:
    """回滚到上一个快照（单位是完整项目状态）。"""
    proj = _project(project)
    version = proj.undo()
    if version is None:
        console.print("（没有可回滚的快照）")
        return
    console.print(f"[green]OK[/green] 已回滚到 {version}")


@app.command()
def audit(ctx: typer.Context, project: Path = PROJECT_OPTION) -> None:
    """审计：版本快照 + 签批 + 模型调用记录。"""
    proj = _project(project)
    snapshots = proj.snapshots()
    table = Table("快照", "标签", "时间")
    for snapshot in snapshots:
        table.add_row(snapshot.id, snapshot.label, snapshot.created_at)
    console.print(table)
    console.print(f"当前版本：{proj.manifest.current_version}")
    console.print(f"人工签批：{proj.manifest.approvals or '（无）'}")
    trail = _router(ctx).audit_trail
    if trail:
        calls = Table("任务", "模型", "档位", "降级", "人工签发", "耗时ms")
        for entry in trail:
            calls.add_row(entry["task"], entry["model"], entry["tier"], str(entry["degraded"]),
                          str(entry["requires_human_signoff"]), str(entry["latency_ms"]))
        console.print(calls)


# ================================================================ 宣传片（promo）
@app.command()
def promo(
    ctx: typer.Context,
    docs: list[Path] = typer.Argument(..., help="文档文件：md / csv / json / pptx（可多个）"),
    assets: Path = typer.Option(None, "--assets", help="素材文件夹（图片，可选）"),
    note: str = typer.Option("", "--note", help="一句话补充说明（可选）"),
    output: Path = typer.Option("out", "-o", help="输出目录"),
    quality: str = typer.Option("final", "--quality", help="preview=5fps 快速预览 / final=30fps 成片"),
    chat_model: str = typer.Option(None, "--model", help="对话模型 ID（默认取 DEEPSEEK_MODEL 或 deepseek-chat）"),
    chat_base_url: str = typer.Option(None, "--base-url", help="对话模型 Base URL（默认 https://api.deepseek.com）"),
    image_model: str = typer.Option(None, "--image-model", help="生图模型 ID（可选，留空不生图）"),
    image_base_url: str = typer.Option(None, "--image-base-url", help="生图模型 Base URL（可选）"),
) -> None:
    """宣传片管线：文档 → 30 秒企业设备宣传片 MP4（全自动，无签批）。"""
    import os

    from .llm.image_provider import ImageProvider
    from .llm.openai_provider import OpenAIProvider
    from .llm.registry import ModelSpec
    from .llm.types import Message
    from .promo import run_promo

    def log(level: str, message: str) -> None:
        style = {"ok": "green", "warn": "yellow", "err": "red", "info": "cyan"}.get(level, "dim")
        console.print(f"[{style}]{message}[/{style}]")

    chat_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    chat_fn = None
    resolved_chat_model = chat_model or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    if chat_key:
        os.environ["MOTIONNEST_CHAT_API_KEY"] = chat_key
        spec = ModelSpec(
            name="promo-chat",
            model_id=resolved_chat_model,
            provider_format="openai",
            base_url=chat_base_url or "https://api.deepseek.com",
            api_key_env="MOTIONNEST_CHAT_API_KEY",
            tier="low",
            max_output_tokens=4096,
        )
        provider = OpenAIProvider(spec, timeout=120.0, max_retries=2)
        chat_fn = lambda system, user: provider.chat(  # noqa: E731
            [Message(role="system", content=system), Message(role="user", content=user)], temperature=0.3
        ).text
    else:
        log("warn", "未检测到 DEEPSEEK_API_KEY：要点蒸馏与文案将使用模板降级")

    image_fn = None
    image_key = os.environ.get("MOTIONNEST_IMAGE_API_KEY", "").strip()
    if image_model and image_key:
        image_provider = ImageProvider(
            base_url=image_base_url or "", api_key=image_key, model=image_model, timeout=180.0
        )
        image_fn = lambda prompt: image_provider.generate(prompt, size="1792x1024")  # noqa: E731
    elif image_model:
        log("warn", "指定了生图模型但未设置 MOTIONNEST_IMAGE_API_KEY：跳过生图")

    try:
        result = run_promo(
            output,
            list(docs),
            asset_dir=assets,
            note=note,
            chat_fn=chat_fn,
            image_fn=image_fn,
            chat_model=resolved_chat_model if chat_fn else "",
            image_model=image_model if image_fn else "",
            quality=quality,
            logger=log,
        )
    except (MotionNestError, RuntimeError) as exc:
        # RuntimeError：渲染依赖缺失 / 帧数或 ffprobe 时长校验失败（不静默降级）
        _fail(exc)
        return
    console.print(f"[green]OK[/green] 成片：{result['video']}")
    console.print(f"[dim]审计清单：{result['audit']}[/dim]")


if __name__ == "__main__":  # pragma: no cover
    app()
