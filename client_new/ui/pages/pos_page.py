from loguru import logger
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.pos_controller import PosController
from server.config import PosConfig, SearchConfig, StartConfig
from ui.dialogs.change_pos_dialog import ChangePosDialog
from ui.dialogs.dialog_service import DialogService
from ui.dialogs.local_env_dialog import LocalEnvDialog
from ui.dialogs.pos_account_dialog import PosAccountDialog
from ui.dialogs.pos_setting_dialog import PosSettingDialog
from ui.dialogs.process_manager_dialog import ProcessManagerDialog
from ui.dialogs.work_dir_dialog import WorkDirDialog
from ui.widgets.pos_table_widget import PosTableWidget


class PosPage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_results = []
        self.controller = PosController()
        self.dialog_service = DialogService(self)
        self._result_set = set()
        self._sync_in_progress = False

        self._init_ui()
        self._bind()
        self._load_start_config()
        QTimer.singleShot(0, self._maybe_auto_sync_config)

    def _init_ui(self):
        self.setWindowTitle("POS 启动器")

        main_layout = QVBoxLayout(self)

        top_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        self.dir_btn = QPushButton("工作目录")
        self.scan_btn = QPushButton("扫描")
        self.stop_pos_btn = QPushButton("停止POS")
        self.stop_offline_btn = QPushButton("停止离线")
        self.switch_pos_btn = QPushButton("切换POS")
        self.process_btn = QPushButton("结束进程")
        self.account_btn = QPushButton("POS账号处理")
        self.btn_setting = QPushButton("POS设置")

        row1.addWidget(self.dir_btn)
        row1.addWidget(self.scan_btn)
        row1.addStretch()
        row1.addWidget(self.stop_pos_btn)
        row1.addWidget(self.stop_offline_btn)
        row1.addWidget(self.switch_pos_btn)
        row1.addWidget(self.process_btn)
        row1.addWidget(self.account_btn)
        row1.addWidget(self.btn_setting)

        row3 = QHBoxLayout()
        self.cb_cert = QCheckBox("替换证书")
        self.cb_cache = QCheckBox("清缓存")
        self.cb_driver = QCheckBox("覆盖驱动")

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("输入关键字过滤（路径/文件名）")
        self.filter_input.setClearButtonEnabled(True)

        self.refresh_btn = QPushButton("刷新列表")

        row3.addWidget(QLabel("启动前:"))
        row3.addWidget(self.cb_cert)
        row3.addWidget(self.cb_cache)
        row3.addWidget(self.cb_driver)
        row3.addWidget(QLabel("过滤:"))
        row3.addWidget(self.filter_input)
        row3.addWidget(self.refresh_btn)
        row3.addStretch()

        top_layout.addLayout(row1)
        top_layout.addLayout(row3)
        main_layout.addLayout(top_layout)

        self.status_label = QLabel("状态：就绪")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)

        self.result_table = PosTableWidget(self)
        main_layout.addWidget(self.result_table, 1)

        self.load_history()

    def _bind(self):
        self.dir_btn.clicked.connect(self.open_work_dir_dialog)
        self.scan_btn.clicked.connect(self.on_scan)
        self.stop_pos_btn.clicked.connect(self.on_stop_pos)
        self.stop_offline_btn.clicked.connect(self.on_stop_offline)
        self.cb_cert.toggled.connect(self._save_start_config)
        self.cb_cache.toggled.connect(self._save_start_config)
        self.cb_driver.toggled.connect(self._save_start_config)
        self.filter_input.textChanged.connect(self.apply_filter)
        self.refresh_btn.clicked.connect(self.refresh_list)
        self.btn_setting.clicked.connect(self.open_setting_dialog)
        self.switch_pos_btn.clicked.connect(self.open_change_pos_dialog)
        self.process_btn.clicked.connect(self.open_process_dialog)
        self.account_btn.clicked.connect(self.open_pos_account_dialog)

        self.result_table.open_dir_requested.connect(self.on_row_open_dir)
        self.result_table.switch_online_requested.connect(
            self.on_row_switch_online
        )
        self.result_table.load_env_requested.connect(self.on_row_load_env)
        self.result_table.start_requested.connect(self.on_row_start)
        self.result_table.more_requested.connect(self.open_row_more_menu)
        self.result_table.copy_path_requested.connect(self.copy_path)

        self.controller.result_signal.connect(self.add_result)
        self.controller.status_signal.connect(self.update_status)
        self.controller.finished_signal.connect(self.on_finished)
        self.controller.log_signal.connect(self.update_status)
        self.controller.config_sync_signal.connect(self._on_config_sync_finished)

    def open_work_dir_dialog(self):
        dialog = WorkDirDialog(self)
        dialog.exec()

    def on_scan(self):
        logger.info("开始扫描")
        config = SearchConfig.read()
        file_pattern = config.file_pattern or "*"
        dir_pattern = config.dir_pattern or "*"
        try:
            depth = int(config.max_depth)
        except Exception:
            depth = 3

        self.clear_list()
        self.controller.start_search(
            file_pattern=file_pattern,
            dir_pattern=dir_pattern,
            depth=depth,
        )

    def on_stop_pos(self):
        logger.info("停止POS")
        self.controller.stop_pos()

    def on_stop_offline(self):
        logger.info("停止离线进程")
        self.controller.stop_offline()

    def refresh_list(self):
        self.apply_filter()

    def apply_filter(self, *_args):
        self.result_table.set_filter_text(self._get_filter_keyword())

    def sync_remote_config(self, auto: bool = False):
        if self._sync_in_progress:
            return

        config = PosConfig.read_pos_config()
        config_url = (config.config_sync_url or "").strip()
        if not config_url:
            self.update_status("请先在 POS 设置中填写配置拉取地址")
            return

        self.set_config_syncing(True)
        if auto:
            self.update_status("正在初始化 POS 配置...")
        self.controller.sync_remote_config(config_url)

    def load_history(self):
        results = list(dict.fromkeys(SearchConfig.read_search_result() or []))
        self.clear_list()
        self.all_results = results
        self._result_set = set(self.all_results)
        self.result_table.set_paths(self.all_results)
        self.apply_filter()

    def add_result(self, file_path):
        if not file_path or file_path in self._result_set:
            return
        self._result_set.add(file_path)
        self.all_results.append(file_path)
        self.result_table.add_path(file_path)

    def update_status(self, text):
        self.status_label.setText(f"状态：{text}")

    def on_finished(self):
        pass

    def clear_list(self):
        self._result_set.clear()
        self.all_results.clear()
        self.result_table.clear()

    def copy_path(self, pos_path: str):
        if not pos_path:
            return
        QGuiApplication.clipboard().setText(pos_path)
        self.update_status("POS路径已复制")

    def on_row_open_dir(self, pos_path: str):
        self.controller.open_pos_location(pos_path)

    def on_row_switch_online(self, pos_path: str):
        self.controller.switch_pos_online_by_path(pos_path)

    def on_row_load_env(self, pos_path: str):
        self.result_table.set_env_loading(pos_path)

        def callback(text, target_path=pos_path):
            self.result_table.update_env_info(target_path, text)
            self.update_status(text)

        self.controller.get_env(pos_path, callback)

    def on_row_start(self, pos_path: str):
        self.controller.start_pos(pos_path, self.dialog_service)

    def open_row_more_menu(self, pos_path: str, global_pos):
        if not pos_path:
            return
        if global_pos is None or global_pos.isNull():
            global_pos = self.mapToGlobal(self.rect().center())

        menu = QMenu(self)
        action_change_env = menu.addAction("切换本地环境")
        action_open_online_dialog = menu.addAction("打开切换POS(在线)弹窗")
        action_backup_driver = menu.addAction("备份支付驱动")
        action_restore_driver = menu.addAction("恢复支付驱动")
        action_cover_driver = menu.addAction("覆盖支付驱动")
        action_clear_env_file = menu.addAction("清理当前环境文件")
        action_replace_cert = menu.addAction("替换证书")
        action_logout = menu.addAction("退出账号")
        menu.addSeparator()
        action_copy_path = menu.addAction("复制路径")

        selected_action = menu.exec(global_pos)
        if selected_action == action_change_env:
            self.open_local_env_dialog(pos_path)
            return
        if selected_action == action_open_online_dialog:
            self.open_change_pos_dialog(pos_path)
            return
        if selected_action == action_backup_driver:
            self.controller.backup_payment_driver(pos_path)
            return
        if selected_action == action_restore_driver:
            self.controller.restore_payment_driver(pos_path)
            return
        if selected_action == action_cover_driver:
            self.controller.cover_payment_driver(pos_path)
            return
        if selected_action == action_clear_env_file:
            self.controller.clear_pos_env_file(pos_path)
            return
        if selected_action == action_replace_cert:
            self.controller.replace_mitm_cert(pos_path)
            return
        if selected_action == action_logout:
            self.controller.logout_pos_account(pos_path)
            return
        if selected_action == action_copy_path:
            self.copy_path(pos_path)

    def _get_filter_keyword(self):
        return self.filter_input.text().lower().strip()

    def open_setting_dialog(self):
        dlg = PosSettingDialog(self)
        dlg.exec()

    def open_change_pos_dialog(self, pos_path: str = ""):
        dlg = ChangePosDialog(self, pos_path=pos_path)
        dlg.exec()

    def open_local_env_dialog(self, pos_path: str):
        dlg = LocalEnvDialog(pos_path=pos_path, parent=self)
        ok = dlg.exec()
        if ok:
            self.update_status("本地环境切换成功")

    def open_process_dialog(self):
        dlg = ProcessManagerDialog(self)
        dlg.exec()

    def open_pos_account_dialog(self):
        dlg = PosAccountDialog(self)
        dlg.exec()

    def set_config_syncing(self, syncing: bool):
        self._sync_in_progress = syncing

    def _load_start_config(self):
        start_config = StartConfig.read()
        for checkbox, value in (
            (self.cb_cert, start_config.replace_mitm_cert),
            (self.cb_cache, start_config.remove_cache),
            (self.cb_driver, start_config.cover_payment_driver),
        ):
            checkbox.blockSignals(True)
            checkbox.setChecked(bool(value))
            checkbox.blockSignals(False)

    def _save_start_config(self, *_args):
        start_config = StartConfig.read()
        start_config.replace_mitm_cert = self.cb_cert.isChecked()
        start_config.remove_cache = self.cb_cache.isChecked()
        start_config.cover_payment_driver = self.cb_driver.isChecked()
        StartConfig.write(start_config)

    def _maybe_auto_sync_config(self):
        config = PosConfig.read_pos_config()
        if not (config.config_sync_url or "").strip():
            return
        if config.config_sync_initialized:
            return
        self.sync_remote_config(auto=True)

    def _on_config_sync_finished(self, _success: bool, _message: str, _payload: object):
        self.set_config_syncing(False)
