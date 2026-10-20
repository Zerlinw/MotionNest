"""后台工作线程：把 motionnest 操作放到子线程执行，不阻塞 UI。"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class CallableWorker(QThread):
    """执行任意可调用对象，通过信号回传日志/结果/错误。

    约定：fn 的第一个参数固定为 logger(level, message)，由本类注入。
    """

    logged = Signal(str, str)     # (level, message)
    finished_ok = Signal(object)  # result
    failed = Signal(str)          # error message

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        logger: Callable[[str, str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._logger = logger

    def _log(self, level: str, message: str) -> None:
        if self._logger is not None:
            self._logger(level, message)
        self.logged.emit(level, message)

    def run(self) -> None:
        try:
            result = self._fn(self._log, *self._args, **self._kwargs)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001 - 线程内兜底并上报
            self._log("err", f"{type(exc).__name__}: {exc}")
            self._log("dim", traceback.format_exc(limit=3))
            self.failed.emit(str(exc))
