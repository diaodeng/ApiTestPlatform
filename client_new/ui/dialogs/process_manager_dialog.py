from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.common import get_all_process, kill_process_by_id


class ProcessManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("结束进程")
        self.resize(1000, 560)
        self.pool = QThreadPool.globalInstance()
        self._all_process = []

        self._init_ui()
        self._load_processes()

    def _init_ui(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("输入进程名过滤")
        self.btn_filter = QPushButton("查询")
        self.btn_refresh = QPushButton("更新")
        top.addWidget(self.filter_input, 1)
        top.addWidget(self.btn_filter)
        top.addWidget(self.btn_refresh)
        root.addLayout(top)

        self.list_widget = QListWidget()
        root.addWidget(self.list_widget, 1)

        bottom = QHBoxLayout()
        self.btn_close = QPushButton("关闭")
        bottom.addStretch()
        bottom.addWidget(self.btn_close)
        root.addLayout(bottom)

        self.btn_filter.clicked.connect(self._apply_filter)
        self.btn_refresh.clicked.connect(self._load_processes)
        self.btn_close.clicked.connect(self.accept)

    def _load_processes(self):
        self._all_process = get_all_process()
        self._render(self._all_process)

    def _apply_filter(self):
        key = (self.filter_input.text() or "").strip().lower()
        if not key:
            self._render(self._all_process)
            return
        data = [p for p in self._all_process if key in str(p.get("name", "")).lower()]
        self._render(data)

    def _render(self, data: list[dict]):
        self.list_widget.clear()
        for item in data:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 4, 6, 4)

            title = QLineEdit(
                f"{item.get('name', '-')} | PID:{item.get('pid', '-')} | {item.get('exe', '-')}"
            )
            title.setReadOnly(True)
            title.setStyleSheet("border:none;background:transparent;")

            btn_kill = QPushButton("停止")
            pid = item.get("pid")
            btn_kill.clicked.connect(lambda _, p=pid: self._kill_process(p))

            row_layout.addWidget(title, 1)
            if item.get("is_current_child"):
                child_tag = QLineEdit("子进程")
                child_tag.setReadOnly(True)
                child_tag.setFixedWidth(60)
                child_tag.setStyleSheet(
                    "border:1px solid #9ae6b4;border-radius:4px;background:#f0fff4;color:#2f855a;"
                )
                row_layout.addWidget(child_tag)
            row_layout.addWidget(btn_kill)

            list_item = QListWidgetItem(self.list_widget)
            list_item.setSizeHint(row_widget.sizeHint())
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, row_widget)

    def _kill_process(self, pid):
        if not pid:
            QMessageBox.warning(self, "提示", "无效PID")
            return
        try:
            kill_process_by_id(pid)
            QMessageBox.information(self, "成功", f"进程已停止: {pid}")
            self._load_processes()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止进程失败: {e}")
