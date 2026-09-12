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
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from loguru import logger

from ui.theme_manager import (
    THEME_MODE_AUTO,
    THEME_MODE_DARK,
    THEME_MODE_LIGHT,
    ThemeManager,
    theme_mode_label,
)
from ui.utils.icon_util import apply_window_icon


def _create_agent_page():
    from ui.pages.agent_page import AgentPage

    return AgentPage()


def _create_pos_page():
    from ui.pages.pos_page import PosPage

    return PosPage()


def _create_sqlite_page():
    from ui.pages.sqlite_query_page import SqliteQueryPage

    return SqliteQueryPage()


def _create_mitm_page(parent=None):
    from ui.pages.mitmproxy_page import MitmWidget

    return MitmWidget(parent)


def _create_log_page():
    from ui.pages.log_view_page import LogViewPage

    return LogViewPage()


def _create_about_page():
    from ui.pages.about_page import AboutPage

    return AboutPage()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._closing_for_update = False
        self._page_loading_enabled = False
        self._initial_page_load_scheduled = False
        self._default_page_name = "POS"
        self.theme_manager = ThemeManager.instance()
        self.setWindowTitle("QTRClient")
        self.resize(1200, 800)
        apply_window_icon(self)

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
                lambda checked, selected_mode=mode: (
                    checked and self.theme_manager.apply_theme(selected_mode)
                )
            )
            self.theme_action_group.addAction(action)
            self.theme_menu.addAction(action)
            self.theme_actions[mode] = action
        self.theme_button.setMenu(self.theme_menu)

        # 插件管理入口：重依赖（桌面测试/Web 测试）按需安装，异常不影响主窗口
        self.plugin_button = QToolButton()
        self.plugin_button.setObjectName("pluginManagerButton")
        self.plugin_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.plugin_button.setText("插件")
        self.plugin_button.clicked.connect(self._open_plugin_manager)

        header_layout.addWidget(self.app_title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.plugin_button)
        header_layout.addWidget(self.theme_button)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # 左侧菜单
        # 菜单按插件显隐：mitmproxy 页依赖 proxy 插件（未安装时隐藏菜单项）；
        # Agent 页是平台连接核心（httpx/websocket），常驻并在页内对插件缺失做降级提示
        self.nav_items = self._resolve_nav_items(
            ["Agent", "POS", "SQLite", "mitmproxy", "日志", "关于"]
        )
        self.menu = QListWidget()
        self.menu.addItems(self.nav_items)
        self.menu.setFixedWidth(150)
        self.menu.setFrameShape(QFrame.NoFrame)
        self.menu.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # 右侧内容区
        self.stack = QStackedWidget()
        self.stack.setObjectName("mainContentStack")
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.page_factories = {
            "Agent": _create_agent_page,
            "POS": _create_pos_page,
            "SQLite": _create_sqlite_page,
            "mitmproxy": _create_mitm_page,
            "日志": _create_log_page,
            "关于": _create_about_page,
        }
        self.pages: dict[str, QWidget | None] = {
            name: None for name in self.nav_items
        }
        self._page_placeholders: dict[str, QWidget] = {}

        for name in self.nav_items:
            placeholder = self._build_page_placeholder(name)
            self._page_placeholders[name] = placeholder
            self.stack.addWidget(placeholder)

        # 绑定菜单
        self.menu.currentRowChanged.connect(self._on_nav_row_changed)
        self.menu.setCurrentRow(self.nav_items.index(self._default_page_name))

        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("mainNavFrame")
        nav_layout = QVBoxLayout(self.nav_frame)
        nav_layout.setContentsMargins(6, 6, 6, 6)
        nav_layout.setSpacing(0)
        nav_layout.addWidget(self.menu, 1)

        self.content_frame = QFrame()
        self.content_frame.setObjectName("mainContentFrame")
        stack_layout = QVBoxLayout(self.content_frame)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(0)
        stack_layout.addWidget(self.stack, 1)

        content_layout.addWidget(self.nav_frame)
        content_layout.addWidget(self.content_frame, 1)
        content_layout.setStretch(0, 0)
        content_layout.setStretch(1, 1)

        root_layout.addWidget(self.header_bar)
        root_layout.addLayout(content_layout, 1)

        central.setLayout(root_layout)
        self.setCentralWidget(central)

        self.theme_manager.theme_changed.connect(self._update_theme_button)
        self._update_theme_button(
            self.theme_manager.current_mode(), self.theme_manager.is_dark()
        )

    # 需要插件才显示的菜单项：插件标识 -> 依赖它的菜单项列表
    _PLUGIN_GATED_NAV_ITEMS = {
        "proxy": ["mitmproxy"],
    }

    def _resolve_nav_items(self, items: list[str]) -> list[str]:
        """
        按插件安装状态过滤菜单项，未安装对应插件的菜单不显示。
        过滤过程异常时保持完整菜单，避免影响主界面可用性。
        :param items: 全量菜单项
        :return: 过滤后的菜单项
        """
        try:
            from plugins.manager import PLUGIN_DEFINITIONS, plugin_manager

            hidden: set[str] = set()
            for plugin_name, gated_items in self._PLUGIN_GATED_NAV_ITEMS.items():
                if plugin_name not in PLUGIN_DEFINITIONS:
                    continue
                if (
                    plugin_manager.get_status(plugin_name)
                    == plugin_manager.STATUS_MISSING
                ):
                    hidden.update(gated_items)
            return [item for item in items if item not in hidden]
        except Exception as e:
            logger.warning(f"按插件过滤菜单失败，保持完整菜单: {e}")
            return list(items)

    def _build_page_placeholder(self, page_name: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch()

        label = QLabel(f"{page_name} 页面加载中...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: gray; font-size: 14px;")
        layout.addWidget(label)
        layout.addStretch()
        return widget

    def _ensure_page(self, page_name: str) -> QWidget:
        page = self.pages.get(page_name)
        if page is not None:
            return page

        factory = self.page_factories[page_name]
        if page_name == "mitmproxy":
            page = factory(self.stack)
        else:
            page = factory()
        self.pages[page_name] = page

        placeholder = self._page_placeholders.pop(page_name, None)
        if placeholder is not None:
            index = self.stack.indexOf(placeholder)
            if index >= 0:
                self.stack.removeWidget(placeholder)
                self.stack.insertWidget(index, page)
                placeholder.deleteLater()
        return page

    def _on_nav_row_changed(self, row: int):
        if row < 0 or row >= len(self.nav_items):
            return

        page_name = self.nav_items[row]
        if self._page_loading_enabled:
            self._ensure_page(page_name)
        self.stack.setCurrentIndex(row)

    def _init_status_bar(self):
        self.statusBar().showMessage("就绪 | 当前运行POS: -")
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._refresh_global_status)
        self._status_timer.start()

    def _open_plugin_manager(self):
        """
        打开插件管理对话框；对话框内部异常仅记录日志，不影响主窗口。
        :return:
        """
        try:
            from ui.dialogs.plugin_manager_dialog import PluginManagerDialog

            dialog = PluginManagerDialog(self)
            dialog.exec()
        except Exception as e:
            logger.exception(f"打开插件管理失败: {e}")

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
        from managers.pos_manager import PosManager

        current = PosManager.instance().get()
        if current:
            path = current.get("path") or "-"
            pid = current.get("pid") or "-"
            self.statusBar().showMessage(f"运行中 | 当前POS: {path} | PID: {pid}")
        else:
            self.statusBar().showMessage("就绪 | 当前运行POS: -")

    def close_for_update(self):
        self._closing_for_update = True
        self.close()

    def showEvent(self, event):
        super().showEvent(event)
        if self._initial_page_load_scheduled:
            return
        self._initial_page_load_scheduled = True
        QTimer.singleShot(0, self._activate_initial_page)

    def _activate_initial_page(self):
        self._page_loading_enabled = True
        current_row = self.menu.currentRow()
        if current_row < 0:
            current_row = self.nav_items.index(self._default_page_name)
            self.menu.setCurrentRow(current_row)
            return
        self._on_nav_row_changed(current_row)

    def closeEvent(self, event):
        if not self._closing_for_update:
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
            if page is None:
                continue
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
