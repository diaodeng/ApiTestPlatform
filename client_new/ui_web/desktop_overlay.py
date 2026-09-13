"""桌面测试的屏幕覆盖层（pywebview 版，替代原 Qt desktop_record_overlay）。

提供与原 Qt 版一致的六 个公开函数（desktop_test_service 按相同签名调用）：

- show_recording_viewport(viewport_payload): 显示录制视口描边（视口为全屏时不显示）
- hide_recording_viewport(): 隐藏视口描边
- suspend_recording_overlays_for_capture(): 截屏前隐藏全部覆盖层（避免被截进画面），返回可见状态
- resume_recording_overlays_after_capture(state): 截屏后按状态恢复覆盖层
- request_recording_annotation(viewport_payload, prompt): 弹出标注工具条与拖拽选择框，
  返回 Future，结果为 {focusRegion, maskRegions, assertRegions, skipped}
- cancel_recording_annotation(): 取消进行中的标注（按 skipped 处理）

实现方式：三个 pywebview 无边框窗口（透明描边窗 / 交互选择窗 / 不透明工具条窗），
按需懒创建；描边窗通过 Win32 WS_EX_TRANSPARENT 设置整窗点击穿透（等价原
Qt WA_TransparentForMouseEvents），保证桌面自动化操作不受遮挡影响。

坐标系说明：pywebview 初始化时已调用 SetProcessDPIAware，进程内
GetSystemMetrics / GetWindowRect / pyautogui 坐标一致（物理像素，主屏基准）；
窗口内 JS 使用 CSS 像素，Python 侧按“物理宽度 / innerWidth”动态换算，
因此对系统缩放不敏感。
"""

from __future__ import annotations

import ctypes
import concurrent.futures
import json
import sys
import threading
from typing import Any

from loguru import logger

# 视口描边与各类区域颜色（与原版一致）
OUTLINE_COLOR = "#ff3b30"
FOCUS_COLOR = "#22c55e"
MASK_COLOR = "#f59e0b"
ASSERT_COLOR = "#2563eb"

# Win32 常量
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_NOACTIVATE = 0x08000000
_HWND_TOPMOST = -1
_SWP_NOACTIVATE = 0x0010

_PURPOSE_TEXT = {
    "focus": "拖拽选择验证区域",
    "mask": "拖拽选择忽略区域",
    "assert": "拖拽选择新增断言区域",
}
_PURPOSE_COLOR = {
    "focus": FOCUS_COLOR,
    "mask": MASK_COLOR,
    "assert": ASSERT_COLOR,
}


def _virtual_geometry() -> dict[str, int]:
    """多屏虚拟桌面几何（物理像素），GetSystemMetrics 失败时退回 1920x1080。"""
    try:
        user32 = ctypes.windll.user32
        left, top = user32.GetSystemMetrics(_SM_XVIRTUALSCREEN), user32.GetSystemMetrics(_SM_YVIRTUALSCREEN)
        width, height = user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN), user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN)
        if width > 0 and height > 0:
            return {"left": left, "top": top, "width": width, "height": height}
    except Exception:
        pass
    return {"left": 0, "top": 0, "width": 1920, "height": 1080}


def _normalize_rect(payload: dict[str, Any] | None) -> dict[str, int] | None:
    payload = payload or {}
    width = max(int(payload.get("width") or 0), 0)
    height = max(int(payload.get("height") or 0), 0)
    if width <= 0 or height <= 0:
        return None
    return {
        "left": int(payload.get("left") or 0),
        "top": int(payload.get("top") or 0),
        "width": width,
        "height": height,
    }


def _rect_contains(container: dict[str, int], rect: dict[str, int]) -> bool:
    return (
        rect["left"] >= container["left"]
        and rect["top"] >= container["top"]
        and rect["left"] + rect["width"] <= container["left"] + container["width"]
        and rect["top"] + rect["height"] <= container["top"] + container["height"]
    )


