from PySide6.QtCore import QEvent, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from emitter.mitm_flow_emitter import flow_emitter
from models.mitmproxy_models import FlowTableModel
from ui.theme_manager import ThemeManager, color_to_hex


class HoverTableView(QTableView):
    def __init__(self):
        super().__init__()
        self.hover_row = -1
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def viewportEvent(self, event):
        event_type = event.type()
        if event_type in (QEvent.MouseMove, QEvent.HoverMove):
            position = self._event_pos(event)
            if position is not None:
                index = self.indexAt(position)
                self._set_hover_row(index.row() if index.isValid() else -1)
        elif event_type in (QEvent.Leave, QEvent.HoverLeave):
            self._set_hover_row(-1)
        return super().viewportEvent(event)

    def _event_pos(self, event):
        if hasattr(event, "position"):
            return event.position().toPoint()
        if hasattr(event, "pos"):
            return event.pos()
        return None

    def _set_hover_row(self, row: int):
        if row == self.hover_row:
            return

        previous = self.hover_row
        self.hover_row = row

        if previous >= 0:
            self._update_row(previous)
        if row >= 0:
            self._update_row(row)

    def _update_row(self, row: int):
        model = self.model()
        if not model or row < 0 or model.columnCount() <= 0:
            self.viewport().update()
            return

        left = model.index(row, 0)
        right = model.index(row, model.columnCount() - 1)
        self.viewport().update(self.visualRect(left).united(self.visualRect(right)))


class FlowRowDelegate(QStyledItemDelegate):
    def __init__(self, table_view):
        super().__init__(table_view)
        self._table_view = table_view

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        is_selected = bool(opt.state & QStyle.State_Selected)
        is_hovered = index.row() == self._table_view.hover_row
        tokens = ThemeManager.instance().tokens()

        if is_hovered and not is_selected:
            hovered_color = QColor(tokens.surface_hover)
            opt.backgroundBrush = hovered_color
            opt.palette.setColor(QPalette.Base, hovered_color)
            opt.palette.setColor(QPalette.AlternateBase, hovered_color)

        if is_selected:
            selected_color = QColor(tokens.selection)
            opt.backgroundBrush = selected_color
            opt.palette.setColor(QPalette.Highlight, selected_color)
            opt.palette.setColor(
                QPalette.HighlightedText, QColor(tokens.selection_text)
            )

        super().paint(painter, opt, index)


class FlowFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self._method_filter = "ALL"
        self._status_filter = "ALL"
        self._failed_only = False
        self.setDynamicSortFilter(True)

    def set_search_text(self, text: str):
        normalized = text.strip().lower()
        if normalized == self._search_text:
            return
        self._search_text = normalized
        self.invalidateFilter()

    def set_method_filter(self, method: str):
        normalized = (method or "ALL").upper()
        if normalized == self._method_filter:
            return
        self._method_filter = normalized
        self.invalidateFilter()

    def set_status_filter(self, status_filter: str):
        normalized = status_filter or "ALL"
        if normalized == self._status_filter:
            return
        self._status_filter = normalized
        self.invalidateFilter()

    def set_failed_only(self, failed_only: bool):
        if failed_only == self._failed_only:
            return
        self._failed_only = failed_only
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        item = model.get_item(source_row) if model else None
        if not item:
            return False

        if self._method_filter != "ALL" and item.method.upper() != self._method_filter:
            return False

        if not self._match_status(item.status_code):
            return False

        if self._failed_only and not self._is_failed(item.status_code):
            return False

        if not self._search_text:
            return True

        haystack = " ".join(
            [
                item.method,
                item.url,
                item.path,
                str(item.status_code or ""),
                str(item.size),
                item.request_host,
                item.request_scheme,
                item.response_reason,
                item.request_content_type,
                item.response_content_type,
            ]
        ).lower()
        return self._search_text in haystack

    def _match_status(self, status_code: int | None) -> bool:
        if self._status_filter == "ALL":
            return True
        if self._status_filter == "NO_STATUS":
            return status_code is None
        if status_code is None:
            return False
        if self._status_filter == "2XX":
            return 200 <= status_code < 300
        if self._status_filter == "3XX":
            return 300 <= status_code < 400
        if self._status_filter == "4XX":
            return 400 <= status_code < 500
        if self._status_filter == "5XX":
            return 500 <= status_code < 600
        return True

    def _is_failed(self, status_code: int | None) -> bool:
        return status_code is not None and status_code >= 400


