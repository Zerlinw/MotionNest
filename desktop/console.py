"""IDEA Run 工具窗风格的控制台：等宽字体、分级着色、自动滚动。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from . import theme

_LEVEL_LABEL = {"info": "INFO", "ok": "OK", "warn": "WARN", "err": "ERROR", "dim": "····"}


class Console(QWidget):
    """底部控制台：日志流 + 清空/复制操作。"""

    def __init__(self, theme_name: str = "darcula", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme_name
        self.setObjectName("ConsolePane")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._view = QPlainTextEdit()
        self._view.setObjectName("Console")
        self._view.setReadOnly(True)
        self._view.setMaximumBlockCount(2000)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self._view, 1)

        self._buttons = QWidget()
        self._buttons.setObjectName("ConsoleButtons")
        # 竖排：控制台右侧较窄时也不会把“清空/复制”挤成竖排文字。
        button_column = QVBoxLayout(self._buttons)
        button_column.setContentsMargins(8, 8, 8, 8)
        button_column.setSpacing(6)
        self._clear_button = QPushButton("清空")
        self._clear_button.setObjectName("consoleAction")
        self._clear_button.setMinimumHeight(28)
        self._clear_button.clicked.connect(self.clear)
        self._copy_button = QPushButton("复制")
        self._copy_button.setObjectName("consoleAction")
        self._copy_button.setMinimumHeight(28)
        self._copy_button.clicked.connect(self.copy_all)
        button_column.addWidget(self._clear_button)
        button_column.addWidget(self._copy_button)
        button_column.addStretch(1)
        self._buttons.setFixedWidth(96)
        layout.addWidget(self._buttons)

        self.apply_theme(theme_name)

    # ---------------------------------------------------------------- 主题
    def apply_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        colors = theme.console_colors(theme_name)
        self._colors = colors
        self._buttons.setStyleSheet(
            f"background: {theme.palette(theme_name)['bg_panel']};"
            f"border-left: 1px solid {theme.palette(theme_name)['border']};"
        )

    # ---------------------------------------------------------------- 输出
    def log(self, message: str, level: str = "info") -> None:
        colors = theme.console_colors(self._theme)
        color = colors.get(level, colors["text"])
        stamp = datetime.now().strftime("%H:%M:%S")
        label = _LEVEL_LABEL.get(level, level.upper())
        line = (
            f'<span style="color:{colors["dim"]}">[{stamp}]</span> '
            f'<span style="color:{color}">{label}</span> '
            f'<span style="color:{colors["text"]}">{_escape(message)}</span>'
        )
        self._view.appendHtml(line)
        self._view.moveCursor(QTextCursor.MoveOperation.End)

    def clear(self) -> None:
        self._view.clear()

    def copy_all(self) -> None:

        self._view.selectAll()
        self._view.copy()
        cursor = self._view.textCursor()
        cursor.clearSelection()
        self._view.setTextCursor(cursor)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