class _OverlayApi:
    """
    覆盖层窗口的 js_api：选择窗与工具条窗把用户操作回传到 Python 侧。
    """

    def __init__(self, runtime: "_OverlayRuntime"):
        self._runtime = runtime

    def selection_finished(self, purpose: str, rect_json: str) -> dict:
        """选择窗拖拽完成（rect 为窗口内 CSS 像素），由 runtime 换算为屏幕坐标。"""
        self._runtime.handle_selection_finished(str(purpose or ""), rect_json)
        return {"ok": True}

    def selection_cancelled(self) -> dict:
        self._runtime.handle_selection_cancelled()
        return {"ok": True}

    def toolbar_action(self, action: str) -> dict:
        """工具条按钮点击（focus/mask/assert/clear/accept/cancel）。"""
        self._runtime.handle_toolbar_action(str(action or ""))
        return {"ok": True}


class _OverlayRuntime:
    """覆盖层窗口运行时：懒创建三个窗口并维护标注状态。"""

    def __init__(self):
        self._lock = threading.RLock()
        self._windows: dict[str, Any] = {}
        # 自行跟踪各窗口可见性（pywebview 的 window.hidden 不随 show/hide 更新）
        self._visible: dict[str, bool] = {}
        self._api = _OverlayApi(self)
        self._desktop: dict[str, int] = {}
        self._viewport: dict[str, int] | None = None
        self._pending_future: concurrent.futures.Future | None = None
        self._annotation_state: dict[str, Any] = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
        self._suspended: dict[str, Any] = {}
        self._last_prompt = ""

    # ===== 窗口管理 =====

    def _set_visible(self, kind: str, flag: bool) -> None:
        self._visible[kind] = flag

    def _show_win(self, kind: str) -> None:
        win = self._windows.get(kind)
        if win is not None:
            try:
                win.show()
                self._visible[kind] = True
            except Exception as e:
                logger.debug(f"显示覆盖层窗口失败 kind={kind}: {e}")

    def _hide_win(self, kind: str) -> None:
        win = self._windows.get(kind)
        if win is not None:
            try:
                win.hide()
                self._visible[kind] = False
            except Exception as e:
                logger.debug(f"隐藏覆盖层窗口失败 kind={kind}: {e}")

    def _create_window(self, kind: str):
        import webview

        geom = self._desktop or _virtual_geometry()
        common = dict(
            x=geom["left"],
            y=geom["top"],
            width=geom["width"],
            height=geom["height"],
            frameless=True,
            on_top=True,
            hidden=True,
            js_api=self._api,
        )
        if kind == "outline":
            win = webview.create_window(
                "QTRDesktopOverlayOutline", html=_OUTLINE_HTML, transparent=True, focus=False, **common
            )
        elif kind == "selector":
            win = webview.create_window(
                "QTRDesktopOverlaySelector", html=_SELECTOR_HTML, transparent=True, focus=True, **common
            )
        else:  # toolbar：不透明深色面板，固定尺寸
            win = webview.create_window(
                "QTRDesktopOverlayToolbar",
                html=_TOOLBAR_HTML,
                x=geom["left"] + geom["width"] - 620,
                y=geom["top"] + 40,
                width=600,
                height=190,
                frameless=True,
                on_top=True,
                focus=False,
                hidden=True,
                js_api=self._api,
            )
        try:
            win.events.loaded.wait(timeout=5)
        except Exception as e:
            logger.debug(f"等待覆盖层窗口加载超时 kind={kind}: {e}")
        return win

    def _ensure_window(self, kind: str):
        win = self._windows.get(kind)
        if win is not None:
            return win
        win = self._create_window(kind)
        self._windows[kind] = win
        if kind == "outline":
            self._apply_click_through(win)
        return win

    def _hwnd(self, win) -> int:
        """取窗口原生 HWND（pywebview winforms 下 window.native 为 BrowserView）。"""
        native = getattr(win, "native", None)
        form = getattr(native, "form", native)
        handle = getattr(form, "Handle", None)
        try:
            return int(handle.ToInt64())
        except Exception:
            try:
                return int(handle)
            except Exception:
                return 0

    def _apply_click_through(self, win) -> None:
        """
        描边窗整窗点击穿透（等价 Qt WA_TransparentForMouseEvents）：
        追加 WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW。
        """
        try:
            hwnd = self._hwnd(win)
            if not hwnd or not sys.platform.startswith("win"):
                return
            user32 = ctypes.windll.user32
            ex_style = user32.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
            user32.SetWindowLongPtrW(
                hwnd,
                _GWL_EXSTYLE,
                ex_style | _WS_EX_TRANSPARENT | _WS_EX_LAYERED | _WS_EX_NOACTIVATE | 0x80,
            )
            logger.debug("描边覆盖层已设置点击穿透")
        except Exception as e:
            logger.warning(f"设置描边覆盖层点击穿透失败: {e}")

    def _place_window(self, win, left: int, top: int, width: int, height: int) -> None:
        """以物理像素直接定位窗口（进程 DPI 感知，与 pyautogui 坐标一致）。"""
        try:
            hwnd = self._hwnd(win)
            if not hwnd or not sys.platform.startswith("win"):
                return
            ctypes.windll.user32.SetWindowPos(
                hwnd, _HWND_TOPMOST, int(left), int(top), int(width), int(height), _SWP_NOACTIVATE
            )
        except Exception as e:
            logger.warning(f"覆盖层窗口定位失败: {e}")

    def _scale_info(self, win) -> tuple[int, int, float]:
        """
        返回 (窗口原点物理 x, 窗口原点物理 y, 物理px/CSSpx 缩放比)。
        用于窗口内 CSS 坐标与屏幕坐标互转。
        """
        try:
            hwnd = self._hwnd(win)
            import ctypes.wintypes as wintypes

            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            phys_width = max(rect.right - rect.left, 1)
            inner = win.evaluate_js("window.innerWidth") or phys_width
            return rect.left, rect.top, phys_width / max(inner, 1)
        except Exception:
            return 0, 0, 1.0

    def _css_to_screen(self, scale: tuple[int, int, float], rect: dict[str, int]) -> dict[str, int]:
        origin_x, origin_y, scale_factor = scale
        return {
            "left": int(origin_x + rect["left"] * scale_factor),
            "top": int(origin_y + rect["top"] * scale_factor),
            "width": max(int(rect["width"] * scale_factor), 0),
            "height": max(int(rect["height"] * scale_factor), 0),
        }

    def _screen_to_css(self, scale: tuple[int, int, float], rect: dict[str, int]) -> dict[str, float]:
        origin_x, origin_y, scale_factor = scale
        return {
            "left": (rect["left"] - origin_x) / scale_factor,
            "top": (rect["top"] - origin_y) / scale_factor,
            "width": rect["width"] / scale_factor,
            "height": rect["height"] / scale_factor,
        }

    def _resolve_context(self, viewport_payload: dict[str, Any] | None):
        """解析桌面与视口矩形（视口缺省/无效时取整桌面）。"""
        self._desktop = _virtual_geometry()
        viewport = _normalize_rect(viewport_payload)
        if viewport is None or not _rect_contains(
            {
                "left": self._desktop["left"] - 1,
                "top": self._desktop["top"] - 1,
                "width": self._desktop["width"] + 2,
                "height": self._desktop["height"] + 2,
            },
            viewport,
        ):
            viewport = dict(self._desktop)
        self._viewport = viewport
        return self._desktop, viewport

    def _is_full_viewport(self, viewport: dict[str, int], desktop: dict[str, int]) -> bool:
        return (
            viewport["left"] <= desktop["left"]
            and viewport["top"] <= desktop["top"]
            and viewport["width"] >= desktop["width"]
            and viewport["height"] >= desktop["height"]
        )

    # ===== 公开命令实现 =====

    def show_viewport(self, viewport_payload: dict[str, Any] | None) -> None:
        with self._lock:
            desktop, viewport = self._resolve_context(viewport_payload)
            if self._is_full_viewport(viewport, desktop):
                self.hide_viewport()
                return
            win = self._ensure_window("outline")
            self._place_window(win, desktop["left"], desktop["top"], desktop["width"], desktop["height"])
            self._show_win("outline")
            scale = self._scale_info(win)
            css = self._screen_to_css(scale, viewport)
            try:
                win.evaluate_js(
                    f"setViewportBox({json.dumps(css, ensure_ascii=False)})"  # noqa: S603
                )
            except Exception as e:
                logger.warning(f"更新视口描边失败: {e}")

    def hide_viewport(self) -> None:
        with self._lock:
            win = self._windows.get("outline")
            if win is not None:
                try:
                    win.evaluate_js("setViewportBox(null)")
                except Exception:
                    pass
            self._hide_win("outline")

    def suspend_capture(self) -> dict[str, Any]:
        with self._lock:
            selector = self._windows.get("selector")
            purpose = "focus"
            try:
                if selector is not None:
                    purpose = str(selector.evaluate_js("window.__purpose || 'focus'") or "focus")
            except Exception:
                pass

            state = {
                "outlineVisible": bool(self._visible.get("outline")),
                "toolbarVisible": bool(self._visible.get("toolbar")),
                "selectorVisible": bool(self._visible.get("selector")),
                "selectorPurpose": purpose,
            }
            for kind in ("outline", "toolbar", "selector"):
                self._hide_win(kind)
            return state

    def resume_capture(self, state: dict[str, Any] | None) -> None:
        with self._lock:
            state = state or {}
            if state.get("outlineVisible") and self._viewport and self._desktop:
                self.show_viewport(self._viewport)
            if state.get("toolbarVisible") and self._pending_future and not self._pending_future.done():
                self._show_toolbar(self._last_prompt)
            if state.get("selectorVisible") and self._pending_future and not self._pending_future.done():
                self._start_selection(str(state.get("selectorPurpose") or "focus"))

    def request_annotation(self, viewport_payload: dict[str, Any] | None, prompt: str) -> concurrent.futures.Future:
        future: concurrent.futures.Future = concurrent.futures.Future()

        def _run():
            with self._lock:
                if self._pending_future and not self._pending_future.done():
                    self._pending_future.set_result(
                        {"focusRegion": None, "maskRegions": [], "assertRegions": [], "skipped": True}
                    )
                self._pending_future = future
                self._annotation_state = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
                self.show_viewport(viewport_payload)
                self._show_toolbar(prompt)

        # 窗口创建/展示较重，放后台线程执行，调用方只持有 Future
        threading.Thread(target=_run, name="desktop-overlay-annotation", daemon=True).start()
        return future

    def cancel_annotation(self) -> None:
        with self._lock:
            future = self._pending_future
            self._hide_annotation_windows()
            self._pending_future = None
            self._annotation_state = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
            if future is not None and not future.done():
                future.set_result({"focusRegion": None, "maskRegions": [], "assertRegions": [], "skipped": True})

    def shutdown(self) -> None:
        with self._lock:
            future = self._pending_future
            if future is not None and not future.done():
                future.set_result({"focusRegion": None, "maskRegions": [], "assertRegions": [], "skipped": True})
            self._pending_future = None
            for win in self._windows.values():
                try:
                    win.destroy()
                except Exception:
                    pass
            self._windows.clear()

    # ===== 工具条与选择交互 =====

    def _show_toolbar(self, prompt: str) -> None:
        self._last_prompt = str(prompt or "")
        win = self._ensure_window("toolbar")
        self._update_toolbar_content(win, self._last_prompt, "已暂停录制，选择要标注的区域后继续。")
        self._place_toolbar(win)
        self._show_win("toolbar")

    def _update_toolbar_content(self, win, prompt: str, status_prefix: str) -> None:
        state = self._annotation_state
        payload = {
            "prompt": prompt or "已暂停录制，选择要标注的区域后继续。",
            "focusSet": bool(state.get("focusRegion")),
            "maskCount": len(state.get("maskRegions") or []),
            "assertCount": len(state.get("assertRegions") or []),
            "statusPrefix": status_prefix,
        }
        try:
            win.evaluate_js(f"updateState({json.dumps(payload, ensure_ascii=False)})")  # noqa: S603
        except Exception as e:
            logger.debug(f"更新标注工具条状态失败: {e}")

    def _place_toolbar(self, win) -> None:
        """工具条贴视口摆放：右侧 → 下方 → 上方 → 工作区右上角（与原版策略一致）。"""
        desktop = self._desktop or _virtual_geometry()
        viewport = self._viewport or dict(desktop)
        margin = 18
        toolbar_w, toolbar_h = 600, 190

        min_x = desktop["left"] + margin
        min_y = desktop["top"] + margin
        max_x = max(min_x, desktop["left"] + desktop["width"] - toolbar_w - margin)
        max_y = max(min_y, desktop["top"] + desktop["height"] - toolbar_h - margin)

        def clamp(x: int, y: int) -> tuple[int, int]:
            return min(max(x, min_x), max_x), min(max(y, min_y), max_y)

        candidates = [
            (viewport["left"] + viewport["width"] + margin, max(viewport["top"], min_y)),
            (max(viewport["left"], min_x), viewport["top"] + viewport["height"] + margin),
            (max(viewport["left"], min_x), viewport["top"] - toolbar_h - margin),
            (max_x, min_y),
        ]
        chosen = (max_x, min_y)
        for x, y in candidates:
            chosen = clamp(x, y)
            if (
                min_x <= chosen[0]
                and chosen[0] + toolbar_w <= desktop["left"] + desktop["width"] - margin
                and min_y <= chosen[1]
                and chosen[1] + toolbar_h <= desktop["top"] + desktop["height"] - margin
            ):
                break
        self._place_window(win, chosen[0], chosen[1], toolbar_w, toolbar_h)

    def _start_selection(self, purpose: str) -> None:
        if not self._pending_future or self._pending_future.done():
            return
        self._hide_win("toolbar")
        win = self._ensure_window("selector")
        self._place_window(win, self._desktop["left"], self._desktop["top"], self._desktop["width"], self._desktop["height"])
        scale = self._scale_info(win)
        viewport_css = self._screen_to_css(scale, self._viewport or dict(self._desktop))
        payload = {
            "viewport": viewport_css,
            "purpose": purpose,
            "text": _PURPOSE_TEXT.get(purpose, "拖拽选择区域"),
            "color": _PURPOSE_COLOR.get(purpose, FOCUS_COLOR),
        }
        try:
            win.evaluate_js(f"beginSelection({json.dumps(payload, ensure_ascii=False)})")  # noqa: S603
            self._set_visible("selector", True)
        except Exception as e:
            logger.warning(f"启动区域选择失败: {e}")

    def _hide_annotation_windows(self) -> None:
        for kind in ("selector", "toolbar"):
            self._hide_win(kind)

    def _finish_annotation(self) -> None:
        with self._lock:
            future = self._pending_future
            self._hide_annotation_windows()
            self._pending_future = None
            result = {
                "focusRegion": self._annotation_state.get("focusRegion"),
                "maskRegions": list(self._annotation_state.get("maskRegions") or []),
                "assertRegions": list(self._annotation_state.get("assertRegions") or []),
                "skipped": False,
            }
            self._annotation_state = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
            if future is not None and not future.done():
                future.set_result(result)

    # ===== js_api 回调 =====

    def handle_selection_finished(self, purpose: str, rect_json: str) -> None:
        with self._lock:
            try:
                rect_css = json.loads(rect_json or "{}")
            except Exception:
                rect_css = {}
            win = self._windows.get("selector")
            scale = self._scale_info(win) if win is not None else (0, 0, 1.0)
            rect = self._css_to_screen(scale, rect_css)
            self._hide_win("selector")
            if rect["width"] < 4 or rect["height"] < 4:
                # 过小的选择视为取消（与原版一致）
                if self._pending_future and not self._pending_future.done():
                    self._show_toolbar(self._last_prompt)
                    self._update_toolbar_content(
                        self._windows.get("toolbar"), self._last_prompt, "已取消当前选择。"
                    )
                return

            if purpose == "focus":
                self._annotation_state["focusRegion"] = rect
            elif purpose == "mask":
                self._annotation_state.setdefault("maskRegions", []).append({**rect, "exclude": True})
            elif purpose == "assert":
                self._annotation_state.setdefault("assertRegions", []).append(rect)
            self._show_toolbar(self._last_prompt)
            self._update_toolbar_content(
                self._windows.get("toolbar"), self._last_prompt, "标注已记录，可继续增加区域或继续录制。"
            )

    def handle_selection_cancelled(self) -> None:
        with self._lock:
            if self._pending_future and not self._pending_future.done():
                self._show_toolbar(self._last_prompt)
                self._update_toolbar_content(
                    self._windows.get("toolbar"), self._last_prompt, "已取消当前选择。"
                )

    def handle_toolbar_action(self, action: str) -> None:
        with self._lock:
            if action == "clear":
                self._annotation_state = {"focusRegion": None, "maskRegions": [], "assertRegions": []}
                if self._pending_future and not self._pending_future.done():
                    self._update_toolbar_content(
                        self._windows.get("toolbar"), self._last_prompt, "已清空标注，可重新选择。"
                    )
                return
            if action in ("focus", "mask", "assert"):
                self._start_selection(action)
                return
            if action == "accept":
                self._finish_annotation()
                return
            if action == "cancel":
                self.cancel_annotation()


