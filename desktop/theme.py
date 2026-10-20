"""IntelliJ IDEA 风格双主题：Darcula（Dark）与 IntelliJ Light。

调色板为 JetBrains IDE 配色的工程近似值（Darcula 面板 #3C3F41 /
编辑器 #2B2B22 / 强调蓝 #4A88C7；Light 面板 #F2F2F2 / 编辑器 #FFFFFF /
强调蓝 #3574F0），视觉规范遵循 IDEA：扁平、1px 细边框、紧凑间距、
控件 4px 圆角、蓝色焦点与选中态。
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

PALETTES: dict[str, dict[str, str]] = {
    "darcula": {
        "name": "Darcula",
        "bg_window": "#3C3F41",
        "bg_panel": "#3C3F41",
        "bg_editor": "#2B2B2B",
        "bg_input": "#45494A",
        "bg_hover": "#4C5052",
        "bg_pressed": "#5C6063",
        "bg_alt": "#383B3D",
        "border": "#323232",
        "border_strong": "#646464",
        "border_focus": "#4A88C7",
        "text": "#BBBBBB",
        "text_dim": "#787878",
        "text_bright": "#E0E0E0",
        "accent": "#4A88C7",
        "accent_hover": "#5A98D7",
        "accent_pressed": "#3F7DB6",
        "on_accent": "#FFFFFF",
        "sel_bg": "#214283",
        "sel_text": "#FFFFFF",
        "sel_hover": "#2F5B9E",
        "ok": "#6A8759",
        "warn": "#BBB529",
        "err": "#BC3F3C",
        "info": "#4A88C7",
        "shadow": "rgba(0, 0, 0, 90)",
    },
    "light": {
        "name": "IntelliJ Light",
        "bg_window": "#F2F2F2",
        "bg_panel": "#F2F2F2",
        "bg_editor": "#FFFFFF",
        "bg_input": "#FFFFFF",
        "bg_hover": "#E2E2E2",
        "bg_pressed": "#D2D2D2",
        "bg_alt": "#F5F5F5",
        "border": "#C9C9C9",
        "border_strong": "#A8A8A8",
        "border_focus": "#3574F0",
        "text": "#000000",
        "text_dim": "#808080",
        "text_bright": "#000000",
        "accent": "#3574F0",
        "accent_hover": "#5B91F3",
        "accent_pressed": "#2A5FD0",
        "on_accent": "#FFFFFF",
        "sel_bg": "#AFD1FB",
        "sel_text": "#000000",
        "sel_hover": "#C7DEF9",
        "ok": "#3E8E43",
        "warn": "#C77D0A",
        "err": "#D0433B",
        "info": "#3574F0",
        "shadow": "rgba(0, 0, 0, 40)",
    },
}

DEFAULT_THEME = "darcula"

_QSS_TEMPLATE = """
/* ============ MotionNest Desktop · IDEA 风格（@theme_name@） ============ */

QWidget {
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
    font-size: 13px;
    color: @text@;
}

QMainWindow, QDialog { background: @bg_window@; }
QWidget#Central { background: @bg_panel@; }

/* ---- 顶栏 ---- */
QWidget#Toolbar {
    background: @bg_panel@;
    border-bottom: 1px solid @border@;
}
QToolBar { spacing: 10px; padding: 6px 12px; }
QToolBar::separator { width: 1px; margin: 6px 4px; background: @border@; }
QLabel#AppTitle {
    color: @text_bright@;
    font-size: 15px;
    font-weight: 600;
    padding-left: 4px;
}
QLabel#AppSubtitle { color: @text_dim@; font-size: 12px; padding-left: 2px; }

/* ---- 左侧工具窗（IDEA Tool Window） ---- */
QWidget#Sidebar {
    background: @bg_panel@;
    border-right: 1px solid @border@;
}
QLabel#SidebarHeader {
    color: @text_dim@;
    font-size: 11px;
    font-weight: 600;
    padding: 10px 12px 4px 12px;
}
QListWidget#Nav {
    background: transparent;
    border: none;
    outline: 0;
    font-size: 13px;
}
QListWidget#Nav::item {
    padding: 10px 14px 10px 12px;
    margin: 2px 6px;
    border-radius: 4px;
    border-left: 3px solid transparent;
    color: @text@;
    font-size: 13.5px;
}
QListWidget#Nav::item:hover { background: @bg_hover@; }
QListWidget#Nav::item:selected {
    background: @bg_hover@;
    border-left: 3px solid @accent@;
    color: @text_bright@;
}

