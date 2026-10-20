"""MotionNest Desktop 入口。

用法：
  python -m desktop                # 启动 GUI
  python -m desktop --selfcheck    # 无头自检（离屏初始化 + 构建模型栈）
  python -m desktop --demo         # 自检并执行一次主题切换与页面构建
  python -m desktop --render-selftest  # 冻结态渲染自检（逐帧 → MP4）
"""

from __future__ import annotations

import sys


def _run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from .app import MainWindow
    from .settings import SettingsStore

    app = QApplication(sys.argv)
    app.setApplicationName("MotionNest Desktop")
    window = MainWindow(SettingsStore())
    window.show()
    return app.exec()


def _selfcheck(demo: bool = False) -> int:
    """无头自检：离屏创建 QApplication 与主窗口，验证双主题与管线可用性。"""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from . import theme
    from .app import MainWindow
    from .settings import SettingsStore

    checks: list[tuple[str, bool, str]] = []

    app = QApplication(sys.argv)
    store = SettingsStore()
    checks.append(("设置加载", True, str(store.path)))

    window = MainWindow(store)
    checks.append(("主窗口构建", True, f"{window.stack.count()} 个页面"))

    for name in theme.theme_names():
        theme.apply_theme(app, name)
        checks.append((f"主题 {name}", True, f"{len(theme.stylesheet(name))} 字符 QSS"))

    checks.append(
        ("对话模型", True, f"{store.chat.get('model_id', '')}（{'已配置' if store.chat_ready() else '未配置：模板降级'}）")
    )
    checks.append(
        (
            "生图模型",
            True,
            f"{store.image.get('model_id', '') or '未配置'}"
            f"（{'已配置' if store.image_ready() else '素材 + 图形兜底'}）",
        )
    )

    try:
        from motionnest.promo import run_promo  # noqa: F401 - 管线可导入

        checks.append(("promo 管线导入", True, "motionnest.promo"))
    except Exception as exc:  # noqa: BLE001 - 自检需要报告而非中断
        checks.append(("promo 管线导入", False, str(exc)))

    if demo:
        window.switch_theme("light" if store.theme == "darcula" else "darcula")
        checks.append(("主题切换", True, store.theme))

    failed = 0
    lines: list[str] = []
    for name, ok, detail in checks:
        line = f"[{'PASS' if ok else 'FAIL'}] {name}：{detail}"
        lines.append(line)
        print(line)
        failed += 0 if ok else 1
    summary = f"selfcheck: {len(checks) - failed}/{len(checks)} 通过"
    lines.append(summary)
    print(summary)

    # 报告落盘：windowed 模式（无控制台）也能看到结果
    try:
        import os
        import tempfile
        from pathlib import Path

        if getattr(sys, "frozen", False):
            report = Path(sys.executable).parent / "motionnest-selfcheck.txt"
        else:
            report = Path(tempfile.gettempdir()) / "motionnest-selfcheck.txt"
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"报告已写入：{report}")
    except OSError:
        pass
    return 1 if failed else 0


def _render_selftest() -> int:
    """冻结态渲染自检：Composition → HTML → Playwright 逐帧 → FFmpeg MP4。"""
    import tempfile
    from pathlib import Path

    from motionnest.core.project import Project
    from motionnest.core.schemas import Composition, Layer, Scene
    from motionnest.runtime.renderer import Renderer

    lines: list[str] = []
    ok = False
    try:
        tmp = Path(tempfile.mkdtemp(prefix="motionnest-render-"))
        project = Project.create(tmp / "ws", "render-selftest")
        composition = Composition(
            fps=30,
            width=640,
            height=360,
            scenes=[
                Scene(
                    id="scene-01",
                    shot_id="shot-1",
                    duration_ms=1000,
                    layers=[
                        Layer(
                            id="layer-01-text",
                            type="text",
                            props={
                                "text": "MotionNest render selftest",
                                "size": 36,
                                "x": 40,
                                "y": 150,
                                "color": "#F5F7FA",
                            },
                        ),
                        Layer(
                            id="layer-01-bar",
                            type="shape",
                            props={"x": 40, "y": 210, "w": 120, "h": 8, "color": "#4A88C7", "radius": 4},
                        ),
                    ],
                )
            ],
        )
        renderer = Renderer(project.path("composition", "html"))
        result = renderer.render_video(composition, quality="preview", strict=True)
        video = next((path for path in result.outputs if path.suffix == ".mp4"), None)
        size = video.stat().st_size if video is not None and video.is_file() else 0
        ok = result.status == "video" and size > 0
        lines.append(f"[{'PASS' if ok else 'FAIL'}] render selftest: status={result.status} video={video} size={size}")
        lines.extend(result.notes)
    except Exception as exc:  # noqa: BLE001 - 自检需要报告而非崩溃
        lines.append(f"[FAIL] render selftest: {type(exc).__name__}: {exc}")

    try:
        if getattr(sys, "frozen", False):
            report = Path(sys.executable).parent / "motionnest-render-selftest.txt"
        else:
            report = Path(tempfile.gettempdir()) / "motionnest-render-selftest.txt"
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass
    print("\n".join(lines))
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if "--render-selftest" in args:
        return _render_selftest()
    if "--selfcheck" in args:
        return _selfcheck(demo="--demo" in args)
    return _run_gui()


if __name__ == "__main__":
    sys.exit(main())
