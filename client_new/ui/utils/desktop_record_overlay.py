from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


OUTLINE_COLOR = QColor("#ff3b30")
FOCUS_COLOR = QColor("#22c55e")
MASK_COLOR = QColor("#f59e0b")
ASSERT_COLOR = QColor("#2563eb")


@dataclass
class _OverlayCommand:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    future: concurrent.futures.Future | None = None


def _virtual_geometry() -> QRect:
    screens = QGuiApplication.screens()
    if not screens:
        return QRect(0, 0, 1920, 1080)
    geometry = QRect(screens[0].geometry())
    for screen in screens[1:]:
        geometry = geometry.united(screen.geometry())
    return geometry


def _intersection_area(rect1: QRect, rect2: QRect) -> int:
    intersected = rect1.intersected(rect2)
    if not intersected.isValid():
        return 0
    return max(intersected.width(), 0) * max(intersected.height(), 0)


def _available_geometry_for_rect(target_rect: QRect) -> QRect:
    screens = QGuiApplication.screens()
    if not screens:
        return QRect(0, 0, 1920, 1080)
    if target_rect.isValid():
        target_center = target_rect.center()
        screen = QGuiApplication.screenAt(target_center)
        if screen is not None:
            return QRect(screen.availableGeometry())
        best_screen = max(
            screens,
            key=lambda screen_obj: _intersection_area(screen_obj.availableGeometry(), target_rect),
            default=screens[0],
        )
        return QRect(best_screen.availableGeometry())
    return QRect(screens[0].availableGeometry())


def _payload_to_rect(payload: dict[str, Any] | None) -> QRect:
    payload = payload or {}
    return QRect(
        int(payload.get("left") or 0),
        int(payload.get("top") or 0),
        max(int(payload.get("width") or 0), 0),
        max(int(payload.get("height") or 0), 0),
    )


def _rect_to_payload(rect: QRect) -> dict[str, int]:
    return {
        "left": int(rect.x()),
        "top": int(rect.y()),
        "width": int(rect.width()),
        "height": int(rect.height()),
    }


def _is_full_viewport(viewport_rect: QRect, desktop_rect: QRect) -> bool:
    if not viewport_rect.isValid():
        return True
    normalized_viewport = QRect(viewport_rect)
    normalized_desktop = QRect(desktop_rect)
    return (
        normalized_viewport.x() <= normalized_desktop.x()
        and normalized_viewport.y() <= normalized_desktop.y()
        and normalized_viewport.width() >= normalized_desktop.width()
        and normalized_viewport.height() >= normalized_desktop.height()
    )


