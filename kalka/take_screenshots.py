#!/usr/bin/env python3
"""Generate screenshots of the Kalka UI with sample data.

Usage:
    cd kalka
    python take_screenshots.py

Saves PNG files to kalka/screenshots/.
Requires a display (X11/Wayland) or use with xvfb-run for headless:
    xvfb-run -a python take_screenshots.py
"""

import sys
import os
from pathlib import Path

# Ensure we can import app modules
sys.path.insert(0, str(Path(__file__).parent))


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "xcb"))

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    from app.localizer import init as init_l10n
    init_l10n()

    app = QApplication(sys.argv)
    app.setApplicationName("Kalka")

    from PySide6.QtGui import QIcon
    from app.icons import app_icon
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    from app.main_window import MainWindow
    window = MainWindow()
    window.resize(1280, 800)
    window.show()

    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    # Schedule screenshots after the event loop starts and widgets are painted
    QTimer.singleShot(500, lambda: _take_all_screenshots(window, screenshots_dir, app))

    app.exec()


def _take_all_screenshots(window, out_dir: Path, app):
    """Take screenshots of various UI states."""
    from PySide6.QtCore import QTimer
    from app.models import ActiveTab, ResultEntry

    steps = [
        ("duplicates", ActiveTab.DUPLICATE_FILES, _make_duplicate_data),
        ("similar-images", ActiveTab.SIMILAR_IMAGES, _make_similar_images_data),
        ("similar-music", ActiveTab.SIMILAR_MUSIC, _make_similar_music_data),
        ("empty-folders", ActiveTab.EMPTY_FOLDERS, _make_empty_folders_data),
        ("broken-files", ActiveTab.BROKEN_FILES, _make_broken_files_data),
        ("settings", None, None),
    ]

    def run_step(idx):
        if idx >= len(steps):
            # Final: take the about dialog screenshot
            _screenshot_about(window, out_dir)
            print(f"All screenshots saved to {out_dir}/")
            app.quit()
            return

        name, tab, data_fn = steps[idx]

        if name == "settings":
            _screenshot_settings(window, out_dir)
        else:
            # Switch tab
            window._left_panel.set_active_tab(tab)
            window._on_tab_changed(tab)

            # Populate with sample data
            results = data_fn()
            window._state.set_results(tab, results)
            window._results_view.set_results(results)
            window._action_buttons.set_has_results(True)

        # Let the UI repaint, then grab
        QTimer.singleShot(300, lambda: _grab_and_next(window, out_dir, name, idx))

    def _grab_and_next(window, out_dir, name, idx):
        pixmap = window.grab()
        path = out_dir / f"{name}.png"
        pixmap.save(str(path))
        print(f"  Saved {path.name} ({pixmap.width()}x{pixmap.height()})")
        QTimer.singleShot(200, lambda: run_step(idx + 1))

    print("Taking screenshots...")
    run_step(0)


def _screenshot_settings(window, out_dir: Path):
    """Open settings panel and take screenshot."""
    window._show_settings()


def _screenshot_about(window, out_dir: Path):
    """Open about dialog and take screenshot."""
    from app.dialogs import AboutDialog
    from PySide6.QtCore import QTimer

    dialog = AboutDialog(window)
    dialog.resize(520, 550)
    dialog.show()

    def grab_dialog():
        pixmap = dialog.grab()
        path = out_dir / "about.png"
        pixmap.save(str(path))
        print(f"  Saved about.png ({pixmap.width()}x{pixmap.height()})")
        dialog.close()

    QTimer.singleShot(300, grab_dialog)


# ── Sample data generators ──────────────────────────────────

def _make_result(values: dict, header=False, checked=False, group_id=0) -> "ResultEntry":
    from app.models import ResultEntry
    return ResultEntry(
        values=values,
        header_row=header,
        checked=checked,
        group_id=group_id,
    )


def _make_duplicate_data():
    """Generate sample duplicate file entries."""
    results = []
    groups = [
        {
            "header": "Group 1 — 3 files, 15.2 MB",
            "files": [
                {"Size": "5.1 MB", "File Name": "report_2024.pdf", "Path": "/home/user/Documents", "Modification Date": "2024-11-15", "Hash": "a3f8c1..."},
                {"Size": "5.1 MB", "File Name": "report_2024_copy.pdf", "Path": "/home/user/Downloads", "Modification Date": "2024-11-20", "Hash": "a3f8c1..."},
                {"Size": "5.1 MB", "File Name": "report_2024 (1).pdf", "Path": "/home/user/Desktop", "Modification Date": "2024-12-01", "Hash": "a3f8c1..."},
            ],
        },
        {
            "header": "Group 2 — 2 files, 128.0 MB",
            "files": [
                {"Size": "64.0 MB", "File Name": "vacation_video.mp4", "Path": "/home/user/Videos", "Modification Date": "2024-08-10", "Hash": "b7e2d0..."},
                {"Size": "64.0 MB", "File Name": "vacation_video_backup.mp4", "Path": "/mnt/backup/Videos", "Modification Date": "2024-08-10", "Hash": "b7e2d0..."},
            ],
        },
        {
            "header": "Group 3 — 4 files, 2.4 MB",
            "files": [
                {"Size": "612 KB", "File Name": "logo.png", "Path": "/home/user/Projects/website/assets", "Modification Date": "2024-06-01", "Hash": "c9a1f2..."},
                {"Size": "612 KB", "File Name": "logo.png", "Path": "/home/user/Projects/website/public", "Modification Date": "2024-06-01", "Hash": "c9a1f2..."},
                {"Size": "612 KB", "File Name": "logo_original.png", "Path": "/home/user/Projects/website/src", "Modification Date": "2024-05-28", "Hash": "c9a1f2..."},
                {"Size": "612 KB", "File Name": "logo.png", "Path": "/home/user/Projects/mobile/assets", "Modification Date": "2024-07-15", "Hash": "c9a1f2..."},
            ],
        },
    ]
    for gid, group in enumerate(groups):
        results.append(_make_result({"__header": group["header"]}, header=True, group_id=gid))
        for i, f in enumerate(group["files"]):
            f["__full_path"] = f"{f['Path']}/{f['File Name']}"
            results.append(_make_result(f, checked=(i > 0), group_id=gid))
    return results


