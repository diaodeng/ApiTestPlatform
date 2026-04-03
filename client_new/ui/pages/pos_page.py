from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller.pos_controller import PosController
from server.config import SearchConfig
from ui.dialogs.change_pos_dialog import ChangePosDialog
from ui.dialogs.local_env_dialog import LocalEnvDialog
from ui.dialogs.pos_account_dialog import PosAccountDialog
from ui.dialogs.pos_setting_dialog import PosSettingDialog
from ui.dialogs.process_manager_dialog import ProcessManagerDialog
from ui.dialogs.work_dir_dialog import WorkDirDialog

from .pos_item import PosItemWidget


class PosPage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_results = []  # 原始数据（不会变）
        self.filtered_results = []  # 当前显示

        self.controller = PosController()
        self._result_set = set()

        self._init_ui()
        self._bind()

    # ======================
    # UI 初始化
    # ======================
    def _init_ui(self):
        self.setWindowTitle("POS 启动器")

        main_layout = QVBoxLayout(self)

        # ======================
        # 顶部控制区
        # ======================
        top_layout = QVBoxLayout()

        # ===== 第一行（按钮）
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

        # ===== 第三行（启动前选项）
        row3 = QHBoxLayout()

        self.cb_cert = QCheckBox("替换证书")
        self.cb_cache = QCheckBox("清缓存")
        self.cb_driver = QCheckBox("覆盖驱动")

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("输入关键字过滤（路径/文件名）")

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

        # ======================
        # 状态栏
        # ======================
        self.status_label = QLabel("状态：就绪")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)

        # ======================
        # 列表区（卡片容器）
        # ======================
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        # self.list_container.setStyleSheet("background: #ffffff;")

        self.scroll.setWidget(self.list_container)

        main_layout.addWidget(self.scroll)
        self.load_history()

    # ======================
    # 信号绑定
    # ======================
    def _bind(self):
        # UI按钮
        self.dir_btn.clicked.connect(self.open_work_dir_dialog)
        self.scan_btn.clicked.connect(self.on_scan)
        self.stop_pos_btn.clicked.connect(self.on_stop_pos)
        self.stop_offline_btn.clicked.connect(self.on_stop_offline)
        self.filter_input.textChanged.connect(self.apply_filter)
        self.refresh_btn.clicked.connect(self.refresh_list)
        self.btn_setting.clicked.connect(self.open_setting_dialog)
        self.switch_pos_btn.clicked.connect(self.open_change_pos_dialog)
        self.process_btn.clicked.connect(self.open_process_dialog)
        self.account_btn.clicked.connect(self.open_pos_account_dialog)

        # controller 信号
        self.controller.result_signal.connect(self.add_result)
        self.controller.status_signal.connect(self.update_status)
        self.controller.finished_signal.connect(self.on_finished)
        self.controller.log_signal.connect(self.update_status)

    # ======================
    # UI -> Controller
    # ======================
    def open_work_dir_dialog(self):
        dialog = WorkDirDialog(self)
        dialog.exec()

    def on_scan(self):
        """开始扫描"""
        logger.info("开始扫描")
        config = SearchConfig.read()
        file_pattern = config.file_pattern or "*"
        dir_pattern = config.dir_pattern or "*"
        try:
            depth = int(config.max_depth)
        except Exception:
            depth = 3

        # 清空UI
        self.clear_list()
        self.all_results.clear()
        self.filtered_results.clear()
        self._result_set.clear()

        # 调controller
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

    # ======================
    # Controller -> UI
    # ======================
    #
    def refresh_list(self):
        self.apply_filter()

    def apply_filter(self):
        keyword = self.filter_input.text().lower().strip()

        if not keyword:
            self.filtered_results = self.all_results[:]
        else:
            self.filtered_results = [
                p for p in self.all_results if keyword in p.lower()
            ]

        self.render_list()

    def render_list(self):
        # 清空UI
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # 重新渲染
        for path in self.filtered_results:
            item = PosItemWidget(path, self)
            self.list_layout.addWidget(item)

        self.list_container.adjustSize()

    def load_history(self):
        results = SearchConfig.read_search_result()

        self.all_results = results or []
        self._result_set = set(self.all_results)
        self.refresh_list()

    def add_result(self, file_path):
        """添加一条结果（卡片）"""
        if not file_path or file_path in self._result_set:
            return
        self._result_set.add(file_path)
        self.all_results.append(file_path)
        keyword = self.filter_input.text().lower().strip()
        if not keyword or keyword in file_path.lower():
            item = PosItemWidget(file_path, self)
            self.list_layout.addWidget(item)

    def update_status(self, text):
        self.status_label.setText(f"状态：{text}")

    def on_finished(self):
        self.status_label.setText("状态：完成")

    # ======================
    # 工具方法
    # ======================
    def clear_list(self):
        self._result_set.clear()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

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