_runtime: _OverlayRuntime | None = None
_runtime_lock = threading.Lock()


def _get_runtime() -> _OverlayRuntime | None:
    """
    获取覆盖层运行时；仅在主 GUI 已初始化（进程 DPI 感知已建立）后可用，
    且仅 Windows 平台支持。
    """
    global _runtime
    if not sys.platform.startswith("win"):
        return None
    with _runtime_lock:
        if _runtime is None:
            try:
                import webview  # noqa: F401

                _runtime = _OverlayRuntime()
            except Exception as e:
                logger.warning(f"初始化桌面覆盖层运行时失败: {e}")
                return None
        return _runtime


# ===== 对外公开 API（与原 Qt 版签名一致） =====


def show_recording_viewport(viewport_payload: dict[str, Any] | None) -> None:
    runtime = _get_runtime()
    if runtime is None:
        return
    try:
        runtime.show_viewport(viewport_payload)
    except Exception as e:
        logger.warning(f"显示录制视口描边失败: {e}")


def hide_recording_viewport() -> None:
    runtime = _get_runtime()
    if runtime is None:
        return
    try:
        runtime.hide_viewport()
    except Exception as e:
        logger.warning(f"隐藏录制视口描边失败: {e}")


def suspend_recording_overlays_for_capture() -> dict[str, Any]:
    runtime = _get_runtime()
    if runtime is None:
        return {}
    try:
        return runtime.suspend_capture()
    except Exception as e:
        logger.warning(f"挂起覆盖层失败: {e}")
        return {}


