from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


@dataclass
class PosRowItem:
    path: str
    env_info: str = "环境: 未获取"
    env_loading: bool = False


class PosTableModel(QAbstractTableModel):
    ITEM_ROLE = Qt.UserRole + 1
    PATH_ROLE = Qt.UserRole + 2
    ENV_ROLE = Qt.UserRole + 3
    LOADING_ROLE = Qt.UserRole + 4

    COL_INFO = 0
    COL_OPEN_DIR = 1
    COL_SWITCH = 2
    COL_ENV = 3
    COL_START = 4
    COL_MORE = 5

    COLUMN_COUNT = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[PosRowItem] = []
        self._row_map: dict[str, int] = {}

    def rowCount(self, parent=None):
        return 0 if parent and parent.isValid() else len(self._rows)

    def columnCount(self, parent=None):
        return 0 if parent and parent.isValid() else self.COLUMN_COUNT

    def data(self, index, role):
        if not index.isValid():
            return None

        item = self._rows[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == self.COL_INFO:
                return item.path
            return ""

        if role == Qt.ToolTipRole:
            if column == self.COL_INFO:
                return f"{item.path}\n{item.env_info}"
            if column == self.COL_OPEN_DIR:
                return "打开所在目录"
            if column == self.COL_SWITCH:
                return "切换POS(在线)"
            if column == self.COL_ENV:
                return "查看环境"
            if column == self.COL_START:
                return "启动POS"
            if column == self.COL_MORE:
                return "更多操作"

        if role == self.ITEM_ROLE:
            return item
        if role == self.PATH_ROLE:
            return item.path
        if role == self.ENV_ROLE:
            return item.env_info
        if role == self.LOADING_ROLE:
            return item.env_loading
        return None

    def clear(self):
        if not self._rows:
            return
        self.beginResetModel()
        self._rows = []
        self._row_map = {}
        self.endResetModel()

    def set_paths(self, paths: list[str]):
        normalized = []
        result_set = set()
        for path in paths or []:
            if not path or path in result_set:
                continue
            result_set.add(path)
            normalized.append(PosRowItem(path=path))

        self.beginResetModel()
        self._rows = normalized
        self._row_map = {item.path: index for index, item in enumerate(self._rows)}
        self.endResetModel()

    def add_path(self, path: str) -> bool:
        if not path or path in self._row_map:
            return False

        row = len(self._rows)
        self.beginInsertRows(QModelIndex(), row, row)
        self._rows.append(PosRowItem(path=path))
        self._row_map[path] = row
        self.endInsertRows()
        return True

    def set_env_loading(self, path: str, text: str = "环境: 获取中..."):
        row = self._row_map.get(path)
        if row is None:
            return
        item = self._rows[row]
        item.env_info = text or "环境: 获取中..."
        item.env_loading = True
        index = self.index(row, self.COL_INFO)
        self.dataChanged.emit(
            index,
            index,
            [Qt.DisplayRole, Qt.ToolTipRole, self.ENV_ROLE, self.LOADING_ROLE],
        )

    def update_env_info(self, path: str, env_info: str):
        row = self._row_map.get(path)
        if row is None:
            return
        item = self._rows[row]
        item.env_info = env_info or "环境: 未获取"
        item.env_loading = False
        index = self.index(row, self.COL_INFO)
        self.dataChanged.emit(
            index,
            index,
            [Qt.DisplayRole, Qt.ToolTipRole, self.ENV_ROLE, self.LOADING_ROLE],
        )

    def get_item(self, row: int) -> PosRowItem | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def total_count(self) -> int:
        return len(self._rows)
