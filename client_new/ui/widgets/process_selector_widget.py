import os

import psutil
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class _ProcessComboBox(QComboBox):
    popup_about_to_show = Signal()

    def showPopup(self):
        self.popup_about_to_show.emit()
        super().showPopup()


class ProcessSelectorWidget(QWidget):
    value_committed = Signal(str)

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self._loaded_once = False
        self._process_names: list[str] = []

        self.combo = _ProcessComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.setMinimumWidth(280)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.lineEdit().setClearButtonEnabled(True)
        self.combo.lineEdit().setPlaceholderText(placeholder)

        completer = QCompleter(self.combo.model(), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.combo.setCompleter(completer)

        self.refresh_btn = QPushButton("加载")
        self.refresh_btn.setFixedWidth(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.refresh_btn)

        self.refresh_btn.clicked.connect(self.refresh_processes)
        self.combo.popup_about_to_show.connect(self._refresh_before_popup)
        self.combo.activated.connect(self._emit_value)
        self.combo.lineEdit().editingFinished.connect(self._emit_value)

    def value(self) -> str:
        return self.combo.currentText().strip()

    def set_value(self, value: str):
        text = (value or "").strip()
        self._apply_items(self._process_names, text)

    def set_placeholder(self, placeholder: str):
        self.combo.lineEdit().setPlaceholderText(placeholder)

    def refresh_processes(self):
        current = self.value()
        self._process_names = self._list_process_names()
        self._apply_items(self._process_names, current)
        self._loaded_once = True

    def _refresh_before_popup(self):
        if not self._loaded_once:
            self.refresh_processes()

    def _emit_value(self, *_args):
        self.value_committed.emit(self.value())

    def _apply_items(self, items: list[str], current: str):
        values = list(items)
        current_text = (current or "").strip()
        if current_text and current_text.lower() not in {
            item.lower() for item in values
        }:
            values.insert(0, current_text)

        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(values)
        if current_text:
            index = self.combo.findText(current_text, Qt.MatchFixedString)
            if index >= 0:
                self.combo.setCurrentIndex(index)
            self.combo.setEditText(current_text)
        else:
            self.combo.setCurrentIndex(-1)
            self.combo.lineEdit().clear()
        self.combo.blockSignals(False)

    def _list_process_names(self) -> list[str]:
        names = {}
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                name = (proc.info.get("name") or "").strip()
                exe = (proc.info.get("exe") or "").strip()
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue

            display = name or os.path.basename(exe)
            if not display:
                continue

            key = display.lower()
            if key not in names:
                names[key] = display

        return sorted(names.values(), key=str.lower)
