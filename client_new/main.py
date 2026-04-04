import sys
from multiprocessing import freeze_support

from PySide6.QtWidgets import QApplication

from services.mitmproxy_service.helper_process import main as mitm_helper_main
from ui.main_window import MainWindow
from ui.theme_manager import ThemeManager
from utils.logger import logger

if __name__ == "__main__":
    if "--mitm-helper" in sys.argv:
        mitm_helper_main()
        sys.exit(0)

    logger.info("应用开始启动")
    freeze_support()
    app = QApplication(sys.argv)
    ThemeManager.initialize(app).apply_saved_theme()

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
