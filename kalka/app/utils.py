"""Shared utility functions for the Kalka UI."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel


def format_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable string (e.g. '1.5 MB')."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}" if i > 0 else f"{int(size)} B"


def make_bold_label(text: str, point_size: int | None = None) -> QLabel:
    """Create a QLabel with bold font and optional custom point size."""
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    if point_size is not None:
        font.setPointSize(point_size)
    label.setFont(font)
    return label