def resume_recording_overlays_after_capture(state: dict[str, Any] | None) -> None:
    runtime = _get_runtime()
    if runtime is None:
        return
    try:
        runtime.resume_capture(state)
    except Exception as e:
        logger.warning(f"恢复覆盖层失败: {e}")


def request_recording_annotation(
    viewport_payload: dict[str, Any] | None, *, prompt: str = ""
) -> concurrent.futures.Future:
    runtime = _get_runtime()
    if runtime is None:
        future: concurrent.futures.Future = concurrent.futures.Future()
        future.set_result({"focusRegion": None, "maskRegions": [], "assertRegions": [], "skipped": True})
        return future
    return runtime.request_annotation(viewport_payload, prompt)


def cancel_recording_annotation() -> None:
    runtime = _get_runtime()
    if runtime is None:
        return
    try:
        runtime.cancel_annotation()
    except Exception as e:
        logger.warning(f"取消标注失败: {e}")


def shutdown_overlays() -> None:
    """应用退出时销毁覆盖层窗口并放行未决标注。"""
    global _runtime
    with _runtime_lock:
        if _runtime is not None:
            try:
                _runtime.shutdown()
            except Exception as e:
                logger.debug(f"销毁覆盖层失败: {e}")
            _runtime = None


# ===== 窗口页面模板 =====