def _make_similar_images_data():
    """Generate sample similar image entries."""
    results = []
    groups = [
        {
            "header": "Group 1 — 2 images, 95% similar",
            "files": [
                {"Similarity": "95%", "Size": "3.2 MB", "Resolution": "4032x3024", "File Name": "IMG_20240815.jpg", "Path": "/home/user/Photos/2024", "Modification Date": "2024-08-15", "Hash": "d4e5f6..."},
                {"Similarity": "95%", "Size": "3.1 MB", "Resolution": "4032x3024", "File Name": "IMG_20240815_edited.jpg", "Path": "/home/user/Photos/Edited", "Modification Date": "2024-08-16", "Hash": "d4e5f7..."},
            ],
        },
        {
            "header": "Group 2 — 3 images, 88% similar",
            "files": [
                {"Similarity": "88%", "Size": "2.8 MB", "Resolution": "3840x2160", "File Name": "sunset_beach.jpg", "Path": "/home/user/Photos/Vacation", "Modification Date": "2024-07-20", "Hash": "e5f6a7..."},
                {"Similarity": "88%", "Size": "2.7 MB", "Resolution": "3840x2160", "File Name": "sunset_beach_2.jpg", "Path": "/home/user/Photos/Vacation", "Modification Date": "2024-07-20", "Hash": "e5f6a8..."},
                {"Similarity": "88%", "Size": "1.5 MB", "Resolution": "1920x1080", "File Name": "sunset_resized.jpg", "Path": "/home/user/Photos/Web", "Modification Date": "2024-07-22", "Hash": "e5f6a9..."},
            ],
        },
    ]
    for gid, group in enumerate(groups):
        results.append(_make_result({"__header": group["header"]}, header=True, group_id=gid))
        for i, f in enumerate(group["files"]):
            f["__full_path"] = f"{f['Path']}/{f['File Name']}"
            results.append(_make_result(f, checked=(i > 0), group_id=gid))
    return results


def _make_similar_music_data():
    results = []
    groups = [
        {
            "header": "Group 1 — same title + artist",
            "files": [
                {"Size": "8.5 MB", "File Name": "bohemian_rhapsody.mp3", "Path": "/home/user/Music/Queen", "Title": "Bohemian Rhapsody", "Artist": "Queen", "Year": "1975", "Bitrate": "320", "Genre": "Rock", "Length": "5:55"},
                {"Size": "4.2 MB", "File Name": "bohemian_rhapsody_128.mp3", "Path": "/home/user/Music/Downloads", "Title": "Bohemian Rhapsody", "Artist": "Queen", "Year": "1975", "Bitrate": "128", "Genre": "Rock", "Length": "5:55"},
            ],
        },
    ]
    for gid, group in enumerate(groups):
        results.append(_make_result({"__header": group["header"]}, header=True, group_id=gid))
        for i, f in enumerate(group["files"]):
            f["__full_path"] = f"{f['Path']}/{f['File Name']}"
            results.append(_make_result(f, checked=(i > 0), group_id=gid))
    return results


def _make_empty_folders_data():
    results = []
    folders = [
        {"Folder Name": "old_project", "Path": "/home/user/Projects", "Modification Date": "2023-01-15"},
        {"Folder Name": ".cache", "Path": "/home/user/Projects/build", "Modification Date": "2024-03-01"},
        {"Folder Name": "temp", "Path": "/home/user/Downloads", "Modification Date": "2024-10-20"},
        {"Folder Name": "empty_backup", "Path": "/mnt/external/Backups", "Modification Date": "2024-06-05"},
        {"Folder Name": "__pycache__", "Path": "/home/user/Projects/kalka/app", "Modification Date": "2024-12-01"},
    ]
    for f in folders:
        f["__full_path"] = f"{f['Path']}/{f['Folder Name']}"
        results.append(_make_result(f, checked=True, group_id=0))
    return results


def _make_broken_files_data():
    results = []
    files = [
        {"File Name": "corrupted.zip", "Path": "/home/user/Downloads", "Error Type": "Invalid ZIP header", "Size": "12.5 MB", "Modification Date": "2024-09-10"},
        {"File Name": "damaged_photo.jpg", "Path": "/home/user/Photos", "Error Type": "Truncated JPEG data", "Size": "2.1 MB", "Modification Date": "2024-08-20"},
        {"File Name": "broken.pdf", "Path": "/home/user/Documents", "Error Type": "Invalid PDF structure", "Size": "156 KB", "Modification Date": "2024-11-05"},
    ]
    for f in files:
        f["__full_path"] = f"{f['Path']}/{f['File Name']}"
        results.append(_make_result(f, checked=True, group_id=0))
    return results


if __name__ == "__main__":
    main()
