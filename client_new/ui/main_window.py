from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from managers.pos_manager import PosManager
from ui.pages.about_page import AboutPage
from ui.pages.agent_page import AgentPage
from ui.pages.log_view_page import LogViewPage
from ui.pages.mitmproxy_page import MitmWidget
from ui.pages.pos_page import PosPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QTRClient - PySide6")
        self.resize(1200, 800)

        self._init_ui()
        self._init_status_bar()

    def _init_ui(self):
        central = QWidget()
        layout = QHBoxLayout()

        # 左侧菜单
        self.menu = QListWidget()
        self.menu.addItems(
            ["设置", "商品", "Agent", "POS", "mitmproxy", "FTP", "日志", "关于"]
        )
        self.menu.setFixedWidth(150)

        # 右侧内容区
        self.stack = QStackedWidget()

        # 页面注册
        self.pages = {
            "设置": QWidget(),
            "商品": QWidget(),
            "Agent": AgentPage(),
            "POS": PosPage(),
            "mitmproxy": MitmWidget(),
            "FTP": QWidget(),
            "日志": LogViewPage(),
            "关于": AboutPage(),
        }

        for name in [
            "设置",
            "商品",
            "Agent",
            "POS",
            "mitmproxy",
            "FTP",
            "日志",
            "关于",
        ]:
            self.stack.addWidget(self.pages[name])

        # 绑定菜单
        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.menu.setCurrentRow(3)

        layout.addWidget(self.menu)
        layout.addWidget(self.stack)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _init_status_bar(self):
        self.statusBar().showMessage("就绪 | 当前运行POS: -")
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._refresh_global_status)
        self._status_timer.start()

    def _refresh_global_status(self):
        current = PosManager.instance().get()
        if current:
            path = current.get("path") or "-"
            pid = current.get("pid") or "-"
            self.statusBar().showMessage(f"运行中 | 当前POS: {path} | PID: {pid}")
        else:
            self.statusBar().showMessage("就绪 | 当前运行POS: -")

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "退出确认",
            "确认关闭应用吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            event.ignore()
            return

        if hasattr(self, "_status_timer") and self._status_timer:
            self._status_timer.stop()

        # 应用退出前，先关闭 mitmproxy helper，避免残留进程影响下次启动
        for page in self.pages.values():
            if hasattr(page, "controller"):
                try:
                    page.controller.shutdown()
                except Exception:
                    pass
            if hasattr(page, "shutdown"):
                try:
                    page.shutdown()
                except Exception:
                    pass

        super().closeEvent(event)
