"""Shared utility functions and KDE HIG constants for the Kalka UI.

Spacing values follow the Kirigami Units specification:
https://api.kde.org/kirigami-platform-units.html
"""

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication, QLabel


# ── KDE HIG spacing constants (Kirigami Units) ─────────────

SMALL_SPACING = 4    # Between related items within a group
MEDIUM_SPACING = 6   # Toolbar item spacing
LARGE_SPACING = 8    # Between control groups; standard edge padding
GRID_UNIT = 18       # Fundamental sizing unit (font metrics height)
CORNER_RADIUS = 5    # Rounded corners on cards, containers

# Icon sizes (FreeDesktop / KDE HIG)
ICON_SMALL = QSize(16, 16)        # Menu icons
ICON_SMALL_MEDIUM = QSize(22, 22) # Toolbar icons
ICON_MEDIUM = QSize(32, 32)       # List items with subtitles
ICON_LARGE = QSize(48, 48)        # Large tiles

# Animation durations (ms)
TOOLTIP_DELAY = 700
SHORT_DURATION = 100
LONG_DURATION = 200


# ── DPI-aware sizing ────────────────────────────────────────

def dpi_scale(px: int) -> int:
    """Scale a pixel value by the current screen DPI ratio."""
    app = QApplication.instance()
    if app and app.primaryScreen():
        return round(px * app.primaryScreen().devicePixelRatio())
    return px


def grid_units(n: float) -> int:
    """Return n * GRID_UNIT, DPI-scaled."""
    return dpi_scale(round(GRID_UNIT * n))


# ── Palette helpers ─────────────────────────────────────────

def palette_color(role: QPalette.ColorRole):
    """Read a color from the current application palette."""
    app = QApplication.instance()
    return app.palette().color(role) if app else None


def is_dark_theme() -> bool:
    """Detect if the current system theme is dark."""
    bg = palette_color(QPalette.ColorRole.Window)
    return bg.lightness() < 128 if bg else False


# ── Widget helpers ──────────────────────────────────────────

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
