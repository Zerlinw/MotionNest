"""设置页：极致减法——对话模型与生图模型各三项（密钥 / 地址 / 模型 ID）+ 主题。

其余参数（超时、重试、帧率、分辨率、时长、提示词、档位路由）全部内置默认值。
密钥以密码框显示；修改即保存（设置文件位置见状态栏提示）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import theme


class _ModelCard(QGroupBox):
    """一组模型配置：API Key（密码框）/ Base URL / Model ID。"""

    def __init__(self, title: str, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._config = config
        form = QFormLayout(self)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.key_edit = QLineEdit(config.get("api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-…")
        self.key_edit.setMinimumWidth(360)
        form.addRow("API Key", self.key_edit)

        self.base_edit = QLineEdit(config.get("base_url", ""))
        self.base_edit.setMinimumWidth(360)
        form.addRow("Base URL", self.base_edit)

        self.model_edit = QLineEdit(config.get("model_id", ""))
        self.model_edit.setMinimumWidth(360)
        form.addRow("模型 ID", self.model_edit)

    def apply(self) -> None:
        self._config["api_key"] = self.key_edit.text().strip()
        self._config["base_url"] = self.base_edit.text().strip()
        self._config["model_id"] = self.model_edit.text().strip()


class SettingsPage(QWidget):
    """极简设置：两组模型卡片 + 主题切换。"""

    def __init__(self, bridge, settings_store, logger, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.settings_store = settings_store
        self.log = logger

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(16)
        layout.setContentsMargins(22, 20, 22, 20)

        title = QLabel("设置")
        title.setObjectName("h1")
        layout.addWidget(title)

        hint = QLabel("只需配置模型；生成参数（30 秒 / 1920×1080 / 30fps）已内置最优默认值。")
        hint.setObjectName("dim")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.chat_card = _ModelCard("对话模型（要点蒸馏 · 分镜文案）", self.settings_store.chat)
        layout.addWidget(self.chat_card)
        chat_hint = QLabel("未配置时自动降级为模板文案，仍可出片（审计清单中注明）。")
        chat_hint.setObjectName("dim")
        layout.addWidget(chat_hint)

        self.image_card = _ModelCard("生图模型（OpenAI 兼容 /images/generations）", self.settings_store.image)
        layout.addWidget(self.image_card)
        image_hint = QLabel("留空则仅使用文档内图片与自带素材，缺图镜头以图形兜底。")
        image_hint.setObjectName("dim")
        layout.addWidget(image_hint)

        # ---- 主题 ----
        theme_box = QGroupBox("主题")
        theme_row = QHBoxLayout(theme_box)
        theme_row.setContentsMargins(16, 16, 16, 16)
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_buttons: dict[str, QPushButton] = {}
        for key in theme.theme_names():
            button = QPushButton(theme.palette(key)["name"])
            button.setObjectName("flat")
            button.setCheckable(True)
            button.setChecked(settings_store.theme == key)
            button.clicked.connect(lambda _checked=False, name=key: self._switch_theme(name))
            self.theme_group.addButton(button)
            theme_row.addWidget(button)
            self.theme_buttons[key] = button
        theme_row.addStretch(1)
        layout.addWidget(theme_box)

        path_hint = QLabel(f"设置文件：{settings_store.path}")
        path_hint.setObjectName("dim")
        path_hint.setWordWrap(True)
        layout.addWidget(path_hint)

        layout.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        for card in (self.chat_card, self.image_card):
            for edit in (card.key_edit, card.base_edit, card.model_edit):
                edit.textChanged.connect(self._save)

    # ================================================================ 行为
    def _save(self) -> None:
        self.chat_card.apply()
        self.image_card.apply()
        self.settings_store.save()

    def _switch_theme(self, theme_name: str) -> None:
        self.settings_store.theme = theme_name
        self.settings_store.save()
        self.log("info", f"主题已切换：{theme.palette(theme_name)['name']}（重启窗口后全局生效）")

    def apply_theme(self, theme_name: str) -> None:
        button = self.theme_buttons.get(theme_name)
        if button is not None:
            button.setChecked(True)