class _ViewportOutlineWidget(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self._desktop_rect = QRect()
        self._viewport_rect = QRect()

    def set_viewport(self, desktop_rect: QRect, viewport_rect: QRect) -> None:
        self._desktop_rect = QRect(desktop_rect)
        self._viewport_rect = QRect(viewport_rect)
        if not self._desktop_rect.isValid() or not self._viewport_rect.isValid():
            self.hide()
            return
        self.setGeometry(self._desktop_rect)
        self.show()
        self.raise_()
        self.update()

    def clear_viewport(self) -> None:
        self._viewport_rect = QRect()
        self.hide()

    def paintEvent(self, _event) -> None:  # pragma: no cover - GUI paint
        if not self._viewport_rect.isValid():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(OUTLINE_COLOR, 3)
        pen.setCosmetic(True)
        painter.setPen(pen)
        local_rect = self._viewport_rect.translated(-self._desktop_rect.x(), -self._desktop_rect.y())
        painter.drawRect(local_rect.adjusted(1, 1, -2, -2))


class _SelectionOverlayWidget(QWidget):
    selection_finished = Signal(object)
    selection_cancelled = Signal()

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._desktop_rect = QRect()
        self._viewport_rect = QRect()
        self._purpose = "focus"
        self._purpose_text = ""
        self._purpose_color = FOCUS_COLOR
        self._start_pos: QPoint | None = None
        self._current_pos: QPoint | None = None

    def current_purpose(self) -> str:
        return str(self._purpose or "focus")

    def begin(self, desktop_rect: QRect, viewport_rect: QRect, purpose: str) -> None:
        self._desktop_rect = QRect(desktop_rect)
        self._viewport_rect = QRect(viewport_rect)
        self._purpose = purpose
        self._purpose_text = {
            "focus": "拖拽选择验证区域",
            "mask": "拖拽选择忽略区域",
            "assert": "拖拽选择新增断言区域",
        }.get(purpose, "拖拽选择区域")
        self._purpose_color = {
            "focus": FOCUS_COLOR,
            "mask": MASK_COLOR,
            "assert": ASSERT_COLOR,
        }.get(purpose, FOCUS_COLOR)
        self._start_pos = None
        self._current_pos = None
        self.setGeometry(self._desktop_rect)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.ActiveWindowFocusReason)
        self.update()

    def _clamp_to_viewport(self, point: QPoint) -> QPoint:
        x = min(max(point.x(), self._viewport_rect.x()), self._viewport_rect.x() + self._viewport_rect.width() - 1)
        y = min(max(point.y(), self._viewport_rect.y()), self._viewport_rect.y() + self._viewport_rect.height() - 1)
        return QPoint(x, y)

    def _current_selection_rect(self) -> QRect:
        if self._start_pos is None or self._current_pos is None:
            return QRect()
        return QRect(self._start_pos, self._current_pos).normalized()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - GUI interaction
        if event.button() != Qt.LeftButton:
            return
        local_pos = event.position().toPoint()
        global_pos = local_pos + self._desktop_rect.topLeft()
        if not self._viewport_rect.contains(global_pos):
            return
        self._start_pos = self._clamp_to_viewport(global_pos)
        self._current_pos = QPoint(self._start_pos)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - GUI interaction
        if self._start_pos is None:
            return
        local_pos = event.position().toPoint()
        global_pos = self._clamp_to_viewport(local_pos + self._desktop_rect.topLeft())
        self._current_pos = global_pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - GUI interaction
        if event.button() != Qt.LeftButton or self._start_pos is None:
            return
        local_pos = event.position().toPoint()
        self._current_pos = self._clamp_to_viewport(local_pos + self._desktop_rect.topLeft())
        rect = self._current_selection_rect()
        self._start_pos = None
        self._current_pos = None
        self.hide()
        self.update()
        if rect.width() < 4 or rect.height() < 4:
            self.selection_cancelled.emit()
            return
        self.selection_finished.emit({"purpose": self._purpose, "rect": _rect_to_payload(rect)})

    def keyPressEvent(self, event) -> None:  # pragma: no cover - GUI interaction
        if event.key() == Qt.Key_Escape:
            self._start_pos = None
            self._current_pos = None
            self.hide()
            self.selection_cancelled.emit()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:  # pragma: no cover - GUI paint
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(15, 23, 42, 35))

        viewport_rect = self._viewport_rect.translated(-self._desktop_rect.x(), -self._desktop_rect.y())
        outline_pen = QPen(OUTLINE_COLOR, 3)
        outline_pen.setCosmetic(True)
        painter.setPen(outline_pen)
        painter.drawRect(viewport_rect.adjusted(1, 1, -2, -2))

        if self._start_pos is not None and self._current_pos is not None:
            selection_rect = self._current_selection_rect().translated(-self._desktop_rect.x(), -self._desktop_rect.y())
            select_pen = QPen(self._purpose_color, 2, Qt.DashLine)
            select_pen.setCosmetic(True)
            painter.setPen(select_pen)
            painter.drawRect(selection_rect)

        text_rect = QRect(24, 20, min(max(self.width() - 48, 320), 720), 56)
        painter.fillRect(text_rect, QColor(15, 23, 42, 180))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(text_rect.adjusted(14, 8, -14, -8), Qt.AlignLeft | Qt.AlignVCenter, self._purpose_text + "，按 Esc 取消")


