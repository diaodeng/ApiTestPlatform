from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SqliteColumnConfigDialog(QDialog):
    def __init__(
        self,
        columns: list[str],
        visible_columns: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("列显示设置")
        self.resize(420, 520)

        self._columns = list(columns or [])
        current_visible = set(visible_columns or self._columns)
        self._checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tool_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.clear_all_btn = QPushButton("清空")
        tool_layout.addWidget(self.select_all_btn)
        tool_layout.addWidget(self.clear_all_btn)
        tool_layout.addStretch()
        layout.addLayout(tool_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_container = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_container)
        self.scroll_layout.setContentsMargins(6, 6, 6, 6)
        self.scroll_layout.setSpacing(8)

        for column in self._columns:
            checkbox = QCheckBox(column)
            checkbox.setChecked(column in current_visible)
            self.scroll_layout.addWidget(checkbox)
            self._checkboxes[column] = checkbox
        self.scroll_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_container)
        layout.addWidget(self.scroll_area, 1)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self._handle_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.select_all_btn.clicked.connect(self._select_all)
        self.clear_all_btn.clicked.connect(self._clear_all)

    def visible_columns(self) -> list[str]:
        return [
            column
            for column, checkbox in self._checkboxes.items()
            if checkbox.isChecked()
        ]

    def _select_all(self):
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(True)

    def _clear_all(self):
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(False)

    def _handle_accept(self):
        if not self.visible_columns():
            self._select_all()
        self.accept()
