from PySide6.QtCore import QEvent, QSize, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from emitter.mitm_flow_emitter import flow_emitter
from models.mitmproxy_models import FlowTableModel
from ui.theme_manager import ThemeManager, color_to_hex
from ui.widgets.menu_select_button import MenuSelectButton


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


class BreakpointActionDelegate(QStyledItemDelegate):
    action_clicked = Signal(object)

    def paint(self, painter, option, index):
        """
        在断点列绘制“继续请求/继续响应”按钮样式。
        :param painter: Qt painter
        :param option: 绘制选项
        :param index: 当前单元格索引
        :return:
        """
        action_state = index.data(FlowTableModel.BREAKPOINT_ACTION_ROLE)
        if index.column() != 8 or not action_state:
            super().paint(painter, option, index)
            return

        button_option = QStyleOptionButton()
        button_option.rect = option.rect.adjusted(6, 4, -6, -4)
        button_option.state = QStyle.State_Enabled
        if option.state & QStyle.State_MouseOver:
            button_option.state |= QStyle.State_MouseOver
        style = option.widget.style() if option.widget else None
        if not style:
            return

        if action_state in {"play_request", "play_response"}:
            button_option.icon = style.standardIcon(QStyle.SP_MediaPlay)
            button_option.iconSize = QSize(
                max(int(button_option.rect.width() * 0.5), 12),
                max(int(button_option.rect.height() * 0.5), 12),
            )
            style.drawControl(QStyle.CE_PushButton, button_option, painter)
            return

        if action_state == "pause_wait_response":
            button_option.icon = style.standardIcon(QStyle.SP_MediaPause)
            button_option.state &= ~QStyle.State_Enabled
            button_option.iconSize = QSize(
                max(int(button_option.rect.width() * 0.5), 12),
                max(int(button_option.rect.height() * 0.5), 12),
            )
            style.drawControl(QStyle.CE_PushButton, button_option, painter)
            return

        super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        """
        处理断点按钮点击事件。
        :param event: 鼠标事件
        :param model: 表格模型
        :param option: 绘制选项
        :param index: 当前单元格索引
        :return: 是否已处理
        """
        if index.column() != 8:
            return super().editorEvent(event, model, option, index)
        action_state = index.data(FlowTableModel.BREAKPOINT_ACTION_ROLE)
        if action_state not in {"play_request", "play_response"}:
            return super().editorEvent(event, model, option, index)
        event_pos = None
        if hasattr(event, "position"):
            event_pos = event.position().toPoint()
        elif hasattr(event, "pos"):
            event_pos = event.pos()
        if (
            event.type() == QEvent.MouseButtonRelease
            and event_pos is not None
            and option.rect.contains(event_pos)
        ):
            self.action_clicked.emit(index)
            return True
        return super().editorEvent(event, model, option, index)


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
    breakpoint_rule_changed = Signal(bool, str)
    breakpoint_continue_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.model = FlowTableModel()
        self.proxy_model = FlowFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self._selected_flow_id = ""
        self._breakpoint_sync_guard = False

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "筛选 URL / 路径 / 方法 / 状态 / Content-Type"
        )
        self.search_input.setClearButtonEnabled(True)

        self.method_filter = MenuSelectButton(
            "方法",
            [("全部方法", "ALL")]
            + [
                (method, method)
                for method in (
                    "GET",
                    "POST",
                    "PUT",
                    "DELETE",
                    "PATCH",
                    "OPTIONS",
                    "HEAD",
                )
            ],
            self,
        )
        self.method_filter.setMinimumWidth(110)

        self.status_filter = MenuSelectButton(
            "状态",
            [
                ("全部状态", "ALL"),
                ("2xx", "2XX"),
                ("3xx", "3XX"),
                ("4xx", "4XX"),
                ("5xx", "5XX"),
                ("未响应", "NO_STATUS"),
            ],
            self,
        )
        self.status_filter.setMinimumWidth(110)

        self.failed_only_checkbox = QCheckBox("只看失败请求")
        self.breakpoint_enabled_checkbox = QCheckBox("启用断点")
        self.breakpoint_input = QLineEdit()
        self.breakpoint_input.setPlaceholderText(
            "输入断点接口关键字（包含匹配），如 /pos/token"
        )
        self.breakpoint_input.setEnabled(False)
        self.clear_filter_btn = QPushButton("清除筛选")
        # self.count_label = QLabel("记录 0 条")

        self.table = HoverTableView()
        self.table.setModel(self.proxy_model)
        self.table.setItemDelegate(FlowRowDelegate(self.table))
        self.breakpoint_action_delegate = BreakpointActionDelegate(self.table)
        self.table.setItemDelegateForColumn(8, self.breakpoint_action_delegate)
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
        self.table.horizontalHeader().setSectionResizeMode(
            8, QHeaderView.ResizeToContents
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(7, 160)
        self.table.setColumnWidth(8, 120)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addWidget(self.search_input, 1)
        toolbar_layout.addWidget(self.method_filter)
        toolbar_layout.addWidget(self.status_filter)
        toolbar_layout.addWidget(self.failed_only_checkbox)
        toolbar_layout.addWidget(self.clear_filter_btn)
        toolbar_layout.addWidget(self.breakpoint_enabled_checkbox)
        toolbar_layout.addWidget(self.breakpoint_input, 1)

        # toolbar_layout.addWidget(self.count_label)
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
        self.method_filter.value_changed.connect(self._apply_filters)
        self.status_filter.value_changed.connect(self._apply_filters)
        self.failed_only_checkbox.toggled.connect(self._apply_filters)
        self.breakpoint_enabled_checkbox.toggled.connect(
            self._on_breakpoint_enabled_toggled
        )
        self.breakpoint_input.returnPressed.connect(self._emit_breakpoint_rule_changed)
        self.clear_filter_btn.clicked.connect(self._clear_filters)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.breakpoint_action_delegate.action_clicked.connect(
            self._on_breakpoint_action_clicked
        )
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
        self.method_filter.set_current_data("ALL", emit_signal=False)
        self.status_filter.set_current_data("ALL", emit_signal=False)
        self.failed_only_checkbox.setChecked(False)
        self._apply_filters()

    def _on_breakpoint_enabled_toggled(self, enabled: bool):
        """
        断点开关变化时同步控件状态。
        :param enabled: 是否启用断点
        :return:
        """
        self.breakpoint_input.setEnabled(enabled)
        if self._breakpoint_sync_guard:
            return
        if not enabled:
            self._emit_breakpoint_rule_changed()

    def _emit_breakpoint_rule_changed(self):
        """
        派发断点规则变更事件。
        :return:
        """
        if self._breakpoint_sync_guard:
            return
        enabled = self.breakpoint_enabled_checkbox.isChecked()
        pattern = self.breakpoint_input.text().strip() if enabled else ""
        self.breakpoint_rule_changed.emit(enabled, pattern)

    def _on_breakpoint_action_clicked(self, proxy_index):
        """
        处理断点列按钮点击，通知上层执行放行。
        :param proxy_index: 代理模型索引
        :return:
        """
        if not proxy_index or not proxy_index.isValid():
            return
        source_index = self.proxy_model.mapToSource(proxy_index)
        if not source_index.isValid():
            return
        item = self.model.get_item(source_index.row())
        if not item or not item.breakpoint_paused:
            return
        self.table.selectRow(proxy_index.row())
        self.breakpoint_continue_requested.emit(item)

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
        # if visible_count == total_count:
        #     self.count_label.setText(f"记录 {total_count} 条")
        # else:
        #     self.count_label.setText(f"显示 {visible_count} / 总计 {total_count}")
        self.stats_changed.emit(visible_count, total_count)

    def clear(self):
        self._selected_flow_id = ""
        self.search_input.clear()
        self.method_filter.set_current_data("ALL", emit_signal=False)
        self.status_filter.set_current_data("ALL", emit_signal=False)
        self.failed_only_checkbox.setChecked(False)
        self.table.clearSelection()
        self.model.clear()
        self.flow_selected.emit(None)

    def set_breakpoint_rule(self, enabled: bool, pattern: str):
        """
        外部设置断点规则，避免触发重复保存。
        :param enabled: 是否启用
        :param pattern: 匹配关键字
        :return:
        """
        self._breakpoint_sync_guard = True
        self.breakpoint_enabled_checkbox.setChecked(bool(enabled))
        self.breakpoint_input.setText(str(pattern or ""))
        self.breakpoint_input.setEnabled(bool(enabled))
        self._breakpoint_sync_guard = False

    def set_record_limit(self, limit: int):
        """
        设置抓包记录最大保留条数。
        :param limit: 最大条数
        :return:
        """
        self.model.set_max_records(limit)
        self._refresh_stats()

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