# 描边窗：透明背景，仅绘制视口红色边框；整窗点击穿透由 Python 侧设置
_OUTLINE_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;background:transparent;overflow:hidden}
#box{position:fixed;display:none;border:3px solid __OUTLINE__;box-sizing:border-box;pointer-events:none}
</style></head><body>
<div id="box"></div>
<script>
function setViewportBox(rect){
  var box=document.getElementById('box');
  if(!rect){box.style.display='none';return;}
  box.style.display='block';
  box.style.left=rect.left+'px';box.style.top=rect.top+'px';
  box.style.width=rect.width+'px';box.style.height=rect.height+'px';
}
</script></body></html>""".replace("__OUTLINE__", OUTLINE_COLOR)

# 选择窗：透明背景 + 半透明遮罩 + 视口描边 + 拖拽虚线框 + 顶部提示横幅
_SELECTOR_HTML_SOURCE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;background:transparent;overflow:hidden;user-select:none;cursor:crosshair}
#dim{position:fixed;inset:0;background:rgba(15,23,42,0.14)}
#vp{position:fixed;display:none;border:3px solid __OUTLINE__;box-sizing:border-box;pointer-events:none}
#sel{position:fixed;display:none;border:2px dashed __FOCUS__;box-sizing:border-box;pointer-events:none}
#banner{position:fixed;left:24px;top:20px;min-width:320px;max-width:720px;background:rgba(15,23,42,0.75);
 color:#fff;font:13px/1.5 "Microsoft YaHei",sans-serif;padding:10px 14px;border-radius:8px}
</style></head><body>
<div id="dim"></div><div id="vp"></div><div id="sel"></div><div id="banner"></div>
<script>
var vpRect=null, purpose='focus', start=null, cur=null;
window.__purpose='focus';
document.addEventListener('contextmenu',function(e){e.preventDefault();});
function clampPt(x,y){
  var x1=Math.min(Math.max(x,vpRect.left),vpRect.left+vpRect.width-1);
  var y1=Math.min(Math.max(y,vpRect.top),vpRect.top+vpRect.height-1);
  return {x:x1,y:y1};
}
function drawSel(){
  var box=document.getElementById('sel');
  if(start===null||cur===null){box.style.display='none';return;}
  var left=Math.min(start.x,cur.x),top=Math.min(start.y,cur.y);
  box.style.display='block';
  box.style.left=left+'px';box.style.top=top+'px';
  box.style.width=Math.abs(cur.x-start.x)+'px';box.style.height=Math.abs(cur.y-start.y)+'px';
  box.style.borderColor=window.__color;
}
function screenToCss(e){return {x:e.screenX-window.screenX,y:e.screenY-window.screenY};}
function beginSelection(cfg){
  vpRect=cfg.viewport;purpose=cfg.purpose;start=null;cur=null;
  window.__purpose=cfg.purpose;window.__color=cfg.color;
  document.getElementById('banner').textContent=cfg.text+'，按 Esc 取消';
  var vp=document.getElementById('vp');
  vp.style.display='block';
  vp.style.left=vpRect.left+'px';vp.style.top=vpRect.top+'px';
  vp.style.width=vpRect.width+'px';vp.style.height=vpRect.height+'px';
  drawSel();
}
document.addEventListener('mousedown',function(e){
  if(e.button!==0||!vpRect)return;
  var p=screenToCss(e);
  if(p.x<vpRect.left||p.y<vpRect.top||p.x>vpRect.left+vpRect.width||p.y>vpRect.top+vpRect.height)return;
  start=clampPt(p.x,p.y);cur={x:start.x,y:start.y};drawSel();
});
document.addEventListener('mousemove',function(e){
  if(start===null||!vpRect)return;
  var p=clampPt(screenToCss(e).x,screenToCss(e).y);
  cur=p;drawSel();
});
document.addEventListener('mouseup',function(e){
  if(e.button!==0||start===null||!vpRect)return;
  cur=clampPt(screenToCss(e).x,screenToCss(e).y);
  var left=Math.min(start.x,cur.x),top=Math.min(start.y,cur.y);
  var rect={left:left,top:top,width:Math.abs(cur.x-start.x),height:Math.abs(cur.y-start.y)};
  start=null;cur=null;
  var box=document.getElementById('sel');box.style.display='none';
  window.pywebview.api.selection_finished(window.__purpose, JSON.stringify(rect));
});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){
    start=null;cur=null;
    document.getElementById('sel').style.display='none';
    window.pywebview.api.selection_cancelled();
  }
});
</script></body></html>"""
_SELECTOR_HTML = _SELECTOR_HTML_SOURCE.replace("__OUTLINE__", OUTLINE_COLOR).replace("__FOCUS__", FOCUS_COLOR)

