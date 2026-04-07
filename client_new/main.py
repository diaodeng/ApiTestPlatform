import os
import sys
from multiprocessing import freeze_support

from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from services.mitmproxy_service.helper_process import main as mitm_helper_main
from ui.main_window import MainWindow
from ui.theme_manager import ThemeManager
from ui.utils.desktop_record_overlay import install_desktop_record_overlay
from ui.utils.icon_util import apply_window_icon, install_app_icon
from utils.logger import logger


def _install_qt_message_filter():
    if os.environ.get("QTRCLIENT_SHOW_QT_DPI_WARNINGS") == "1":
        return

    ignored_fragments = (
        "SetProcessDpiAwarenessContext() failed",
        "Qt's default DPI awareness context is DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2",
    )

    def _message_handler(msg_type, context, message):
        text = str(message or "")
        if msg_type == QtMsgType.QtWarningMsg and any(fragment in text for fragment in ignored_fragments):
            return
        print(text, file=sys.stderr)

    qInstallMessageHandler(_message_handler)

if __name__ == "__main__":
    if "--mitm-helper" in sys.argv:
        mitm_helper_main()
        sys.exit(0)

    logger.info("应用开始启动")
    freeze_support()
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
    install_app_icon(app)
    install_desktop_record_overlay(app)
    ThemeManager.initialize(app).apply_saved_theme()

    window = MainWindow()
    window.show()
    apply_window_icon(window)
    sys.exit(app.exec())
