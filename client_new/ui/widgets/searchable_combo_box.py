from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter


class SearchableComboBox(QComboBox):
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        line_edit = self.lineEdit()
        line_edit.setClearButtonEnabled(True)
        line_edit.setPlaceholderText(placeholder)
        line_edit.editingFinished.connect(self._sync_index_from_text)

        completer = QCompleter(self.model(), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

    def set_search_placeholder(self, placeholder: str):
        self.lineEdit().setPlaceholderText(placeholder or "")

    def _sync_index_from_text(self):
        text = self.currentText().strip()
        if not text:
            placeholder_index = self.findData("")
            if placeholder_index >= 0:
                self.setCurrentIndex(placeholder_index)
            elif self.count():
                self.setCurrentIndex(-1)
            return

        normalized = text.casefold()
        for index in range(self.count()):
            item_text = str(self.itemText(index) or "").strip().casefold()
            if item_text == normalized:
                if index != self.currentIndex():
                    self.setCurrentIndex(index)
                return
