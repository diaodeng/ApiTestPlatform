from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

if not sys.platform.startswith("win"):
    from PySide6.QtNetwork import QLocalServer, QLocalSocket


def _build_scope_digest(scope_path: str | Path | None) -> str:
    scope = Path(scope_path or Path.cwd()).resolve()
    return hashlib.sha1(str(scope).lower().encode("utf-8")).hexdigest()[:12]


def _build_mutex_name(app_id: str, scope_path: str | Path | None) -> str:
    safe_app_id = re.sub(r"[^0-9A-Za-z_.-]+", "_", app_id).strip("._-") or "qtrclient"
    return f"Local\\{safe_app_id}_{_build_scope_digest(scope_path)}"


def _allow_set_foreground_window() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)
    except Exception:
        pass


def _activate_window_by_title(window_title: str) -> bool:
    if not sys.platform.startswith("win"):
        return False

    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = int(user32.FindWindowW(None, window_title))
        if not hwnd:
            return False
        _allow_set_foreground_window()
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        else:
            user32.ShowWindow(hwnd, 5)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception as exc:
        logger.debug(f"激活已有窗口失败: {exc}")
        return False


def bring_window_to_front(window: QWidget | None) -> None:
    if window is None:
        return

    if window.isMinimized():
        window.showNormal()
    else:
        window.show()
    window.raise_()
    window.activateWindow()

    if not sys.platform.startswith("win"):
        return

    title = window.windowTitle().strip()
    if title:
        _activate_window_by_title(title)


class SingleInstanceManager(QObject):
    activation_requested = Signal()

    def __init__(
        self,
        app_id: str,
        *,
        scope_path: str | Path | None = None,
        window_title: str = "QTRClient",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._window_title = window_title
        self._ready_for_activation = False
        self._pending_activation = False
        self._mutex_name = _build_mutex_name(app_id, scope_path)
        self._mutex_handle = None

        if not sys.platform.startswith("win"):
            self._server_name = f"{app_id}.{_build_scope_digest(scope_path)}"
            self._server = QLocalServer(self)
            self._server.newConnection.connect(self._on_new_connection)

    def start(self) -> bool:
        if sys.platform.startswith("win"):
            return self._start_windows_mutex()
        return self._start_local_server()

    def mark_ready(self) -> None:
        self._ready_for_activation = True
        if self._pending_activation:
            self._pending_activation = False
            self.activation_requested.emit()

    def shutdown(self) -> None:
        if sys.platform.startswith("win"):
            self._shutdown_windows_mutex()
            return

        if self._server.isListening():
            self._server.close()
        QLocalServer.removeServer(self._server_name)

    def _start_windows_mutex(self) -> bool:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, self._mutex_name)
        if not handle:
            raise ctypes.WinError()

        self._mutex_handle = handle
        if kernel32.GetLastError() == 183:
            logger.info("检测到已有实例，尝试激活现有窗口")
            activated = _activate_window_by_title(self._window_title)
            if not activated:
                logger.warning("已检测到重复启动，但未找到可激活的主窗口")
            self._shutdown_windows_mutex()
            return False

        logger.info(f"单实例互斥量已创建: {self._mutex_name}")
        return True

    def _shutdown_windows_mutex(self) -> None:
        if not self._mutex_handle:
            return

        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.CloseHandle(self._mutex_handle)
        except Exception:
            pass
        finally:
            self._mutex_handle = None

    def _start_local_server(self) -> bool:
        if self._notify_existing_instance():
            return False

        QLocalServer.removeServer(self._server_name)
        if self._server.listen(self._server_name):
            logger.info(f"单实例服务已启动: {self._server_name}")
            return True

        first_error = self._server.errorString()
        QLocalServer.removeServer(self._server_name)
        if self._server.listen(self._server_name):
            logger.info(f"单实例服务已重建: {self._server_name}")
            return True

        raise RuntimeError(
            f"启动单实例服务失败: {self._server_name}, {first_error}; {self._server.errorString()}"
        )

    def _notify_existing_instance(self) -> bool:
        socket = QLocalSocket(self)
        socket.connectToServer(self._server_name)
        if not socket.waitForConnected(300):
            socket.abort()
            return False

        _allow_set_foreground_window()
        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        logger.info("检测到已有实例，已发送窗口激活请求")
        return True

    def _request_activation(self) -> None:
        if self._ready_for_activation:
            self.activation_requested.emit()
            return
        self._pending_activation = True

    def _on_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            if connection is None:
                continue
            connection.readyRead.connect(
                lambda socket=connection: self._consume_connection(socket)
            )
            connection.disconnected.connect(connection.deleteLater)
            self._consume_connection(connection)

    def _consume_connection(self, socket: QLocalSocket) -> None:
        if socket is None:
            return
        if socket.property("_qtrclient_consumed"):
            return

        socket.setProperty("_qtrclient_consumed", True)
        try:
            socket.readAll()
        except Exception:
            pass
        self._request_activation()
        socket.disconnectFromServer()
