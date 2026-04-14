from loguru import logger
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor

from models.mitmproxy_common import FlowItem


class FlowTableModel(QAbstractTableModel):
    changed = Signal()
    BREAKPOINT_ACTION_ROLE = Qt.UserRole + 101
    FLOW_ITEM_ROLE = Qt.UserRole + 102
    HEADERS = ["时间", "方法", "域名", "路径", "状态", "耗时", "大小", "Content-Type", "断点放行"]

    def __init__(self):
        super().__init__()
        self._data = []
        self._map = {}
        self._max_records = 500

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
            elif col == 8:
                return ""

        if role == Qt.ToolTipRole:
            col = index.column()
            if col == 2:
                return item.request_host or "-"
            if col == 3:
                return item.path or "-"
            if col == 7:
                return item.response_content_type or item.request_content_type or "-"
            if col == 8:
                return item.breakpoint_status_text or "-"

        if role == self.BREAKPOINT_ACTION_ROLE and index.column() == 8:
            return self._resolve_breakpoint_action(item)

        if role == self.FLOW_ITEM_ROLE:
            return item

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
        self._trim_before_add(1)
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

    def set_max_records(self, max_records: int):
        """
        设置流量列表最大保留条数，超限时自动丢弃最旧记录。
        :param max_records: 最大条数
        :return:
        """
        resolved = 500
        try:
            resolved = int(max_records)
        except Exception:
            resolved = 500
        if resolved <= 0:
            resolved = 500
        self._max_records = resolved
        self._trim_before_add(0)

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

    def _resolve_breakpoint_action(self, item: FlowItem) -> str:
        """
        计算断点列按钮文案。
        :param item: 流量对象
        :return: 按钮文案，不可放行时返回空串
        """
        if not item.breakpoint_matched:
            return ""
        if item.breakpoint_stage == "request" and item.breakpoint_paused:
            return "play_request"
        if item.breakpoint_stage == "request" and not item.breakpoint_paused:
            return "pause_wait_response"
        if item.breakpoint_stage == "response" and item.breakpoint_paused:
            return "play_response"
        return ""

    def _trim_before_add(self, incoming_count: int):
        """
        在新增流量前按上限裁剪旧数据。
        :param incoming_count: 即将新增条数
        :return:
        """
        total_after_add = len(self._data) + max(incoming_count, 0)
        overflow_count = total_after_add - self._max_records
        if overflow_count <= 0:
            return
        remove_count = min(overflow_count, len(self._data))
        if remove_count <= 0:
            return
        self.beginRemoveRows(QModelIndex(), 0, remove_count - 1)
        del self._data[:remove_count]
        self.endRemoveRows()
        self._rebuild_map()

    def _rebuild_map(self):
        """
        根据当前数据重建 id 到行号的索引。
        :return:
        """
        self._map = {item.id: index for index, item in enumerate(self._data)}
