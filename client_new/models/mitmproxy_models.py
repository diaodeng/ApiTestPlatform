from loguru import logger
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor

from models.mitmproxy_common import FlowItem


class FlowTableModel(QAbstractTableModel):
    changed = Signal()
    HEADERS = ["时间", "方法", "域名", "路径", "状态", "耗时", "大小", "Content-Type"]

    def __init__(self):
        super().__init__()
        self._data = []
        self._map = {}

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self.HEADERS)

    def data(self, index, role):
        if not index.isValid():
            return None

        item = self._data[index.row()]

        if role == Qt.DisplayRole:
            col = index.column()
            if col == 0:
                return item.time.strftime("%H:%M:%S")
            elif col == 1:
                return item.method
            elif col == 2:
                return item.request_host or "-"
            elif col == 3:
                return item.path
            elif col == 4:
                return item.status_code or "-"
            elif col == 5:
                return self._format_duration(item.duration_ms)
            elif col == 6:
                return item.size
            elif col == 7:
                return self._simplify_content_type(
                    item.response_content_type or item.request_content_type
                )

        if role == Qt.ToolTipRole:
            col = index.column()
            if col == 2:
                return item.request_host or "-"
            if col == 3:
                return item.path or "-"
            if col == 7:
                return item.response_content_type or item.request_content_type or "-"

        if role == Qt.ForegroundRole and item.status_code is not None:
            if item.status_code >= 500:
                return QColor("#c53030")
            if item.status_code >= 400:
                return QColor("#dd6b20")
            if item.status_code >= 300:
                return QColor("#2b6cb0")
            if item.status_code >= 200:
                return QColor("#2f855a")

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]

    # ===== 新增 =====
    def add_flow(self, item):
        logger.debug(f"抓取到数据了{item}")
        self.beginInsertRows(QModelIndex(), len(self._data), len(self._data))
        self._data.append(item)
        self._map[item.id] = len(self._data) - 1
        self.endInsertRows()
        self.changed.emit()

    def update_flow(self, item):
        if item.id not in self._map:
            return

        row = self._map[item.id]
        self._data[row] = item
        self._map[item.id] = row

        self.dataChanged.emit(
            self.index(row, 0), self.index(row, self.columnCount() - 1)
        )
        self.changed.emit()

    def clear(self):
        if not self._data:
            return

        self.beginResetModel()
        self._data = []
        self._map = {}
        self.endResetModel()
        self.changed.emit()

    def get_item(self, row: int):
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def find_row_by_id(self, flow_id: str) -> int:
        return self._map.get(flow_id, -1)

    def total_count(self) -> int:
        return len(self._data)

    def _format_duration(self, duration_ms: int | None) -> str:
        if duration_ms is None:
            return "-"
        if duration_ms < 1000:
            return f"{duration_ms} ms"
        seconds = duration_ms / 1000
        return f"{seconds:.2f} s"

    def _simplify_content_type(self, content_type: str) -> str:
        raw = (content_type or "").strip()
        if not raw:
            return "-"
        return raw.split(";", 1)[0].strip()
