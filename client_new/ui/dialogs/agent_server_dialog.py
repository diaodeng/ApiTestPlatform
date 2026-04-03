from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class AgentServerDialog(QDialog):
    def __init__(self, parent=None, server_name: str = "", server_url: str = ""):
        super().__init__(parent)
        self.setWindowTitle("新增服务端地址")
        self.resize(460, 140)

        self.name_input = QLineEdit(server_name)
        self.url_input = QLineEdit(server_url)
        self.url_input.setPlaceholderText("例如: ws://127.0.0.1:9099/qtr/agent/ws")

        form = QFormLayout()
        form.addRow("服务名称", self.name_input)
        form.addRow("服务地址", self.url_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_data(self) -> tuple[str, str]:
        return self.name_input.text().strip(), self.url_input.text().strip()