/* ---- 按钮 ---- */
QPushButton {
    background: @bg_input@;
    border: 1px solid @border_strong@;
    border-radius: 4px;
    padding: 8px 18px;
    min-height: 30px;
    color: @text@;
    font-size: 13px;
}
QPushButton:hover { background: @bg_hover@; border-color: @accent@; }
QPushButton:pressed { background: @bg_pressed@; }
QPushButton:disabled { color: @text_dim@; border-color: @border@; background: @bg_panel@; }
QPushButton#primary {
    background: @accent@;
    border: 1px solid @accent@;
    color: @on_accent@;
    font-weight: 600;
}
QPushButton#primary:hover { background: @accent_hover@; border-color: @accent_hover@; }
QPushButton#primary:pressed { background: @accent_pressed@; }
QPushButton#primary:disabled { background: @bg_panel@; color: @text_dim@; border-color: @border@; }
QPushButton#flat {
    background: transparent;
    border: 1px solid transparent;
    color: @text@;
}
QPushButton#flat:hover { background: @bg_hover@; border-color: @border@; }
QPushButton#flat:checked { background: @bg_input@; border-color: @accent@; color: @text_bright@; }
/* 控制台右侧操作按钮：控制台底色上需要清晰可见 */
QPushButton#consoleAction {
    background: @bg_input@;
    border: 1px solid @border_strong@;
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 26px;
    color: @text@;
    font-size: 12.5px;
}
QPushButton#consoleAction:hover { background: @bg_hover@; border-color: @accent@; }
QPushButton#consoleAction:pressed { background: @bg_pressed@; }

/* ---- 输入 ---- */
QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser {
    background: @bg_input@;
    border: 1px solid @border_strong@;
    border-radius: 4px;
    padding: 8px 10px;
    min-height: 30px;
    selection-background-color: @sel_bg@;
    selection-color: @sel_text@;
    font-size: 13px;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus { border: 1px solid @accent@; }
QLineEdit:disabled, QPlainTextEdit:disabled { color: @text_dim@; }
QPlainTextEdit#Console {
    background: @bg_editor@;
    border: none;
    border-top: 1px solid @border@;
    font-family: "Cascadia Mono", "Consolas", "JetBrains Mono", monospace;
    font-size: 12.5px;
    padding: 10px 12px;
}
QComboBox {
    background: @bg_input@;
    border: 1px solid @border_strong@;
    border-radius: 4px;
    padding: 7px 10px;
    min-height: 30px;
    font-size: 13px;
}
QComboBox:hover { border-color: @accent@; }
QComboBox:focus { border: 1px solid @accent@; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: @bg_input@;
    border: 1px solid @border_strong@;
    selection-background-color: @sel_bg@;
    selection-color: @sel_text@;
    outline: 0;
}
QSpinBox, QDoubleSpinBox {
    background: @bg_input@;
    border: 1px solid @border_strong@;
    border-radius: 4px;
    padding: 7px 9px;
    min-height: 30px;
    font-size: 13px;
}
QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid @accent@; }
QCheckBox, QRadioButton { spacing: 10px; min-height: 26px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 17px; height: 17px;
    border: 1px solid @border_strong@;
    background: @bg_input@;
}
QCheckBox::indicator { border-radius: 3px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: @accent@;
    border-color: @accent@;
}
QCheckBox::indicator:checked:hover, QRadioButton::indicator:checked:hover { background: @accent_hover@; }

/* ---- 列表 / 表格 ---- */
QListWidget, QTableWidget, QTreeWidget {
    background: @bg_editor@;
    border: 1px solid @border@;
    alternate-background-color: @bg_alt@;
    outline: 0;
    font-size: 13px;
}
QListWidget::item, QTableWidget::item { padding: 7px 8px; }
QListWidget::item:selected, QTableWidget::item:selected {
    background: @sel_bg@;
    color: @sel_text@;
}
QHeaderView::section {
    background: @bg_panel@;
    color: @text_dim@;
    border: none;
    border-bottom: 1px solid @border@;
    padding: 9px 10px;
    font-weight: 600;
    font-size: 12.5px;
}
QTableCornerButton::section { background: @bg_panel@; border: none; }

/* ---- 分组 / 选项卡 ---- */
QGroupBox {
    border: 1px solid @border@;
    border-radius: 6px;
    margin-top: 16px;
    padding: 20px 16px 16px 16px;
    background: @bg_panel@;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: @text_bright@;
    font-weight: 600;
    font-size: 13.5px;
}
QTabWidget::pane { border: 1px solid @border@; border-radius: 6px; background: @bg_panel@; }
QTabBar::tab {
    background: transparent;
    color: @text_dim@;
    padding: 9px 20px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}
