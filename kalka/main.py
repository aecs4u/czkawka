#!/usr/bin/env python3
"""
Kalka - A PySide6/Qt interface for czkawka file cleanup tool.

This application provides a graphical interface to czkawka, using the
czkawka_cli binary as its backend for all scanning operations.

Usage:
    python main.py
    python main.py --log-level DEBUG
    python main.py --log-file /tmp/kalka.log

Requirements:
    - PySide6 >= 6.6.0
    - czkawka_cli binary in PATH (or configured in settings)
    - Optional: send2trash (for trash support)
    - Optional: Pillow (for EXIF cleaning)
"""

import sys
import os
from enum import Enum
from typing import Optional

import typer


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


app = typer.Typer(add_completion=False)


@app.command()
def main(
    log_level: LogLevel = typer.Option(
        LogLevel.WARNING,
        help="Set logging verbosity.",
    ),
    log_file: Optional[str] = typer.Option(
        None,
        help="Write structured JSON logs to this local file.",
    ),
):
    """Kalka - PySide6 GUI for czkawka file cleanup."""

    # Initialize structured logging before anything else
    from app.logger import init as init_logging
    init_logging(level=log_level.value, log_file=log_file)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    # Initialize i18n before creating any widgets.
    # Read saved language preference from config (before QApplication exists).
    from app.localizer import init as init_l10n
    locale_override = None
    try:
        import json
        from pathlib import Path
        config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.join(Path.home(), ".config"))
        config_file = Path(config_dir) / "czkawka" / "settings.json"
        if config_file.exists():
            data = json.loads(config_file.read_text())
            lang = data.get("language", "")
            if lang:
                locale_override = lang
    except Exception:
        pass
    init_l10n(locale_override)

    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("Kalka")
    qt_app.setApplicationVersion("11.0.1")
    qt_app.setOrganizationName("czkawka")
    qt_app.setOrganizationDomain("github.com/qarmin")
    qt_app.setDesktopFileName("com.github.qarmin.kalka")

    # Set application icon — use XDG theme icon with fallback to project logo
    from PySide6.QtGui import QIcon
    icon = QIcon.fromTheme("com.github.qarmin.czkawka")
    if icon.isNull():
        from app.icons import app_icon
        icon = app_icon()
    if not icon.isNull():
        qt_app.setWindowIcon(icon)

    # Import and create main window
    from app.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    app()
