import sys
from multiprocessing import freeze_support

from PySide6.QtWidgets import QApplication

from services.mitmproxy_service.helper_process import main as mitm_helper_main
from ui.main_window import MainWindow
from ui.theme_manager import ThemeManager
from ui.utils.icon_util import load_app_icon
from utils.logger import logger

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
    app = QApplication(sys.argv)
    app.setApplicationName("QTRClient")
    app.setApplicationDisplayName("QTRClient")
    app.setWindowIcon(load_app_icon())
    ThemeManager.initialize(app).apply_saved_theme()

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
