"""Main application window for Kalka interface."""

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QMessageBox, QLabel, QApplication, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, QStandardPaths
from PySide6.QtGui import QPalette, QColor

from .state import AppState
from .models import (
    ActiveTab, TAB_COLUMNS, GROUPED_TABS, TABS_WITH_SETTINGS, SelectMode
)
from .left_panel import LeftPanel
from .results_view import ResultsView
from .action_buttons import ActionButtons
from .tool_settings import ToolSettingsPanel
from .settings_panel import SettingsPanel
from .progress_widget import ProgressWidget
from .preview_panel import PreviewPanel
from .bottom_panel import BottomPanel
from .backend import ScanRunner, FileOperations
from .icons import app_icon
from .localizer import tr
from .dialogs import (
    DeleteDialog, MoveDialog, SelectDialog,
    SortDialog, SaveDialog, RenameDialog, AboutDialog
)


class MainWindow(QMainWindow):
    """Main application window with all panels and functionality."""

    def __init__(self):
        super().__init__()
        self._state = AppState()
        self._scan_runner = ScanRunner(self)
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._update_reference_visibility()

        # Restore saved window geometry
        if self._state.settings.save_window_geometry:
            s = self._state.settings
            if s.window_x >= 0 and s.window_y >= 0:
                self.move(s.window_x, s.window_y)
            if s.window_width > 0 and s.window_height > 0:
                self.resize(s.window_width, s.window_height)

        # Apply application scale
        if self._state.settings.app_scale != 1.0:
            from PySide6.QtCore import QCoreApplication
            import os
            os.environ["QT_SCALE_FACTOR"] = str(self._state.settings.app_scale)

        # Live theme switching: re-derive palette colors when system theme changes
        QApplication.instance().paletteChanged.connect(
            lambda: self._results_view._ensure_header_colors()
        )

    def _setup_window(self):
        self.setWindowTitle(tr("main-window-title"))
        self.setMinimumSize(900, 600)
        self.resize(1200, 800)

        # Set window icon from project logo
        icon = app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        # Auto-detect czkawka_cli binary
        self._auto_detect_cli()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top area: left panel + content
        content_splitter = QSplitter(Qt.Horizontal)

        # Left panel (tool selection)
        self._left_panel = LeftPanel()
        content_splitter.addWidget(self._left_panel)

        # Center area
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Results view
        self._results_view = ResultsView()
        center_layout.addWidget(self._results_view, 1)

        # Progress widget (hidden by default)
        self._progress = ProgressWidget()
        center_layout.addWidget(self._progress)

        content_splitter.addWidget(center_widget)

        # Tool settings panel (hidden by default)
        self._tool_settings = ToolSettingsPanel(self._state.tool_settings)
        self._tool_settings.setVisible(False)
        content_splitter.addWidget(self._tool_settings)

        # Preview panel (hidden by default)
        self._preview = PreviewPanel()
        self._preview.setVisible(False)
        content_splitter.addWidget(self._preview)

        # Set splitter sizes
        content_splitter.setStretchFactor(0, 0)  # Left panel: fixed
        content_splitter.setStretchFactor(1, 1)  # Center: stretch
        content_splitter.setStretchFactor(2, 0)  # Tool settings: fixed
        content_splitter.setStretchFactor(3, 0)  # Preview: fixed

        main_layout.addWidget(content_splitter, 1)

        # Action buttons bar
        self._action_buttons = ActionButtons()
        main_layout.addWidget(self._action_buttons)

        # Bottom panel (directories / errors)
        self._bottom_panel = BottomPanel(self._state.settings)
        self._bottom_panel.show_directories()
        main_layout.addWidget(self._bottom_panel)

        # Settings panel (overlay, hidden by default)
        self._settings_panel = SettingsPanel(self._state.settings)
        self._settings_panel.setVisible(False)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel(tr("status-ready"))
        self._statusbar.addWidget(self._status_label, 1)

        # Initialize results view columns for default tab
        self._results_view.set_active_tab(self._state.active_tab)

    def _connect_signals(self):
        # Left panel
        self._left_panel.tab_changed.connect(self._on_tab_changed)
        self._left_panel.settings_requested.connect(self._show_settings)
        self._left_panel.about_requested.connect(self._show_about)
        self._left_panel.tool_settings_toggled.connect(self._toggle_tool_settings)

        # Action buttons
        self._action_buttons.scan_clicked.connect(self._start_scan)
        self._action_buttons.stop_clicked.connect(self._stop_scan)
        self._action_buttons.select_clicked.connect(self._show_select_dialog)
        self._action_buttons.delete_clicked.connect(self._show_delete_dialog)
        self._action_buttons.move_clicked.connect(self._show_move_dialog)
        self._action_buttons.save_clicked.connect(self._save_results)
        self._action_buttons.load_clicked.connect(self._load_results)
        self._action_buttons.sort_clicked.connect(self._show_sort_dialog)
        self._action_buttons.hardlink_clicked.connect(self._create_hardlinks)
        self._action_buttons.symlink_clicked.connect(self._create_symlinks)
        self._action_buttons.rename_clicked.connect(self._rename_files)
        self._action_buttons.clean_exif_clicked.connect(self._clean_exif)
        self._action_buttons.optimize_video_clicked.connect(self._optimize_video)

        # Hamburger menu
        self._action_buttons.settings_clicked.connect(self._show_settings)
        self._action_buttons.about_clicked.connect(self._show_about)
        self._action_buttons.save_profile_clicked.connect(self._save_profile)
        self._action_buttons.load_profile_clicked.connect(self._load_profile)
        self._refresh_profile_menu()

        # Results view
        self._results_view.selection_changed.connect(
            lambda count: self._action_buttons.set_has_selection(count > 0)
        )
        self._results_view.item_activated.connect(self._on_item_activated)
        self._results_view.current_items_changed.connect(self._on_current_items_changed)

        # Tool settings
        self._tool_settings.reference_toggled.connect(self._on_reference_toggled)
        self._tool_settings.set_use_reference(self._state.settings.use_reference_folders)

        # Scan runner
        self._scan_runner.finished.connect(self._on_scan_finished)
        self._scan_runner.progress.connect(self._on_scan_progress)
        self._scan_runner.error.connect(self._on_scan_error)
        self._scan_runner.diagnostics.connect(self._on_scan_diagnostics)

        # Settings
        self._settings_panel.close_requested.connect(
            lambda: self._settings_panel.setVisible(False)
        )
        self._settings_panel.settings_changed.connect(self._on_settings_changed)
        self._settings_panel.settings_changed.connect(self._apply_icons_mode)

        # Bottom panel
        self._bottom_panel.directories_changed.connect(self._on_settings_changed)

    def _on_tab_changed(self, tab: ActiveTab):
        self._state.set_active_tab(tab)
        self._results_view.set_active_tab(tab)
        self._action_buttons.set_active_tab(tab)
        self._tool_settings.set_active_tab(tab)
        self._update_reference_visibility()

        # Show/hide preview for image-related tabs
        show_preview = (
            tab in (ActiveTab.SIMILAR_IMAGES, ActiveTab.DUPLICATE_FILES)
            and self._state.settings.show_image_preview
        )
        self._preview.setVisible(show_preview)

        # Load existing results for this tab
        results = self._state.get_results(tab)
        if results:
            self._results_view.set_results(results)
            self._action_buttons.set_has_results(True)
        else:
            self._results_view.clear()
            self._action_buttons.set_has_results(False)

        self._status_label.setText(tr("status-tab", tab_name=tab.name.replace('_', ' ').title()))

    def _update_reference_visibility(self):
        """Show reference checkboxes on included dirs when reference mode is active and tab supports it."""
        tab = self._state.active_tab
        tab_supports = tab.name in self._bottom_panel.REFERENCE_TABS
        visible = self._state.settings.use_reference_folders and tab_supports
        self._bottom_panel.set_reference_visible(visible)

    def _start_scan(self):
        tab = self._state.active_tab
        if not self._state.settings.included_paths:
            QMessageBox.warning(
                self, tr("no-directories-title"),
                tr("no-directories-message")
            )
            return

        self._state.set_scanning(True)
        self._action_buttons.set_scanning(True)
        self._progress.start(
            tab,
            included_paths=self._state.settings.included_paths,
            excluded_paths=self._state.settings.excluded_paths,
        )
        self._results_view.clear()
        self._status_label.setText(tr("status-scanning", tab_name=tab.name.replace('_', ' ').title()))

        self._scan_runner.start_scan(
            tab, self._state.settings, self._state.tool_settings
        )

    def _stop_scan(self):
        self._state.request_stop()
        self._scan_runner.stop_scan()
        self._status_label.setText(tr("status-scan-stopped"))

    def _on_scan_finished(self, tab: ActiveTab, results: list):
        self._state.set_scanning(False)
        self._state.set_results(tab, results)
        self._action_buttons.set_scanning(False)
        self._progress.stop()

        if tab == self._state.active_tab:
            self._results_view.set_results(results)
            self._action_buttons.set_has_results(len(results) > 0)

        count = sum(1 for r in results if not r.header_row)
        self._status_label.setText(tr("status-scan-complete", count=count))

        # Notifications
        if self._state.settings.notify_on_completion:
            self._send_notification(count)
        if self._state.settings.play_sound_on_completion:
            self._play_completion_sound()

    def _on_scan_progress(self, progress):
        self._progress.update_progress(progress)

    def _on_scan_error(self, error_msg: str):
        self._state.set_scanning(False)
        self._action_buttons.set_scanning(False)
        self._progress.stop()
        self._status_label.setText(tr("status-error", message=error_msg))
        self._bottom_panel.set_text(tr("status-error", message=error_msg))
        self._bottom_panel.show_text()
        QMessageBox.critical(self, tr("scan-error-title"), error_msg)

    def _on_scan_diagnostics(self, lines: list):
        if lines:
            self._bottom_panel.set_text("\n".join(lines))
            self._bottom_panel.show_text()

    def _on_item_activated(self, entry):
        path = entry.values.get("__full_path", "")
        if path and self._preview.isVisible():
            self._preview.show_preview(path)

    def _on_current_items_changed(self, paths: list):
        """Handle tree selection changes for preview/comparison."""
        if not self._preview.isVisible():
            return
        if len(paths) == 2:
            self._preview.show_comparison(paths[0], paths[1])
        elif len(paths) == 1:
            self._preview.show_preview(paths[0])
        elif len(paths) == 0:
            self._preview.clear_preview()

    def _on_reference_toggled(self, enabled: bool):
        self._state.settings.use_reference_folders = enabled
        # Sync all reference checkboxes across tool panels
        self._tool_settings.blockSignals(True)
        self._tool_settings.set_use_reference(enabled)
        self._tool_settings.blockSignals(False)
        self._update_reference_visibility()

    def _show_settings(self):
        self._settings_panel.setVisible(True)
        # Show as a floating window
        self._settings_panel.setParent(None)
        self._settings_panel.setWindowTitle(tr("settings-window-title"))
        self._settings_panel.setMinimumSize(600, 500)
        self._settings_panel.show()
        self._settings_panel.raise_()

    def _show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def _toggle_tool_settings(self, visible: bool):
        self._tool_settings.setVisible(visible)

    def _show_select_dialog(self):
        dialog = SelectDialog(self)
        dialog.mode_selected.connect(self._results_view.apply_selection)
        dialog.exec()

    def _show_delete_dialog(self):
        checked = self._results_view.get_checked_entries()
        if not checked:
            QMessageBox.information(self, tr("no-selection-title"), tr("no-selection-delete"))
            return

        dialog = DeleteDialog(len(checked), self._state.settings.move_to_trash, self)
        if dialog.exec() == DeleteDialog.Accepted:
            dry_run = dialog.dry_run
            deleted, errors = FileOperations.delete_files(
                checked, dialog.move_to_trash, dry_run=dry_run
            )
            self._status_label.setText(tr("status-deleted-dry-run", count=deleted) if dry_run else tr("status-deleted", count=deleted))
            self._show_errors(errors)
            # Refresh results - remove deleted entries (skip on dry run)
            if not dry_run:
                self._refresh_after_action(checked)

    def _show_move_dialog(self):
        checked = self._results_view.get_checked_entries()
        if not checked:
            QMessageBox.information(self, tr("no-selection-title"), tr("no-selection-move"))
            return

        dialog = MoveDialog(len(checked), self)
        if dialog.exec() == MoveDialog.Accepted:
            if not dialog.destination:
                QMessageBox.warning(self, tr("no-destination-title"), tr("no-destination-message"))
                return
            dry_run = dialog.dry_run
            moved, errors = FileOperations.move_files(
                checked, dialog.destination,
                dialog.preserve_structure, dialog.copy_mode,
                dry_run=dry_run
            )
            action_key = "status-copied" if dialog.copy_mode else "status-moved"
            dry_key = action_key + "-dry-run" if dry_run else action_key
            self._status_label.setText(tr(dry_key, count=moved))
            self._show_errors(errors)
            if not dialog.copy_mode and not dry_run:
                self._refresh_after_action(checked)

    def _save_results(self):
        results = self._results_view.get_all_entries()
        if not results:
            QMessageBox.information(self, tr("no-results-title"), tr("no-results-save"))
            return
        all_results = self._state.get_results()
        success = SaveDialog.save(self, all_results, self._state.settings.save_as_json)
        if success:
            self._status_label.setText(tr("status-results-saved"))

    def _load_results(self):
        results = SaveDialog.load(self)
        if results is None:
            return
        tab = self._state.active_tab
        self._state.set_results(tab, results)
        self._results_view.set_results(results)
        self._action_buttons.set_has_results(
            any(not r.header_row for r in results)
        )
        count = sum(1 for r in results if not r.header_row)
        self._status_label.setText(tr("status-results-loaded", count=count))

    def _show_sort_dialog(self):
        columns = TAB_COLUMNS.get(self._state.active_tab, [])
        if not columns:
            return
        dialog = SortDialog(columns, self)
        dialog.sort_requested.connect(self._results_view.sort_by_column)
        dialog.exec()

    def _find_reference_file(self, checked: list) -> str | None:
        """Find the first unchecked file in the same group as the checked entries."""
        all_results = self._state.get_results()
        group_id = checked[0].group_id
        for r in all_results:
            if r.group_id == group_id and not r.header_row and not r.checked:
                return r.values.get("__full_path", "")
        return None

    def _show_errors(self, errors: list[str]):
        """Display errors in the bottom panel if any."""
        if errors:
            self._bottom_panel.set_text("\n".join(errors))
            self._bottom_panel.show_text()

    def _create_hardlinks(self):
        checked = self._results_view.get_checked_entries()
        if not checked:
            return

        reference = self._find_reference_file(checked)
        if not reference:
            QMessageBox.warning(self, tr("no-reference-title"), tr("no-reference-message"))
            return

        reply = QMessageBox.question(
            self, tr("hardlink-dialog-title"),
            tr("hardlink-dialog-message", count=len(checked), reference=reference),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            created, errors = FileOperations.create_hardlinks(checked, reference)
            self._status_label.setText(tr("status-hardlinks-created", count=created))
            self._show_errors(errors)

    def _create_symlinks(self):
        checked = self._results_view.get_checked_entries()
        if not checked:
            return

        reference = self._find_reference_file(checked)
        if not reference:
            QMessageBox.warning(self, tr("no-reference-title"), tr("no-reference-message"))
            return

        reply = QMessageBox.question(
            self, tr("symlink-dialog-title"),
            tr("symlink-dialog-message", count=len(checked), reference=reference),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            created, errors = FileOperations.create_symlinks(checked, reference)
            self._status_label.setText(tr("status-symlinks-created", count=created))
            self._show_errors(errors)

    def _rename_files(self):
        checked = self._results_view.get_checked_entries()
        if not checked:
            return

        tab = self._state.active_tab
        if tab == ActiveTab.BAD_EXTENSIONS:
            dialog = RenameDialog(len(checked), "extensions", self)
            if dialog.exec() == RenameDialog.Accepted:
                self._status_label.setText(tr("status-fixing-extensions"))
                FileOperations.fix_extensions_async(
                    self._state.settings.czkawka_cli_path,
                    self._state.settings, self._state.tool_settings,
                    lambda ok, msg: QTimer.singleShot(0, lambda: self._status_label.setText(
                        tr("status-extensions-fixed") if ok else tr("status-error", message=msg)
                    ))
                )
        elif tab == ActiveTab.BAD_NAMES:
            dialog = RenameDialog(len(checked), "names", self)
            if dialog.exec() == RenameDialog.Accepted:
                self._status_label.setText(tr("status-fixing-names"))
                FileOperations.fix_bad_names_async(
                    self._state.settings.czkawka_cli_path,
                    self._state.settings, self._state.tool_settings,
                    lambda ok, msg: QTimer.singleShot(0, lambda: self._status_label.setText(
                        tr("status-names-fixed") if ok else tr("status-error", message=msg)
                    ))
                )

    def _clean_exif(self):
        checked = self._results_view.get_checked_entries()
        if not checked:
            return

        reply = QMessageBox.question(
            self, tr("exif-dialog-title"),
            tr("exif-dialog-message", count=len(checked)),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._status_label.setText(tr("status-cleaning-exif"))

            def _on_exif_done(cleaned, errors):
                QTimer.singleShot(0, lambda: self._on_exif_complete(cleaned, errors))

            FileOperations.clean_exif_async(
                self._state.settings.czkawka_cli_path,
                checked,
                self._state.tool_settings.exif_ignored_tags,
                True,
                _on_exif_done,
            )

    def _on_exif_complete(self, cleaned, errors):
        self._status_label.setText(tr("status-exif-cleaned", count=cleaned))
        if errors:
            self._bottom_panel.set_text("\n".join(errors))
            self._bottom_panel.show_text()

    def _optimize_video(self):
        checked = self._results_view.get_checked_entries()
        if not checked:
            return

        QMessageBox.information(
            self, tr("video-optimize-title"),
            tr("video-optimize-message", count=len(checked))
        )
        # Video optimization is done via CLI
        self._status_label.setText(tr("status-video-optimize"))

    def _refresh_after_action(self, removed_entries: list):
        """Remove processed entries from results and refresh the view."""
        removed_paths = {e.values.get("__full_path") for e in removed_entries}
        current_results = self._state.get_results()
        new_results = []
        for r in current_results:
            if r.header_row:
                new_results.append(r)
            elif r.values.get("__full_path") not in removed_paths:
                new_results.append(r)

        # Remove empty group headers
        cleaned = []
        i = 0
        while i < len(new_results):
            if new_results[i].header_row:
                # Check if next entries belong to this group
                has_children = False
                for j in range(i + 1, len(new_results)):
                    if new_results[j].header_row:
                        break
                    has_children = True
                if has_children:
                    cleaned.append(new_results[i])
            else:
                cleaned.append(new_results[i])
            i += 1

        self._state.set_results(self._state.active_tab, cleaned)
        self._results_view.set_results(cleaned)
        self._action_buttons.set_has_results(
            any(not r.header_row for r in cleaned)
        )

    def _save_profile(self):
        name, ok = QInputDialog.getText(
            self, tr("save-profile-title"), tr("save-profile-prompt")
        )
        if ok and name.strip():
            self._state.save_profile(name.strip())
            self._refresh_profile_menu()
            self._status_label.setText(tr("status-profile-saved", name=name.strip()))

    def _load_profile(self, name: str):
        if self._state.load_profile(name):
            self._on_tab_changed(self._state.active_tab)
            self._bottom_panel.refresh_lists()
            self._status_label.setText(tr("status-profile-loaded", name=name))

    def _refresh_profile_menu(self):
        self._action_buttons.update_profiles(self._state.list_profiles())

    def _on_settings_changed(self):
        self._state.save_settings()
        self._bottom_panel.refresh_lists()

    def _apply_theme(self):
        """Apply minimal styling that works with the system theme.

        KDE HIG compliance: inherit the desktop theme (Breeze, Adwaita, etc.)
        and only add layout polish using Kirigami-equivalent spacing.
        No color overrides — the system palette drives all colors.
        """
        from .utils import SMALL_SPACING, MEDIUM_SPACING, LARGE_SPACING, CORNER_RADIUS
        app = QApplication.instance()

        app.setStyleSheet(f"""
            QSplitter::handle {{ width: 2px; }}
            QTreeWidget::item {{ padding: {SMALL_SPACING}px; }}
            QListWidget::item {{ padding: {SMALL_SPACING}px; }}
            QGroupBox {{ border-radius: {CORNER_RADIUS}px; margin-top: {LARGE_SPACING}px; padding-top: {LARGE_SPACING}px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: {LARGE_SPACING}px; padding: 0 {SMALL_SPACING}px; }}
            QPushButton {{ padding: {SMALL_SPACING + 1}px {LARGE_SPACING + SMALL_SPACING}px; }}
            QComboBox {{ padding: {SMALL_SPACING}px; }}
            QLineEdit {{ padding: {SMALL_SPACING}px; }}
            QSpinBox {{ padding: {SMALL_SPACING}px; }}
            QProgressBar {{ text-align: center; }}
            QScrollArea {{ border: none; }}
            QCheckBox {{ spacing: {MEDIUM_SPACING}px; }}
            QHeaderView::section {{ padding: {SMALL_SPACING}px; }}
        """)

    def _auto_detect_cli(self):
        """Auto-detect czkawka_cli binary location."""
        s = self._state.settings

        # If already valid and exists, keep it
        if s.czkawka_cli_path != "czkawka_cli" and Path(s.czkawka_cli_path).is_file():
            return
        if shutil.which(s.czkawka_cli_path):
            return

        # Search common locations
        candidates = []
        project_root = Path(__file__).parent.parent.parent

        # Look for compiled binary in standard target dirs
        for build_dir in ["target/release", "target/debug"]:
            candidate = project_root / build_dir / "czkawka_cli"
            if candidate.exists():
                candidates.append(str(candidate))

        # Check cargo metadata for custom target directory
        if not candidates:
            try:
                import subprocess, json
                result = subprocess.run(
                    ["cargo", "metadata", "--manifest-path",
                     str(project_root / "Cargo.toml"),
                     "--format-version", "1", "--no-deps"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    meta = json.loads(result.stdout)
                    target_dir = meta.get("target_directory", "")
                    if target_dir:
                        for sub in ["release", "debug"]:
                            candidate = Path(target_dir) / sub / "czkawka_cli"
                            if candidate.exists():
                                candidates.append(str(candidate))
            except Exception:
                pass

        # Also check PATH
        which_result = shutil.which("czkawka_cli")
        if which_result:
            candidates.append(which_result)

        for candidate in candidates:
            if Path(candidate).is_file():
                s.czkawka_cli_path = str(candidate)
                self._state.save_settings()
                return

    def closeEvent(self, event):
        """Save settings on close."""
        if self._state.settings.save_window_geometry:
            pos = self.pos()
            size = self.size()
            self._state.settings.window_x = pos.x()
            self._state.settings.window_y = pos.y()
            self._state.settings.window_width = size.width()
            self._state.settings.window_height = size.height()
        self._state.save_settings()
        if self._state.scanning:
            self._scan_runner.stop_scan()
        super().closeEvent(event)

    def _apply_icons_mode(self):
        """Toggle icon-only mode on action buttons."""
        icons_only = self._state.settings.show_only_icons
        self._action_buttons.set_icons_only(icons_only)

    def _send_notification(self, count: int):
        """Send a desktop notification on scan completion."""
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            if QSystemTrayIcon.isSystemTrayAvailable():
                tray = QSystemTrayIcon(self.windowIcon(), self)
                tray.show()
                tray.showMessage(
                    "Kalka - Scan Complete",
                    f"Found {count} entries",
                    QSystemTrayIcon.Information,
                    3000,
                )
                # Clean up tray icon after message
                from PySide6.QtCore import QTimer
                QTimer.singleShot(4000, tray.hide)
        except Exception:
            pass

    def _play_completion_sound(self):
        """Play a short beep/sound on scan completion."""
        try:
            QApplication.beep()
        except Exception:
            pass
