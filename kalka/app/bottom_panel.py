from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QTextEdit, QStackedWidget,
    QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QUrl

from .models import AppSettings
from .localizer import tr


class _DroppableListWidget(QListWidget):
    """QListWidget that accepts folder drag & drop."""
    items_dropped = Signal(list)  # list of dropped directory paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # Accept if any URL is a directory
            for url in event.mimeData().urls():
                if url.isLocalFile() and Path(url.toLocalFile()).is_dir():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                p = url.toLocalFile()
                if Path(p).is_dir():
                    paths.append(p)
        if paths:
            self.items_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class BottomPanel(QWidget):
    """Bottom panel showing directories or error messages."""
    directories_changed = Signal()

    # Tabs that support reference folders (must match czkawka_core)
    REFERENCE_TABS = {"DUPLICATE_FILES", "SIMILAR_IMAGES", "SIMILAR_VIDEOS", "SIMILAR_MUSIC"}

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._reference_mode = False
        self._reference_visible = False
        self.setMaximumHeight(200)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self._stack = QStackedWidget()

        # Page 0: Directories view
        dir_widget = QWidget()
        dir_layout = QHBoxLayout(dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)

        # Included directories
        inc_widget = QWidget()
        inc_layout = QVBoxLayout(inc_widget)
        inc_layout.setContentsMargins(0, 0, 0, 0)
        inc_layout.addWidget(QLabel(tr("bottom-included-dirs")))

        self._inc_list = _DroppableListWidget()
        self._inc_list.setMaximumHeight(120)
        self._inc_list.items_dropped.connect(self._on_included_dropped)
        self._inc_list.itemChanged.connect(self._on_reference_checkbox_changed)
        for path in self._settings.included_paths:
            self._add_included_item(path)
        inc_layout.addWidget(self._inc_list)

        inc_btns = QHBoxLayout()
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.clicked.connect(self._add_included)
        inc_btns.addWidget(add_btn)
        rem_btn = QPushButton("-")
        rem_btn.setFixedWidth(30)
        rem_btn.clicked.connect(self._remove_included)
        inc_btns.addWidget(rem_btn)
        inc_btns.addStretch()
        inc_layout.addLayout(inc_btns)
        dir_layout.addWidget(inc_widget)

        # Excluded directories
        exc_widget = QWidget()
        exc_layout = QVBoxLayout(exc_widget)
        exc_layout.setContentsMargins(0, 0, 0, 0)
        exc_layout.addWidget(QLabel(tr("bottom-excluded-dirs")))

        self._exc_list = _DroppableListWidget()
        self._exc_list.setMaximumHeight(120)
        self._exc_list.items_dropped.connect(self._on_excluded_dropped)
        for path in self._settings.excluded_paths:
            self._exc_list.addItem(path)
        exc_layout.addWidget(self._exc_list)

        exc_btns = QHBoxLayout()
        add_exc = QPushButton("+")
        add_exc.setFixedWidth(30)
        add_exc.clicked.connect(self._add_excluded)
        exc_btns.addWidget(add_exc)
        rem_exc = QPushButton("-")
        rem_exc.setFixedWidth(30)
        rem_exc.clicked.connect(self._remove_excluded)
        exc_btns.addWidget(rem_exc)
        exc_btns.addStretch()
        exc_layout.addLayout(exc_btns)
        dir_layout.addWidget(exc_widget)

        self._stack.addWidget(dir_widget)

        # Page 1: Text errors/info
        self._text_area = QTextEdit()
        self._text_area.setReadOnly(True)
        self._text_area.setMaximumHeight(150)
        self._stack.addWidget(self._text_area)

        layout.addWidget(self._stack)

    def show_directories(self):
        self._stack.setCurrentIndex(0)
        self.setVisible(True)

    def show_text(self):
        self._stack.setCurrentIndex(1)
        self.setVisible(True)

    def hide_panel(self):
        self.setVisible(False)

    def set_text(self, text: str):
        self._text_area.setPlainText(text)

    def append_text(self, text: str):
        self._text_area.append(text)

    def _add_included_item(self, path: str):
        """Add an included directory item, with optional reference checkbox."""
        item = QListWidgetItem(path)
        is_ref = path in self._settings.reference_paths
        if self._reference_visible:
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if is_ref else Qt.Unchecked)
            item.setToolTip(tr("bottom-reference-tooltip"))
        self._inc_list.addItem(item)

    def _add_included(self):
        path = QFileDialog.getExistingDirectory(self, tr("settings-select-dir-include"))
        if path and path not in self._settings.included_paths:
            self._settings.included_paths.append(path)
            self._add_included_item(path)
            self.directories_changed.emit()

    def _remove_included(self):
        row = self._inc_list.currentRow()
        if row >= 0:
            path = self._inc_list.item(row).text()
            self._inc_list.takeItem(row)
            self._settings.included_paths.pop(row)
            # Also remove from reference paths if present
            if path in self._settings.reference_paths:
                self._settings.reference_paths.remove(path)
            self.directories_changed.emit()

    def _add_excluded(self):
        path = QFileDialog.getExistingDirectory(self, tr("settings-select-dir-exclude"))
        if path and path not in self._settings.excluded_paths:
            self._settings.excluded_paths.append(path)
            self._exc_list.addItem(path)
            self.directories_changed.emit()

    def _remove_excluded(self):
        row = self._exc_list.currentRow()
        if row >= 0:
            self._exc_list.takeItem(row)
            self._settings.excluded_paths.pop(row)
            self.directories_changed.emit()

    def _on_included_dropped(self, paths: list):
        for path in paths:
            if path not in self._settings.included_paths:
                self._settings.included_paths.append(path)
                self._add_included_item(path)
        self.directories_changed.emit()

    def _on_excluded_dropped(self, paths: list):
        for path in paths:
            if path not in self._settings.excluded_paths:
                self._settings.excluded_paths.append(path)
                self._exc_list.addItem(path)
        self.directories_changed.emit()

    def _on_reference_checkbox_changed(self, item: QListWidgetItem):
        """Update reference_paths when a checkbox is toggled."""
        path = item.text()
        is_checked = item.checkState() == Qt.Checked
        if is_checked and path not in self._settings.reference_paths:
            self._settings.reference_paths.append(path)
        elif not is_checked and path in self._settings.reference_paths:
            self._settings.reference_paths.remove(path)
        self.directories_changed.emit()

    def set_reference_visible(self, visible: bool):
        """Show or hide reference checkboxes on included directory items."""
        if visible == self._reference_visible:
            return
        self._reference_visible = visible
        self._rebuild_included_items()

    def _rebuild_included_items(self):
        """Rebuild included list items with or without checkboxes."""
        self._inc_list.blockSignals(True)
        self._inc_list.clear()
        for path in self._settings.included_paths:
            self._add_included_item(path)
        self._inc_list.blockSignals(False)

    def refresh_lists(self):
        self._rebuild_included_items()
        self._exc_list.clear()
        for path in self._settings.excluded_paths:
            self._exc_list.addItem(path)
