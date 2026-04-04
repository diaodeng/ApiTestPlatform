from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.dialogs.dialog_service import DialogService
from ui.theme_manager import ThemeManager, color_to_hex


class PosItemWidget(QWidget):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.page = parent  # 用来调用controller

        self._init_ui()
        self._bind()
        self.dialog_service = DialogService(self)
        ThemeManager.instance().theme_changed.connect(self._apply_theme)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # 路径
        self.path_label = QLabel(self.path)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.path_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.path_label.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            background: transparent;
            border: none;
        """)

        # 信息
        self.info_label = QLabel("环境: 未获取")
        self.info_label.setStyleSheet("""
            font-size: 12px;
            background: transparent;
            border: none;
        """)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)  # 🔥 关键：缩小间距
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_layout.addWidget(self.path_label)
        title_layout.addWidget(self.info_label)

        # 按钮
        btn_layout = QHBoxLayout()

        self.btn_open_dir = QToolButton()
        self.btn_open_dir.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self.btn_open_dir.setToolTip("打开目录")

        self.btn_switch_online = QToolButton()
        self.btn_switch_online.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.btn_switch_online.setToolTip("切换POS(在线)")

        self.btn_env = QToolButton()
        self.btn_env.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView)
        )
        self.btn_env.setToolTip("查看环境")

        self.btn_start = QToolButton()
        self.btn_start.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.btn_start.setToolTip("启动POS")

        self.btn_more = QToolButton()
        self.btn_more.setStyleSheet("")
        self.btn_more.setText("⋮")
        self.btn_more.setPopupMode(QToolButton.InstantPopup)

        self.menu = QMenu(self)
        self.action_open_dir = QAction("打开所在目录", self)
        self.action_clean_cache = QAction("清理缓存", self)
        self.action_change_env = QAction("切换本地环境", self)
        self.action_open_online_dialog = QAction("打开切换POS(在线)弹窗", self)
        self.action_backup_driver = QAction("备份支付驱动", self)
        self.action_restore_driver = QAction("恢复支付驱动", self)
        self.action_cover_driver = QAction("覆盖支付驱动", self)
        self.action_clear_env_file = QAction("清理当前环境文件", self)
        self.action_replace_cert = QAction("替换证书", self)
        self.action_logout = QAction("退出账号", self)

        for action in [
            self.action_clean_cache,
            self.action_change_env,
            self.action_open_online_dialog,
            self.action_backup_driver,
            self.action_restore_driver,
            self.action_cover_driver,
            self.action_clear_env_file,
            self.action_replace_cert,
            self.action_logout,
        ]:
            self.menu.addAction(action)

        self.btn_more.setMenu(self.menu)

        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)

        # btn_layout.addWidget(self.path_label)
        # btn_layout.addWidget(self.info_label)
        # btn_layout.addStretch()
        btn_layout.addWidget(self.btn_open_dir)
        btn_layout.addWidget(self.btn_switch_online)
        btn_layout.addWidget(self.btn_env)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_more)

        # 左边：标题（主+副）
        main_row.addLayout(title_layout)

        # 右边：按钮
        main_row.addStretch()
        main_row.addLayout(btn_layout)

        layout.addLayout(main_row)

        self.setObjectName("posItem")
        self.setAttribute(
            Qt.WA_StyledBackground, True
        )  # 主动绘制背景，子容器不会主动绘制背景

        self._apply_theme()
        # for w in self.findChildren(QLabel):
        #     w.setStyleSheet("background: transparent; border: none;")

    def _bind(self):
        self.btn_start.clicked.connect(self.on_start)
        self.btn_env.clicked.connect(self.load_env)
        self.btn_open_dir.clicked.connect(self.on_open_dir)
        self.btn_switch_online.clicked.connect(self.on_switch_online)
        self.path_label.customContextMenuRequested.connect(self._show_path_menu)
        self.path_label.mouseDoubleClickEvent = lambda e: self.copy_path()

        self.action_open_dir.triggered.connect(self.on_open_dir)
        self.action_clean_cache.triggered.connect(self.on_clean_cache)
        self.action_change_env.triggered.connect(self.on_change_env)
        self.action_open_online_dialog.triggered.connect(self.on_open_online_dialog)
        self.action_backup_driver.triggered.connect(self.on_backup_driver)
        self.action_restore_driver.triggered.connect(self.on_restore_driver)
        self.action_cover_driver.triggered.connect(self.on_cover_driver)
        self.action_clear_env_file.triggered.connect(self.on_clear_env_file)
        self.action_replace_cert.triggered.connect(self.on_replace_cert)
        self.action_logout.triggered.connect(self.on_logout)
        # self.load_env()

    def on_start(self):
        self.page.controller.start_pos(self.path, self.dialog_service)

    def on_env(self):
        self.page.controller.get_env(self.path)

    def load_env(self):
        def callback(text):
            self.info_label.setText(text)

        self.page.controller.get_env(self.path, callback)

    def _show_path_menu(self, pos):
        menu = QMenu(self)
        copy_action = menu.addAction("复制路径")
        action = menu.exec(self.path_label.mapToGlobal(pos))
        if action == copy_action:
            self.copy_path()

    def copy_path(self):
        QGuiApplication.clipboard().setText(self.path)
        self.dialog_service.success("POS路径已复制")

    def on_open_dir(self):
        self.page.controller.open_pos_location(self.path)

    def on_clean_cache(self):
        self.page.controller.clean_cache(self.path)

    def on_change_env(self):
        self.page.open_local_env_dialog(self.path)

    def on_switch_online(self):
        self.page.controller.switch_pos_online_by_path(self.path)

    def on_open_online_dialog(self):
        self.page.open_change_pos_dialog(self.path)

    def on_backup_driver(self):
        self.page.controller.backup_payment_driver(self.path)

    def on_restore_driver(self):
        self.page.controller.restore_payment_driver(self.path)

    def on_cover_driver(self):
        self.page.controller.cover_payment_driver(self.path)

    def on_clear_env_file(self):
        self.page.controller.clear_pos_env_file(self.path)

    def on_replace_cert(self):
        self.page.controller.replace_mitm_cert(self.path)

    def on_logout(self):
        self.page.controller.logout_pos_account(self.path)

    def update_env_info(self, env_info):
        self.info_label.setText(env_info)

    def _apply_theme(self, *_args):
        tokens = ThemeManager.instance().tokens()
        self.info_label.setStyleSheet(
            f"""
            color: {color_to_hex(tokens.subtle_text)};
            font-size: 12px;
            background: transparent;
            border: none;
            """
        )
        self.setStyleSheet(
            f"""
            #posItem {{
                background-color: {color_to_hex(tokens.surface)};
                border: 1px solid {color_to_hex(tokens.border)};
                border-radius: 6px;
            }}
            #posItem:hover {{
                background-color: {color_to_hex(tokens.surface_hover)};
            }}
            """
        )
