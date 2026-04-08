from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.dialogs.agent_server_dialog import AgentServerDialog


class AgentServerManageDialog(QDialog):
    sync_requested = Signal()

    def __init__(
        self,
        parent=None,
        server_list: dict[str, str] | None = None,
        current_server: str = "",
        config_sync_url: str = "",
        config_sync_initialized: bool = False,
        config_sync_last_sync_at: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("服务器管理")
        self.resize(760, 420)

        self._server_list: dict[str, str] = dict(server_list or {})
        self._current_server = (current_server or "").strip()
        self._config_sync_url = (config_sync_url or "").strip()
        self._config_sync_initialized = bool(config_sync_initialized)
        self._config_sync_last_sync_at = str(config_sync_last_sync_at or "")

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["服务名称", "服务地址"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        self.add_btn = QPushButton("新增")
        self.edit_btn = QPushButton("修改")
        self.delete_btn = QPushButton("删除")

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.add_btn)
        action_layout.addWidget(self.edit_btn)
        action_layout.addWidget(self.delete_btn)
        action_layout.addStretch()

        sync_layout = QHBoxLayout()
        sync_layout.addWidget(QLabel("配置拉取地址"))
        self.config_sync_url_input = QLineEdit(self._config_sync_url)
        self.config_sync_url_input.setClearButtonEnabled(True)
        self.config_sync_url_input.setPlaceholderText(
            "输入 HTTP 配置拉取地址，例如: http://127.0.0.1:9099/qtr/agent/bootstrap/config/agent_client_config"
        )
        sync_layout.addWidget(self.config_sync_url_input, 1)
        self.sync_config_btn = QPushButton("更新配置")
        sync_layout.addWidget(self.sync_config_btn)

        sync_status_layout = QHBoxLayout()
        sync_status_layout.addWidget(QLabel("同步状态"))
        self.sync_status_label = QLabel("未同步")
        self.sync_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.sync_status_label.setWordWrap(True)
        sync_status_layout.addWidget(self.sync_status_label, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(sync_layout)
        layout.addLayout(sync_status_layout)
        layout.addLayout(action_layout)
        layout.addWidget(self.table, 1)
        layout.addWidget(buttons)

        self.add_btn.clicked.connect(self._add_server)
        self.edit_btn.clicked.connect(self._edit_server)
        self.delete_btn.clicked.connect(self._delete_server)
        self.sync_config_btn.clicked.connect(self.sync_requested.emit)

        self._reload_table()
        self.set_sync_state(
            self._config_sync_initialized,
            self._config_sync_last_sync_at,
            self._config_sync_url,
        )

    def get_data(self) -> tuple[str, dict[str, str], str]:
        self._config_sync_url = self.config_sync_url_input.text().strip()
        return self._current_server, dict(self._server_list), self._config_sync_url

    def get_config_sync_url(self) -> str:
        self._config_sync_url = self.config_sync_url_input.text().strip()
        return self._config_sync_url

    def set_sync_state(
        self,
        initialized: bool,
        last_sync_at: str = "",
        sync_url: str = "",
    ):
        self._config_sync_initialized = bool(initialized)
        self._config_sync_last_sync_at = str(last_sync_at or "")
        self._config_sync_url = (sync_url or self.get_config_sync_url()).strip()
        if self._config_sync_initialized:
            text = "已同步"
            if self._config_sync_last_sync_at:
                text = f"{text} {self._config_sync_last_sync_at}"
        else:
            text = "未同步"
        self.set_sync_status_text(text, self._config_sync_url)

    def set_sync_status_text(self, text: str, tooltip: str = ""):
        self.sync_status_label.setText(text or "-")
        self.sync_status_label.setToolTip((tooltip or "").strip())

    def set_config_syncing(self, syncing: bool):
        self.sync_config_btn.setEnabled(not syncing)
        self.sync_config_btn.setText("更新中..." if syncing else "更新配置")

    def _reload_table(self):
        rows = list(self._server_list.items())
        self.table.setRowCount(len(rows))

        current_row = 0
        for index, (url, name) in enumerate(rows):
            self.table.setItem(index, 0, QTableWidgetItem(name))
            self.table.setItem(index, 1, QTableWidgetItem(url))
            if url == self._current_server:
                current_row = index

        if rows:
            self.table.selectRow(current_row)
        else:
            self._current_server = ""

    def _selected_server(self) -> tuple[str, str] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        name_item = self.table.item(row, 0)
        url_item = self.table.item(row, 1)
        if not name_item or not url_item:
            return None
        return name_item.text().strip(), url_item.text().strip()

    def _add_server(self):
        dialog = AgentServerDialog(self)
        if not dialog.exec():
            return

        name, url = dialog.get_data()
        cleaned_url = (url or "").strip().rstrip("/")
        cleaned_name = (name or "").strip()
        if not cleaned_url:
            QMessageBox.warning(self, "提示", "请先填写服务地址")
            return
        if not cleaned_name:
            QMessageBox.warning(self, "提示", "请先填写服务名称")
            return

        self._server_list[cleaned_url] = cleaned_name
        self._current_server = cleaned_url
        self._reload_table()

    def _edit_server(self):
        selected = self._selected_server()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择一条服务器记录")
            return

        old_name, old_url = selected
        dialog = AgentServerDialog(self, server_name=old_name, server_url=old_url)
        if not dialog.exec():
            return

        new_name, new_url = dialog.get_data()
        cleaned_url = (new_url or "").strip().rstrip("/")
        cleaned_name = (new_name or "").strip()
        if not cleaned_url:
            QMessageBox.warning(self, "提示", "请先填写服务地址")
            return
        if not cleaned_name:
            QMessageBox.warning(self, "提示", "请先填写服务名称")
            return

        if old_url in self._server_list:
            del self._server_list[old_url]
        self._server_list[cleaned_url] = cleaned_name
        if self._current_server == old_url:
            self._current_server = cleaned_url
        self._reload_table()

    def _delete_server(self):
        selected = self._selected_server()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择一条服务器记录")
            return

        _name, url = selected
        if url in self._server_list:
            del self._server_list[url]

        if self._current_server == url:
            self._current_server = next(iter(self._server_list.keys()), "")

        self._reload_table()
