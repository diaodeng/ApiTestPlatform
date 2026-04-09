from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMenu, QToolButton


class MenuSelectButton(QToolButton):
    value_changed = Signal(str)

    def __init__(
        self,
        title: str,
        options: list[tuple[str, str]],
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._options = [(text, str(data)) for text, data in options]
        self._option_map = {data: text for text, data in self._options}
        self._current_text = ""
        self._current_data = ""
        self._actions: dict[str, object] = {}
        self._menu: QMenu | None = None
        self._action_group: QActionGroup | None = None

        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.setPopupMode(QToolButton.InstantPopup)

        if options:
            self.set_current_data(str(options[0][1]), emit_signal=False)
        else:
            self._update_button_text()

    def currentData(self) -> str:
        return self._current_data

    def currentText(self) -> str:
        return self._current_text

    def set_current_data(self, data: str, *, emit_signal: bool = True):
        normalized_data = str(data or "")
        text = self._option_map.get(normalized_data)
        if text is None:
            return

        changed = normalized_data != self._current_data or text != self._current_text
        self._current_data = normalized_data
        self._current_text = text
        action = self._actions.get(normalized_data)
        if action is not None:
            action.setChecked(True)
        self._update_button_text()

        if changed and emit_signal:
            self.value_changed.emit(self._current_data)

    def mousePressEvent(self, event):
        self._ensure_menu()
        super().mousePressEvent(event)

    def showMenu(self):
        self._ensure_menu()
        super().showMenu()

    def _ensure_menu(self):
        if self._menu is not None:
            return

        menu = QMenu(self)
        action_group = QActionGroup(self)
        action_group.setExclusive(True)

        for text, data in self._options:
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setData(data)
            action_group.addAction(action)
            action.triggered.connect(
                lambda checked=False, value=data: self.set_current_data(value)
            )
            self._actions[data] = action

        self._menu = menu
        self._action_group = action_group
        self.setMenu(menu)

        if self._current_data:
            action = self._actions.get(self._current_data)
            if action is not None:
                action.setChecked(True)

    def _update_button_text(self):
        suffix = self._current_text or "-"
        self.setText(f"{self._title}: {suffix}")
