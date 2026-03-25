from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeView, QHeaderView,
    QAbstractItemView, QMenu, QLabel, QHBoxLayout, QStyledItemDelegate
)
from PySide6.QtCore import (
    Signal, Qt, QAbstractItemModel, QModelIndex, QPersistentModelIndex
)
from PySide6.QtGui import QColor, QBrush, QFont, QAction

from .models import (
    ActiveTab, ResultEntry, TAB_COLUMNS, GROUPED_TABS, SelectMode
)
from .utils import format_size as _format_size
from .localizer import tr


# ── Model ────────────────────────────────────────────────────


class ResultsModel(QAbstractItemModel):
    """Flat table model backed by a list of ResultEntry objects.

    Each row maps 1:1 to a ResultEntry (headers included).
    Column 0 is the checkbox column; columns 1..N hold display values.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[ResultEntry] = []
        self._columns: list[str] = []
        self._header_bg = QColor()
        self._header_fg = QColor()

    # ── public API ────────────────────────────────────────────

    def set_columns(self, columns: list[str]):
        self.beginResetModel()
        self._columns = columns
        self.endResetModel()

    def set_results(self, results: list[ResultEntry]):
        self.beginResetModel()
        self._results = results
        self.endResetModel()

    def set_header_colors(self, bg: QColor, fg: QColor):
        self._header_bg = bg
        self._header_fg = fg

    def get_entry(self, row: int) -> ResultEntry | None:
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def get_results(self) -> list[ResultEntry]:
        return self._results

    def set_checked(self, row: int, checked: bool):
        entry = self.get_entry(row)
        if entry and not entry.header_row:
            entry.checked = checked
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [Qt.CheckStateRole])

    def sort_results(self, results: list[ResultEntry]):
        """Replace results with a pre-sorted list (sorting logic lives in ResultsView)."""
        self.beginResetModel()
        self._results = results
        self.endResetModel()

    # ── QAbstractItemModel interface ─────────────────────────

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0  # flat model
        return len(self._results)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._columns)

    def index(self, row, column, parent=QModelIndex()):
        if parent.isValid() or not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, index):
        return QModelIndex()  # flat

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        entry = self.get_entry(index.row())
        if not entry:
            return Qt.NoItemFlags
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if not entry.header_row and index.column() == 0:
            base |= Qt.ItemIsUserCheckable
        return base

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self.get_entry(index.row())
        if not entry:
            return None
        col = index.column()

        if entry.header_row:
            if role == Qt.DisplayRole and col == 0:
                return entry.values.get("__header", "Group")
            if role == Qt.FontRole:
                f = QFont()
                f.setBold(True)
                return f
            if role == Qt.BackgroundRole:
                return QBrush(self._header_bg)
            if role == Qt.ForegroundRole:
                return QBrush(self._header_fg)
            return None

        if role == Qt.CheckStateRole and col == 0:
            return Qt.Checked if entry.checked else Qt.Unchecked

        if role == Qt.DisplayRole and col > 0:
            col_name = self._columns[col] if col < len(self._columns) else ""
            return str(entry.values.get(col_name, ""))

        # Store entry ref for external access
        if role == Qt.UserRole:
            return entry

        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        if role == Qt.CheckStateRole and index.column() == 0:
            entry = self.get_entry(index.row())
            if entry and not entry.header_row:
                entry.checked = (value == Qt.Checked)
                self.dataChanged.emit(index, index, [Qt.CheckStateRole])
                return True
        return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self._columns):
                return self._columns[section]
        return None


# ── Delegate for header-row spanning ─────────────────────────


class SpanDelegate(QStyledItemDelegate):
    """Provides visual spanning for group-header rows.

    QTreeView doesn't natively support setFirstColumnSpanned on a flat model,
    so we handle it via the delegate + model data roles above.
    """
    pass  # The model returns data for col 0 only on header rows; other cols are blank.


# ── View widget ──────────────────────────────────────────────


class ResultsView(QWidget):
    """Results display using QTreeView + QAbstractItemModel."""

    selection_changed = Signal(int)
    item_activated = Signal(object)  # ResultEntry
    current_items_changed = Signal(list)
    context_menu_requested = Signal(object, object)

    _header_colors_ready = False
    HEADER_BG = QColor()
    HEADER_FG = QColor()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_tab = ActiveTab.DUPLICATE_FILES
        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder
        self._model = ResultsModel(self)
        self._setup_ui()

    def _ensure_header_colors(self):
        if self._header_colors_ready:
            return
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette
        palette = QApplication.instance().palette()
        win = palette.color(QPalette.ColorRole.Window)
        hi = palette.color(QPalette.ColorRole.Highlight)
        self.HEADER_BG = QColor(
            (win.red() + hi.red()) // 2,
            (win.green() + hi.green()) // 2,
            (win.blue() + hi.blue()) // 2,
        )
        self.HEADER_FG = palette.color(QPalette.ColorRole.HighlightedText)
        self._header_colors_ready = True
        self._model.set_header_colors(self.HEADER_BG, self.HEADER_FG)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Summary bar
        summary_layout = QHBoxLayout()
        self._summary_label = QLabel(tr("results-no-results"))
        summary_layout.addWidget(self._summary_label)
        self._selection_label = QLabel("")
        self._selection_label.setAlignment(Qt.AlignRight)
        self._selection_label.setEnabled(False)
        summary_layout.addWidget(self._selection_label)
        layout.addLayout(summary_layout)

        # Tree view backed by model
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.setItemDelegate(SpanDelegate(self._tree))

        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.doubleClicked.connect(self._on_double_clicked)
        self._tree.selectionModel().selectionChanged.connect(self._on_tree_selection_changed) if self._tree.selectionModel() else None

        # Checkbox clicks via model dataChanged
        self._model.dataChanged.connect(self._on_model_data_changed)

        # Sortable headers
        header = self._tree.header()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_clicked)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        layout.addWidget(self._tree)

    # ── Tab / data ───────────────────────────────────────────

    def set_active_tab(self, tab: ActiveTab):
        self._active_tab = tab
        self._sort_column = -1
        columns = TAB_COLUMNS.get(tab, ["Selection", "File Name", "Path"])
        self._model.set_columns(columns)

        # Reconnect selection model (it gets replaced on model reset)
        sm = self._tree.selectionModel()
        if sm:
            sm.selectionChanged.connect(self._on_tree_selection_changed)

        # Column sizing
        header = self._tree.header()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        for i, col in enumerate(columns):
            if col == "Path":
                header.resizeSection(i, 300)
            elif col == "Selection":
                header.resizeSection(i, 30)
            elif col in ("Size", "Hash", "Modification Date"):
                header.resizeSection(i, 140)
            elif col == "File Name":
                header.resizeSection(i, 200)

    def set_results(self, results: list[ResultEntry]):
        self._ensure_header_colors()
        self._model.set_results(results)

        # Span header rows across all columns
        for row, entry in enumerate(results):
            if entry.header_row:
                self._tree.setFirstColumnSpanned(row, QModelIndex(), True)

        self._update_summary()

    # ── Sorting ──────────────────────────────────────────────

    def _on_header_clicked(self, logical_index: int):
        if logical_index == 0:
            return

        if self._sort_column == logical_index:
            self._sort_order = (
                Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder
                else Qt.AscendingOrder
            )
        else:
            self._sort_column = logical_index
            self._sort_order = Qt.AscendingOrder

        columns = TAB_COLUMNS.get(self._active_tab, [])
        col_name = columns[logical_index] if logical_index < len(columns) else ""
        self._tree.header().setSortIndicator(logical_index, self._sort_order)
        self._tree.header().setSortIndicatorShown(True)

        ascending = self._sort_order == Qt.AscendingOrder
        results = self._model.get_results()

        if self._active_tab in GROUPED_TABS:
            sorted_results = self._sort_within_groups(results, col_name, ascending)
        else:
            sorted_results = sorted(
                results,
                key=lambda e: self._sort_key(e, col_name),
                reverse=not ascending,
            )

        self._model.sort_results(sorted_results)
        # Re-apply header spanning
        for row, entry in enumerate(sorted_results):
            if entry.header_row:
                self._tree.setFirstColumnSpanned(row, QModelIndex(), True)

    @staticmethod
    def _sort_key(entry: ResultEntry, col_name: str):
        if col_name in ("Size",):
            return entry.values.get("__size_bytes", 0)
        if col_name in ("Modification Date",):
            return entry.values.get("__modified_date_ts", 0)
        if col_name in ("Similarity", "Bitrate", "Year", "Length"):
            raw = entry.values.get(col_name, "")
            try:
                return float(str(raw).replace(",", ""))
            except (ValueError, TypeError):
                return 0
        return str(entry.values.get(col_name, "")).lower()

    @staticmethod
    def _sort_within_groups(results: list[ResultEntry], col_name: str, ascending: bool) -> list[ResultEntry]:
        sorted_results = []
        current_group = []
        current_header = None

        for entry in results:
            if entry.header_row:
                if current_header is not None:
                    current_group.sort(
                        key=lambda e: ResultsView._sort_key(e, col_name),
                        reverse=not ascending,
                    )
                    sorted_results.append(current_header)
                    sorted_results.extend(current_group)
                current_header = entry
                current_group = []
            else:
                current_group.append(entry)

        if current_header is not None:
            current_group.sort(
                key=lambda e: ResultsView._sort_key(e, col_name),
                reverse=not ascending,
            )
            sorted_results.append(current_header)
            sorted_results.extend(current_group)

        return sorted_results

    def sort_by_column(self, column: int, ascending: bool = True):
        self._sort_column = column
        self._sort_order = Qt.AscendingOrder if ascending else Qt.DescendingOrder
        columns = TAB_COLUMNS.get(self._active_tab, [])
        col_name = columns[column] if column < len(columns) else ""
        self._tree.header().setSortIndicator(column, self._sort_order)
        self._tree.header().setSortIndicatorShown(True)

        results = self._model.get_results()
        if self._active_tab in GROUPED_TABS:
            sorted_results = self._sort_within_groups(results, col_name, ascending)
        else:
            sorted_results = sorted(
                results,
                key=lambda e: self._sort_key(e, col_name),
                reverse=not ascending,
            )
        self._model.sort_results(sorted_results)
        for row, entry in enumerate(sorted_results):
            if entry.header_row:
                self._tree.setFirstColumnSpanned(row, QModelIndex(), True)

    # ── Item events ──────────────────────────────────────────

    def _on_model_data_changed(self, top_left, bottom_right, roles):
        if Qt.CheckStateRole in roles:
            self._update_selection_count()

    def _on_double_clicked(self, index: QModelIndex):
        entry = self._model.get_entry(index.row())
        if entry and not entry.header_row:
            self.item_activated.emit(entry)

    def _on_tree_selection_changed(self):
        paths = []
        for index in self._tree.selectionModel().selectedRows():
            entry = self._model.get_entry(index.row())
            if entry and not entry.header_row:
                path = entry.values.get("__full_path", "")
                if path:
                    paths.append(path)
        self.current_items_changed.emit(paths)

    def _on_context_menu(self, pos):
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return
        entry = self._model.get_entry(index.row())
        if entry and not entry.header_row:
            menu = QMenu(self)
            open_action = QAction(tr("context-open-file"), self)
            open_action.triggered.connect(lambda: self._open_file(entry))
            menu.addAction(open_action)

            open_dir_action = QAction(tr("context-open-folder"), self)
            open_dir_action.triggered.connect(lambda: self._open_folder(entry))
            menu.addAction(open_dir_action)

            menu.addSeparator()

            select_action = QAction(tr("context-select"), self)
            select_action.triggered.connect(lambda: self._model.set_checked(index.row(), True))
            menu.addAction(select_action)

            deselect_action = QAction(tr("context-deselect"), self)
            deselect_action.triggered.connect(lambda: self._model.set_checked(index.row(), False))
            menu.addAction(deselect_action)

            menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _open_file(self, entry: ResultEntry):
        import subprocess, sys
        path = entry.values.get("__full_path", "")
        if not path:
            return
        try:
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["cmd", "/c", "start", "", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def _open_folder(self, entry: ResultEntry):
        import subprocess, sys
        from pathlib import Path
        path = entry.values.get("__full_path", "")
        if not path:
            return
        folder = str(Path(path).parent)
        try:
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["explorer", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    # ── Summary / selection ──────────────────────────────────

    def _update_summary(self):
        results = self._model.get_results()
        entries = [r for r in results if not r.header_row]
        total = len(entries)
        total_size = sum(r.values.get("__size_bytes", 0) for r in entries)
        groups = sum(1 for r in results if r.header_row)
        size_str = _format_size(total_size)
        if self._active_tab in GROUPED_TABS and groups > 0:
            self._summary_label.setText(tr("results-found-grouped", total=total, size=size_str, groups=groups))
        elif total > 0:
            self._summary_label.setText(tr("results-found-flat", total=total, size=size_str))
        else:
            self._summary_label.setText(tr("results-no-results"))
        self._update_selection_count()

    def _update_selection_count(self):
        results = self._model.get_results()
        entries = [r for r in results if not r.header_row]
        total = len(entries)
        total_size = sum(r.values.get("__size_bytes", 0) for r in entries)
        checked = [r for r in entries if r.checked]
        selected = len(checked)
        selected_size = sum(r.values.get("__size_bytes", 0) for r in checked)
        if selected > 0:
            self._selection_label.setText(
                tr("results-selected", selected=selected, total=total,
                   selected_size=_format_size(selected_size), total_size=_format_size(total_size))
            )
        else:
            self._selection_label.setText("")
        self.selection_changed.emit(selected)

    def apply_selection(self, mode: SelectMode):
        results = self._model.get_results()

        if mode == SelectMode.SELECT_ALL:
            self._set_all(results, True)
        elif mode == SelectMode.UNSELECT_ALL:
            self._set_all(results, False)
        elif mode == SelectMode.INVERT_SELECTION:
            for r in results:
                if not r.header_row:
                    r.checked = not r.checked
        elif mode in (SelectMode.SELECT_BIGGEST_SIZE, SelectMode.SELECT_SMALLEST_SIZE,
                      SelectMode.SELECT_NEWEST, SelectMode.SELECT_OLDEST,
                      SelectMode.SELECT_BIGGEST_RESOLUTION, SelectMode.SELECT_SMALLEST_RESOLUTION,
                      SelectMode.SELECT_SHORTEST_PATH, SelectMode.SELECT_LONGEST_PATH):
            self._select_by_group_criteria(results, mode)

        # Notify model of bulk change
        if results:
            self._model.dataChanged.emit(
                self._model.index(0, 0),
                self._model.index(len(results) - 1, 0),
                [Qt.CheckStateRole],
            )
        self._update_selection_count()

    @staticmethod
    def _set_all(results: list[ResultEntry], checked: bool):
        for r in results:
            if not r.header_row:
                r.checked = checked

    def _select_by_group_criteria(self, results: list[ResultEntry], mode: SelectMode):
        self._set_all(results, False)

        if self._active_tab not in GROUPED_TABS:
            return

        groups: dict[int, list[ResultEntry]] = {}
        for r in results:
            if not r.header_row:
                groups.setdefault(r.group_id, []).append(r)

        for group_entries in groups.values():
            if len(group_entries) <= 1:
                continue

            best_idx = 0
            if mode == SelectMode.SELECT_BIGGEST_SIZE:
                best_idx = max(range(len(group_entries)), key=lambda j: group_entries[j].values.get("__size_bytes", 0))
            elif mode == SelectMode.SELECT_SMALLEST_SIZE:
                best_idx = min(range(len(group_entries)), key=lambda j: group_entries[j].values.get("__size_bytes", 0))
            elif mode == SelectMode.SELECT_NEWEST:
                best_idx = max(range(len(group_entries)), key=lambda j: group_entries[j].values.get("__modified_date_ts", 0))
            elif mode == SelectMode.SELECT_OLDEST:
                best_idx = min(range(len(group_entries)), key=lambda j: group_entries[j].values.get("__modified_date_ts", 0))
            elif mode == SelectMode.SELECT_SHORTEST_PATH:
                best_idx = min(range(len(group_entries)), key=lambda j: len(group_entries[j].values.get("__full_path", "")))
            elif mode == SelectMode.SELECT_LONGEST_PATH:
                best_idx = max(range(len(group_entries)), key=lambda j: len(group_entries[j].values.get("__full_path", "")))

            for j, entry in enumerate(group_entries):
                if j != best_idx:
                    entry.checked = True

    # ── Public accessors ─────────────────────────────────────

    def get_checked_entries(self) -> list[ResultEntry]:
        return [r for r in self._model.get_results() if r.checked and not r.header_row]

    def get_all_entries(self) -> list[ResultEntry]:
        return [r for r in self._model.get_results() if not r.header_row]

    def clear(self):
        self._model.set_results([])
        self._sort_column = -1
        self._tree.header().setSortIndicatorShown(False)
        self._summary_label.setText(tr("results-no-results"))
        self._selection_label.setText("")
