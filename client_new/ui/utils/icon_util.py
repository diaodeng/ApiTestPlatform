from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
WINDOW_ICON_EVENT_TYPES = tuple(
    event_type
    for event_type in (
        getattr(QEvent.Type, "Show", None),
        getattr(QEvent.Type, "Polish", None),
        getattr(QEvent.Type, "WinIdChange", None),
        getattr(QEvent.Type, "WindowStateChange", None),
    )
    if event_type is not None
)
_INSTALLED_APP_IDS: set[int] = set()


@lru_cache(maxsize=1)
def app_icon_path() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "favicon.ico"


@lru_cache(maxsize=1)
def load_app_icon() -> QIcon:
    icon_path = app_icon_path()
    if not icon_path.exists():
        return QIcon()
    pixmap = QPixmap(str(icon_path))
    if pixmap.isNull():
        return QIcon(str(icon_path))
    icon = QIcon()
    for size in ICON_SIZES:
        scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if not scaled.isNull():
            icon.addPixmap(scaled)
    return icon if not icon.isNull() else QIcon(str(icon_path))


def apply_window_icon(widget: QWidget | None) -> None:
    if widget is None:
        return
    icon = load_app_icon()
    if icon.isNull():
        return
    widget.setWindowIcon(icon)
    window_handle = widget.windowHandle()
    if window_handle is not None:
        try:
            window_handle.setIcon(icon)
        except Exception:
            pass


class _WindowIconEventFilter(QObject):
    def eventFilter(self, watched, event) -> bool:
        if event is None or event.type() not in WINDOW_ICON_EVENT_TYPES:
            return False
        if isinstance(watched, QWidget) and watched.isWindow():
            apply_window_icon(watched)
        return False


@lru_cache(maxsize=1)
def _window_icon_event_filter() -> _WindowIconEventFilter:
    return _WindowIconEventFilter()


def install_app_icon(app: QApplication | None) -> None:
    if app is None:
        return
    icon = load_app_icon()
    if icon.isNull():
        return
    app.setWindowIcon(icon)
    app_id = id(app)
    if app_id not in _INSTALLED_APP_IDS:
        event_filter = _window_icon_event_filter()
        if event_filter.parent() is None:
            event_filter.setParent(app)
        app.installEventFilter(event_filter)
        _INSTALLED_APP_IDS.add(app_id)
    for widget in QApplication.topLevelWidgets():
        if widget.isWindow():
            apply_window_icon(widget)
