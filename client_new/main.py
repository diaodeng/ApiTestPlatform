import faulthandler
import os
import sys
import threading
from multiprocessing import freeze_support
from datetime import datetime
from pathlib import Path

_FAULT_LOG_FILE = None


def _install_global_exception_handlers():
    from utils.logger import logger

    def _log_uncaught_exception(prefix, exc_type, exc_value, exc_traceback):
        if exc_type is None:
            return
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        if exc_value is None:
            exc_value = exc_type(prefix)
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(prefix)

    def _sys_excepthook(exc_type, exc_value, exc_traceback):
        _log_uncaught_exception("主线程未捕获异常", exc_type, exc_value, exc_traceback)

    def _thread_excepthook(args):
        thread_name = getattr(getattr(args, "thread", None), "name", "") or "unknown"
        _log_uncaught_exception(
            f"线程未捕获异常[{thread_name}]",
            getattr(args, "exc_type", None),
            getattr(args, "exc_value", None),
            getattr(args, "exc_traceback", None),
        )

    def _unraisablehook(unraisable):
        exc_value = getattr(unraisable, "exc_value", None)
        exc_traceback = getattr(unraisable, "exc_traceback", None)
        exc_type = type(exc_value) if exc_value is not None else RuntimeError
        message = getattr(unraisable, "err_msg", None) or "存在未处理的不可抛出异常"
        obj = getattr(unraisable, "object", None)
        if obj is not None:
            message = f"{message}: {obj!r}"
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).error(message)

    sys.excepthook = _sys_excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_excepthook
    if hasattr(sys, "unraisablehook"):
        sys.unraisablehook = _unraisablehook

    global _FAULT_LOG_FILE
    try:
        os.makedirs("logs", exist_ok=True)
        _FAULT_LOG_FILE = open(
            os.path.join("logs", "fatal_error.log"),
            "a",
            encoding="utf-8",
            buffering=1,
        )
        _FAULT_LOG_FILE.write(
            f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] faulthandler enabled\n"
        )
        faulthandler.enable(file=_FAULT_LOG_FILE, all_threads=True)
    except Exception as e:
        logger.warning(f"启用 faulthandler 失败: {e}")


def _install_qt_message_filter():
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    from utils.logger import logger

    if os.environ.get("QTRCLIENT_SHOW_QT_DPI_WARNINGS") == "1":
        return

    ignored_fragments = (
        "SetProcessDpiAwarenessContext() failed",
        "Qt's default DPI awareness context is DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2",
    )

    def _message_handler(msg_type, context, message):
        text = str(message or "").strip()
        if msg_type == QtMsgType.QtWarningMsg and any(fragment in text for fragment in ignored_fragments):
            return
        if not text:
            return

        level_map = {}
        label_map = {}
        for qt_type, level, label in (
            (getattr(QtMsgType, "QtDebugMsg", None), "DEBUG", "debug"),
            (getattr(QtMsgType, "QtInfoMsg", None), "INFO", "info"),
            (getattr(QtMsgType, "QtWarningMsg", None), "WARNING", "warning"),
            (getattr(QtMsgType, "QtCriticalMsg", None), "ERROR", "critical"),
            (getattr(QtMsgType, "QtFatalMsg", None), "CRITICAL", "fatal"),
        ):
            if qt_type is None:
                continue
            level_map[qt_type] = level
            label_map[qt_type] = label

        level = level_map.get(msg_type, "WARNING")
        if text.startswith("External WM_DESTROY received for"):
            level = "DEBUG"

        context_parts = []
        category = getattr(context, "category", "")
        if category:
            context_parts.append(f"category={category}")

        file_name = getattr(context, "file", "")
        line_no = getattr(context, "line", 0)
        if file_name:
            context_parts.append(
                f"file={os.path.basename(str(file_name))}:{int(line_no or 0)}"
            )
        elif line_no:
            context_parts.append(f"line={int(line_no)}")

        function_name = getattr(context, "function", "")
        if function_name:
            context_parts.append(f"func={function_name}")

        suffix = f" ({', '.join(context_parts)})" if context_parts else ""
        logger.log(level, f"Qt[{label_map.get(msg_type, 'message')}] {text}{suffix}")

    qInstallMessageHandler(_message_handler)

if __name__ == "__main__":
    if "--mitm-helper" in sys.argv:
        from services.mitmproxy_service.helper_process import main as mitm_helper_main

        mitm_helper_main()
        sys.exit(0)

    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow
    from ui.theme_manager import ThemeManager
    from ui.utils.desktop_record_overlay import install_desktop_record_overlay
    from ui.utils.icon_util import apply_window_icon, install_app_icon
    from ui.utils.single_instance import SingleInstanceManager, bring_window_to_front
    from utils.logger import logger

    logger.info("应用开始启动")
    freeze_support()
    _install_global_exception_handlers()
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "api-test-platform.client.qtrclient"
            )
        except Exception:
            pass
    _install_qt_message_filter()
    app = QApplication(sys.argv)
    app.setApplicationName("QTRClient")
    app.setApplicationDisplayName("QTRClient")
    instance_scope = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    single_instance = SingleInstanceManager(
        "api-test-platform.client.qtrclient",
        scope_path=instance_scope,
        parent=app,
    )

    if not single_instance.start():
        sys.exit(0)

    app.aboutToQuit.connect(single_instance.shutdown)
    install_app_icon(app)
    install_desktop_record_overlay(app)
    ThemeManager.initialize(app).apply_saved_theme()

    window = MainWindow()
    single_instance.activation_requested.connect(
        lambda: bring_window_to_front(window)
    )
    window.show()
    apply_window_icon(window)
    bring_window_to_front(window)
    single_instance.mark_ready()
    sys.exit(app.exec())
