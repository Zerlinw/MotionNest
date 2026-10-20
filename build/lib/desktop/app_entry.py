"""PyInstaller 打包入口（绝对导入，冻结运行时可用）。

直接打包 desktop/__main__.py 会因“顶层脚本无父包”导致相对导入失败；
本文件以包路径导入 desktop.__main__.main，保证相对导入可解析。
"""

from __future__ import annotations

import sys

from desktop.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