class FlowTableWidget(QWidget):
    flow_selected = Signal(object)
    stats_changed = Signal(int, int)

    def __init__(self):
        super().__init__()

        self.model = FlowTableModel()
        self.proxy_model = FlowFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self._selected_flow_id = ""

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "筛选 URL / 路径 / 方法 / 状态 / Content-Type"
        )
        self.search_input.setClearButtonEnabled(True)

        self.method_filter = QComboBox()
        self.method_filter.addItem("全部方法", "ALL")
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
            self.method_filter.addItem(method, method)

        self.status_filter = QComboBox()
        self.status_filter.addItem("全部状态", "ALL")
        self.status_filter.addItem("2xx", "2XX")
        self.status_filter.addItem("3xx", "3XX")
        self.status_filter.addItem("4xx", "4XX")
        self.status_filter.addItem("5xx", "5XX")
        self.status_filter.addItem("未响应", "NO_STATUS")

        self.failed_only_checkbox = QCheckBox("只看失败请求")
        self.clear_filter_btn = QPushButton("清除筛选")
        self.count_label = QLabel("记录 0 条")

        self.table = HoverTableView()
        self.table.setModel(self.proxy_model)
        self.table.setItemDelegate(FlowRowDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(False)
        self.table.setMouseTracking(True)
        self.table.viewport().setAttribute(Qt.WA_Hover, True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Interactive)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(7, 160)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addWidget(self.search_input, 1)
        toolbar_layout.addWidget(self.method_filter)
        toolbar_layout.addWidget(self.status_filter)
        toolbar_layout.addWidget(self.failed_only_checkbox)
        toolbar_layout.addWidget(self.clear_filter_btn)
        toolbar_layout.addWidget(self.count_label)
        toolbar_layout.addStretch()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self._bind()
        self._apply_theme()
        self._refresh_stats()

    def _bind(self):
        flow_emitter.new_flow.connect(self.model.add_flow)
        flow_emitter.update_flow.connect(self.model.update_flow)
        self.model.changed.connect(self._on_model_changed)
        self.search_input.textChanged.connect(self._apply_filters)
        self.method_filter.currentTextChanged.connect(self._apply_filters)
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        self.failed_only_checkbox.toggled.connect(self._apply_filters)
        self.clear_filter_btn.clicked.connect(self._clear_filters)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        ThemeManager.instance().theme_changed.connect(self._apply_theme)

    def _on_model_changed(self):
        self._refresh_stats()
        QTimer.singleShot(0, self._restore_selection)

    def _apply_filters(self, *_args):
        self.proxy_model.set_search_text(self.search_input.text())
        self.proxy_model.set_method_filter(self.method_filter.currentData())
        self.proxy_model.set_status_filter(self.status_filter.currentData())
        self.proxy_model.set_failed_only(self.failed_only_checkbox.isChecked())
        self._refresh_stats()
        QTimer.singleShot(0, self._restore_selection)

    def _clear_filters(self):
        self.search_input.clear()
        self.method_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.failed_only_checkbox.setChecked(False)
        self._apply_filters()

    def _on_selection_changed(self, *_args):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.flow_selected.emit(None)
            return

        proxy_index = selected_rows[0]
        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.model.get_item(source_index.row())
        if not item:
            self.flow_selected.emit(None)
            return

        self._selected_flow_id = item.id
        self.flow_selected.emit(item)

    def _restore_selection(self):
        if not self._selected_flow_id:
            return

        source_row = self.model.find_row_by_id(self._selected_flow_id)
        if source_row < 0:
            self._selected_flow_id = ""
            self.table.clearSelection()
            self.flow_selected.emit(None)
            return

        item = self.model.get_item(source_row)
        source_index = self.model.index(source_row, 0)
        proxy_index = self.proxy_model.mapFromSource(source_index)
        if not proxy_index.isValid():
            self.table.clearSelection()
            self.flow_selected.emit(None)
            return

        current_index = self.table.currentIndex()
        if current_index == proxy_index:
            self.flow_selected.emit(item)
            return

        self.table.selectRow(proxy_index.row())
        self.table.scrollTo(proxy_index, QAbstractItemView.PositionAtCenter)

    def _refresh_stats(self):
        visible_count = self.proxy_model.rowCount()
        total_count = self.model.total_count()
        if visible_count == total_count:
            self.count_label.setText(f"记录 {total_count} 条")
        else:
            self.count_label.setText(f"显示 {visible_count} / 总计 {total_count}")
        self.stats_changed.emit(visible_count, total_count)

    def clear(self):
        self._selected_flow_id = ""
        self.search_input.clear()
        self.method_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.failed_only_checkbox.setChecked(False)
        self.table.clearSelection()
        self.model.clear()
        self.flow_selected.emit(None)

    def _apply_theme(self, *_args):
        tokens = ThemeManager.instance().tokens()
        self.table.setStyleSheet(
            f"""
            QTableView {{
                background-color: {color_to_hex(tokens.base)};
                border: 1px solid {color_to_hex(tokens.border)};
                border-radius: 10px;
                selection-background-color: {color_to_hex(tokens.selection)};
                selection-color: {color_to_hex(tokens.selection_text)};
            }}
            """
        )
        self.table.viewport().update()
