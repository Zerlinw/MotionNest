# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('D:/Develop/PythonProject/MotionNest/config', 'config')]
hiddenimports = []
datas += collect_data_files('playwright')
hiddenimports += collect_submodules('motionnest')
hiddenimports += collect_submodules('desktop')
hiddenimports += collect_submodules('playwright')


a = Analysis(
    ['D:/Develop/PythonProject/MotionNest/desktop/app_entry.py'],
    pathex=['D:/Develop/PythonProject/MotionNest/src', 'D:/Develop/PythonProject/MotionNest'],
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
    name='MotionNestDesktop',
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
