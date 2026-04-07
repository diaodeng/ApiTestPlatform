from PySide6.QtCore import QEvent, QPoint, QRect, QSize, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from models.pos_models import PosRowItem, PosTableModel
from ui.theme_manager import ThemeManager, color_to_hex


class PosFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self.setDynamicSortFilter(True)

    def set_search_text(self, text: str):
        normalized = (text or "").strip().lower()
        if normalized == self._search_text:
            return
        self._search_text = normalized
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._search_text:
            return True

        model = self.sourceModel()
        item = model.get_item(source_row) if model else None
        if not item:
            return False
        return self._search_text in item.path.lower()


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
                self._update_cursor(index)
        elif event_type in (QEvent.Leave, QEvent.HoverLeave):
            self._set_hover_row(-1)
            self.viewport().unsetCursor()
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

    def _update_cursor(self, index):
        if index.isValid() and index.column() != PosTableModel.COL_INFO:
            self.viewport().setCursor(Qt.PointingHandCursor)
            return
        self.viewport().unsetCursor()


class PosRowDelegate(QStyledItemDelegate):
    _ACTION_META = {
        PosTableModel.COL_OPEN_DIR: (
            "open_dir",
            QStyle.StandardPixmap.SP_DirOpenIcon,
        ),
        PosTableModel.COL_SWITCH: (
            "switch_online",
            QStyle.StandardPixmap.SP_BrowserReload,
        ),
        PosTableModel.COL_ENV: (
            "load_env",
            QStyle.StandardPixmap.SP_FileDialogInfoView,
        ),
        PosTableModel.COL_START: (
            "start",
            QStyle.StandardPixmap.SP_MediaPlay,
        ),
        PosTableModel.COL_MORE: ("more", None),
    }

    def __init__(self, table_view: HoverTableView):
        super().__init__(table_view)
        self._table_view = table_view
        self._icon_cache: dict[int, object] = {}

    def paint(self, painter, option, index):
        item = index.data(PosTableModel.ITEM_ROLE)
        if not isinstance(item, PosRowItem):
            super().paint(painter, option, index)
            return

        tokens = ThemeManager.instance().tokens()
        hovered = index.row() == self._table_view.hover_row
        background = QColor(tokens.surface_hover if hovered else tokens.base)
        border = QColor(tokens.border)

        painter.save()
        painter.fillRect(option.rect, background)

        if index.row() == 0:
            painter.fillRect(option.rect.adjusted(0, 0, 0, -1), background)

        painter.setPen(QPen(border))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        if index.column() == PosTableModel.COL_INFO:
            self._paint_info_cell(painter, option.rect, item, tokens)
        else:
            self._paint_action_cell(painter, option.rect, index.column(), hovered, tokens)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 60)

    def _paint_info_cell(self, painter, rect: QRect, item: PosRowItem, tokens):
        content_rect = rect.adjusted(12, 8, -10, -8)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        path_font = painter.font()
        path_font.setBold(True)
        path_font.setPointSize(max(path_font.pointSize(), 10))
        info_font = painter.font()
        info_font.setBold(False)
        info_font.setPointSize(max(info_font.pointSize() - 1, 10))

        path_metrics = painter.fontMetrics()
        path_height = path_metrics.height()
        info_rect = QRect(
            content_rect.left(),
            content_rect.top() + path_height + 3,
            content_rect.width(),
            max(content_rect.height() - path_height - 3, 14),
        )

        painter.setFont(path_font)
        path_metrics = painter.fontMetrics()
        path_text = path_metrics.elidedText(item.path, Qt.ElideMiddle, content_rect.width())
        painter.setPen(QColor(tokens.text))
        painter.drawText(
            QRect(content_rect.left(), content_rect.top(), content_rect.width(), path_height + 2),
            Qt.AlignLeft | Qt.AlignVCenter,
            path_text,
        )

        painter.setFont(info_font)
        info_metrics = painter.fontMetrics()
        env_text = info_metrics.elidedText(
            item.env_info or "环境: 未获取",
            Qt.ElideRight,
            info_rect.width(),
        )
        info_color = QColor(tokens.accent if item.env_loading else tokens.subtle_text)
        painter.setPen(info_color)
        painter.drawText(info_rect, Qt.AlignLeft | Qt.AlignVCenter, env_text)

    def _paint_action_cell(self, painter, rect: QRect, column: int, hovered: bool, tokens):
        action, icon_type = self._ACTION_META.get(column, ("", None))
        if not action:
            return

        button_rect = self._button_rect(rect)
        painter.setRenderHint(QPainter.Antialiasing, True)

        fill = QColor(tokens.header if hovered else tokens.surface)
        border = QColor(tokens.border)
        painter.setPen(QPen(border))
        painter.setBrush(fill)
        painter.drawRoundedRect(button_rect, 6, 6)

        if column == PosTableModel.COL_MORE:
            painter.setPen(QColor(tokens.text))
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(button_rect, Qt.AlignCenter, "⋮")
            return

        icon = self._icon_cache.get(column)
        if icon is None:
            icon = self._table_view.style().standardIcon(icon_type)
            self._icon_cache[column] = icon

        icon_rect = QRect(
            button_rect.center().x() - 9,
            button_rect.center().y() - 9,
            18,
            18,
        )
        icon.paint(painter, icon_rect)

    @staticmethod
    def _button_rect(rect: QRect) -> QRect:
        size = 30
        return QRect(
            rect.center().x() - size // 2,
            rect.center().y() - size // 2,
            size,
            size,
        )

