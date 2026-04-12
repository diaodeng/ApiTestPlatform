from __future__ import annotations

import asyncio
import base64
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from loguru import logger

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

try:
    import pyautogui
except Exception:  # pragma: no cover - optional dependency
    pyautogui = None

try:
    import pygetwindow as gw
except Exception:  # pragma: no cover - optional dependency
    gw = None

try:
    from PIL import Image, ImageGrab
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageGrab = None

try:
    from pynput import keyboard, mouse
except Exception:  # pragma: no cover - optional dependency
    keyboard = None
    mouse = None

try:
    import pytesseract
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None

try:
    from ui.utils.desktop_record_overlay import (
        cancel_recording_annotation,
        hide_recording_viewport,
        request_recording_annotation,
        resume_recording_overlays_after_capture,
        show_recording_viewport,
        suspend_recording_overlays_for_capture,
    )
except Exception:  # pragma: no cover - optional dependency
    cancel_recording_annotation = None
    hide_recording_viewport = None
    request_recording_annotation = None
    resume_recording_overlays_after_capture = None
    show_recording_viewport = None
    suspend_recording_overlays_for_capture = None

if pyautogui is not None:
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05

EventSender = Callable[[dict[str, Any]], Awaitable[None]]

REQUEST_TYPE_DESKTOP = 5
VIEWPORT_MODE_SCREEN = "screen"
VIEWPORT_MODE_ACTIVE_WINDOW = "active_window"
VIEWPORT_MODE_MANUAL_REGION = "manual_region"
ANNOTATION_WAIT_DISABLED = "disabled"
ANNOTATION_WAIT_AFTER_CAPTURE = "after_capture"
ANNOTATION_WAIT_BEFORE_CAPTURE = "before_capture"
TRANSPORT_MAX_IMAGE_SIDE = 1600
TRANSPORT_MAX_IMAGE_PIXELS = 1600 * 900
TRANSPORT_WEBP_MIN_PIXELS = 320 * 240

KEY_NAME_MAP = {
    "Key.enter": "enter",
    "Key.tab": "tab",
    "Key.esc": "esc",
    "Key.backspace": "backspace",
    "Key.space": "space",
    "Key.up": "up",
    "Key.down": "down",
    "Key.left": "left",
    "Key.right": "right",
    "Key.delete": "delete",
    "Key.home": "home",
    "Key.end": "end",
    "Key.page_up": "pageup",
    "Key.page_down": "pagedown",
    "Key.insert": "insert",
    "Key.shift": "shift",
    "Key.shift_l": "shift",
    "Key.shift_r": "shift",
    "Key.ctrl": "ctrl",
    "Key.ctrl_l": "ctrl",
    "Key.ctrl_r": "ctrl",
    "Key.alt": "alt",
    "Key.alt_gr": "alt",
    "Key.alt_l": "alt",
    "Key.alt_r": "alt",
    "Key.caps_lock": "capslock",
    "Key.cmd": "win",
    "Key.cmd_l": "win",
    "Key.cmd_r": "win",
    "Key.menu": "apps",
    "Key.num_lock": "numlock",
    "Key.pause": "pause",
    "Key.print_screen": "printscreen",
    "Key.scroll_lock": "scrolllock",
    "Key.media_next": "nexttrack",
    "Key.media_play_pause": "playpause",
    "Key.media_previous": "prevtrack",
    "Key.media_volume_down": "volumedown",
    "Key.media_volume_mute": "volumemute",
    "Key.media_volume_up": "volumeup",
}

for index in range(1, 25):
    KEY_NAME_MAP[f"Key.f{index}"] = f"f{index}"

MODIFIER_KEY_ORDER = {"ctrl": 0, "shift": 1, "alt": 2, "win": 3}

HOTKEY_INTENT_LABELS = {
    ("ctrl", "a"): ("select_all", "全选"),
    ("ctrl", "c"): ("copy", "复制"),
    ("ctrl", "f"): ("find", "查找"),
    ("ctrl", "p"): ("print", "打印"),
    ("ctrl", "s"): ("save", "保存"),
    ("ctrl", "v"): ("paste", "粘贴"),
    ("ctrl", "x"): ("cut", "剪切"),
    ("ctrl", "y"): ("redo", "重做"),
    ("ctrl", "z"): ("undo", "撤销"),
    ("ctrl", "shift", "s"): ("save_as", "另存为"),
    ("ctrl", "shift", "z"): ("redo", "重做"),
    ("ctrl", "shift", "esc"): ("task_manager", "任务管理器"),
    ("ctrl", "insert"): ("copy", "复制"),
    ("shift", "insert"): ("paste", "粘贴"),
    ("shift", "delete"): ("cut", "剪切"),
    ("alt", "f4"): ("close_window", "关闭窗口"),
    ("alt", "tab"): ("switch_window", "切换窗口"),
    ("win", "d"): ("show_desktop", "显示桌面"),
    ("win", "e"): ("open_explorer", "打开资源管理器"),
    ("win", "r"): ("run_dialog", "打开运行窗口"),
}


def _as_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    return {}


def _as_list(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    return []


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _ensure_dependencies(*, need_recording: bool = False, need_compare: bool = False) -> None:
    missing: list[str] = []
    if pyautogui is None:
        missing.append("pyautogui")
    if Image is None or ImageGrab is None:
        missing.append("Pillow")
    if need_recording and (mouse is None or keyboard is None):
        missing.append("pynput")
    if need_compare and cv2 is None:
        missing.append("opencv-python-headless")
    if need_compare and np is None:
        missing.append("numpy")
    if missing:
        raise RuntimeError(f"桌面自动化依赖未安装: {', '.join(sorted(set(missing)))}")


@dataclass(frozen=True)
class DesktopViewport:
    mode: str
    left: int
    top: int
    width: int
    height: int
    logical_width: int
    logical_height: int

    def contains_actual_point(self, x: int, y: int) -> bool:
        return self.left <= int(x) < self.left + self.width and self.top <= int(y) < self.top + self.height

    def actual_to_logical(self, x: int, y: int) -> tuple[int, int]:
        relative_x = max(int(x) - self.left, 0)
        relative_y = max(int(y) - self.top, 0)
        logical_x = int(round(relative_x * self.logical_width / max(self.width, 1)))
        logical_y = int(round(relative_y * self.logical_height / max(self.height, 1)))
        return min(max(logical_x, 0), max(self.logical_width - 1, 0)), min(max(logical_y, 0), max(self.logical_height - 1, 0))

    def logical_to_actual(self, x: int, y: int) -> tuple[int, int]:
        logical_x = max(min(int(x), max(self.logical_width - 1, 0)), 0)
        logical_y = max(min(int(y), max(self.logical_height - 1, 0)), 0)
        actual_x = self.left + int(round(logical_x * self.width / max(self.logical_width, 1)))
        actual_y = self.top + int(round(logical_y * self.height / max(self.logical_height, 1)))
        return actual_x, actual_y

    def to_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "logicalWidth": self.logical_width,
            "logicalHeight": self.logical_height,
        }


def _normalize_viewport_mode(value: Any) -> str:
    normalized = str(value or VIEWPORT_MODE_SCREEN).strip().lower()
    if normalized not in {VIEWPORT_MODE_SCREEN, VIEWPORT_MODE_ACTIVE_WINDOW, VIEWPORT_MODE_MANUAL_REGION}:
        return VIEWPORT_MODE_SCREEN
    return normalized


def _normalize_annotation_wait_mode(value: Any) -> str:
    normalized = str(value or ANNOTATION_WAIT_DISABLED).strip().lower()
    if normalized not in {
        ANNOTATION_WAIT_DISABLED,
        ANNOTATION_WAIT_AFTER_CAPTURE,
        ANNOTATION_WAIT_BEFORE_CAPTURE,
    }:
        return ANNOTATION_WAIT_DISABLED
    return normalized


def _viewport_settings(source: dict[str, Any] | None) -> dict[str, Any]:
    settings = _as_dict(source)
    resolved = {
        "viewportMode": _normalize_viewport_mode(settings.get("viewportMode") or settings.get("viewport_mode")),
        "viewportX": settings.get("viewportX", settings.get("viewport_x")),
        "viewportY": settings.get("viewportY", settings.get("viewport_y")),
        "viewportWidth": settings.get("viewportWidth", settings.get("viewport_width")),
        "viewportHeight": settings.get("viewportHeight", settings.get("viewport_height")),
        "logicalWidth": settings.get("logicalWidth", settings.get("logical_width")),
        "logicalHeight": settings.get("logicalHeight", settings.get("logical_height")),
        "resizeActiveWindow": bool(settings.get("resizeActiveWindow", settings.get("resize_active_window", False))),
        "annotationWaitMode": _normalize_annotation_wait_mode(
            settings.get("annotationWaitMode") or settings.get("annotation_wait_mode")
        ),
    }
    # When only logical size is set in screen mode, treat it as the actual crop region.
    if resolved["viewportMode"] == VIEWPORT_MODE_SCREEN:
        if resolved["viewportWidth"] in (None, "") and resolved["logicalWidth"] not in (None, ""):
            resolved["viewportWidth"] = resolved["logicalWidth"]
        if resolved["viewportHeight"] in (None, "") and resolved["logicalHeight"] not in (None, ""):
            resolved["viewportHeight"] = resolved["logicalHeight"]
    return resolved


def _current_active_window():
    if gw is None:
        return None
    try:
        return gw.getActiveWindow()
    except Exception:
        return None


