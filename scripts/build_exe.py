"""PyInstaller 打包脚本：产出免环境依赖的 MotionNestDesktop.exe。

用法：
    python scripts/build_exe.py              # onefile + windowed（GUI，无控制台）
    python scripts/build_exe.py --verify     # 构建后跑一次 exe 自检
    python scripts/build_exe.py --console    # 附带一个控制台版（自检/调试用）
    python scripts/build_exe.py --clean      # 只清理 build/dist

产物：dist/MotionNestDesktop.exe（双击即运行，无需 Python 环境；
真实出片仍需 FFmpeg 在 PATH，浏览器优先使用系统 Edge/Chrome）。
config/ 目录会随包分发（models.yaml + router.yaml，供 mnest 数据故事 CLI 使用）；
motionnest 全部子模块（含 promo 管线）与 desktop 包列入 hidden-imports；
Playwright Python 包与驱动按需打包，浏览器优先使用系统 Edge/Chrome（不塞 Chromium）；
密钥保存在 exe 同级 motionnest-settings.json（绿色模式）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "MotionNestDesktop"


def _check_environment() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit("缺少 PyInstaller：pip install pyinstaller") from exc
    try:
        import PySide6  # noqa: F401
    except ImportError as exc:
        raise SystemExit("缺少 PySide6：pip install PySide6") from exc
    if not (ROOT / "config" / "models.yaml").is_file():
        raise SystemExit("缺少 config/models.yaml")


def _build(console: bool, verify: bool) -> Path:
    _check_environment()
    sep = os.pathsep  # Windows ';'，POSIX ':'
    # 生成的 spec 放到 build/ 下，避免覆盖仓库里手工维护的 MotionNestDesktop.spec
    (ROOT / "build" / "pyinstaller").mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        APP_NAME if not console else f"{APP_NAME}-console",
        "--specpath",
        str(ROOT / "build" / "pyinstaller"),
        "--paths",
        str(ROOT / "src"),
        "--paths",
        str(ROOT),
        "--add-data",
        f"{ROOT / 'config'}{sep}config",
        "--collect-submodules",
        "motionnest",
        "--collect-submodules",
        "desktop",
    ]
    try:
        import playwright  # noqa: F401

        command += [
            "--collect-submodules",
            "playwright",
            "--collect-data",
            "playwright",
        ]
        print("==> 检测到 Playwright：随包打入 Python 包与驱动（浏览器走系统 Edge/Chrome）")
    except ImportError:
        print("==> 未安装 Playwright：exe 可启动；真实出片前需 pip install playwright")
    command.append(str(ROOT / "desktop" / "app_entry.py"))
    if not console:
        command.append("--windowed")
    print("==> " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)

    suffix = ".exe" if os.name == "nt" else ""
    exe_name = f"{APP_NAME}{suffix}" if not console else f"{APP_NAME}-console{suffix}"
    exe = ROOT / "dist" / exe_name
    if not exe.is_file():
        raise SystemExit(f"构建失败：未找到 {exe}")
    size_mb = exe.stat().st_size / 1024 / 1024
    print(f"==> 构建完成：{exe}（{size_mb:.1f} MB）")
    print("==> 双击即可运行；首次使用请在“设置”页填写 API Key。")
    if verify:
        _verify_exe(exe)
    return exe


def _verify_exe(exe: Path) -> None:
    """运行 exe 的 --selfcheck，校验冻结态可启动、页面可构建、promo 管线可导入。"""
    report = exe.parent / "motionnest-selfcheck.txt"
    if report.exists():
        report.unlink()
    print("==> 自检：" + str(exe) + " --selfcheck")
    result = subprocess.run(
        [str(exe), "--selfcheck"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout[-3000:])
        print(result.stderr[-3000:])
        raise SystemExit(f"exe 自检失败（exit {result.returncode}）")
    if report.is_file():
        print(report.read_text(encoding="utf-8", errors="replace"))
    else:
        print("==> 自检通过（未找到报告文件，但退出码为 0）")


def _clean() -> None:
    for name in ("build", "dist"):
        path = ROOT / name
        if path.is_dir():
            shutil.rmtree(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="打包 MotionNest Desktop")
    parser.add_argument("--console", action="store_true", help="构建控制台版（自检/调试）")
    parser.add_argument("--verify", action="store_true", help="构建后运行 exe --selfcheck")
    parser.add_argument("--clean", action="store_true", help="清理 build/dist 后退出")
    args = parser.parse_args()
    if args.clean:
        _clean()
        print("已清理 build/ dist/")
        return 0
    _build(console=args.console, verify=args.verify)
    return 0


if __name__ == "__main__":
    sys.exit(main())
