"""工作台页：文档进、30 秒宣传片出（DeepSeek 客户端风格，无向导）。

布局自上而下：
  拖放区（md/csv/pptx/图片/文件夹，拖入高亮） → 已选文档列表 →
  素材文件夹（可选） → 一句话补充说明（可选） → 生成按钮 → 结果卡片。
生成过程日志走底部控制台；完成后可播放成片或打开所在文件夹。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..workers import CallableWorker

DOC_SUFFIXES = {".md", ".markdown", ".csv", ".json", ".pptx"}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
DEFAULT_OUTPUT = Path.home() / "Videos" / "MotionNest 宣传片"


class DropZone(QFrame):
    """拖放区：接受文档文件、图片与文件夹。"""

    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        hint = QLabel("把文档拖到这里：Markdown / CSV / PPTX，或拖入图片与素材文件夹")
        hint.setObjectName("DropHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.setSpacing(10)
        self.docs_button = QPushButton("选择文档…")
        self.docs_button.setObjectName("flat")
        self.assets_button = QPushButton("选择素材文件夹…")
        self.assets_button.setObjectName("flat")
        row.addWidget(self.docs_button)
        row.addWidget(self.assets_button)
        layout.addLayout(row)

    # ---------------------------------------------------------------- 拖放
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()


class StudioPage(QWidget):
    """主工作区。"""

    def __init__(self, bridge, settings_store, logger, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.settings_store = settings_store
        self.log = logger
        self._workers: list[CallableWorker] = []
        self._doc_paths: list[str] = []
        self._asset_dir = ""
        self._staging_dir: str | None = None
        self._result: dict | None = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        title = QLabel("宣传片工作台")
        title.setObjectName("h1")
        layout.addWidget(title)
        subtitle = QLabel("提供产品文档，自动生成 30 秒企业设备宣传片（1920×1080 MP4）")
        subtitle.setObjectName("dim")
        layout.addWidget(subtitle)

        # ---- 拖放区 ----
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        self.drop_zone.docs_button.clicked.connect(self._pick_docs)
        self.drop_zone.assets_button.clicked.connect(self._pick_assets)
        layout.addWidget(self.drop_zone)

        # ---- 文档列表 ----
        self.file_list = QListWidget()
        self.file_list.setObjectName("FileList")
        self.file_list.setMaximumHeight(170)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.file_list)

        list_row = QHBoxLayout()
        remove_button = QPushButton("移除所选")
        remove_button.setObjectName("flat")
        remove_button.clicked.connect(self._remove_selected)
        clear_button = QPushButton("清空")
        clear_button.setObjectName("flat")
        clear_button.clicked.connect(self._clear_all)
        list_row.addWidget(remove_button)
        list_row.addWidget(clear_button)
        list_row.addStretch(1)
        self.assets_label = QLabel("素材文件夹：未选择（可选）")
        self.assets_label.setObjectName("dim")
        list_row.addWidget(self.assets_label)
        layout.addLayout(list_row)

        # ---- 补充说明 ----
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("一句话补充说明（可选）：如“突出续航与防护，面向海外客户”")
        layout.addWidget(self.note_edit)

        # ---- 输出位置 ----
        self.output_label = QLabel(f"成片输出：{self._default_output_dir()}")
        self.output_label.setObjectName("dim")
        layout.addWidget(self.output_label)

        # ---- 生成 ----
        self.generate_button = QPushButton("生成 30 秒宣传片")
        self.generate_button.setObjectName("primary")
        self.generate_button.setMinimumHeight(42)
        self.generate_button.clicked.connect(self._generate)
        layout.addWidget(self.generate_button)

        # ---- 结果卡片 ----
        self.result_card = QFrame()
        self.result_card.setObjectName("ResultCard")
        self.result_card.setProperty("class", "Card")
        self.result_card.hide()
        result_layout = QVBoxLayout(self.result_card)
        result_layout.setSpacing(10)
        self.result_title = QLabel("成片已生成")
        self.result_title.setObjectName("h2")
        result_layout.addWidget(self.result_title)
        self.result_meta = QLabel("")
        self.result_meta.setObjectName("dim")
        self.result_meta.setWordWrap(True)
        result_layout.addWidget(self.result_meta)
        self.result_path = QLabel("")
        self.result_path.setWordWrap(True)
        self.result_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result_layout.addWidget(self.result_path)
        buttons_row = QHBoxLayout()
        self.play_button = QPushButton("播放成片")
        self.play_button.setObjectName("primary")
        self.play_button.clicked.connect(self._play)
        self.folder_button = QPushButton("打开所在文件夹")
        self.folder_button.setObjectName("flat")
        self.folder_button.clicked.connect(self._open_folder)
        buttons_row.addWidget(self.play_button)
        buttons_row.addWidget(self.folder_button)
        buttons_row.addStretch(1)
        result_layout.addLayout(buttons_row)
        layout.addWidget(self.result_card)

        layout.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ================================================================ 文件收集
    def _on_drop(self, paths: list[str]) -> None:
        staging = self._ensure_staging()
        for raw in paths:
            path = Path(raw)
            if path.is_dir():
                self._asset_dir = str(path)
                self.assets_label.setText(f"素材文件夹：{path}")
                self.log("info", f"已选择素材文件夹：{path}")
                continue
            suffix = path.suffix.lower()
            if suffix in DOC_SUFFIXES:
                self._add_doc(str(path))
            elif suffix in ASSET_SUFFIXES:
                target = Path(staging) / path.name
                if not target.exists():
                    shutil.copy2(path, target)
                self._asset_dir = staging
                self.assets_label.setText(f"素材：拖入的 {len(list(Path(staging).iterdir()))} 张图片")
                self.log("info", f"已加入拖入图片：{path.name}")
            else:
                self.log("warn", f"不支持的文件类型，已忽略：{path.name}")

    def _pick_docs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择文档", str(Path.home()), "文档 (*.md *.markdown *.csv *.json *.pptx)"
        )
        for path in paths:
            self._add_doc(path)

    def _pick_assets(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择素材文件夹", str(Path.home()))
        if directory:
            self._asset_dir = directory
            self.assets_label.setText(f"素材文件夹：{directory}")
            self.log("info", f"已选择素材文件夹：{directory}")

    def _add_doc(self, path: str) -> None:
        if path in self._doc_paths:
            return
        self._doc_paths.append(path)
        size_kb = Path(path).stat().st_size / 1024
        item = QListWidgetItem(f"{Path(path).name}   {Path(path).suffix.lower().lstrip('.')} · {size_kb:.0f} KB")
        item.setToolTip(path)
        item.setData(Qt.ItemDataRole.UserRole, path)
        self.file_list.addItem(item)
        self.log("info", f"已添加文档：{path}")

    def _remove_selected(self) -> None:
        for item in self.file_list.selectedItems():
            path = item.data(Qt.ItemDataRole.UserRole)
            if path in self._doc_paths:
                self._doc_paths.remove(path)
            self.file_list.takeItem(self.file_list.row(item))

    def _clear_all(self) -> None:
        self._doc_paths.clear()
        self.file_list.clear()
        self._asset_dir = ""
        self.assets_label.setText("素材文件夹：未选择（可选）")
        if self._staging_dir:
            shutil.rmtree(self._staging_dir, ignore_errors=True)
            self._staging_dir = None

    def _ensure_staging(self) -> str:
        if not self._staging_dir:
            self._staging_dir = tempfile.mkdtemp(prefix="motionnest-assets-")
        return self._staging_dir

    # ================================================================ 生成
    def _generate(self) -> None:
        if not self._doc_paths and not self._asset_dir:
            self.log("err", "请先添加至少一个文档或素材文件夹")
            return
        self._set_busy(True)
        self.result_card.hide()
        self._result = None
        note = self.note_edit.text().strip()

        def done(result: dict) -> None:
            self._result = result
            self._show_result(result)

        worker = CallableWorker(
            self.bridge.generate_promo,
            logger=self._log,
            doc_paths=list(self._doc_paths),
            asset_dir=self._asset_dir,
            note=note,
            quality="final",
        )
        worker.finished_ok.connect(done)
        worker.finished.connect(lambda: self._set_busy(False))
        self._workers.append(worker)
        worker.start()
        self.log("info", "开始生成 30 秒宣传片…")

    def _show_result(self, result: dict) -> None:
        duration = result.get("duration_s")
        meta = (
            f"时长 {duration:.1f}s · {result.get('frames')} 帧 · {result.get('shots')} 个镜头"
            if duration is not None
            else f"{result.get('shots')} 个镜头"
        )
        degraded = result.get("degraded") or []
        if degraded:
            meta += f" · {len(degraded)} 条降级记录（见审计清单）"
        self.result_meta.setText(meta)
        self.result_path.setText(result.get("video", ""))
        self.result_card.show()

    def _play(self) -> None:
        if not self._result:
            return
        try:
            self.bridge.open_path(self._result["video"])
        except Exception as exc:  # noqa: BLE001 - 打开失败不致命
            self.log("err", f"无法播放：{exc}")

    def _open_folder(self) -> None:
        if not self._result:
            return
        try:
            self.bridge.reveal_in_folder(self._result["video"])
        except Exception as exc:  # noqa: BLE001
            self.log("err", f"无法打开文件夹：{exc}")

    # ================================================================ 工具
    def _default_output_dir(self) -> str:
        return self.settings_store.last_output_dir or str(DEFAULT_OUTPUT)

    def _log(self, level: str, message: str) -> None:
        self.log(level, message)

    def _set_busy(self, busy: bool) -> None:
        self.generate_button.setEnabled(not busy)
        self.generate_button.setText("生成中…" if busy else "生成 30 秒宣传片")
        self.drop_zone.docs_button.setEnabled(not busy)
        self.drop_zone.assets_button.setEnabled(not busy)

    def apply_theme(self, theme_name: str) -> None:
        """样式由全局 QSS 驱动，无需逐控件刷新。"""