def _resolve_viewport(viewport_source: dict[str, Any] | None, *, screen_image=None) -> DesktopViewport:
    settings = _viewport_settings(viewport_source)
    mode = settings["viewportMode"]
    screen_width = int(getattr(screen_image, "width", 0) or 0)
    screen_height = int(getattr(screen_image, "height", 0) or 0)
    if screen_width <= 0 or screen_height <= 0:
        fallback_size = pyautogui.size() if pyautogui is not None else None
        screen_width = int(getattr(fallback_size, "width", 1920) or 1920)
        screen_height = int(getattr(fallback_size, "height", 1080) or 1080)

    left = 0
    top = 0
    width = screen_width
    height = screen_height

    if mode == VIEWPORT_MODE_SCREEN:
        left = _as_int(settings.get("viewportX"), 0)
        top = _as_int(settings.get("viewportY"), 0)
        width = max(_as_int(settings.get("viewportWidth"), screen_width), 1)
        height = max(_as_int(settings.get("viewportHeight"), screen_height), 1)

    if mode == VIEWPORT_MODE_ACTIVE_WINDOW:
        if gw is None:
            raise RuntimeError("活动窗口模式依赖 pygetwindow，当前环境未安装，可安装后重试或改用手动区域模式")
        active_window = _current_active_window()
        if active_window is None:
            raise RuntimeError("未检测到活动窗口，请先激活目标应用窗口后重试，或改用手动区域模式")
        try:
            resize_window = bool(settings.get("resizeActiveWindow"))
            requested_width = _as_int(settings.get("viewportWidth"), 0)
            requested_height = _as_int(settings.get("viewportHeight"), 0)
            requested_x = settings.get("viewportX")
            requested_y = settings.get("viewportY")
            if resize_window and requested_width > 0 and requested_height > 0:
                active_window.resizeTo(requested_width, requested_height)
            if requested_x is not None or requested_y is not None:
                active_window.moveTo(_as_int(requested_x, active_window.left), _as_int(requested_y, active_window.top))
        except Exception:
            pass
        try:
            active_window = _current_active_window() or active_window
            left = int(getattr(active_window, "left", 0) or 0)
            top = int(getattr(active_window, "top", 0) or 0)
            width = max(int(getattr(active_window, "width", 0) or 0), 1)
            height = max(int(getattr(active_window, "height", 0) or 0), 1)
        except Exception as exc:
            raise RuntimeError(f"获取活动窗口尺寸失败: {exc}") from exc

    if mode == VIEWPORT_MODE_MANUAL_REGION:
        left = _as_int(settings.get("viewportX"), 0)
        top = _as_int(settings.get("viewportY"), 0)
        width = max(_as_int(settings.get("viewportWidth"), screen_width), 1)
        height = max(_as_int(settings.get("viewportHeight"), screen_height), 1)

    left = max(left, 0)
    top = max(top, 0)
    if left >= screen_width:
        left = max(screen_width - 1, 0)
    if top >= screen_height:
        top = max(screen_height - 1, 0)
    width = max(min(width, screen_width - left), 1)
    height = max(min(height, screen_height - top), 1)
    logical_width = max(_as_int(settings.get("logicalWidth"), _as_int(settings.get("viewportWidth"), width)), 1)
    logical_height = max(_as_int(settings.get("logicalHeight"), _as_int(settings.get("viewportHeight"), height)), 1)
    return DesktopViewport(
        mode=mode,
        left=left,
        top=top,
        width=width,
        height=height,
        logical_width=logical_width,
        logical_height=logical_height,
    )


def _capture_screen(viewport_settings: dict[str, Any] | None = None):
    _ensure_dependencies()
    overlay_state = {}
    if suspend_recording_overlays_for_capture is not None:
        try:
            overlay_state = suspend_recording_overlays_for_capture() or {}
            if overlay_state:
                time.sleep(0.03)
        except Exception:
            overlay_state = {}
    try:
        full_image = ImageGrab.grab(all_screens=True)
    finally:
        if resume_recording_overlays_after_capture is not None and overlay_state:
            try:
                resume_recording_overlays_after_capture(overlay_state)
            except Exception:
                pass
    viewport = _resolve_viewport(viewport_settings, screen_image=full_image)
    cropped = full_image.crop((viewport.left, viewport.top, viewport.left + viewport.width, viewport.top + viewport.height))
    if cropped.size != (viewport.logical_width, viewport.logical_height):
        cropped = cropped.resize((viewport.logical_width, viewport.logical_height))
    return cropped, viewport


async def _capture_screen_async(viewport_settings: dict[str, Any] | None = None):
    return await asyncio.to_thread(_capture_screen, viewport_settings)


def _resolution_key(image) -> str:
    return f"{image.width}x{image.height}"


def _image_resample_filter():
    if Image is None:
        return 1
    resampling = getattr(Image, "Resampling", None)
    if resampling is not None:
        return getattr(resampling, "LANCZOS", 1)
    return getattr(Image, "LANCZOS", 1)


def _resize_image_for_transport(image) -> tuple[Any, dict[str, Any]]:
    width = max(int(getattr(image, "width", 0) or 0), 1)
    height = max(int(getattr(image, "height", 0) or 0), 1)
    pixel_count = width * height
    scale = 1.0
    if max(width, height) > TRANSPORT_MAX_IMAGE_SIDE:
        scale = min(scale, TRANSPORT_MAX_IMAGE_SIDE / max(width, height))
    if pixel_count > TRANSPORT_MAX_IMAGE_PIXELS:
        scale = min(scale, (TRANSPORT_MAX_IMAGE_PIXELS / pixel_count) ** 0.5)
    if scale >= 0.999:
        return image, {}
    resized = image.resize(
        (
            max(1, int(round(width * scale))),
            max(1, int(round(height * scale))),
        ),
        _image_resample_filter(),
    )
    return resized, {
        "transportScaled": True,
        "transportScale": round(scale, 6),
        "originalWidth": width,
        "originalHeight": height,
        "originalResolutionKey": f"{width}x{height}",
        "transportResolutionKey": _resolution_key(resized),
    }


def _replace_file_extension(file_name: str, extension: str) -> str:
    root, _ = os.path.splitext(str(file_name or "image"))
    root = root or "image"
    return f"{root}.{extension}"


def _image_to_base64(image) -> tuple[str, str]:
    buffer = io.BytesIO()
    prefer_webp = image.width * image.height >= TRANSPORT_WEBP_MIN_PIXELS
    if prefer_webp:
        try:
            image.save(buffer, format="WEBP", lossless=True, method=6)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            return f"data:image/webp;base64,{encoded}", "webp"
        except Exception:
            buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True, compress_level=9)
    return base64.b64encode(buffer.getvalue()).decode("ascii"), "png"


