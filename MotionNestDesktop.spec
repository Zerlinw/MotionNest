# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：MotionNest Desktop（windowed / onefile）。

- 入口：desktop/app_entry.py（绝对导入，冻结态可用）
- pathex 同时包含 src/ 与仓库根：motionnest 在 src 下，desktop 在根下
- hiddenimports 用 collect_submodules 覆盖 promo 管线与延迟导入
  （bridge.generate_promo / renderer.capture_frames 都是函数内 import）
- Playwright 只打包 Python 包与 node 驱动；浏览器优先用系统 Edge/Chrome
  （renderer._launch_browser 的 channel 回退），避免把 Chromium 塞进 exe
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

import sys
from pathlib import Path

# spec 执行时把仓库根与 src 放进 sys.path，保证 collect_submodules 能发现
# motionnest 与 desktop（否则会报 ModuleNotFoundError）。
ROOT = Path(globals().get("SPECPATH", Path.cwd())).resolve()
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

hiddenimports = collect_submodules("motionnest") + collect_submodules("desktop")
datas = [(str(ROOT / "config"), "config")]

# 可选：打包 Playwright Python 包与 node 驱动；未安装时跳过（渲染时会给出安装提示）
try:
    hiddenimports += collect_submodules("playwright")
    datas += collect_data_files("playwright")
except Exception:  # noqa: BLE001 - 未安装 Playwright 不应阻断 GUI 打包
    pass

a = Analysis(
    [str(ROOT / "desktop" / "app_entry.py")],
    pathex=[str(ROOT / "src"), str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MotionNestDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