# 工具条窗：不透明深色面板（提示 + 状态 + 六个操作按钮）
_TOOLBAR_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;overflow:hidden}
body{background:rgba(15,23,42,0.96);border:1px solid rgba(148,163,184,0.8);border-radius:12px;
 box-sizing:border-box;padding:12px 14px;font:13px/1.5 "Microsoft YaHei",sans-serif;color:#f8fafc}
#title{font-size:15px;font-weight:600;color:#fff}
#prompt{margin-top:6px;color:#e2e8f0}
#status{margin-top:4px;color:#94a3b8}
.row{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}
button{background:#1d4ed8;color:#fff;border:none;border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px}
button:hover{background:#2563eb}
button.subtle{background:#334155}
button.subtle:hover{background:#475569}
</style></head><body>
<div id="title">录制中标注</div>
<div id="prompt"></div>
<div id="status"></div>
<div class="row">
 <button onclick="act('focus')">验证区域</button>
 <button class="subtle" onclick="act('mask')">忽略区域</button>
 <button class="subtle" onclick="act('assert')">增加断言</button>
 <button class="subtle" onclick="act('clear')">清空标注</button>
 <button onclick="act('accept')">继续录制</button>
 <button class="subtle" onclick="act('cancel')">跳过标注</button>
</div>
<script>
function act(a){window.pywebview.api.toolbar_action(a);}
function updateState(s){
  document.getElementById('prompt').textContent=s.prompt||'已暂停录制，选择要标注的区域后继续。';
  var parts=['验证区域: '+(s.focusSet?'已设置':'未设置'),'忽略区域: '+s.maskCount,'新增断言: '+s.assertCount];
  var prefix=s.statusPrefix||'';
  document.getElementById('status').textContent=(prefix?prefix+' | ':'')+parts.join(' | ');
}
</script></body></html>"""
