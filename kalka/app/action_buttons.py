from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QSizePolicy, QMenu, QToolButton
)
from PySide6.QtCore import Signal, QSize

from .models import ActiveTab, GROUPED_TABS
from .icons import (
    icon_search, icon_stop, icon_select, icon_delete, icon_move,
    icon_save, icon_sort, icon_hardlink, icon_symlink, icon_rename,
    icon_clean, icon_optimize, icon_dir,
)
from .localizer import tr


def _make_btn(icon_fn, label_key: str, signal, layout) -> QPushButton:
    """Create and register an icon button with standard sizing."""
    btn = QPushButton(icon_fn(18), " " + tr(label_key))
    btn.setIconSize(ICON_SIZE)
    btn.clicked.connect(signal.emit)
    layout.addWidget(btn)
    return btn

ICON_SIZE = QSize(18, 18)


class ActionButtons(QWidget):
    """Action buttons bar: Scan, Stop, Select, Delete, Move, Save, Sort, etc."""

    scan_clicked = Signal()
    stop_clicked = Signal()
    select_clicked = Signal()
    delete_clicked = Signal()
    move_clicked = Signal()
    save_clicked = Signal()
    load_clicked = Signal()
    sort_clicked = Signal()
    hardlink_clicked = Signal()
    symlink_clicked = Signal()
    rename_clicked = Signal()
    clean_exif_clicked = Signal()
    optimize_video_clicked = Signal()
    # Hamburger menu signals
    settings_clicked = Signal()
    about_clicked = Signal()
    save_profile_clicked = Signal()
    load_profile_clicked = Signal(str)  # profile name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_tab = ActiveTab.DUPLICATE_FILES
        self._scanning = False
        self._has_results = False
        self._has_selection = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._scan_btn = _make_btn(icon_search, "scan-button", self.scan_clicked, layout)
        self._scan_btn.setMinimumWidth(90)

        self._stop_btn = _make_btn(icon_stop, "stop-button", self.stop_clicked, layout)
        self._stop_btn.setMinimumWidth(80)
        self._stop_btn.setVisible(False)

        spacer = QWidget()
        spacer.setFixedWidth(10)
        layout.addWidget(spacer)

        self._select_btn = _make_btn(icon_select, "select-button", self.select_clicked, layout)
        self._delete_btn = _make_btn(icon_delete, "delete-button", self.delete_clicked, layout)
        self._move_btn = _make_btn(icon_move, "move-button", self.move_clicked, layout)
        self._save_btn = _make_btn(icon_save, "save-button", self.save_clicked, layout)

        self._load_btn = _make_btn(icon_dir, "load-button", self.load_clicked, layout)
        self._load_btn.setToolTip(tr("load-button-tooltip"))

        self._sort_btn = _make_btn(icon_sort, "sort-button", self.sort_clicked, layout)
        self._hardlink_btn = _make_btn(icon_hardlink, "hardlink-button", self.hardlink_clicked, layout)
        self._symlink_btn = _make_btn(icon_symlink, "symlink-button", self.symlink_clicked, layout)
        self._rename_btn = _make_btn(icon_rename, "rename-button", self.rename_clicked, layout)
        self._clean_exif_btn = _make_btn(icon_clean, "clean-exif-button", self.clean_exif_clicked, layout)
        self._optimize_btn = _make_btn(icon_optimize, "optimize-button", self.optimize_video_clicked, layout)

        # Stretch at the end
        layout.addStretch()

        # Hamburger menu button
        self._hamburger_btn = QToolButton()
        self._hamburger_btn.setText("\u2630")  # trigram for heaven (hamburger icon)
        self._hamburger_btn.setFixedSize(32, 32)
        self._hamburger_btn.setPopupMode(QToolButton.InstantPopup)
        self._hamburger_btn.setStyleSheet(
            "QToolButton { font-size: 18px; border: none; }"
            "QToolButton::menu-indicator { image: none; }"
        )
        self._hamburger_menu = QMenu(self)
        self._hamburger_btn.setMenu(self._hamburger_menu)
        self._build_hamburger_menu()
        layout.addWidget(self._hamburger_btn)

        self._update_visibility()

    def set_active_tab(self, tab: ActiveTab):
        self._active_tab = tab
        self._update_visibility()

    def set_scanning(self, scanning: bool):
        self._scanning = scanning
        self._scan_btn.setVisible(not scanning)
        self._stop_btn.setVisible(scanning)
        self._update_enabled()

    def set_has_results(self, has_results: bool):
        self._has_results = has_results
        self._update_enabled()

    def set_has_selection(self, has_selection: bool):
        self._has_selection = has_selection
        self._update_enabled()

    def _update_visibility(self):
        tab = self._active_tab
        is_grouped = tab in GROUPED_TABS

        # Always visible
        self._select_btn.setVisible(True)
        self._delete_btn.setVisible(True)
        self._move_btn.setVisible(True)
        self._save_btn.setVisible(True)
        self._sort_btn.setVisible(True)

        # Conditional buttons
        self._hardlink_btn.setVisible(is_grouped)
        self._symlink_btn.setVisible(is_grouped)
        self._rename_btn.setVisible(tab in (ActiveTab.BAD_EXTENSIONS, ActiveTab.BAD_NAMES))
        self._clean_exif_btn.setVisible(tab == ActiveTab.EXIF_REMOVER)
        self._optimize_btn.setVisible(tab == ActiveTab.VIDEO_OPTIMIZER)

        self._update_enabled()

    def _update_enabled(self):
        has_data = self._has_results and not self._scanning
        has_sel = self._has_selection and not self._scanning

        self._scan_btn.setEnabled(not self._scanning)
        self._select_btn.setEnabled(has_data)
        self._delete_btn.setEnabled(has_sel)
        self._move_btn.setEnabled(has_sel)
        self._save_btn.setEnabled(has_data)
        self._sort_btn.setEnabled(has_data)
        self._hardlink_btn.setEnabled(has_sel)
        self._symlink_btn.setEnabled(has_sel)
        self._rename_btn.setEnabled(has_sel)
        self._clean_exif_btn.setEnabled(has_sel)
        self._optimize_btn.setEnabled(has_sel)

    def _build_hamburger_menu(self):
        m = self._hamburger_menu
        m.clear()

        # Profiles submenu
        self._profiles_menu = m.addMenu(tr("menu-profiles"))
        self._profiles_menu.addAction(tr("menu-save-profile"), self.save_profile_clicked.emit)
        self._profiles_menu.addSeparator()
        # Populated dynamically via update_profiles()

        m.addSeparator()
        m.addAction(tr("menu-settings"), self.settings_clicked.emit)
        m.addAction(tr("menu-about"), self.about_clicked.emit)

    def update_profiles(self, profile_names: list[str]):
        """Refresh the load-profile submenu with current profile names."""
        # Remove old dynamic actions (after the separator)
        actions = self._profiles_menu.actions()
        # Keep first action (Save) and separator
        for action in actions[2:]:
            self._profiles_menu.removeAction(action)
        if profile_names:
            for name in profile_names:
                self._profiles_menu.addAction(
                    name, lambda n=name: self.load_profile_clicked.emit(n)
                )