def _image_payload(
    image,
    *,
    asset_type: str,
    file_name: str,
    region: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    original_resolution_key = _resolution_key(image)
    payload_metadata = dict(metadata or {})
    transport_image, transport_metadata = _resize_image_for_transport(image)
    payload_metadata.update(transport_metadata)
    image_base64, extension = _image_to_base64(transport_image)
    return {
        "assetType": asset_type,
        "fileName": _replace_file_extension(file_name, extension),
        "resolutionKey": original_resolution_key,
        "width": transport_image.width,
        "height": transport_image.height,
        "region": region,
        "metadata": payload_metadata,
        "imageBase64": image_base64,
    }


def _normalize_region(region: dict[str, Any] | None, image) -> tuple[int, int, int, int]:
    if not region:
        return 0, 0, image.width, image.height
    x = max(int(region.get("x") or 0), 0)
    y = max(int(region.get("y") or 0), 0)
    width = max(int(region.get("width") or image.width), 1)
    height = max(int(region.get("height") or image.height), 1)
    x2 = min(x + width, image.width)
    y2 = min(y + height, image.height)
    return x, y, max(x2 - x, 1), max(y2 - y, 1)


def _logical_region_from_actual_rect(
    viewport: DesktopViewport,
    rect_payload: dict[str, Any],
    *,
    exclude: bool,
    name: str | None = None,
) -> dict[str, Any]:
    left = _as_int(rect_payload.get("left"))
    top = _as_int(rect_payload.get("top"))
    width = max(_as_int(rect_payload.get("width"), 0), 1)
    height = max(_as_int(rect_payload.get("height"), 0), 1)
    start_x, start_y = viewport.actual_to_logical(left, top)
    end_x, end_y = viewport.actual_to_logical(left + width - 1, top + height - 1)
    x1, x2 = sorted((start_x, end_x))
    y1, y2 = sorted((start_y, end_y))
    return {
        "name": name,
        "x": x1,
        "y": y1,
        "width": max(x2 - x1 + 1, 1),
        "height": max(y2 - y1 + 1, 1),
        "exclude": exclude,
    }


def _crop_image_with_region(image, region: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    x, y, width, height = _normalize_region(region, image)
    cropped = image.crop((x, y, x + width, y + height))
    return cropped, {
        "name": region.get("name"),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "exclude": bool(region.get("exclude", False)),
    }


def _build_image_payload_from_region(
    image,
    region: dict[str, Any],
    *,
    asset_type: str,
    file_name: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cropped, normalized_region = _crop_image_with_region(image, region)
    return _image_payload(
        cropped,
        asset_type=asset_type,
        file_name=file_name,
        region=normalized_region,
        metadata=metadata or {},
    )


def _crop_target_image(image, x: int, y: int, size: int) -> tuple[Any, dict[str, Any]]:
    half = max(int(size / 2), 1)
    left = max(x - half, 0)
    top = max(y - half, 0)
    right = min(x + half, image.width)
    bottom = min(y + half, image.height)
    cropped = image.crop((left, top, right, bottom))
    return cropped, {"x": left, "y": top, "width": cropped.width, "height": cropped.height, "exclude": False}


def _pil_to_gray_array(image, *, grayscale: bool = True, blur_kernel: int = 3):
    _ensure_dependencies(need_compare=True)
    rgb = image.convert("RGB")
    array = np.array(rgb)
    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY if grayscale else cv2.COLOR_RGB2BGR)
    if grayscale and blur_kernel and blur_kernel > 1:
        kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
        gray = cv2.GaussianBlur(gray, (kernel, kernel), 0)
    return gray


def _build_mask(shape: tuple[int, int], mask_regions: list[dict[str, Any]], *, offset_x: int = 0, offset_y: int = 0):
    if np is None:
        return None
    mask = np.ones(shape[:2], dtype=np.uint8)
    for region in mask_regions:
        if not isinstance(region, dict) or not bool(region.get("exclude", True)):
            continue
        x = max(int(region.get("x") or 0) - offset_x, 0)
        y = max(int(region.get("y") or 0) - offset_y, 0)
        width = max(int(region.get("width") or 0), 0)
        height = max(int(region.get("height") or 0), 0)
        if width <= 0 or height <= 0:
            continue
        x2 = min(x + width, shape[1])
        y2 = min(y + height, shape[0])
        mask[y:y2, x:x2] = 0
    return mask


def _difference_hash(gray_array, hash_size: int = 8) -> int:
    resized = cv2.resize(gray_array, (hash_size + 1, hash_size))
    diff = resized[:, 1:] > resized[:, :-1]
    bits = "".join("1" if item else "0" for item in diff.flatten())
    return int(bits, 2)


def _hash_distance(hash1: int, hash2: int) -> int:
    return int((hash1 ^ hash2).bit_count())


def _global_ssim(gray1, gray2, *, mask=None) -> float:
    arr1 = gray1.astype(np.float64)
    arr2 = gray2.astype(np.float64)
    if mask is not None:
        valid = mask.astype(bool)
        if not np.any(valid):
            return 1.0
        arr1 = arr1[valid]
        arr2 = arr2[valid]
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    mu1 = arr1.mean()
    mu2 = arr2.mean()
    sigma1 = arr1.var()
    sigma2 = arr2.var()
    sigma12 = ((arr1 - mu1) * (arr2 - mu2)).mean()
    denominator = (mu1**2 + mu2**2 + c1) * (sigma1 + sigma2 + c2)
    if denominator == 0:
        return 1.0
    return float(((2 * mu1 * mu2 + c1) * (2 * sigma12 + c2)) / denominator)


def _build_diff_image(gray_baseline, gray_current, *, mask=None):
    diff = cv2.absdiff(gray_baseline, gray_current)
    if mask is not None:
        diff = cv2.bitwise_and(diff, diff, mask=mask)
    _, thresh = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
    diff_pixels = int(cv2.countNonZero(thresh))
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    annotated = cv2.cvtColor(gray_current, cv2.COLOR_GRAY2RGB)
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width <= 1 and height <= 1:
            continue
        cv2.rectangle(annotated, (x, y), (x + width, y + height), (255, 0, 0), 2)
    image = Image.fromarray(annotated)
    return diff_pixels, image


def _decode_image_payload(payload: dict[str, Any]):
    image_base64 = payload.get("imageBase64") or payload.get("image_base64")
    if not image_base64:
        raise RuntimeError("缺少图片数据，无法执行桌面视觉比对")
    encoded = str(image_base64)
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    image_bytes = base64.b64decode(encoded)
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def _compare_visual(
    current_image,
    baseline_payload: dict[str, Any],
    *,
    mask_regions: list[dict[str, Any]],
    compare_config: dict[str, Any],
) -> tuple[bool, dict[str, Any], Any | None, Any]:
    baseline_image = _decode_image_payload(baseline_payload)
    region = _as_dict(baseline_payload.get("region"))
    metadata = _as_dict(baseline_payload.get("metadata"))
    x, y, width, height = _normalize_region(region, current_image)
    current_crop = current_image.crop((x, y, x + width, y + height))
    original_crop_size = current_crop.size
    if current_crop.size != baseline_image.size:
        should_resize_current = bool(metadata.get("transportScaled")) or (
            baseline_image.width * baseline_image.height <= current_crop.width * current_crop.height
        )
        if should_resize_current:
            current_crop = current_crop.resize(baseline_image.size, _image_resample_filter())
        else:
            baseline_image = baseline_image.resize(current_crop.size, _image_resample_filter())

    gray_baseline = _pil_to_gray_array(
        baseline_image,
        grayscale=bool(compare_config.get("preprocessGrayscale", True)),
        blur_kernel=int(compare_config.get("blurKernel") or 3),
    )
    gray_current = _pil_to_gray_array(
        current_crop,
        grayscale=bool(compare_config.get("preprocessGrayscale", True)),
        blur_kernel=int(compare_config.get("blurKernel") or 3),
    )
    mask = _build_mask((original_crop_size[1], original_crop_size[0]), mask_regions, offset_x=x, offset_y=y)
    if mask is not None and (mask.shape[1], mask.shape[0]) != (gray_current.shape[1], gray_current.shape[0]):
        mask = cv2.resize(mask, (gray_current.shape[1], gray_current.shape[0]), interpolation=cv2.INTER_NEAREST)

    if mask is not None:
        gray_baseline = np.where(mask > 0, gray_baseline, 0)
        gray_current = np.where(mask > 0, gray_current, 0)

    metrics: dict[str, Any] = {
        "resolutionKey": _resolution_key(current_image),
        "region": {"x": x, "y": y, "width": width, "height": height},
        "hashDistance": None,
        "hashPassed": True,
        "ssimScore": None,
        "ssimPassed": True,
        "diffRatio": 0.0,
        "diffPixels": 0,
        "diffPassed": True,
        "ocrEnabled": bool(compare_config.get("useOcr", False)),
        "ocrAvailable": pytesseract is not None,
        "ocrPassed": True,
    }

    passed = True
    if bool(compare_config.get("useHash", True)):
        baseline_hash = _difference_hash(gray_baseline)
        current_hash = _difference_hash(gray_current)
        metrics["hashDistance"] = _hash_distance(baseline_hash, current_hash)
        metrics["hashPassed"] = metrics["hashDistance"] <= int(compare_config.get("hashThreshold") or 6)
        passed = passed and metrics["hashPassed"]

    if bool(compare_config.get("useSsim", True)):
        metrics["ssimScore"] = round(_global_ssim(gray_baseline, gray_current, mask=mask), 6)
        metrics["ssimPassed"] = metrics["ssimScore"] >= float(compare_config.get("ssimThreshold") or 0.995)
        passed = passed and metrics["ssimPassed"]

    diff_pixels, diff_image = _build_diff_image(gray_baseline, gray_current, mask=mask)
    valid_pixels = int(mask.sum()) if mask is not None else int(gray_current.shape[0] * gray_current.shape[1])
    valid_pixels = max(valid_pixels, 1)
    metrics["diffPixels"] = diff_pixels
    metrics["diffRatio"] = round(diff_pixels / valid_pixels, 6)
    if bool(compare_config.get("useLocalDiff", True) or compare_config.get("useFullDiff", True)):
        metrics["diffPassed"] = metrics["diffRatio"] <= float(compare_config.get("pixelDiffThreshold") or 0.01)
        passed = passed and metrics["diffPassed"]

    if bool(compare_config.get("useOcr", False)):
        if pytesseract is None:
            metrics["ocrPassed"] = False
            metrics["ocrMessage"] = "OCR 引擎不可用"
            passed = False
        else:
            baseline_text = pytesseract.image_to_string(baseline_image).strip()
            current_text = pytesseract.image_to_string(current_crop).strip()
            metrics["ocrExpected"] = baseline_text
            metrics["ocrActual"] = current_text
            metrics["ocrPassed"] = baseline_text == current_text
            passed = passed and metrics["ocrPassed"]

    metrics["status"] = "passed" if passed else "failed"
    return passed, metrics, diff_image if not passed else None, current_crop


def _template_match(
    screen_image,
    target_payload: dict[str, Any],
    *,
    threshold: float,
    grayscale: bool = True,
    blur_kernel: int = 3,
) -> tuple[dict[str, Any] | None, Any | None]:
    target_image = _decode_image_payload(target_payload)
    screen_rgb = np.array(screen_image.convert("RGB"))
    target_rgb = np.array(target_image.convert("RGB"))
    if grayscale:
        screen_array = cv2.cvtColor(screen_rgb, cv2.COLOR_RGB2GRAY)
        target_array = cv2.cvtColor(target_rgb, cv2.COLOR_RGB2GRAY)
        if blur_kernel and blur_kernel > 1:
            kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
            screen_array = cv2.GaussianBlur(screen_array, (kernel, kernel), 0)
            target_array = cv2.GaussianBlur(target_array, (kernel, kernel), 0)
    else:
        screen_array = screen_rgb
        target_array = target_rgb

    if target_array.shape[0] > screen_array.shape[0] or target_array.shape[1] > screen_array.shape[1]:
        return None, None

    match_result = cv2.matchTemplate(screen_array, target_array, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(match_result)
    if float(max_val) < threshold:
        return None, None

    match_x, match_y = max_loc
    match_width = int(target_image.width)
    match_height = int(target_image.height)
    matched_crop = screen_image.crop((match_x, match_y, match_x + match_width, match_y + match_height))
    result = {
        "x": int(match_x + match_width / 2),
        "y": int(match_y + match_height / 2),
        "left": int(match_x),
        "top": int(match_y),
        "width": match_width,
        "height": match_height,
        "score": round(float(max_val), 6),
    }
    return result, matched_crop


async def _find_image_on_screen(
    target_payload: dict[str, Any],
    *,
    timeout_ms: int,
    compare_config: dict[str, Any],
    viewport_settings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    _ensure_dependencies(need_compare=True)
    threshold = float(compare_config.get("templateThreshold") or 0.9)
    grayscale = bool(compare_config.get("preprocessGrayscale", True))
    blur_kernel = int(compare_config.get("blurKernel") or 3)
    poll_ms = max(int(compare_config.get("searchIntervalMs") or 250), 80)
    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while True:
        screenshot, viewport = await _capture_screen_async(viewport_settings)
        match, matched_crop = await asyncio.to_thread(
            _template_match,
            screenshot,
            target_payload,
            threshold=threshold,
            grayscale=grayscale,
            blur_kernel=blur_kernel,
        )
        if match:
            matched_payload = None
            if matched_crop is not None:
                matched_payload = _image_payload(
                    matched_crop,
                    asset_type="match",
                    file_name=f"matched-target-{int(time.time() * 1000)}.png",
                    region={
                        "x": match["left"],
                        "y": match["top"],
                        "width": match["width"],
                        "height": match["height"],
                        "exclude": False,
                    },
                    metadata={"score": match["score"], "viewport": viewport.to_payload()},
                )
            return match, matched_payload
        if time.perf_counter() >= deadline:
            raise RuntimeError(f"未在 {timeout_ms}ms 内找到目标图片")
        await asyncio.sleep(poll_ms / 1000.0)


def _normalize_press_key(key_value: str) -> str:
    if not key_value:
        return "enter"
    return KEY_NAME_MAP.get(key_value, key_value).lower()


def _safe_key_to_str(key: Any) -> str:
    try:
        if hasattr(key, "char") and key.char:
            return str(key.char)
        return str(key)
    except Exception:
        return ""


def _modifier_name(key_name: str) -> str | None:
    normalized = KEY_NAME_MAP.get(key_name)
    if normalized in {"ctrl", "alt", "shift", "win"}:
        return normalized
    return None


def _ordered_hotkey_keys(keys: list[str]) -> list[str]:
    normalized_keys: list[str] = []
    seen: set[str] = set()
    for item in keys:
        normalized = _normalize_press_key(str(item))
        if normalized in seen:
            continue
        normalized_keys.append(normalized)
        seen.add(normalized)
    return sorted(normalized_keys, key=lambda item: (MODIFIER_KEY_ORDER.get(item, 99), item))


def _hotkey_intent(keys: list[str]) -> tuple[str | None, str | None]:
    key_tuple = tuple(_ordered_hotkey_keys(keys))
    return HOTKEY_INTENT_LABELS.get(key_tuple, (None, None))


def _build_compare_config(
    step: dict[str, Any],
    *,
    runtime_options: dict[str, Any] | None = None,
    case_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    compare_config = _as_dict(step.get("compareConfig") or step.get("compare_config"))
    runtime_options = _as_dict(runtime_options)
    runtime_overrides = _as_dict(runtime_options.get("runtimeOverrides") or runtime_options.get("runtime_overrides"))
    case_runtime_settings = _as_dict(_as_dict(case_data).get("runtimeSettings"))
    case_compare_config = _as_dict(case_runtime_settings.get("compareConfig") or case_runtime_settings.get("compare_config"))
    runtime_compare_config = _as_dict(runtime_options.get("compareConfig") or runtime_options.get("compare_config"))
    runtime_override_compare_config = _as_dict(
        runtime_overrides.get("compareConfig") or runtime_overrides.get("compare_config")
    )
    defaults = {
        "useHash": True,
        "useSsim": True,
        "useOcr": False,
        "useLocalDiff": True,
        "useFullDiff": True,
        "hashThreshold": 6,
        "ssimThreshold": 0.995,
        "pixelDiffThreshold": 0.01,
        "templateThreshold": 0.9,
        "preprocessGrayscale": True,
        "preprocessBlur": True,
        "blurKernel": 3,
        "searchIntervalMs": 250,
    }
    defaults.update(case_compare_config)
    defaults.update(compare_config)
    defaults.update(runtime_compare_config)
    defaults.update(runtime_override_compare_config)
    return defaults


def _default_recorded_compare_config(options: dict[str, Any]) -> dict[str, Any]:
    compare_config = _as_dict(options.get("compareConfig"))
    return _build_compare_config({"compareConfig": compare_config})


def _normalize_launch_path(app_path: str) -> str:
    normalized = str(app_path or "").strip().strip('"').strip("'")
    if not normalized:
        return ""
    normalized = os.path.expandvars(os.path.expanduser(normalized))
    return os.path.normpath(normalized)


def _launch_process(app_path: str, app_args: list[str]) -> subprocess.Popen | None:
    normalized_path = _normalize_launch_path(app_path)
    if not normalized_path:
        return None
    path_obj = Path(normalized_path)
    executable = normalized_path
    if path_obj.exists():
        executable = str(path_obj)
    else:
        executable = shutil.which(normalized_path) or ""
    if not executable:
        raise RuntimeError(f"应用路径不存在或不可执行: {normalized_path}")
    command = [executable, *[str(item) for item in app_args if item not in (None, "")]]
    popen_kwargs: dict[str, Any] = {}
    if path_obj.exists() and path_obj.parent.exists():
        popen_kwargs["cwd"] = str(path_obj.parent)
    if sys.platform.startswith("win"):
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(command, **popen_kwargs)


def _close_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=3)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _position_from_params(params: dict[str, Any]) -> tuple[int | None, int | None]:
    position = _as_dict(params.get("position"))
    x = position.get("x", params.get("x"))
    y = position.get("y", params.get("y"))
    if x is None or y is None:
        return None, None
    return _as_int(x), _as_int(y)


def _drag_end_position_from_params(
    params: dict[str, Any],
    start_x: int,
    start_y: int,
    *,
    prefer_offset: bool = False,
) -> tuple[int | None, int | None]:
    end_position = _as_dict(params.get("endPosition") or params.get("end_position"))
    offset = _as_dict(params.get("offset"))
    if prefer_offset and offset:
        return start_x + _as_int(offset.get("dx")), start_y + _as_int(offset.get("dy"))
    if end_position.get("x") is not None and end_position.get("y") is not None:
        return _as_int(end_position.get("x")), _as_int(end_position.get("y"))
    if offset:
        return start_x + _as_int(offset.get("dx")), start_y + _as_int(offset.get("dy"))
    return None, None


def _select_baseline_image(step: dict[str, Any], resolution_key: str) -> dict[str, Any] | None:
    baseline_images = _as_list(step.get("baselineImages") or step.get("baseline_images"))
    if not baseline_images:
        return None
    exact_match = next(
        (
            item
            for item in baseline_images
            if isinstance(item, dict)
            and resolution_key
            in {
                str(item.get("resolutionKey") or item.get("resolution_key") or ""),
                str(_as_dict(item.get("metadata")).get("originalResolutionKey") or ""),
            }
        ),
        None,
    )
    if exact_match:
        return exact_match
    for item in baseline_images:
        if isinstance(item, dict):
            return item
    return None


async def _safe_capture_image_payload(
    *,
    asset_type: str,
    file_name: str,
    viewport_settings: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        screenshot, viewport = await _capture_screen_async(viewport_settings)
    except Exception:
        return None
    return _image_payload(
        screenshot,
        asset_type=asset_type,
        file_name=file_name,
        region={"x": 0, "y": 0, "width": screenshot.width, "height": screenshot.height, "exclude": False},
        metadata={
            "capturedAt": int(time.time() * 1000),
            "viewport": viewport.to_payload(),
        },
    )


@dataclass
class DesktopRecorderSession:
    recording_id: int
    sender: EventSender
    loop: asyncio.AbstractEventLoop
    session_name: str
    app_path: str
    app_args: list[str]
    options: dict[str, Any]
    process: subprocess.Popen | None = None
    mouse_listener: Any = None
    keyboard_listener: Any = None
    active: bool = True
    events: list[dict[str, Any]] = field(default_factory=list)
    event_index: int = 0
    typing_buffer: list[str] = field(default_factory=list)
    modifier_keys: set[str] = field(default_factory=set)
    last_key_at: float = 0.0
    pressed_button: str | None = None
    mouse_down_position: tuple[int, int] | None = None
    mouse_down_at: float = 0.0
    last_mouse_position: tuple[int, int] | None = None
    mouse_dragging: bool = False
    pending_click: dict[str, Any] | None = None
    pending_click_token: int = 0
    record_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    annotation_active: bool = False
    last_viewport_payload: dict[str, Any] | None = None
    sender_queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    sender_worker: asyncio.Task | None = None
    pre_action_capture: dict[str, Any] | None = None

    async def start_sender_worker(self) -> None:
        if self.sender_worker is not None and not self.sender_worker.done():
            return
        self.sender_worker = asyncio.create_task(self._sender_loop())

    async def _sender_loop(self) -> None:
        while self.active or not self.sender_queue.empty():
            try:
                message = await asyncio.wait_for(self.sender_queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            try:
                await self.sender(message)
            except Exception as exc:
                logger.warning(f"录制事件发送失败，将重试: {exc}")
                resent = False
                for retry_idx in range(3):
                    await asyncio.sleep(min(0.2 * (retry_idx + 1), 1.0))
                    try:
                        await self.sender(message)
                        resent = True
                        break
                    except Exception as retry_exc:
                        logger.warning(f"录制事件第{retry_idx + 1}次重试失败: {retry_exc}")
                if not resent and self.active:
                    await self.sender_queue.put(message)
                    await asyncio.sleep(0.2)
            finally:
                self.sender_queue.task_done()

    async def wait_sender_queue(self, timeout_sec: float | None = None) -> None:
        try:
            if timeout_sec is None:
                await self.sender_queue.join()
            else:
                await asyncio.wait_for(self.sender_queue.join(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            logger.warning(
                "录制事件队列在超时时间内未完全发送，remaining={}",
                self.sender_queue.qsize(),
            )

    async def _enqueue_message(self, message: dict[str, Any]) -> None:
        if not self.active:
            return
        await self.sender_queue.put(message)

    async def emit(self, payload: dict[str, Any], event_type: str = "desktop_record_event") -> None:
        if not self.active:
            return
        self.event_index += 1
        if event_type == "desktop_record_event":
            self.events.append(payload)
        await self._enqueue_message(
            {
                "type": event_type,
                "recording_id": self.recording_id,
                "event_index": self.event_index,
                "payload": payload,
            }
        )

    async def emit_status(self, payload: dict[str, Any]) -> None:
        await self._enqueue_message(
            {
                "type": "desktop_record_status",
                "recording_id": self.recording_id,
                "payload": payload,
            }
        )

    def _schedule(self, coro: Awaitable[Any]) -> None:
        if not self.active:
            return
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)

            def _log_future_error(fut):
                try:
                    fut.result()
                except Exception as exc:  # pragma: no cover - background callback
                    logger.exception(exc)

            future.add_done_callback(_log_future_error)
        except Exception as exc:  # pragma: no cover - event loop closed
            logger.exception(exc)

    def start_listeners(self) -> None:
        _ensure_dependencies(need_recording=True)
        self.mouse_listener = mouse.Listener(
            on_click=self._on_mouse_click,
            on_move=self._on_mouse_move,
            on_scroll=self._on_mouse_scroll,
        )
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()
        try:
            self._resolve_viewport()
        except Exception:
            pass

    def _drag_threshold(self) -> int:
        return max(_as_int(self.options.get("dragThresholdPx"), 12), 2)

    def _double_click_interval(self) -> float:
        interval_ms = max(_as_int(self.options.get("doubleClickIntervalMs"), 320), 120)
        return interval_ms / 1000.0

    def _annotation_wait_mode(self) -> str:
        return _normalize_annotation_wait_mode(
            self.options.get("annotationWaitMode") or self.options.get("annotation_wait_mode")
        )

    def _resolve_viewport(self) -> DesktopViewport:
        viewport = _resolve_viewport(self.options)
        viewport_payload = viewport.to_payload()
        if show_recording_viewport is not None:
            try:
                if self.last_viewport_payload != viewport_payload:
                    show_recording_viewport(viewport_payload)
                    self.last_viewport_payload = dict(viewport_payload)
            except Exception:
                pass
        return viewport

    def _hide_viewport_outline(self) -> None:
        self.last_viewport_payload = None
        if hide_recording_viewport is not None:
            try:
                hide_recording_viewport()
            except Exception:
                pass

    async def _request_annotation(
        self,
        *,
        viewport: DesktopViewport,
        step_name: str,
        stage: str,
    ) -> dict[str, Any]:
        if request_recording_annotation is None:
            return {}
        self.annotation_active = True
        self.modifier_keys.clear()
        prompt_prefix = "截图前" if stage == ANNOTATION_WAIT_BEFORE_CAPTURE else "截图后"
        prompt = (
            f"{prompt_prefix}已暂停录制：{step_name or '当前步骤'}。"
            "可标记当前步骤的验证区域、忽略区域，或增加独立视觉断言，完成后点击“继续录制”。"
        )
        try:
            future = request_recording_annotation(viewport.to_payload(), prompt=prompt)
            result = await asyncio.wrap_future(future)
            return _as_dict(result)
        finally:
            self.annotation_active = False
            self._resolve_viewport()

    def _build_assert_step_from_region(
        self,
        *,
        screenshot,
        viewport: DesktopViewport,
        region: dict[str, Any],
        compare_config: dict[str, Any],
        inherited_masks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        file_suffix = int(time.time() * 1000)
        baseline_payload = _build_image_payload_from_region(
            screenshot,
            region,
            asset_type="baseline",
            file_name=f"baseline-assert-{self.recording_id}-{self.event_index + 1}-{file_suffix}.png",
            metadata={
                "recordingId": self.recording_id,
                "actionType": "assert_visual",
                "viewport": viewport.to_payload(),
            },
        )
        x = _as_int(region.get("x"))
        y = _as_int(region.get("y"))
        width = _as_int(region.get("width"))
        height = _as_int(region.get("height"))
        return {
            "stepName": f"视觉断言区域 ({x}, {y}, {width}x{height})",
            "stepLevel": str(self.options.get("defaultStepLevel") or "MID"),
            "actionType": "assert_visual",
            "enabled": True,
            "timeoutMs": None,
            "continueOnFailure": False,
            "recordOrigin": "recording",
            "params": {"region": {"x": x, "y": y, "width": width, "height": height}},
            "targetImage": None,
            "baselineImages": [baseline_payload],
            "maskRegions": [dict(item) for item in inherited_masks],
            "compareConfig": dict(compare_config or _default_recorded_compare_config(self.options)),
            "rawEvent": {
                "eventType": "annotation_assert",
                "region": {"x": x, "y": y, "width": width, "height": height},
                "viewport": viewport.to_payload(),
            },
        }

    def _apply_annotation_result(
        self,
        *,
        step: dict[str, Any],
        screenshot,
        viewport: DesktopViewport,
        annotation_result: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        annotation_result = _as_dict(annotation_result)
        if not annotation_result or annotation_result.get("skipped"):
            return []

        step.setdefault("rawEvent", {})
        step.setdefault("maskRegions", [])
        step.setdefault("baselineImages", [])
        extra_steps: list[dict[str, Any]] = []

        focus_region_payload = _as_dict(annotation_result.get("focusRegion"))
        focus_region = None
        if focus_region_payload:
            focus_region = _logical_region_from_actual_rect(
                viewport,
                focus_region_payload,
                exclude=False,
                name="验证区域",
            )
            step["baselineImages"] = [
                _build_image_payload_from_region(
                    screenshot,
                    focus_region,
                    asset_type="baseline",
                    file_name=f"baseline-focus-{self.recording_id}-{self.event_index + 1}.png",
                    metadata={
                        "recordingId": self.recording_id,
                        "actionType": step.get("actionType"),
                        "viewport": viewport.to_payload(),
                    },
                )
            ]

        mask_regions = []
        for item in _as_list(annotation_result.get("maskRegions")):
            if not isinstance(item, dict):
                continue
            mask_regions.append(
                _logical_region_from_actual_rect(
                    viewport,
                    item,
                    exclude=True,
                    name=item.get("name") or "忽略区域",
                )
            )
        if mask_regions:
            step["maskRegions"] = [*_as_list(step.get("maskRegions")), *mask_regions]

        compare_config = _as_dict(step.get("compareConfig"))
        for item in _as_list(annotation_result.get("assertRegions")):
            if not isinstance(item, dict):
                continue
            assert_region = _logical_region_from_actual_rect(
                viewport,
                item,
                exclude=False,
                name="断言区域",
            )
            extra_steps.append(
                self._build_assert_step_from_region(
                    screenshot=screenshot,
                    viewport=viewport,
                    region=assert_region,
                    compare_config=compare_config,
                    inherited_masks=[*_as_list(step.get("maskRegions"))],
                )
            )

        step["rawEvent"]["annotation"] = {
            "focusRegion": focus_region,
            "maskRegions": mask_regions,
            "assertRegions": [item.get("params", {}).get("region") for item in extra_steps],
        }
        return extra_steps

    def _actual_to_logical_point(self, x: int, y: int) -> tuple[int | None, int | None, DesktopViewport]:
        viewport = self._resolve_viewport()
        if not viewport.contains_actual_point(x, y):
            return None, None, viewport
        logical_x, logical_y = viewport.actual_to_logical(x, y)
        return logical_x, logical_y, viewport

    async def _capture_pre_action_snapshot(self, x: int, y: int) -> None:
        if not self.active:
            return
        try:
            screenshot, viewport = await _capture_screen_async(self.options)
        except Exception as exc:
            logger.debug(f"预采集点击截图失败: {exc}")
            return
        self.pre_action_capture = {
            "captured_at": time.perf_counter(),
            "x": int(x),
            "y": int(y),
            "screenshot": screenshot,
            "viewport": viewport,
        }

    def _consume_pre_action_snapshot(self, capture_x: int | None, capture_y: int | None):
        if capture_x is None or capture_y is None:
            return None
        snapshot = self.pre_action_capture
        self.pre_action_capture = None
        if not isinstance(snapshot, dict):
            return None
        captured_at = float(snapshot.get("captured_at") or 0.0)
        if captured_at <= 0 or time.perf_counter() - captured_at > 1.5:
            return None
        snapshot_x = _as_int(snapshot.get("x"))
        snapshot_y = _as_int(snapshot.get("y"))
        tolerance = max(self._drag_threshold() * 2, 24)
        if abs(snapshot_x - int(capture_x)) > tolerance or abs(snapshot_y - int(capture_y)) > tolerance:
            return None
        screenshot = snapshot.get("screenshot")
        viewport = snapshot.get("viewport")
        if screenshot is None or viewport is None:
            return None
        return screenshot, viewport

    async def _build_recorded_step(
        self,
        *,
        action_type: str,
        step_name: str,
        params: dict[str, Any],
        raw_event: dict[str, Any],
        capture_x: int | None = None,
        capture_y: int | None = None,
        return_context: bool = False,
    ) -> dict[str, Any] | tuple[dict[str, Any], Any, DesktopViewport]:
        capture_before_action = bool(self.options.get("captureBeforeAction", True))
        pre_capture = self._consume_pre_action_snapshot(capture_x, capture_y) if capture_before_action else None
        if pre_capture is not None:
            screenshot, viewport = pre_capture
        else:
            capture_delay_ms = max(_as_int(self.options.get("captureDelayMs"), 400), 0)
            if capture_delay_ms > 0 and not capture_before_action:
                await asyncio.sleep(capture_delay_ms / 1000.0)
            screenshot, viewport = await _capture_screen_async(self.options)
        viewport_payload = viewport.to_payload()
        target_image = None
        if (
            capture_x is not None
            and capture_y is not None
            and bool(self.options.get("captureTargetImage", True))
        ):
            crop_size = max(_as_int(self.options.get("targetImageSize"), 96), 32)
            cropped, region = _crop_target_image(screenshot, capture_x, capture_y, crop_size)
            target_image = _image_payload(
                cropped,
                asset_type="target",
                file_name=f"target-{self.recording_id}-{self.event_index + 1}.png",
                region=region,
                metadata={
                    "recordingId": self.recording_id,
                    "actionType": action_type,
                    "viewport": viewport_payload,
                },
            )
        baseline_images: list[dict[str, Any]] = []
        if bool(self.options.get("captureBaselineAfterAction", True)):
            baseline_images.append(
                _image_payload(
                    screenshot,
                    asset_type="baseline",
                    file_name=f"baseline-{self.recording_id}-{self.event_index + 1}-{_resolution_key(screenshot)}.png",
                    region={
                        "x": 0,
                        "y": 0,
                        "width": screenshot.width,
                        "height": screenshot.height,
                        "exclude": False,
                    },
                    metadata={
                        "recordingId": self.recording_id,
                        "actionType": action_type,
                        "viewport": viewport_payload,
                    },
                )
            )
        step_payload = {
            "stepName": step_name,
            "stepLevel": str(self.options.get("defaultStepLevel") or "MID"),
            "actionType": action_type,
            "enabled": True,
            "timeoutMs": None,
            "continueOnFailure": False,
            "recordOrigin": "recording",
            "params": params,
            "targetImage": target_image,
            "baselineImages": baseline_images,
            "maskRegions": [],
            "compareConfig": _default_recorded_compare_config(self.options),
            "rawEvent": {**raw_event, "viewport": viewport_payload},
            "viewport": viewport_payload,
        }
        if return_context:
            return step_payload, screenshot, viewport
        return step_payload

    async def _record_step(
        self,
        *,
        action_type: str,
        step_name: str,
        params: dict[str, Any],
        raw_event: dict[str, Any],
        capture_x: int | None = None,
        capture_y: int | None = None,
    ) -> None:
        annotation_before = {}
        if self._annotation_wait_mode() == ANNOTATION_WAIT_BEFORE_CAPTURE:
            annotation_before = await self._request_annotation(
                viewport=self._resolve_viewport(),
                step_name=step_name,
                stage=ANNOTATION_WAIT_BEFORE_CAPTURE,
            )
        step, screenshot, viewport = await self._build_recorded_step(
            action_type=action_type,
            step_name=step_name,
            params=params,
            raw_event=raw_event,
            capture_x=capture_x,
            capture_y=capture_y,
            return_context=True,
        )
        annotation_after = {}
        if self._annotation_wait_mode() == ANNOTATION_WAIT_AFTER_CAPTURE:
            annotation_after = await self._request_annotation(
                viewport=viewport,
                step_name=step_name,
                stage=ANNOTATION_WAIT_AFTER_CAPTURE,
            )
        extra_steps = self._apply_annotation_result(
            step=step,
            screenshot=screenshot,
            viewport=viewport,
            annotation_result=annotation_after or annotation_before,
        )
        await self.emit(step)
        for extra_step in extra_steps:
            await self.emit(extra_step)

    async def _flush_typing_buffer_locked(self) -> None:
        if not self.typing_buffer:
            return
        text = "".join(self.typing_buffer)
        self.typing_buffer.clear()
        await self._record_step(
            action_type="typewrite",
            step_name=f"输入文本 {text[:16]}",
            params={"text": text, "interval": 0.02},
            raw_event={"eventType": "keyboard_text", "text": text},
        )

    async def flush_typing_buffer(self) -> None:
        async with self.record_lock:
            await self._flush_typing_buffer_locked()

    async def _emit_click_step_locked(
        self,
        x: int,
        y: int,
        button_name: str,
        *,
        action_type: str | None = None,
        click_count: int = 1,
    ) -> None:
        effective_action_type = action_type or ("right_click" if button_name == "right" else "click")
        action_label = {
            "click": "点击",
            "double_click": "双击",
            "right_click": "右键点击",
        }.get(effective_action_type, "点击")
        if effective_action_type == "click" and button_name == "middle":
            action_label = "中键点击"
        await self._record_step(
            action_type=effective_action_type,
            step_name=f"{action_label} ({x}, {y})",
            params={"button": button_name, "position": {"x": x, "y": y}, "clicks": click_count},
            raw_event={
                "eventType": "mouse_click",
                "x": x,
                "y": y,
                "button": button_name,
                "clicks": click_count,
                "actionType": effective_action_type,
            },
            capture_x=x,
            capture_y=y,
        )

    async def _flush_pending_click_locked(self) -> None:
        if not self.pending_click:
            return
        pending_click = dict(self.pending_click)
        self.pending_click = None
        await self._emit_click_step_locked(
            _as_int(pending_click.get("x")),
            _as_int(pending_click.get("y")),
            str(pending_click.get("button") or "left"),
        )

    async def _emit_pending_click_if_still_valid(self, token: int) -> None:
        await asyncio.sleep(self._double_click_interval())
        async with self.record_lock:
            if not self.pending_click or _as_int(self.pending_click.get("token")) != token:
                return
            await self._flush_pending_click_locked()

    async def flush_pending_events(self) -> None:
        async with self.record_lock:
            await self._flush_typing_buffer_locked()
            await self._flush_pending_click_locked()

    async def handle_mouse_click(self, x: int, y: int, button_name: str) -> None:
        if not self.active:
            return
        async with self.record_lock:
            await self._flush_typing_buffer_locked()
            await self._flush_pending_click_locked()
            await self._emit_click_step_locked(x, y, button_name)

    async def handle_click_candidate(self, x: int, y: int, button_name: str) -> None:
        if not self.active:
            return
        async with self.record_lock:
            await self._flush_typing_buffer_locked()
            if button_name != "left":
                await self._flush_pending_click_locked()
                await self._emit_click_step_locked(x, y, button_name)
                return

            now = time.perf_counter()
            pending_click = self.pending_click
            if pending_click:
                within_interval = now - float(pending_click.get("at") or 0.0) <= self._double_click_interval()
                within_distance = (
                    abs(_as_int(pending_click.get("x")) - x) <= self._drag_threshold()
                    and abs(_as_int(pending_click.get("y")) - y) <= self._drag_threshold()
                )
                if within_interval and within_distance and str(pending_click.get("button") or "left") == button_name:
                    self.pending_click = None
                    await self._emit_click_step_locked(
                        x,
                        y,
                        button_name,
                        action_type="double_click",
                        click_count=2,
                    )
                    return
                await self._flush_pending_click_locked()

            self.pending_click_token += 1
            token = self.pending_click_token
            self.pending_click = {"token": token, "x": x, "y": y, "button": button_name, "at": now}
            asyncio.create_task(self._emit_pending_click_if_still_valid(token))

    async def handle_mouse_drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button_name: str,
        duration_ms: int,
    ) -> None:
        if not self.active:
            return
        async with self.record_lock:
            await self._flush_typing_buffer_locked()
            await self._flush_pending_click_locked()
            await self._record_step(
                action_type="drag",
                step_name=f"拖拽 ({start_x}, {start_y}) -> ({end_x}, {end_y})",
                params={
                    "button": button_name,
                    "position": {"x": start_x, "y": start_y},
                    "endPosition": {"x": end_x, "y": end_y},
                    "offset": {"dx": end_x - start_x, "dy": end_y - start_y},
                    "duration": round(max(duration_ms, 0) / 1000.0, 3),
                    "durationMs": max(duration_ms, 0),
                },
                raw_event={
                    "eventType": "mouse_drag",
                    "button": button_name,
                    "start": {"x": start_x, "y": start_y},
                    "end": {"x": end_x, "y": end_y},
                    "durationMs": max(duration_ms, 0),
                },
                capture_x=start_x,
                capture_y=start_y,
            )

    async def handle_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self.active:
            return
        async with self.record_lock:
            await self._flush_typing_buffer_locked()
            await self._flush_pending_click_locked()
            direction_label = "上滚" if dy > 0 else "下滚"
            if dy == 0 and dx != 0:
                direction_label = "横向滚动"
            await self._record_step(
                action_type="scroll",
                step_name=f"{direction_label} ({x}, {y})",
                params={
                    "position": {"x": x, "y": y},
                    "scrollAmount": dy,
                    "horizontalScroll": dx,
                },
                raw_event={"eventType": "mouse_scroll", "x": x, "y": y, "dx": dx, "dy": dy},
                capture_x=x,
                capture_y=y,
            )

    async def handle_special_key(self, key_name: str) -> None:
        if not self.active:
            return
        async with self.record_lock:
            await self._flush_typing_buffer_locked()
            await self._flush_pending_click_locked()
            modifiers = _ordered_hotkey_keys(list(self.modifier_keys))
            if modifiers:
                hotkey_keys = _ordered_hotkey_keys(modifiers + [_normalize_press_key(key_name)])
                semantic, semantic_label = _hotkey_intent(hotkey_keys)
                params = {"keys": hotkey_keys}
                raw_event = {"eventType": "hotkey", "keys": hotkey_keys}
                if semantic:
                    params["semantic"] = semantic
                    raw_event["intent"] = semantic
                if semantic_label:
                    raw_event["intentLabel"] = semantic_label
                await self._record_step(
                    action_type="hotkey",
                    step_name=semantic_label or f"快捷键 {' + '.join(hotkey_keys)}",
                    params=params,
                    raw_event=raw_event,
                )
            else:
                normalized_key = _normalize_press_key(key_name)
                await self._record_step(
                    action_type="press",
                    step_name=f"按键 {normalized_key}",
                    params={"key": normalized_key},
                    raw_event={"eventType": "press", "key": normalized_key},
                )

    def _on_mouse_click(self, x, y, button, pressed) -> None:
        if not self.active or self.annotation_active:
            return
        button_name = str(button).split(".")[-1]
        x_int = int(x)
        y_int = int(y)
        if pressed:
            logical_x, logical_y, _ = self._actual_to_logical_point(x_int, y_int)
            if logical_x is None or logical_y is None:
                self.pressed_button = None
                self.mouse_down_position = None
                self.last_mouse_position = None
                self.mouse_dragging = False
                return
            self.pressed_button = button_name
            self.mouse_down_position = (x_int, y_int)
            self.last_mouse_position = (x_int, y_int)
            self.mouse_down_at = time.perf_counter()
            self.mouse_dragging = False
            self._schedule(self._capture_pre_action_snapshot(logical_x, logical_y))
            return

        start_position = self.mouse_down_position or (x_int, y_int)
        end_position = self.last_mouse_position or (x_int, y_int)
        duration_ms = int(max(time.perf_counter() - self.mouse_down_at, 0.0) * 1000)
        button_name = self.pressed_button or button_name
        self.pressed_button = None
        self.mouse_down_position = None
        self.last_mouse_position = None
        self.mouse_down_at = 0.0
        dragging = self.mouse_dragging or (
            max(abs(end_position[0] - start_position[0]), abs(end_position[1] - start_position[1])) >= self._drag_threshold()
        )
        self.mouse_dragging = False
        start_x, start_y, viewport = self._actual_to_logical_point(start_position[0], start_position[1])
        end_x, end_y, _ = self._actual_to_logical_point(end_position[0], end_position[1])
        if start_x is None or start_y is None or end_x is None or end_y is None:
            return
        if dragging:
            self._schedule(
                self.handle_mouse_drag(
                    start_x,
                    start_y,
                    end_x,
                    end_y,
                    button_name,
                    duration_ms,
                )
            )
            return
        self._schedule(self.handle_click_candidate(end_x, end_y, button_name))

    def _on_mouse_move(self, x, y) -> None:
        if not self.active or self.annotation_active or self.mouse_down_position is None:
            return
        current_position = (int(x), int(y))
        self.last_mouse_position = current_position
        start_x, start_y = self.mouse_down_position
        if max(abs(current_position[0] - start_x), abs(current_position[1] - start_y)) >= self._drag_threshold():
            self.mouse_dragging = True

    def _on_mouse_scroll(self, x, y, dx, dy) -> None:
        if not self.active or self.annotation_active:
            return
        logical_x, logical_y, _ = self._actual_to_logical_point(int(x), int(y))
        if logical_x is None or logical_y is None:
            return
        self._schedule(self.handle_scroll(logical_x, logical_y, int(dx), int(dy)))

    def _on_key_press(self, key) -> None:
        if not self.active or self.annotation_active:
            return
        key_name = _safe_key_to_str(key)
        modifier = _modifier_name(key_name)
        if modifier:
            self.modifier_keys.add(modifier)
            return

        now = time.perf_counter()
        non_text_modifiers = {item for item in self.modifier_keys if item != "shift"}
        if key_name == "Key.backspace" and bool(self.options.get("includeKeyboardText", True)) and not non_text_modifiers:
            if self.typing_buffer:
                self.typing_buffer.pop()
                self.last_key_at = now
                return

        if hasattr(key, "char") and key.char and bool(self.options.get("includeKeyboardText", True)) and not non_text_modifiers:
            if self.typing_buffer and now - self.last_key_at > 0.8:
                self._schedule(self.flush_typing_buffer())
            self.typing_buffer.append(str(key.char))
            self.last_key_at = now
            return

        self._schedule(self.handle_special_key(key_name))

    def _on_key_release(self, key) -> None:
        if self.annotation_active:
            return
        key_name = _safe_key_to_str(key)
        modifier = _modifier_name(key_name)
        if modifier:
            self.modifier_keys.discard(modifier)

    async def close(self, *, close_process: bool) -> None:
        self.active = False
        self.annotation_active = False
        self.pending_click = None
        self.pre_action_capture = None
        self.modifier_keys.clear()
        mouse_listener = self.mouse_listener
        keyboard_listener = self.keyboard_listener
        sender_worker = self.sender_worker
        self.sender_worker = None
        self.mouse_listener = None
        self.keyboard_listener = None
        if mouse_listener is not None:
            try:
                mouse_listener.stop()
            except Exception:
                pass
        if keyboard_listener is not None:
            try:
                keyboard_listener.stop()
            except Exception:
                pass
        process = self.process
        if close_process:
            self.process = None
            await asyncio.to_thread(_close_process, process)
        await self.wait_sender_queue(timeout_sec=2.0)
        if sender_worker is not None:
            if not sender_worker.done():
                try:
                    await asyncio.wait_for(sender_worker, timeout=2.0)
                except asyncio.TimeoutError:
                    sender_worker.cancel()
                except Exception:
                    sender_worker.cancel()
            try:
                await sender_worker
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug(f"录制事件发送协程关闭时异常: {exc}")
        if cancel_recording_annotation is not None:
            try:
                cancel_recording_annotation()
            except Exception:
                pass
        self._hide_viewport_outline()


class DesktopTestService:
    _recorders: dict[int, DesktopRecorderSession] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def handle_request(cls, req_data: dict[str, Any], event_sender: EventSender | None = None) -> dict[str, Any]:
        command = req_data.get("command") or "run_case"
        if command == "run_case":
            return await cls._run_case(req_data)
        if command == "start_recording":
            return await cls._start_recording(req_data, event_sender)
        if command == "stop_recording":
            return await cls._stop_recording(req_data)
        return {
            "request_type": REQUEST_TYPE_DESKTOP,
            "command": command,
            "success": False,
            "status": "failed",
            "message": f"unsupported desktopui command: {command}",
        }

    @classmethod
    async def _start_recording(cls, req_data: dict[str, Any], event_sender: EventSender | None) -> dict[str, Any]:
        if event_sender is None:
            return {
                "request_type": REQUEST_TYPE_DESKTOP,
                "command": "start_recording",
                "success": False,
                "status": "failed",
                "message": "缺少事件发送器，无法实时推送录制结果",
            }
        recording_id = _as_int(req_data.get("recordingId"))
        if not recording_id:
            return {
                "request_type": REQUEST_TYPE_DESKTOP,
                "command": "start_recording",
                "success": False,
                "status": "failed",
                "message": "recordingId 不能为空",
            }

        async with cls._lock:
            if recording_id in cls._recorders:
                return {
                    "request_type": REQUEST_TYPE_DESKTOP,
                    "command": "start_recording",
                    "success": True,
                    "status": "accepted",
                    "recording_id": recording_id,
                    "message": "录制已在进行中",
                }
            session = DesktopRecorderSession(
                recording_id=recording_id,
                sender=event_sender,
                loop=asyncio.get_running_loop(),
                session_name=str(req_data.get("sessionName") or f"桌面录制-{recording_id}"),
                app_path=str(req_data.get("appPath") or ""),
                app_args=[str(item) for item in _as_list(req_data.get("appArgs"))],
                options=_as_dict(req_data.get("recordingOptions")),
            )
            cls._recorders[recording_id] = session

        try:
            _ensure_dependencies(need_recording=True)
            await session.start_sender_worker()
            if session.app_path:
                session.process = await asyncio.to_thread(_launch_process, session.app_path, session.app_args)
                startup_delay_ms = max(_as_int(session.options.get("appStartupDelayMs"), 1200), 0)
                if startup_delay_ms > 0:
                    await asyncio.sleep(startup_delay_ms / 1000.0)
            _resolve_viewport(session.options)
            session.start_listeners()
            await session.emit_status(
                {
                    "message": "录制已启动",
                    "sessionName": session.session_name,
                    "appLaunched": bool(session.process),
                    "appPath": session.app_path,
                }
            )
            return {
                "request_type": REQUEST_TYPE_DESKTOP,
                "command": "start_recording",
                "success": True,
                "status": "accepted",
                "recording_id": recording_id,
            }
        except Exception as exc:
            logger.exception(exc)
            async with cls._lock:
                cls._recorders.pop(recording_id, None)
            try:
                await event_sender(
                    {
                        "type": "desktop_record_error",
                        "recording_id": recording_id,
                        "message": str(exc),
                        "payload": {"message": str(exc)},
                    }
                )
            except Exception:
                pass
            try:
                await session.close(close_process=True)
            except Exception:
                pass
            return {
                "request_type": REQUEST_TYPE_DESKTOP,
                "command": "start_recording",
                "success": False,
                "status": "failed",
                "message": str(exc),
            }

    @classmethod
    async def _stop_recording(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        recording_id = _as_int(req_data.get("recordingId"))
        async with cls._lock:
            session = cls._recorders.pop(recording_id, None)
        if session is None:
            return {
                "request_type": REQUEST_TYPE_DESKTOP,
                "command": "stop_recording",
                "success": False,
                "status": "failed",
                "message": "录制会话不存在",
            }
        close_app_on_stop = req_data.get("closeAppOnStop")
        if close_app_on_stop is None:
            close_app_on_stop = session.options.get("closeAppOnStop")
        close_app_on_stop = bool(close_app_on_stop)

        try:
            await session.flush_pending_events()
            session.active = False
            await session.wait_sender_queue(timeout_sec=8.0)
            await session.sender(
                {
                    "type": "desktop_record_finished",
                    "recording_id": recording_id,
                    "payload": {
                        "eventCount": len(session.events),
                        "appRetained": not close_app_on_stop and session.process is not None,
                    },
                }
            )
        finally:
            await session.close(close_process=close_app_on_stop)

        return {
            "request_type": REQUEST_TYPE_DESKTOP,
            "command": "stop_recording",
            "success": True,
            "status": "stopped",
            "recording_id": recording_id,
            "data": {
                "eventCount": len(session.events),
                "appRetained": not close_app_on_stop and session.process is not None,
            },
        }

    @classmethod
    async def shutdown_all_sessions(cls) -> None:
        async with cls._lock:
            sessions = list(cls._recorders.values())
            cls._recorders.clear()
        for session in sessions:
            try:
                await session.close(close_process=True)
            except Exception as exc:
                logger.exception(exc)

    @classmethod
    def _step_timeout_ms(cls, step: dict[str, Any], runtime_options: dict[str, Any], case_data: dict[str, Any]) -> int:
        params = _as_dict(step.get("params"))
        candidates = [
            step.get("timeoutMs"),
            step.get("timeout_ms"),
            params.get("timeoutMs"),
            params.get("timeout_ms"),
            runtime_options.get("stepTimeoutMs"),
            runtime_options.get("timeoutMs"),
            _as_dict(case_data.get("runtimeSettings")).get("stepTimeoutMs"),
            _as_dict(case_data.get("runtimeSettings")).get("timeoutMs"),
            10000,
        ]
        for candidate in candidates:
            if candidate not in (None, ""):
                return max(_as_int(candidate, 10000), 500)
        return 10000

    @classmethod
    def _step_think_time_ms(cls, step: dict[str, Any], runtime_options: dict[str, Any], case_data: dict[str, Any]) -> int:
        params = _as_dict(step.get("params"))
        runtime_settings = _as_dict(case_data.get("runtimeSettings"))
        candidates = [
            step.get("thinkTimeMs"),
            step.get("think_time_ms"),
            params.get("thinkTimeMs"),
            params.get("think_time_ms"),
            runtime_options.get("stepThinkTimeMs"),
            runtime_options.get("step_think_time_ms"),
            runtime_options.get("thinkTimeMs"),
            runtime_options.get("think_time_ms"),
            runtime_settings.get("stepThinkTimeMs"),
            runtime_settings.get("step_think_time_ms"),
            runtime_settings.get("thinkTimeMs"),
            runtime_settings.get("think_time_ms"),
            0,
        ]
        for candidate in candidates:
            if candidate not in (None, ""):
                return max(_as_int(candidate, 0), 0)
        return 0

    @classmethod
    def _has_following_enabled_step(cls, steps: list[Any], current_index: int) -> bool:
        for idx in range(current_index + 1, len(steps)):
            step = _as_dict(steps[idx])
            if bool(step.get("enabled", True)):
                return True
        return False

    @classmethod
    def _continue_on_failure(cls, step: dict[str, Any], runtime_options: dict[str, Any]) -> bool:
        if step.get("continueOnFailure") is not None:
            return bool(step.get("continueOnFailure"))
        if step.get("continue_on_failure") is not None:
            return bool(step.get("continue_on_failure"))
        return bool(runtime_options.get("continueOnFailure", False))

    @classmethod
    async def _locate_target_if_needed(
        cls,
        step: dict[str, Any],
        compare_config: dict[str, Any],
        timeout_ms: int,
        viewport_settings: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        params = _as_dict(step.get("params"))
        target_image = _as_dict(step.get("targetImage") or step.get("target_image"))
        action_type = str(step.get("actionType") or step.get("action_type") or "")
        if not target_image:
            x, y = _position_from_params(params)
            if x is None or y is None:
                return None, None
            return {"x": x, "y": y}, None
        if action_type not in {"click", "double_click", "right_click", "move", "drag", "scroll", "find_image", "wait_image"}:
            return None, None
        match, matched_payload = await _find_image_on_screen(
            target_image,
            timeout_ms=timeout_ms,
            compare_config=compare_config,
            viewport_settings=viewport_settings,
        )
        return match, matched_payload

    @classmethod
    async def _execute_action(
        cls,
        action_type: str,
        params: dict[str, Any],
        *,
        location: dict[str, Any] | None,
        timeout_ms: int,
        runtime_options: dict[str, Any] | None,
        launched_processes: list[subprocess.Popen],
        case_app_path: str | None = None,
        case_app_args: list[str] | None = None,
    ) -> dict[str, Any]:
        viewport = _resolve_viewport(runtime_options)
        if action_type in {"wait", "sleep"}:
            duration_ms = max(
                _as_int(params.get("durationMs"), 0)
                or _as_int(params.get("waitMs"), 0)
                or _as_int(params.get("seconds"), 0) * 1000,
                0,
            )
            if duration_ms <= 0:
                duration_ms = timeout_ms
            await asyncio.sleep(duration_ms / 1000.0)
            return {"waitMs": duration_ms}

        if action_type in {"find_image", "wait_image"}:
            if location is None:
                raise RuntimeError("未找到目标图片")
            actual_x, actual_y = viewport.logical_to_actual(_as_int(location.get("x")), _as_int(location.get("y")))
            return {"location": location, "actualPosition": {"x": actual_x, "y": actual_y}}

        if action_type == "launch_app":
            app_path = str(params.get("appPath") or params.get("path") or case_app_path or "")
            app_args = [str(item) for item in _as_list(params.get("appArgs") or case_app_args or [])]
            process = await asyncio.to_thread(_launch_process, app_path, app_args)
            if process is not None:
                launched_processes.append(process)
            launch_wait_ms = max(_as_int(params.get("waitMs"), 1200), 0)
            if launch_wait_ms > 0:
                await asyncio.sleep(launch_wait_ms / 1000.0)
            return {"appPath": app_path, "launched": process is not None}

        if action_type == "close_app":
            if not launched_processes:
                return {"closed": False}
            process = launched_processes.pop()
            await asyncio.to_thread(_close_process, process)
            return {"closed": True}

        if action_type == "typewrite":
            text = str(params.get("text") or params.get("value") or "")
            interval = max(_as_float(params.get("interval"), 0.02), 0.0)
            await asyncio.to_thread(pyautogui.write, text, interval=interval)
            return {"text": text}

        if action_type == "press":
            key_name = _normalize_press_key(str(params.get("key") or "enter"))
            await asyncio.to_thread(pyautogui.press, key_name)
            return {"key": key_name}

        if action_type == "hotkey":
            keys = params.get("keys") or params.get("hotkeys") or []
            if not isinstance(keys, list):
                keys = [str(keys)]
            keys = [_normalize_press_key(str(item)) for item in keys if item not in (None, "")]
            if not keys:
                raise RuntimeError("hotkey 缺少 keys 参数")
            await asyncio.to_thread(pyautogui.hotkey, *keys)
            return {"keys": keys}

        if action_type in {"move", "click", "double_click", "right_click"}:
            x = None
            y = None
            if location:
                x = _as_int(location.get("x"))
                y = _as_int(location.get("y"))
            else:
                x, y = _position_from_params(params)
            if x is None or y is None:
                raise RuntimeError(f"{action_type} 缺少点击坐标或目标图片")
            actual_x, actual_y = viewport.logical_to_actual(x, y)
            duration = max(_as_float(params.get("duration"), 0.0), 0.0)
            button_name = str(params.get("button") or "left")
            if action_type == "move":
                await asyncio.to_thread(pyautogui.moveTo, actual_x, actual_y, duration=duration)
                return {"position": {"x": x, "y": y}, "actualPosition": {"x": actual_x, "y": actual_y}}
            if action_type == "right_click":
                await asyncio.to_thread(pyautogui.rightClick, x=actual_x, y=actual_y)
                return {"position": {"x": x, "y": y}, "actualPosition": {"x": actual_x, "y": actual_y}, "button": "right"}
            if action_type == "double_click":
                await asyncio.to_thread(pyautogui.doubleClick, x=actual_x, y=actual_y, button=button_name)
            else:
                clicks = max(_as_int(params.get("clicks"), 1), 1)
                await asyncio.to_thread(pyautogui.click, x=actual_x, y=actual_y, clicks=clicks, button=button_name)
            return {"position": {"x": x, "y": y}, "actualPosition": {"x": actual_x, "y": actual_y}, "button": button_name}

        if action_type == "drag":
            if location:
                start_x = _as_int(location.get("x"))
                start_y = _as_int(location.get("y"))
            else:
                start_x, start_y = _position_from_params(params)
            if start_x is None or start_y is None:
                raise RuntimeError("drag 缺少起始坐标或目标图片")
            end_x, end_y = _drag_end_position_from_params(params, start_x, start_y, prefer_offset=location is not None)
            if end_x is None or end_y is None:
                raise RuntimeError("drag 缺少结束坐标")
            actual_start_x, actual_start_y = viewport.logical_to_actual(start_x, start_y)
            actual_end_x, actual_end_y = viewport.logical_to_actual(end_x, end_y)
            button_name = str(params.get("button") or "left")
            duration = max(_as_float(params.get("duration"), 0.2), 0.0)
            move_duration = max(_as_float(params.get("moveDuration"), 0.0), 0.0)
            await asyncio.to_thread(pyautogui.moveTo, actual_start_x, actual_start_y, duration=move_duration)
            await asyncio.to_thread(pyautogui.dragTo, actual_end_x, actual_end_y, duration=duration, button=button_name)
            return {
                "position": {"x": start_x, "y": start_y},
                "endPosition": {"x": end_x, "y": end_y},
                "actualPosition": {"x": actual_start_x, "y": actual_start_y},
                "actualEndPosition": {"x": actual_end_x, "y": actual_end_y},
                "offset": {"dx": end_x - start_x, "dy": end_y - start_y},
                "button": button_name,
            }

        if action_type == "scroll":
            if location:
                x = _as_int(location.get("x"))
                y = _as_int(location.get("y"))
            else:
                x, y = _position_from_params(params)
            if x is not None and y is not None:
                actual_x, actual_y = viewport.logical_to_actual(x, y)
                await asyncio.to_thread(pyautogui.moveTo, actual_x, actual_y)
            else:
                actual_x = None
                actual_y = None
            scroll_amount = _as_int(params.get("scrollAmount"), _as_int(params.get("scrolls"), _as_int(params.get("dy"), 0)))
            horizontal_scroll = _as_int(
                params.get("horizontalScroll"),
                _as_int(params.get("hscroll"), _as_int(params.get("dx"), 0)),
            )
            if scroll_amount:
                await asyncio.to_thread(pyautogui.scroll, scroll_amount)
            if horizontal_scroll and hasattr(pyautogui, "hscroll"):
                await asyncio.to_thread(pyautogui.hscroll, horizontal_scroll)
            return {
                "position": {"x": x, "y": y},
                "actualPosition": {"x": actual_x, "y": actual_y} if actual_x is not None and actual_y is not None else None,
                "scrollAmount": scroll_amount,
                "horizontalScroll": horizontal_scroll,
            }

        if action_type == "assert_visual":
            return {}

        raise RuntimeError(f"不支持的桌面动作: {action_type}")

    @classmethod
    async def _run_case(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        _ensure_dependencies(need_compare=True)
        case_data = _as_dict(req_data.get("caseData"))
        runtime_options = _as_dict(req_data.get("runtimeOptions"))
        runtime_overrides = _as_dict(runtime_options.get("runtimeOverrides") or runtime_options.get("runtime_overrides"))
        runtime_settings = _as_dict(case_data.get("runtimeSettings"))
        effective_runtime = {**runtime_settings, **runtime_overrides, **runtime_options}
        app_path = str(effective_runtime.get("appPath") or case_data.get("appPath") or "")
        app_args = [str(item) for item in _as_list(effective_runtime.get("appArgs") or case_data.get("appArgs"))]
        steps = _as_list(case_data.get("steps"))
        close_app_on_finish = effective_runtime.get("closeAppOnFinish")
        if close_app_on_finish is None:
            close_app_on_finish = True
        else:
            close_app_on_finish = bool(close_app_on_finish)
        startup_delay_ms = max(_as_int(effective_runtime.get("appStartupDelayMs"), 1200), 0)

        result_steps: list[dict[str, Any]] = []
        launched_processes: list[subprocess.Popen] = []
        overall_success = True
        last_error: str | None = None

        try:
            if app_path:
                process = await asyncio.to_thread(_launch_process, app_path, app_args)
                if process is not None:
                    launched_processes.append(process)
                if startup_delay_ms > 0:
                    await asyncio.sleep(startup_delay_ms / 1000.0)
            _resolve_viewport(effective_runtime)

            for step_index, raw_step in enumerate(steps):
                step = _as_dict(raw_step)
                if not bool(step.get("enabled", True)):
                    result_steps.append(
                        {
                            "stepId": step.get("stepId") or step.get("step_id"),
                            "stepName": step.get("stepName") or step.get("step_name") or "step",
                            "actionType": step.get("actionType") or step.get("action_type"),
                            "status": "skipped",
                            "durationMs": 0,
                            "message": "步骤已禁用",
                        }
                    )
                    continue

                step_result = await cls._run_single_step(step, effective_runtime, case_data, launched_processes)
                result_steps.append(step_result)
                if step_result["status"] != "passed":
                    overall_success = False
                    last_error = step_result.get("error") or step_result.get("message") or "步骤执行失败"
                    if not cls._continue_on_failure(step, effective_runtime):
                        break
                think_time_ms = cls._step_think_time_ms(step, effective_runtime, case_data)
                if think_time_ms > 0 and cls._has_following_enabled_step(steps, step_index):
                    await asyncio.sleep(think_time_ms / 1000.0)
                    step_result["thinkTimeMs"] = think_time_ms
        except Exception as exc:
            logger.exception(exc)
            overall_success = False
            last_error = str(exc)

        final_screenshot = await _safe_capture_image_payload(
            asset_type="final",
            file_name=f"desktop-final-{int(time.time() * 1000)}.png",
            viewport_settings=effective_runtime,
        )

        if close_app_on_finish:
            for process in launched_processes:
                await asyncio.to_thread(_close_process, process)

        result: dict[str, Any] = {
            "steps": result_steps,
            "finalScreenshot": final_screenshot,
            "appRetained": bool(launched_processes) and not close_app_on_finish,
        }
        if final_screenshot:
            result["resolutionKey"] = final_screenshot.get("resolutionKey")

        return {
            "request_type": REQUEST_TYPE_DESKTOP,
            "command": "run_case",
            "success": overall_success,
            "status": "success" if overall_success else "failed",
            "message": None if overall_success else (last_error or "执行失败"),
            "result": result,
        }

    @classmethod
    async def _run_single_step(
        cls,
        step: dict[str, Any],
        runtime_options: dict[str, Any],
        case_data: dict[str, Any],
        launched_processes: list[subprocess.Popen],
    ) -> dict[str, Any]:
        action_type = str(step.get("actionType") or step.get("action_type") or "")
        step_id = step.get("stepId") or step.get("step_id")
        step_name = step.get("stepName") or step.get("step_name") or action_type or "step"
        params = _as_dict(step.get("params"))
        compare_config = _build_compare_config(step, runtime_options=runtime_options, case_data=case_data)
        mask_regions = _as_list(step.get("maskRegions") or step.get("mask_regions"))
        timeout_ms = cls._step_timeout_ms(step, runtime_options, case_data)
        started_at = time.perf_counter()
        step_result: dict[str, Any] = {
            "stepId": step_id,
            "stepName": step_name,
            "actionType": action_type,
            "status": "passed",
            "durationMs": 0,
        }

        try:
            location = None
            matched_target_payload = None
            if action_type in {"click", "double_click", "right_click", "move", "drag", "scroll", "find_image", "wait_image"}:
                location, matched_target_payload = await asyncio.wait_for(
                    cls._locate_target_if_needed(
                        step,
                        compare_config,
                        timeout_ms,
                        viewport_settings=runtime_options,
                    ),
                    timeout=timeout_ms / 1000.0,
                )
                if matched_target_payload is not None:
                    step_result["matchedTargetImage"] = matched_target_payload
                if location is not None:
                    step_result["location"] = location

            action_result = await asyncio.wait_for(
                cls._execute_action(
                    action_type,
                    params,
                    location=location,
                    timeout_ms=timeout_ms,
                    runtime_options=runtime_options,
                    launched_processes=launched_processes,
                    case_app_path=str(case_data.get("appPath") or ""),
                    case_app_args=[str(item) for item in _as_list(case_data.get("appArgs"))],
                ),
                timeout=timeout_ms / 1000.0,
            )
            if action_result:
                step_result["actionResult"] = action_result

            need_visual_assert = action_type == "assert_visual" or bool(
                _as_list(step.get("baselineImages") or step.get("baseline_images"))
            )
            if need_visual_assert:
                current_screen, current_viewport = await _capture_screen_async(runtime_options)
                baseline_payload = _select_baseline_image(step, _resolution_key(current_screen))
                if baseline_payload is None:
                    raise RuntimeError("当前步骤缺少基准图片")
                passed, metrics, diff_image, current_crop = await asyncio.to_thread(
                    _compare_visual,
                    current_screen,
                    baseline_payload,
                    mask_regions=mask_regions,
                    compare_config=compare_config,
                )
                step_result["metrics"] = metrics
                step_result["resolutionKey"] = metrics.get("resolutionKey")
                if not passed:
                    step_result["currentImage"] = _image_payload(
                        current_crop,
                        asset_type="current",
                        file_name=f"current-{step_id or int(time.time() * 1000)}.png",
                        region=metrics.get("region"),
                        metadata={
                            "stepId": step_id,
                            "stepName": step_name,
                            "viewport": current_viewport.to_payload(),
                        },
                    )
                    if diff_image is not None:
                        step_result["diffImage"] = _image_payload(
                            diff_image,
                            asset_type="diff",
                            file_name=f"diff-{step_id or int(time.time() * 1000)}.png",
                            region=metrics.get("region"),
                            metadata={
                                "stepId": step_id,
                                "stepName": step_name,
                                "viewport": current_viewport.to_payload(),
                            },
                        )
                    raise RuntimeError(
                        f"视觉断言失败: hash={metrics.get('hashDistance')}, "
                        f"ssim={metrics.get('ssimScore')}, diffRatio={metrics.get('diffRatio')}"
                    )
        except Exception as exc:
            logger.exception(exc)
            step_result["status"] = "failed"
            step_result["error"] = str(exc)
            if "currentImage" not in step_result:
                error_image = await _safe_capture_image_payload(
                    asset_type="current",
                    file_name=f"desktop-step-error-{step_id or int(time.time() * 1000)}.png",
                    viewport_settings=runtime_options,
                )
                if error_image is not None:
                    step_result["currentImage"] = error_image
                    step_result["resolutionKey"] = error_image.get("resolutionKey")
        finally:
            step_result["durationMs"] = int((time.perf_counter() - started_at) * 1000)
        return step_result
