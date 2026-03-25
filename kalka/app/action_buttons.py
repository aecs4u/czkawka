from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QSizePolicy, QMenu, QToolButton
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

from .models import ActiveTab, GROUPED_TABS
from .icons import (
    icon_search, icon_stop, icon_select, icon_delete, icon_move,
    icon_save, icon_sort, icon_hardlink, icon_symlink, icon_rename,
    icon_clean, icon_optimize, icon_dir,
)
from .localizer import tr
from .utils import ICON_SMALL_MEDIUM, MEDIUM_SPACING, LARGE_SPACING

# FreeDesktop theme icon names with fallback to bundled SVGs
_THEME_ICONS = {
    "scan": ("system-search", icon_search),
    "stop": ("process-stop", icon_stop),
    "select": ("edit-select-all", icon_select),
    "delete": ("edit-delete", icon_delete),
    "move": ("document-save-as", icon_move),
    "save": ("document-save", icon_save),
    "load": ("document-open", icon_dir),
    "sort": ("view-sort-ascending", icon_sort),
    "hardlink": ("edit-link", icon_hardlink),
    "symlink": ("edit-link", icon_symlink),
    "rename": ("edit-rename", icon_rename),
    "clean": ("edit-clear", icon_clean),
    "optimize": ("media-playback-start", icon_optimize),
}


def _themed_icon(key: str) -> QIcon:
    """Try FreeDesktop theme icon first, fall back to bundled SVG."""
    theme_name, fallback_fn = _THEME_ICONS[key]
    icon = QIcon.fromTheme(theme_name)
    return icon if not icon.isNull() else fallback_fn(22)


def _make_btn(key: str, label_key: str, signal, layout) -> QPushButton:
    """Create and register an icon button with KDE HIG sizing."""
    btn = QPushButton(_themed_icon(key), " " + tr(label_key))
    btn.setIconSize(ICON_SMALL_MEDIUM)
    btn.clicked.connect(signal.emit)
    layout.addWidget(btn)
    return btn


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
        layout.setContentsMargins(LARGE_SPACING, MEDIUM_SPACING, LARGE_SPACING, MEDIUM_SPACING)
        layout.setSpacing(MEDIUM_SPACING)

        self._scan_btn = _make_btn("scan", "scan-button", self.scan_clicked, layout)
        self._scan_btn.setMinimumWidth(90)

        self._stop_btn = _make_btn("stop", "stop-button", self.stop_clicked, layout)
        self._stop_btn.setMinimumWidth(80)
        self._stop_btn.setVisible(False)

        spacer = QWidget()
        spacer.setFixedWidth(LARGE_SPACING)
        layout.addWidget(spacer)

        self._select_btn = _make_btn("select", "select-button", self.select_clicked, layout)
        self._delete_btn = _make_btn("delete", "delete-button", self.delete_clicked, layout)
        self._move_btn = _make_btn("move", "move-button", self.move_clicked, layout)
        self._save_btn = _make_btn("save", "save-button", self.save_clicked, layout)

        self._load_btn = _make_btn("load", "load-button", self.load_clicked, layout)
        self._load_btn.setToolTip(tr("load-button-tooltip"))

        self._sort_btn = _make_btn("sort", "sort-button", self.sort_clicked, layout)
        self._hardlink_btn = _make_btn("hardlink", "hardlink-button", self.hardlink_clicked, layout)
        self._symlink_btn = _make_btn("symlink", "symlink-button", self.symlink_clicked, layout)
        self._rename_btn = _make_btn("rename", "rename-button", self.rename_clicked, layout)
        self._clean_exif_btn = _make_btn("clean", "clean-exif-button", self.clean_exif_clicked, layout)
        self._optimize_btn = _make_btn("optimize", "optimize-button", self.optimize_video_clicked, layout)

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
