"""MotionNest Desktop 主窗口：DeepSeek 客户端风格（极简，无向导）。

布局：
- 顶栏：产品名 + Darcula/Light 主题分段切换 + 控制台开关；
- 左侧窄导航（约 200px）：工作台 / 设置，选中项带强调色左条纹；
- 中部：页面堆叠区（splitter 可拖拽）；
- 底部：Run 工具窗风格控制台（可折叠）；
- 状态栏：当前主题与最近操作。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QToolButton,
    QWidget,
)

from . import theme
from .console import Console
from .pages import SettingsPage, StudioPage
from .settings import SettingsStore

NAV_ITEMS = [
    ("工作台", "提供文档，生成 30 秒企业设备宣传片"),
    ("设置", "对话模型 / 生图模型 / 主题"),
]


def app_icon() -> QIcon:
    """用代码绘制应用图标（避免二进制资源）。"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(theme.QColor(theme.palette(theme.DEFAULT_THEME)["accent"]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 10, 56, 44, 8, 8)
    painter.setBrush(theme.QColor("#FFFFFF"))
    painter.drawRect(12, 40, 10, 14)
    painter.drawRect(27, 28, 10, 26)
    painter.drawRect(42, 18, 10, 36)
    painter.end()
    return QIcon(pixmap)


def _dock_features(*names: str):
    """跨 PySide6 版本兼容的 DockWidget 特性组合（各版本枚举前缀不同）。"""
    feature = QDockWidget.DockWidgetFeature
    flags = None
    for name in names:
        member = None
        for candidate in (f"DockWidget{name}", f"Dock{name}", name):
            member = getattr(feature, candidate, None)
            if member is not None:
                break
        if member is None:
            continue
        flags = member if flags is None else flags | member
    return flags if flags is not None else feature.DockWidgetClosable


class MainWindow(QMainWindow):
    """主窗口。"""

    def __init__(self, settings_store: SettingsStore | None = None) -> None:
        super().__init__()
        self.settings_store = settings_store or SettingsStore()
        self.setWindowTitle("MotionNest Desktop · 动巢")
        self.setWindowIcon(app_icon())
        self.resize(1280, 860)
        self.setMinimumSize(1100, 720)

        # ---- 中部 ----
        central = QWidget()
        central.setObjectName("Central")
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        splitter = QSplitter()

        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setFixedWidth(200)
        for title, tooltip in NAV_ITEMS:
            self.nav.addItem(title)
            self.nav.item(self.nav.count() - 1).setToolTip(tooltip)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)
        splitter.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.console = Console(self.settings_store.theme)

        from .bridge import Bridge

        self.bridge = Bridge(self.settings_store)
        self.studio_page = StudioPage(self.bridge, self.settings_store, self._log)
        self.settings_page = SettingsPage(self.bridge, self.settings_store, self._log)
        for page in (self.studio_page, self.settings_page):
            self.stack.addWidget(page)
        splitter.addWidget(self.stack)
        splitter.setSizes([200, 1080])
        splitter.setCollapsible(0, False)
        splitter.setStretchFactor(1, 1)
        central_layout.addWidget(splitter)

        self.setCentralWidget(central)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._make_console_dock())
        self.resizeDocks(
            [self.findChild(QDockWidget, "ConsoleDock")], [240], Qt.Orientation.Horizontal
        )

        # ---- 顶栏 ----
        toolbar = QToolBar()
        toolbar.setObjectName("Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        title_label = QLabel("MotionNest Desktop")
        title_label.setObjectName("AppTitle")
        subtitle = QLabel("文档进 · 30 秒宣传片出")
        subtitle.setObjectName("AppSubtitle")
        toolbar.addWidget(title_label)
        toolbar.addWidget(subtitle)
        toolbar.addSeparator()

        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_buttons: dict[str, QToolButton] = {}
        for key in ("darcula", "light"):
            button = QToolButton()
            button.setText(theme.palette(key)["name"])
            button.setCheckable(True)
            button.setObjectName("flat")
            button.setToolTip(f"切换主题：{theme.palette(key)['name']}")
            button.clicked.connect(lambda _checked=False, name=key: self.switch_theme(name))
            self.theme_group.addButton(button)
            toolbar.addWidget(button)
            self.theme_buttons[key] = button
        toolbar.addSeparator()

        self.console_action = QAction("控制台", self)
        self.console_action.setCheckable(True)
        self.console_action.setChecked(True)
        self.console_action.triggered.connect(self._toggle_console)
        toolbar.addAction(self.console_action)
        self.addToolBar(toolbar)

        # ---- 状态栏 ----
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_label = QLabel("就绪")
        self.status.addPermanentWidget(self.status_label)

        # ---- 初始化 ----
        self._apply_theme(self.settings_store.theme)
        self.console.log("MotionNest Desktop 已启动。拖入产品文档，点击“生成 30 秒宣传片”。", "info")
        self.console.log(f"设置文件：{self.settings_store.path}", "dim")
        if not self.settings_store.chat_ready():
            self.console.log("尚未配置对话模型密钥：将使用模板降级出片，可在“设置”页配置。", "warn")

    # ================================================================ 布局部件
    def _make_console_dock(self) -> QDockWidget:
        dock = QDockWidget("运行")
        dock.setObjectName("ConsoleDock")
        dock.setWidget(self.console)
        dock.setFeatures(_dock_features("Closable", "Movable"))
        return dock

    # ================================================================ 行为
    def _on_nav_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)

    def _log(self, level: str, message: str) -> None:
        self.console.log(message, level)
        if level == "err":
            self.status_label.setText(f"错误：{message[:60]}")

    def _toggle_console(self, checked: bool) -> None:
        for dock in self.findChildren(QWidget):
            if dock.objectName() == "ConsoleDock":
                dock.setVisible(checked)

    def switch_theme(self, theme_name: str) -> None:
        self.settings_store.theme = theme_name
        self.settings_store.save()
        self._apply_theme(theme_name)
        self.status_label.setText(f"主题：{theme.palette(theme_name)['name']}")

    def _apply_theme(self, theme_name: str) -> None:
        theme.apply_theme(QApplication.instance(), theme_name)
        self.console.apply_theme(theme_name)
        for page in (self.studio_page, self.settings_page):
            page.apply_theme(theme_name)
        button = self.theme_buttons.get(theme_name)
        if button is not None:
            button.setChecked(True)
        self.status_label.setText(f"主题：{theme.palette(theme_name)['name']}")