QTabBar::tab:hover { color: @text@; }
QTabBar::tab:selected { color: @accent@; border-bottom: 2px solid @accent@; }

/* ---- 滚动条（IDEA 细滚动条） ---- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: @border_strong@;
    border-radius: 5px;
    min-height: 32px;
    min-width: 32px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: @accent@; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::page { background: transparent; }

/* ---- 其它 ---- */
QToolTip {
    background: @bg_input@;
    color: @text@;
    border: 1px solid @border_strong@;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12.5px;
}
QStatusBar { background: @bg_panel@; border-top: 1px solid @border@; color: @text_dim@; }
QStatusBar::item { border: none; }
QSplitter::handle { background: @border@; }
QProgressBar {
    background: @bg_input@;
    border: 1px solid @border_strong@;
    border-radius: 4px;
    text-align: center;
    color: @text@;
    max-height: 16px;
}
QProgressBar::chunk { background: @accent@; border-radius: 3px; }
QLabel#dim { color: @text_dim@; font-size: 12.5px; }
QLabel#h2 { color: @text_bright@; font-size: 15px; font-weight: 600; }
QLabel#h1 { color: @text_bright@; font-size: 20px; font-weight: 600; }

/* ---- 工作台拖放区 / 结果卡片 ---- */
QFrame#DropZone {
    background: @bg_editor@;
    border: 2px dashed @border_strong@;
    border-radius: 10px;
}
QFrame#DropZone[dragActive="true"] {
    border-color: @accent@;
    background: @bg_hover@;
}
QLabel#DropHint { color: @text_dim@; font-size: 13px; }
QListWidget#FileList { border-radius: 6px; }
QFrame#ResultCard { padding: 4px; }
QFrame#ResultCard QLabel { background: transparent; }
QFrame.Card {
    background: @bg_panel@;
    border: 1px solid @border@;
    border-radius: 8px;
}
QLabel#StepBadge {
    background: @accent@;
    color: @on_accent@;
    border-radius: 14px;
    font-weight: 700;
    font-size: 13px;
    min-width: 28px; max-width: 28px;
    min-height: 28px; max-height: 28px;
    qproperty-alignment: AlignCenter;
}
QLabel#StepBadgeDone { background: @ok@; color: #FFFFFF; }
QLabel#StepBadgeTodo { background: @bg_input@; color: @text_dim@; border: 1px solid @border_strong@; }
"""


def palette(theme: str) -> dict[str, str]:
    return PALETTES.get(theme, PALETTES[DEFAULT_THEME])


def stylesheet(theme: str) -> str:
    """生成完整 QSS。"""
    colors = palette(theme)
    qss = _QSS_TEMPLATE
    for token, value in colors.items():
        qss = qss.replace(f"@{token}@", str(value))
    qss = qss.replace("@theme_name@", colors["name"])
    return qss


def apply_theme(app: QApplication, theme: str) -> None:
    """应用主题：QSS + Fusion 调色板兜底 + 字体。"""
    colors = palette(theme)
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet(theme))

    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(colors["bg_window"]))
    pal.setColor(QPalette.WindowText, QColor(colors["text"]))
    pal.setColor(QPalette.Base, QColor(colors["bg_editor"]))
    pal.setColor(QPalette.AlternateBase, QColor(colors["bg_alt"]))
    pal.setColor(QPalette.Text, QColor(colors["text"]))
    pal.setColor(QPalette.Button, QColor(colors["bg_input"]))
    pal.setColor(QPalette.ButtonText, QColor(colors["text"]))
    pal.setColor(QPalette.Highlight, QColor(colors["sel_bg"]))
    pal.setColor(QPalette.HighlightedText, QColor(colors["sel_text"]))
    pal.setColor(QPalette.ToolTipBase, QColor(colors["bg_input"]))
    pal.setColor(QPalette.ToolTipText, QColor(colors["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(colors["text_dim"]))
    app.setPalette(pal)

    font = QFont("Segoe UI", 9)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)


def theme_names() -> list[str]:
    return list(PALETTES)


def accent_color(theme: str) -> str:
    return palette(theme)["accent"]


def console_colors(theme: str) -> dict[str, str]:
    colors = palette(theme)
    return {
        "info": colors["info"],
        "ok": colors["ok"],
        "warn": colors["warn"],
        "err": colors["err"],
        "dim": colors["text_dim"],
        "text": colors["text"],
    }
