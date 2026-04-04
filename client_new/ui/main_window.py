from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from managers.pos_manager import PosManager
from ui.pages.about_page import AboutPage
from ui.pages.agent_page import AgentPage
from ui.pages.log_view_page import LogViewPage
from ui.pages.mitmproxy_page import MitmWidget
from ui.pages.pos_page import PosPage
from ui.theme_manager import (
    THEME_MODE_AUTO,
    THEME_MODE_DARK,
    THEME_MODE_LIGHT,
    ThemeManager,
    theme_mode_label,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.theme_manager = ThemeManager.instance()
        self.setWindowTitle("QTRClient - PySide6")
        self.resize(1200, 800)

        self._init_ui()
        self._init_status_bar()

    def _init_ui(self):
        central = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        self.header_bar = QFrame()
        self.header_bar.setObjectName("mainHeaderBar")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(10)

        self.app_title_label = QLabel("QTRClient")
        self.app_title_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        self.theme_button = QToolButton()
        self.theme_button.setObjectName("themeToggleButton")
        self.theme_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.theme_button.setPopupMode(QToolButton.InstantPopup)
        self.theme_menu = QMenu(self.theme_button)
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        self.theme_actions = {}
        for mode in (THEME_MODE_AUTO, THEME_MODE_LIGHT, THEME_MODE_DARK):
            action = QAction(theme_mode_label(mode), self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, selected_mode=mode: checked
                and self.theme_manager.apply_theme(selected_mode)
            )
            self.theme_action_group.addAction(action)
            self.theme_menu.addAction(action)
            self.theme_actions[mode] = action
        self.theme_button.setMenu(self.theme_menu)

        header_layout.addWidget(self.app_title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.theme_button)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

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

        content_layout.addWidget(self.menu)
        content_layout.addWidget(self.stack)

        root_layout.addWidget(self.header_bar)
        root_layout.addLayout(content_layout, 1)

        central.setLayout(root_layout)
        self.setCentralWidget(central)

        self.theme_manager.theme_changed.connect(self._update_theme_button)
        self._update_theme_button(
            self.theme_manager.current_mode(), self.theme_manager.is_dark()
        )

    def _init_status_bar(self):
        self.statusBar().showMessage("就绪 | 当前运行POS: -")
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._refresh_global_status)
        self._status_timer.start()

    def _update_theme_button(self, mode: str, is_dark: bool):
        for theme_mode, action in self.theme_actions.items():
            action.setChecked(theme_mode == mode)

        resolved = "深色" if is_dark else "浅色"
        self.theme_button.setText(f"主题: {theme_mode_label(mode)}")
        if mode == THEME_MODE_AUTO:
            self.theme_button.setToolTip(f"当前跟随系统主题，已应用 {resolved} 模式")
            return
        self.theme_button.setToolTip(f"当前固定为 {resolved} 模式")

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
