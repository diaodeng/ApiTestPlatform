from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

if sys.platform.startswith("win"):
    import ctypes
    from ctypes import wintypes

    GCLP_HICON = -14
    GCLP_HICONSM = -34
    ICON_BIG = 1
    ICON_SMALL = 0
    IMAGE_ICON = 1
    LR_DEFAULTSIZE = 0x00000040
    LR_LOADFROMFILE = 0x00000010
    SM_CXICON = 11
    SM_CYICON = 12
    SM_CXSMICON = 49
    SM_CYSMICON = 50
    WM_SETICON = 0x0080
    _lresult_type = getattr(wintypes, "LRESULT", ctypes.c_ssize_t)

    _user32 = ctypes.windll.user32
    _load_image_w = _user32.LoadImageW
    _load_image_w.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _load_image_w.restype = wintypes.HANDLE
    _send_message_w = _user32.SendMessageW
    _send_message_w.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _send_message_w.restype = _lresult_type
    _get_system_metrics = _user32.GetSystemMetrics
    _get_system_metrics.argtypes = [ctypes.c_int]
    _get_system_metrics.restype = ctypes.c_int
    _set_class_long_ptr_w = getattr(_user32, "SetClassLongPtrW", None)
    if _set_class_long_ptr_w is None:
        _set_class_long_ptr_w = _user32.SetClassLongW
    _set_class_long_ptr_w.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_ssize_t,
    ]
    _set_class_long_ptr_w.restype = ctypes.c_ssize_t

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
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        bundled_icon = Path(bundle_root) / "assets" / "favicon.ico"
        if bundled_icon.exists():
            return bundled_icon
    return Path(__file__).resolve().parents[2] / "assets" / "favicon.ico"


@lru_cache(maxsize=1)
def load_app_icon() -> QIcon:
    icon_path = app_icon_path()
    if not icon_path.exists():
        return QIcon()
    return QIcon(str(icon_path))


@lru_cache(maxsize=1)
def _native_icon_handles(icon_path: str) -> tuple[int, int]:
    if not sys.platform.startswith("win"):
        return 0, 0

    big_icon = _load_image_w(
        None,
        icon_path,
        IMAGE_ICON,
        _get_system_metrics(SM_CXICON) or 32,
        _get_system_metrics(SM_CYICON) or 32,
        LR_LOADFROMFILE,
    )
    small_icon = _load_image_w(
        None,
        icon_path,
        IMAGE_ICON,
        _get_system_metrics(SM_CXSMICON) or 16,
        _get_system_metrics(SM_CYSMICON) or 16,
        LR_LOADFROMFILE,
    )

    if not big_icon:
        big_icon = _load_image_w(
            None,
            icon_path,
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
    if not small_icon:
        small_icon = big_icon

    return int(big_icon or 0), int(small_icon or 0)


def _apply_native_window_icon(widget: QWidget | None, icon_path: Path) -> None:
    if widget is None or not sys.platform.startswith("win") or not icon_path.exists():
        return

    try:
        hwnd = int(widget.winId())
    except Exception:
        return

    if not hwnd:
        return

    big_icon, small_icon = _native_icon_handles(str(icon_path))
    if not big_icon and not small_icon:
        return

    try:
        if big_icon:
            _send_message_w(hwnd, WM_SETICON, ICON_BIG, big_icon)
            _set_class_long_ptr_w(hwnd, GCLP_HICON, big_icon)
        if small_icon:
            _send_message_w(hwnd, WM_SETICON, ICON_SMALL, small_icon)
            _set_class_long_ptr_w(hwnd, GCLP_HICONSM, small_icon)
    except Exception:
        pass


def _should_apply_window_icon(widget: QWidget | None) -> bool:
    if widget is None or not widget.isWindow():
        return False

    if not isinstance(widget, (QMainWindow, QDialog)):
        return False

    return True


def apply_window_icon(widget: QWidget | None) -> None:
    if not _should_apply_window_icon(widget):
        return
    icon = load_app_icon()
    if icon.isNull():
        return
    widget.setWindowIcon(icon)
    _apply_native_window_icon(widget, app_icon_path())
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
        if isinstance(watched, QWidget) and _should_apply_window_icon(watched):
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
        if _should_apply_window_icon(widget):
            apply_window_icon(widget)
