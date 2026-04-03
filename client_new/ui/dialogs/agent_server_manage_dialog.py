from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.dialogs.agent_server_dialog import AgentServerDialog


class AgentServerManageDialog(QDialog):
    def __init__(
        self,
        parent=None,
        server_list: dict[str, str] | None = None,
        current_server: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("服务器管理")
        self.resize(760, 420)

        self._server_list: dict[str, str] = dict(server_list or {})
        self._current_server = (current_server or "").strip()

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

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(action_layout)
        layout.addWidget(self.table, 1)
        layout.addWidget(buttons)

        self.add_btn.clicked.connect(self._add_server)
        self.edit_btn.clicked.connect(self._edit_server)
        self.delete_btn.clicked.connect(self._delete_server)

        self._reload_table()

    def get_data(self) -> tuple[str, dict[str, str]]:
        return self._current_server, dict(self._server_list)

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
