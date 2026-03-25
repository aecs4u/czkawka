import subprocess
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSizePolicy, QSplitter,
    QStackedWidget, QPlainTextEdit
)
from PySide6.QtCore import Qt, QSize, Signal, QObject
from PySide6.QtGui import QPixmap

from .localizer import tr
from .utils import format_size as _format_size


# File extension sets for different preview types
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".ico",
}

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".log", ".sh", ".bash",
    ".py", ".rs", ".js", ".ts", ".html", ".css", ".c", ".cpp",
    ".h", ".hpp", ".java", ".go", ".rb", ".php", ".sql",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ogv", ".ts",
}

PDF_EXTENSIONS = {".pdf"}

MAX_TEXT_PREVIEW_BYTES = 64 * 1024  # 64 KB


class _LoadResult(QObject):
    """Emitted from background thread when preview data is ready."""
    ready = Signal(str, object, str)  # (file_path, data, info_text)


class _PreviewSlot(QWidget):
    """Single preview slot supporting images, text, PDF, and video thumbnails.

    Heavy I/O (image loading, video thumbnail, PDF rendering) runs in a
    background thread so the UI stays responsive.
    """

    SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | TEXT_EXTENSIONS | VIDEO_EXTENSIONS | PDF_EXTENSIONS

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = ""
        self._pixmap = None
        self._pending_path = ""  # track which load is in-flight

        self._loader = _LoadResult()
        self._loader.ready.connect(self._on_loaded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_label.setMinimumSize(QSize(100, 100))
        self._image_label.setFrameShape(QLabel.StyledPanel)
        self._image_label.setScaledContents(False)
        layout.addWidget(self._image_label)

        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._text_edit.setVisible(False)
        layout.addWidget(self._text_edit)

        self._info_label = QLabel()
        self._info_label.setAlignment(Qt.AlignCenter)
        self._info_label.setWordWrap(True)
        self._info_label.setEnabled(False)
        layout.addWidget(self._info_label)

    def show_file(self, file_path: str):
        if not file_path:
            self.clear()
            return

        self._current_path = file_path
        p = Path(file_path)

        if not p.exists():
            self._show_image_mode()
            self._pixmap = None
            self._image_label.setText(tr("preview-file-not-found"))
            self._info_label.setText("")
            return

        ext = p.suffix.lower()

        if ext in TEXT_EXTENSIONS:
            # Text is fast enough to load inline
            self._preview_text(p)
        elif ext in (IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | PDF_EXTENSIONS):
            # Heavy previews: show placeholder, load in background
            self._show_image_mode()
            self._pixmap = None
            self._image_label.setText(tr("preview-loading"))
            self._info_label.setText(p.name)
            self._pending_path = file_path
            threading.Thread(
                target=self._load_heavy_preview,
                args=(file_path, ext),
                daemon=True,
            ).start()
        else:
            self._show_image_mode()
            self._pixmap = None
            self._image_label.setText(tr("preview-not-available"))
            self._info_label.setText(p.name)

    # ── Background loading ──────────────────────────────

    def _load_heavy_preview(self, file_path: str, ext: str):
        """Runs in a background thread. Loads data then signals the main thread."""
        p = Path(file_path)
        try:
            if ext in IMAGE_EXTENSIONS:
                data = p.read_bytes()
                size = len(data)
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if pixmap.isNull():
                    self._loader.ready.emit(file_path, None, p.name)
                else:
                    info = f"{p.name}\n{pixmap.width()}x{pixmap.height()} | {_format_size(size)}"
                    self._loader.ready.emit(file_path, pixmap, info)

            elif ext in VIDEO_EXTENSIONS:
                result = subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", file_path,
                        "-ss", "00:00:03", "-frames:v", "1",
                        "-f", "image2pipe", "-vcodec", "png", "-"
                    ],
                    capture_output=True, timeout=10,
                )
                if result.returncode == 0 and result.stdout:
                    pixmap = QPixmap()
                    pixmap.loadFromData(result.stdout)
                    if not pixmap.isNull():
                        size = p.stat().st_size
                        info = f"{p.name}\n{pixmap.width()}x{pixmap.height()} | {_format_size(size)}"
                        self._loader.ready.emit(file_path, pixmap, info)
                        return
                size = p.stat().st_size
                self._loader.ready.emit(file_path, "video_fail", f"{p.name} | {_format_size(size)}")

            elif ext in PDF_EXTENSIONS:
                from PySide6.QtPdf import QPdfDocument
                doc = QPdfDocument()
                doc.load(file_path)
                if doc.pageCount() > 0:
                    image = doc.render(0, QSize(380, 500))
                    pixmap = QPixmap.fromImage(image)
                    size = p.stat().st_size
                    info = f"{p.name}\n{doc.pageCount()} pages | {_format_size(size)}"
                    doc.close()
                    if not pixmap.isNull():
                        self._loader.ready.emit(file_path, pixmap, info)
                        return
                    doc.close()
                size = p.stat().st_size
                self._loader.ready.emit(file_path, "pdf_fail", f"{p.name} | {_format_size(size)}")

        except Exception:
            self._loader.ready.emit(file_path, None, p.name)

    def _on_loaded(self, file_path: str, data, info_text: str):
        """Called on the main thread when background load completes."""
        # Ignore stale results (user moved on to a different file)
        if file_path != self._pending_path:
            return

        self._show_image_mode()
        if isinstance(data, QPixmap):
            self._pixmap = data
            self._rescale()
            self._info_label.setText(info_text)
        elif data == "video_fail":
            self._pixmap = None
            self._image_label.setText(tr("preview-video-unavailable"))
            self._info_label.setText(info_text)
        elif data == "pdf_fail":
            self._pixmap = None
            self._image_label.setText(tr("preview-pdf-unavailable"))
            self._info_label.setText(info_text)
        else:
            self._pixmap = None
            self._image_label.setText(tr("preview-cannot-load"))
            self._info_label.setText(info_text)

    # ── Inline previews ─────────────────────────────────

    def _preview_text(self, p: Path):
        self._show_text_mode()
        self._pixmap = None
        try:
            size = p.stat().st_size
            with open(p, "r", errors="replace") as f:
                content = f.read(MAX_TEXT_PREVIEW_BYTES)
            if size > MAX_TEXT_PREVIEW_BYTES:
                content += f"\n\n... (truncated, {_format_size(size)} total)"
            self._text_edit.setPlainText(content)
            self._info_label.setText(f"{p.name} | {_format_size(size)}")
        except OSError:
            self._text_edit.setPlainText(tr("preview-read-error"))
            self._info_label.setText(p.name)

    # ── Mode switching ──────────────────────────────────

    def _show_image_mode(self):
        self._image_label.setVisible(True)
        self._text_edit.setVisible(False)

    def _show_text_mode(self):
        self._image_label.setVisible(False)
        self._text_edit.setVisible(True)

    def clear(self):
        self._current_path = ""
        self._pending_path = ""
        self._pixmap = None
        self._image_label.clear()
        self._image_label.setText(tr("preview-no-preview"))
        self._text_edit.clear()
        self._text_edit.setVisible(False)
        self._image_label.setVisible(True)
        self._info_label.setText("")

    def _rescale(self):
        if self._pixmap and not self._pixmap.isNull():
            label_size = self._image_label.size()
            scaled = self._pixmap.scaled(
                label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


class PreviewPanel(QWidget):
    """File preview panel supporting single and side-by-side comparison modes,
    with extended file type support (images, text, PDF, video)."""

    SUPPORTED_EXTENSIONS = _PreviewSlot.SUPPORTED_EXTENSIONS

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self._current_path = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._title = QLabel(tr("preview-title"))
        font = self._title.font()
        font.setBold(True)
        self._title.setFont(font)
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

        # Stacked widget: page 0 = single, page 1 = comparison
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Single preview mode
        self._single_slot = _PreviewSlot()
        self._stack.addWidget(self._single_slot)

        # Side-by-side comparison mode
        comparison_widget = QWidget()
        comparison_layout = QVBoxLayout(comparison_widget)
        comparison_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        self._left_slot = _PreviewSlot()
        self._right_slot = _PreviewSlot()
        splitter.addWidget(self._left_slot)
        splitter.addWidget(self._right_slot)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        comparison_layout.addWidget(splitter)

        self._stack.addWidget(comparison_widget)

    def show_preview(self, file_path: str):
        """Show a single file preview."""
        if not file_path or file_path == self._current_path:
            return
        self._current_path = file_path
        self._stack.setCurrentIndex(0)
        self._title.setText(tr("preview-title"))
        self._single_slot.show_file(file_path)

    def show_comparison(self, left_path: str, right_path: str):
        """Show two files side by side for comparison."""
        self._current_path = ""
        self._stack.setCurrentIndex(1)
        self._title.setText(tr("preview-comparison"))
        self.setMinimumWidth(400)
        self._left_slot.show_file(left_path)
        self._right_slot.show_file(right_path)

    def clear_preview(self):
        self._current_path = ""
        self._single_slot.clear()
        self._left_slot.clear()
        self._right_slot.clear()
        self._stack.setCurrentIndex(0)
        self._title.setText(tr("preview-title"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Only rescale the existing pixmap, don't reload the file
        self._single_slot._rescale()
        self._left_slot._rescale()
        self._right_slot._rescale()