class PosTableWidget(QWidget):
    open_dir_requested = Signal(str)
    switch_online_requested = Signal(str)
    load_env_requested = Signal(str)
    start_requested = Signal(str)
    more_requested = Signal(str, QPoint)
    copy_path_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.model = PosTableModel(self)
        self.proxy_model = PosFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table = HoverTableView()
        self.delegate = PosRowDelegate(self.table)
        self.table.setModel(self.proxy_model)
        self.table.setItemDelegate(self.delegate)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setAlternatingRowColors(False)
        self.table.viewport().setAttribute(Qt.WA_Hover, True)
        self.table.setMouseTracking(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalScrollBar().setSingleStep(14)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(60)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.horizontalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(
            PosTableModel.COL_INFO, QHeaderView.Stretch
        )
        for column in (
            PosTableModel.COL_OPEN_DIR,
            PosTableModel.COL_SWITCH,
            PosTableModel.COL_ENV,
            PosTableModel.COL_START,
            PosTableModel.COL_MORE,
        ):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.Fixed)
            self.table.setColumnWidth(column, 44)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.table)

        self.table.clicked.connect(self._handle_clicked)
        self.table.doubleClicked.connect(self._handle_double_clicked)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme()

    def set_filter_text(self, text: str):
        self.proxy_model.set_search_text(text)

    def set_paths(self, paths: list[str]):
        self.model.set_paths(paths)

    def add_path(self, path: str):
        self.model.add_path(path)

    def clear(self):
        self.table.hover_row = -1
        self.model.clear()

    def set_env_loading(self, path: str):
        self.model.set_env_loading(path)

    def update_env_info(self, path: str, env_info: str):
        self.model.update_env_info(path, env_info)

    def _dispatch_action(self, action: str, path: str, global_pos: QPoint):
        if action == "open_dir":
            self.open_dir_requested.emit(path)
            return
        if action == "switch_online":
            self.switch_online_requested.emit(path)
            return
        if action == "load_env":
            self.load_env_requested.emit(path)
            return
        if action == "start":
            self.start_requested.emit(path)
            return
        if action == "more":
            self.more_requested.emit(path, global_pos)

    def _handle_clicked(self, index):
        if not index.isValid():
            return

        path = index.data(PosTableModel.PATH_ROLE) or ""
        if not path:
            return

        action, _icon = self.delegate._ACTION_META.get(index.column(), ("", None))
        if not action:
            return

        global_pos = QPoint()
        if action == "more":
            rect = self.table.visualRect(index)
            global_pos = self.table.viewport().mapToGlobal(rect.bottomLeft())
        self._dispatch_action(action, path, global_pos)

    def _handle_double_clicked(self, index):
        if not index.isValid() or index.column() != PosTableModel.COL_INFO:
            return

        path = index.data(PosTableModel.PATH_ROLE) or ""
        if path:
            self.copy_path_requested.emit(path)

    def _show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        path = index.data(PosTableModel.PATH_ROLE) or ""
        if not path:
            return

        menu = QMenu(self)
        copy_action = menu.addAction("复制路径")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == copy_action:
            self.copy_path_requested.emit(path)

    def _apply_theme(self, *_args):
        tokens = ThemeManager.instance().tokens()
        self.table.setStyleSheet(
            f"""
            QTableView {{
                background-color: {color_to_hex(tokens.base)};
                border: 1px solid {color_to_hex(tokens.border)};
                border-radius: 10px;
                outline: none;
            }}
            QTableCornerButton::section {{
                background-color: {color_to_hex(tokens.base)};
                border: none;
            }}
            """
        )
        self.table.viewport().update()