class _AnnotationToolbarWidget(QFrame):
    focus_requested = Signal()
    mask_requested = Signal()
    assert_requested = Signal()
    clear_requested = Signal()
    accept_requested = Signal()
    cancel_requested = Signal()

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("desktopRecordAnnotationToolbar")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("桌面录制标注")
        self._status_label = QLabel()
        self._prompt_label = QLabel()
        self._prompt_label.setWordWrap(True)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QFrame#desktopRecordAnnotationToolbar {
                background: rgba(15, 23, 42, 235);
                border: 1px solid rgba(148, 163, 184, 200);
                border-radius: 12px;
            }
            QLabel {
                color: #f8fafc;
                font-size: 13px;
            }
            QPushButton {
                background: #1d4ed8;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton[role="subtle"] {
                background: #334155;
            }
            QPushButton[role="subtle"]:hover {
                background: #475569;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        title_label = QLabel("录制中标注")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #ffffff;")
        root_layout.addWidget(title_label)
        root_layout.addWidget(self._prompt_label)
        root_layout.addWidget(self._status_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        focus_button = QPushButton("验证区域")
        focus_button.clicked.connect(self.focus_requested.emit)

        mask_button = QPushButton("忽略区域")
        mask_button.setProperty("role", "subtle")
        mask_button.clicked.connect(self.mask_requested.emit)

        assert_button = QPushButton("增加断言")
        assert_button.setProperty("role", "subtle")
        assert_button.clicked.connect(self.assert_requested.emit)

        clear_button = QPushButton("清空标注")
        clear_button.setProperty("role", "subtle")
        clear_button.clicked.connect(self.clear_requested.emit)

        continue_button = QPushButton("继续录制")
        continue_button.clicked.connect(self.accept_requested.emit)

        cancel_button = QPushButton("跳过标注")
        cancel_button.setProperty("role", "subtle")
        cancel_button.clicked.connect(self.cancel_requested.emit)

        for button in (focus_button, mask_button, assert_button, clear_button, continue_button, cancel_button):
            button_row.addWidget(button)

        root_layout.addLayout(button_row)

    def update_state(self, *, prompt: str, focus_region: dict[str, Any] | None, mask_regions: list[dict[str, Any]], assert_regions: list[dict[str, Any]]) -> None:
        self._prompt_label.setText(prompt or "已暂停录制，选择要标注的区域后继续。")
        status_parts = []
        status_parts.append("验证区域: 已设置" if focus_region else "验证区域: 未设置")
        status_parts.append(f"忽略区域: {len(mask_regions)}")
        status_parts.append(f"新增断言: {len(assert_regions)}")
        self._status_label.setText(" | ".join(status_parts))
        self.adjustSize()


class _DesktopRecordOverlayController(QObject):
    command_received = Signal(object)

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._app = app
        self._outline_widget: _ViewportOutlineWidget | None = None
        self._selector_widget: _SelectionOverlayWidget | None = None
        self._toolbar_widget: _AnnotationToolbarWidget | None = None
        self._desktop_rect = QRect()
        self._viewport_rect = QRect()
        self._pending_annotation_future: concurrent.futures.Future | None = None
        self._annotation_state: dict[str, Any] = {
            "focusRegion": None,
            "maskRegions": [],
            "assertRegions": [],
        }
        self._suspended_state: dict[str, bool] = {}

        self.command_received.connect(self._handle_command, Qt.QueuedConnection)

    def _ensure_outline_widget(self) -> _ViewportOutlineWidget:
        if self._outline_widget is None:
            self._outline_widget = _ViewportOutlineWidget()
        return self._outline_widget

    def _ensure_selector_widget(self) -> _SelectionOverlayWidget:
        if self._selector_widget is None:
            self._selector_widget = _SelectionOverlayWidget()
            self._selector_widget.selection_finished.connect(
                self._handle_selection_finished
            )
            self._selector_widget.selection_cancelled.connect(
                self._handle_selection_cancelled
            )
        return self._selector_widget

    def _ensure_toolbar_widget(self) -> _AnnotationToolbarWidget:
        if self._toolbar_widget is None:
            self._toolbar_widget = _AnnotationToolbarWidget()
            self._toolbar_widget.focus_requested.connect(
                lambda: self._start_selection("focus")
            )
            self._toolbar_widget.mask_requested.connect(
                lambda: self._start_selection("mask")
            )
            self._toolbar_widget.assert_requested.connect(
                lambda: self._start_selection("assert")
            )
            self._toolbar_widget.clear_requested.connect(self._clear_annotation_state)
            self._toolbar_widget.accept_requested.connect(self._finish_annotation)
            self._toolbar_widget.cancel_requested.connect(self._cancel_annotation)
        return self._toolbar_widget

    def _resolve_desktop_context(self, viewport_payload: dict[str, Any] | None) -> tuple[QRect, QRect]:
        desktop_rect = _virtual_geometry()
        viewport_rect = _payload_to_rect(viewport_payload)
        if not viewport_rect.isValid():
            viewport_rect = QRect(desktop_rect)
        self._desktop_rect = desktop_rect
        self._viewport_rect = viewport_rect
        return desktop_rect, viewport_rect

    def _place_toolbar(self) -> None:
        toolbar_widget = self._toolbar_widget
        if toolbar_widget is None:
            return
        desktop_rect = self._desktop_rect if self._desktop_rect.isValid() else _virtual_geometry()
        viewport_rect = self._viewport_rect if self._viewport_rect.isValid() else QRect(desktop_rect)
        available_rect = _available_geometry_for_rect(viewport_rect)
        toolbar_widget.adjustSize()
        toolbar_size = toolbar_widget.size()
        margin = 18

        safe_rect = available_rect.adjusted(margin, margin, -margin, -margin)
        if safe_rect.width() < toolbar_size.width():
            safe_rect = QRect(available_rect)
        if safe_rect.height() < toolbar_size.height():
            safe_rect = QRect(available_rect)

        min_x = safe_rect.left()
        min_y = safe_rect.top()
        max_x = max(min_x, safe_rect.right() - toolbar_size.width() + 1)
        max_y = max(min_y, safe_rect.bottom() - toolbar_size.height() + 1)

        candidates = [
            QPoint(viewport_rect.right() + margin, max(viewport_rect.top(), min_y)),
            QPoint(max(viewport_rect.left(), min_x), viewport_rect.bottom() + margin),
            QPoint(max(viewport_rect.left(), min_x), viewport_rect.top() - toolbar_size.height() - margin),
            QPoint(max_x, min_y),
        ]

        chosen = QPoint(max_x, min_y)
        for candidate in candidates:
            clamped_x = min(max(candidate.x(), min_x), max_x)
            clamped_y = min(max(candidate.y(), min_y), max_y)
            candidate_rect = QRect(clamped_x, clamped_y, toolbar_size.width(), toolbar_size.height())
            if safe_rect.contains(candidate_rect):
                chosen = QPoint(clamped_x, clamped_y)
                break
            chosen = QPoint(clamped_x, clamped_y)

        toolbar_widget.move(chosen)

    def _update_toolbar(self, prompt: str = "") -> None:
        toolbar_widget = self._ensure_toolbar_widget()
        toolbar_widget.update_state(
            prompt=prompt,
            focus_region=self._annotation_state.get("focusRegion"),
            mask_regions=list(self._annotation_state.get("maskRegions") or []),
            assert_regions=list(self._annotation_state.get("assertRegions") or []),
        )
        self._place_toolbar()

    def _show_viewport_outline(self, viewport_payload: dict[str, Any] | None) -> None:
        desktop_rect, viewport_rect = self._resolve_desktop_context(viewport_payload)
        outline_widget = self._ensure_outline_widget()
        if _is_full_viewport(viewport_rect, desktop_rect):
            outline_widget.clear_viewport()
            return
        outline_widget.set_viewport(desktop_rect, viewport_rect)

    def _hide_viewport_outline(self) -> None:
        if self._outline_widget is not None:
            self._outline_widget.clear_viewport()

    def _clear_annotation_state(self) -> None:
        self._annotation_state = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
        if self._pending_annotation_future and not self._pending_annotation_future.done():
            self._update_toolbar("已清空标注，可重新选择。")

    def _start_selection(self, purpose: str) -> None:
        if not self._pending_annotation_future or self._pending_annotation_future.done():
            return
        toolbar_widget = self._toolbar_widget
        if toolbar_widget is not None:
            toolbar_widget.hide()
        self._ensure_selector_widget().begin(
            self._desktop_rect,
            self._viewport_rect,
            purpose,
        )

    def _handle_selection_finished(self, payload: dict[str, Any]) -> None:  # pragma: no cover - GUI callback
        purpose = str(payload.get("purpose") or "")
        rect_payload = payload.get("rect") or {}
        if purpose == "focus":
            self._annotation_state["focusRegion"] = rect_payload
        elif purpose == "mask":
            self._annotation_state.setdefault("maskRegions", []).append({**rect_payload, "exclude": True})
        elif purpose == "assert":
            self._annotation_state.setdefault("assertRegions", []).append(rect_payload)
        toolbar_widget = self._ensure_toolbar_widget()
        toolbar_widget.show()
        toolbar_widget.raise_()
        self._update_toolbar("标注已记录，可继续增加区域或继续录制。")

    def _handle_selection_cancelled(self) -> None:  # pragma: no cover - GUI callback
        if self._pending_annotation_future and not self._pending_annotation_future.done():
            toolbar_widget = self._ensure_toolbar_widget()
            toolbar_widget.show()
            toolbar_widget.raise_()
            self._update_toolbar("已取消当前选择。")

    def _finish_annotation(self) -> None:
        future = self._pending_annotation_future
        result = {
            "focusRegion": self._annotation_state.get("focusRegion"),
            "maskRegions": list(self._annotation_state.get("maskRegions") or []),
            "assertRegions": list(self._annotation_state.get("assertRegions") or []),
            "skipped": False,
        }
        if self._selector_widget is not None:
            self._selector_widget.hide()
        if self._toolbar_widget is not None:
            self._toolbar_widget.hide()
        self._pending_annotation_future = None
        self._annotation_state = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
        if future is not None and not future.done():
            future.set_result(result)

    def _cancel_annotation(self) -> None:
        future = self._pending_annotation_future
        if self._selector_widget is not None:
            self._selector_widget.hide()
        if self._toolbar_widget is not None:
            self._toolbar_widget.hide()
        self._pending_annotation_future = None
        self._annotation_state = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
        if future is not None and not future.done():
            future.set_result({"focusRegion": None, "maskRegions": [], "assertRegions": [], "skipped": True})

    def _suspend_capture(self) -> dict[str, Any]:
        selector_widget = self._selector_widget
        toolbar_widget = self._toolbar_widget
        outline_widget = self._outline_widget
        state = {
            "outlineVisible": bool(outline_widget and outline_widget.isVisible()),
            "toolbarVisible": bool(toolbar_widget and toolbar_widget.isVisible()),
            "selectorVisible": bool(selector_widget and selector_widget.isVisible()),
            "selectorPurpose": selector_widget.current_purpose() if selector_widget else "focus",
        }
        if outline_widget is not None:
            outline_widget.hide()
        if toolbar_widget is not None:
            toolbar_widget.hide()
        if selector_widget is not None:
            selector_widget.hide()
        return state

    def _resume_capture(self, state: dict[str, Any] | None) -> None:
        state = state or {}
        if state.get("outlineVisible") and self._viewport_rect.isValid() and not _is_full_viewport(self._viewport_rect, self._desktop_rect):
            self._ensure_outline_widget().set_viewport(
                self._desktop_rect,
                self._viewport_rect,
            )
        if state.get("toolbarVisible") and self._pending_annotation_future and not self._pending_annotation_future.done():
            toolbar_widget = self._ensure_toolbar_widget()
            toolbar_widget.show()
            toolbar_widget.raise_()
            self._update_toolbar()
        if state.get("selectorVisible") and self._pending_annotation_future and not self._pending_annotation_future.done():
            self._ensure_selector_widget().begin(
                self._desktop_rect,
                self._viewport_rect,
                str(state.get("selectorPurpose") or "focus"),
            )

    def _handle_command(self, command: _OverlayCommand) -> None:  # pragma: no cover - GUI dispatch
        try:
            if command.kind == "show_viewport":
                self._show_viewport_outline(command.payload.get("viewport"))
                if command.future and not command.future.done():
                    command.future.set_result(True)
                return

            if command.kind == "hide_viewport":
                self._hide_viewport_outline()
                if command.future and not command.future.done():
                    command.future.set_result(True)
                return

            if command.kind == "suspend_capture":
                state = self._suspend_capture()
                if command.future and not command.future.done():
                    command.future.set_result(state)
                return

            if command.kind == "resume_capture":
                self._resume_capture(command.payload.get("state"))
                if command.future and not command.future.done():
                    command.future.set_result(True)
                return

            if command.kind == "request_annotation":
                future = command.future
                if future is None:
                    return
                if self._pending_annotation_future and not self._pending_annotation_future.done():
                    self._pending_annotation_future.set_result({"focusRegion": None, "maskRegions": [], "assertRegions": [], "skipped": True})
                self._pending_annotation_future = future
                self._annotation_state = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
                self._show_viewport_outline(command.payload.get("viewport"))
                self._update_toolbar(command.payload.get("prompt") or "")
                toolbar_widget = self._ensure_toolbar_widget()
                toolbar_widget.show()
                toolbar_widget.raise_()
                return

            if command.kind == "cancel_annotation":
                self._cancel_annotation()
                if command.future and not command.future.done():
                    command.future.set_result(True)
                return

            if command.future and not command.future.done():
                command.future.set_result(None)
        except Exception as exc:
            if command.future and not command.future.done():
                command.future.set_exception(exc)


_controller: _DesktopRecordOverlayController | None = None


def install_desktop_record_overlay(app: QApplication | None = None) -> None:
    global _controller
    if _controller is not None:
        return
    app = app or QApplication.instance()
    if app is None:
        return
    _controller = _DesktopRecordOverlayController(app)


def _dispatch_command(kind: str, payload: dict[str, Any] | None = None, *, wait: bool = False, timeout: float = 1.5, future: concurrent.futures.Future | None = None):
    controller = _controller
    if controller is None:
        if future is not None and not future.done():
            future.set_result(None)
        return None
    command = _OverlayCommand(kind=kind, payload=payload or {}, future=future or (concurrent.futures.Future() if wait else None))
    controller.command_received.emit(command)
    if wait and command.future is not None:
        return command.future.result(timeout=timeout)
    return command.future


def show_recording_viewport(viewport_payload: dict[str, Any] | None) -> None:
    _dispatch_command("show_viewport", {"viewport": viewport_payload}, wait=False)


def hide_recording_viewport() -> None:
    _dispatch_command("hide_viewport", wait=False)


def suspend_recording_overlays_for_capture() -> dict[str, Any]:
    result = _dispatch_command("suspend_capture", wait=True)
    return result if isinstance(result, dict) else {}


def resume_recording_overlays_after_capture(state: dict[str, Any] | None) -> None:
    _dispatch_command("resume_capture", {"state": state or {}}, wait=False)


def request_recording_annotation(viewport_payload: dict[str, Any] | None, *, prompt: str = "") -> concurrent.futures.Future:
    future: concurrent.futures.Future = concurrent.futures.Future()
    _dispatch_command("request_annotation", {"viewport": viewport_payload, "prompt": prompt}, wait=False, future=future)
    return future


def cancel_recording_annotation() -> None:
    _dispatch_command("cancel_annotation", wait=False)
