import sys
from pathlib import Path

from loguru import logger

# 单实例互斥体名与主窗口标题：重复启动时用于识别并激活已有实例。
_MUTEX_NAME = "QTRClientNew_PyWebview_SingleInstance"
_WINDOW_TITLE = "QTRClient"


class SingleInstanceManager:
    """
    单实例管理（pywebview 版）。

    原 Qt 版本在 Windows 上使用命名互斥量 + FindWindow 激活旧窗口，
    非 Windows 使用 QLocalServer。pywebview 版保留同等语义：
    - Windows：命名互斥量判定重复启动；发现旧实例时用 FindWindow 把
      已有窗口带到前台。
    - 其他平台：临时目录锁文件判定；不做窗口激活。
    """

    def __init__(self):
        self._handle = None
        self._lock_path: Path | None = None

    def acquire(self) -> bool:
        """
        尝试获取单实例标识。

        :return: True 表示当前是唯一实例；False 表示已有实例在运行。
        """
        if sys.platform.startswith("win"):
            return self._acquire_windows()
        return self._acquire_lock_file()

    # ===== Windows 实现 =====

    def _acquire_windows(self) -> bool:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            logger.warning("检测到已有 QTRClient 实例，尝试激活旧窗口")
            self._activate_existing_window()
            return False

        self._handle = handle
        return True

    def _activate_existing_window(self) -> None:
        import ctypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        hwnd = user32.FindWindowW(None, _WINDOW_TITLE)
        if not hwnd:
            logger.info("未找到已有主窗口句柄，跳过激活")
            return
        try:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
        except Exception as e:
            logger.warning(f"激活已有窗口失败: {e}")

    # ===== 非 Windows 实现 =====

    def _acquire_lock_file(self) -> bool:
        import os
        import tempfile

        lock_file = Path(tempfile.gettempdir()) / f"{_MUTEX_NAME}.lock"
        try:
            if lock_file.exists():
                logger.warning("检测到已有 QTRClient 实例（锁文件存在）")
                return False
            lock_file.write_text(str(os.getpid()), encoding="utf-8")
            self._lock_path = lock_file
            return True
        except Exception as e:
            logger.warning(f"锁文件判定失败，按可启动处理: {e}")
            return True

    def release(self) -> None:
        if self._lock_path is not None:
            try:
                self._lock_path.unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"清理单实例锁文件失败: {e}")
            self._lock_path = None
        self._handle = None
