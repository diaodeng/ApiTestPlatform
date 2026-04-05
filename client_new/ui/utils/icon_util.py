from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget


@lru_cache(maxsize=1)
def app_icon_path() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "favicon.ico"


@lru_cache(maxsize=1)
def load_app_icon() -> QIcon:
    icon_path = app_icon_path()
    if not icon_path.exists():
        return QIcon()
    return QIcon(str(icon_path))


def apply_window_icon(widget: QWidget) -> None:
    icon = load_app_icon()
    if icon.isNull():
        return
    widget.setWindowIcon(icon)
