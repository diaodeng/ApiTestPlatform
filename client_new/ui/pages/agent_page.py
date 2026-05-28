from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from model.config import AgentBrowserConfigModel

class AgentLogPane(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 600;")

        self.copy_btn = QPushButton("复制")
        self.clear_btn = QPushButton("清空")

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        toolbar.addWidget(self.title_label)
        toolbar.addStretch()
        toolbar.addWidget(self.copy_btn)
        toolbar.addWidget(self.clear_btn)

        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText("暂无内容")

        font = QFont("Consolas")
        if not font.exactMatch():
            font = QFont("Courier New")
        self.editor.setFont(font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(toolbar)
        layout.addWidget(self.editor, 1)

        self.copy_btn.clicked.connect(self._copy)
        self.clear_btn.clicked.connect(self.clear)

    def set_text(self, text: str):
        """
        覆盖日志文本内容。

        :param text: 完整日志文本。
        """
        self.editor.setPlainText(text or "")

    def append_text(self, text: str):
        """
        追加一行日志文本。

        :param text: 待追加内容。
        """
        message = str(text or "").strip()
        if not message:
            return
        if self.editor.toPlainText():
            self.editor.appendPlainText(message)
        else:
            self.editor.setPlainText(message)
        scrollbar = self.editor.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self):
        """
        清空日志区域。
        """
        self.editor.clear()

    def _copy(self):
        self.editor.selectAll()
        self.editor.copy()
        cursor = self.editor.textCursor()
        cursor.clearSelection()
        self.editor.setTextCursor(cursor)


class AgentPage(QWidget):
    start_clicked = Signal()
    stop_clicked = Signal()
    save_clicked = Signal(dict)
    sync_config_clicked = Signal()
    manual_browser_download_clicked = Signal(str, dict)

    def __init__(self):
        super().__init__()
        self.proxy_state = "stopped"
        self._quick_save_guard = False
        self._server_list: dict[str, str] = {}
        self._browser_config = AgentBrowserConfigModel()
        self._config_sync_url = ""
        self._config_sync_initialized = False
        self._config_sync_last_sync_at = ""
        self._sync_in_progress = False
        self._server_manage_dialog = None
        self._browser_setting_dialog = None
        self._manual_download_in_progress = False
        self.controller = None
        self._runtime_initialized = False
        self._runtime_init_scheduled = False

        self._init_ui()
        self._bind()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.title_label = QLabel("Agent")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        self.start_btn = QPushButton("连接服务器")
        self.stop_btn = QPushButton("停止")
        self.clear_all_btn = QPushButton("清空日志")
        self.add_server_btn = QPushButton("服务器管理")
        self.browser_settings_btn = QPushButton("浏览器设置")
        self.stop_btn.setEnabled(False)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addWidget(self.title_label)
        action_layout.addSpacing(12)
        action_layout.addWidget(self.clear_all_btn)
        action_layout.addWidget(self.add_server_btn)
        action_layout.addWidget(self.browser_settings_btn)
        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        action_layout.addStretch()

        self.status_badge = QLabel("未连接")
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFixedWidth(72)
        self.status_badge.setStyleSheet(self._badge_style(False))

        self.server_combo = QComboBox()
        self.server_combo.setEditable(True)
        self.server_combo.setMinimumWidth(320)
        self.server_combo.lineEdit().setPlaceholderText(
            "输入服务地址，例如: ws://127.0.0.1:9099/qtr/agent/ws"
        )

        self.server_alias_label = QLabel("-")
        self.server_alias_label.setMinimumWidth(120)

        self.max_send_size_input = QSpinBox()
        self.max_send_size_input.setRange(1, 1024 * 1024)
        self.max_send_size_input.setSuffix(" KB")
        self.max_send_size_input.setFixedWidth(110)

        self.show_log_checkbox = QCheckBox("显示日志")
        self.retry_checkbox = QCheckBox("自动重试")

        self.retry_times_input = QSpinBox()
        self.retry_times_input.setRange(0, 999)
        self.retry_times_input.setFixedWidth(90)

        self.retry_interval_input = QDoubleSpinBox()
        self.retry_interval_input.setRange(0.1, 3600.0)
        self.retry_interval_input.setDecimals(1)
        self.retry_interval_input.setSingleStep(0.5)
        self.retry_interval_input.setSuffix(" s")
        self.retry_interval_input.setFixedWidth(100)

        self.ai_workspace_root_input = QLineEdit()
        self.ai_workspace_root_input.setPlaceholderText("AI 工作区根目录，留空则使用默认值")
        self.ai_workspace_root_input.setMinimumWidth(260)

        self.ai_local_repo_path_input = QLineEdit()
        self.ai_local_repo_path_input.setPlaceholderText("AI 本地仓库路径，留空则回退到映射配置")
        self.ai_local_repo_path_input.setMinimumWidth(260)

        config_layout = QHBoxLayout()
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(10)
        config_layout.addWidget(QLabel("状态"))
        config_layout.addWidget(self.status_badge)
        config_layout.addWidget(QLabel("地址"))
        config_layout.addWidget(self.server_combo)
        config_layout.addWidget(QLabel("别名"))
        config_layout.addWidget(self.server_alias_label)
        config_layout.addWidget(QLabel("最大发送"))
        config_layout.addWidget(self.max_send_size_input)
        config_layout.addWidget(self.show_log_checkbox)
        config_layout.addWidget(self.retry_checkbox)
        config_layout.addWidget(QLabel("重试次数"))
        config_layout.addWidget(self.retry_times_input)
        config_layout.addWidget(QLabel("重试间隔"))
        config_layout.addWidget(self.retry_interval_input)
        config_layout.addStretch()

        ai_config_layout = QHBoxLayout()
        ai_config_layout.setContentsMargins(0, 0, 0, 0)
        ai_config_layout.setSpacing(10)
        ai_config_layout.addWidget(QLabel("AI工作区"))
        ai_config_layout.addWidget(self.ai_workspace_root_input)
        ai_config_layout.addWidget(QLabel("AI本地仓库"))
        ai_config_layout.addWidget(self.ai_local_repo_path_input)
        ai_config_layout.addStretch()

        self.mac_value_label = QLabel("-")
        self.mac_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.mac_value_label.setMinimumWidth(160)

        self.ws_url_value_label = QLabel("-")
        self.ws_url_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.ws_url_value_label.setWordWrap(True)

        self.status_detail_label = QLabel("就绪")
        self.status_detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status_detail_label.setWordWrap(True)

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        info_layout.addWidget(QLabel("MAC"))
        info_layout.addWidget(self.mac_value_label)
        info_layout.addWidget(QLabel("连接地址"))
        info_layout.addWidget(self.ws_url_value_label, 1)
        info_layout.addWidget(QLabel("状态信息"))
        info_layout.addWidget(self.status_detail_label, 1)

        self.request_log = AgentLogPane("请求参数")
        self.response_log = AgentLogPane("响应信息")

        self.log_splitter = QSplitter(Qt.Horizontal)
        self.log_splitter.addWidget(self.request_log)
        self.log_splitter.addWidget(self.response_log)
        self.log_splitter.setChildrenCollapsible(False)
        self.log_splitter.setStretchFactor(0, 1)
        self.log_splitter.setStretchFactor(1, 1)
        self.log_splitter.setSizes([560, 560])

        main_layout.addLayout(action_layout)
        main_layout.addLayout(config_layout)
        main_layout.addLayout(ai_config_layout)
        main_layout.addLayout(info_layout)
        main_layout.addWidget(self.log_splitter, 1)

    def _bind(self):
        self.start_btn.clicked.connect(self._handle_start_clicked)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.clear_all_btn.clicked.connect(self.clear_logs)
        self.add_server_btn.clicked.connect(self._open_server_manage_dialog)
        self.browser_settings_btn.clicked.connect(self._open_browser_setting_dialog)

        self.server_combo.currentTextChanged.connect(self._on_server_text_changed)
        self.server_combo.currentIndexChanged.connect(self._save_quick_settings)
        self.server_combo.lineEdit().editingFinished.connect(self._save_quick_settings)
        self.max_send_size_input.valueChanged.connect(self._save_quick_settings)
        self.show_log_checkbox.toggled.connect(self._save_quick_settings)
        self.retry_checkbox.toggled.connect(self._save_quick_settings)
        self.retry_times_input.valueChanged.connect(self._save_quick_settings)
        self.retry_interval_input.valueChanged.connect(self._save_quick_settings)
        self.ai_workspace_root_input.editingFinished.connect(self._save_quick_settings)
        self.ai_local_repo_path_input.editingFinished.connect(self._save_quick_settings)

    def _handle_start_clicked(self):
        if self.controller is None and not self._runtime_initialized:
            self._initialize_runtime()
        self._save_quick_settings()
        self.start_clicked.emit()

    def _open_server_manage_dialog(self):
        if self.controller is None and not self._runtime_initialized:
            self._initialize_runtime()
        from ui.dialogs.agent_server_manage_dialog import AgentServerManageDialog

        dialog = AgentServerManageDialog(
            self,
            server_list=self._server_list,
            current_server=self.current_server(),
            config_sync_url=self._config_sync_url,
            config_sync_initialized=self._config_sync_initialized,
            config_sync_last_sync_at=self._config_sync_last_sync_at,
        )
        dialog.sync_requested.connect(lambda: self._handle_server_manage_sync(dialog))
        self._server_manage_dialog = dialog
        self._sync_server_manage_dialog_state()
        try:
            if not dialog.exec():
                return

            self._apply_server_manage_dialog_data(dialog)
        finally:
            if self._server_manage_dialog is dialog:
                self._server_manage_dialog = None

    def _open_browser_setting_dialog(self):
        """
        打开浏览器设置弹窗，并处理保存/手动下载事件。
        """
        if self.controller is None and not self._runtime_initialized:
            self._initialize_runtime()
        from ui.dialogs.agent_browser_setting_dialog import AgentBrowserSettingDialog

        dialog = AgentBrowserSettingDialog(self._browser_config, self)
        dialog.manual_download_requested.connect(
            lambda browser_name, payload: self._handle_manual_download(dialog, browser_name, payload)
        )
        self._browser_setting_dialog = dialog
        self._sync_browser_setting_dialog_state()
        try:
            if not dialog.exec():
                return

            data = dialog.get_data()
            if data is None:
                return

            self._browser_config = AgentBrowserConfigModel.model_validate(data)
            self._save_quick_settings()
        finally:
            if self._browser_setting_dialog is dialog:
                self._browser_setting_dialog = None

    def _on_server_text_changed(self, _text: str):
        self._update_server_meta()

    def _handle_manual_download(
        self,
        dialog,
        browser_name: str,
        payload: dict,
    ):
        """
        处理手动下载浏览器请求。

        :param dialog: 当前浏览器设置对话框实例。
        :param browser_name: 目标浏览器名称。
        :param payload: 对话框收集到的浏览器配置。
        """
        try:
            self._browser_config = AgentBrowserConfigModel.model_validate(payload or {})
        except Exception as exc:
            dialog.set_manual_download_state(False, f"配置错误: {exc}")
            return

        self._save_quick_settings()
        target_browser = str(browser_name or "chromium").strip().lower() or "chromium"
        self.set_manual_downloading(True, f"正在下载 {target_browser} ...")
        self.manual_browser_download_clicked.emit(target_browser, self._browser_config.model_dump())

    def _save_quick_settings(self, *_args):
        if self._quick_save_guard:
            return
        self.save_clicked.emit(self._collect_data())

    def _collect_data(self) -> dict:
        return {
            "current_server": self.current_server(),
            "server_list": dict(self._server_list),
            "show_logs": self.show_log_checkbox.isChecked(),
            "max_send_size": int(self.max_send_size_input.value() * 1024),
            "retry_times": int(self.retry_times_input.value()),
            "retry_interval": float(self.retry_interval_input.value()),
            "retry": self.retry_checkbox.isChecked(),
            "config_sync_url": self._config_sync_url,
            "config_sync_initialized": self._config_sync_initialized,
            "config_sync_last_sync_at": self._config_sync_last_sync_at,
            "ticket_ai_workspace_root": self.ai_workspace_root_input.text().strip(),
            "ticket_ai_local_repo_path": self.ai_local_repo_path_input.text().strip(),
            "browser": self._browser_config.model_dump(),
        }

    def apply_config(self, config, connection_state: str, local_mac: str):
        """
        将配置数据渲染到 Agent 页面。

        :param config: Agent 配置模型。
        :param connection_state: 当前连接状态。
        :param local_mac: 本机 MAC。
        """
        self.proxy_state = connection_state
        self._server_list = dict(config.server_list or {})
        browser_config = getattr(config, "browser", None)
        if isinstance(browser_config, AgentBrowserConfigModel):
            self._browser_config = browser_config.model_copy(deep=True)
        elif isinstance(browser_config, dict):
            self._browser_config = AgentBrowserConfigModel.model_validate(browser_config)
        else:
            self._browser_config = AgentBrowserConfigModel()
        self._config_sync_url = str(getattr(config, "config_sync_url", "") or "")
        self._config_sync_initialized = bool(getattr(config, "config_sync_initialized", False))
        self._config_sync_last_sync_at = str(getattr(config, "config_sync_last_sync_at", "") or "")

        self._quick_save_guard = True
        self._apply_server_options(config.current_server)
        self.max_send_size_input.setValue(max(1, int(config.max_send_size / 1024)))
        self.show_log_checkbox.setChecked(config.show_logs)
        self.retry_checkbox.setChecked(config.retry)
        self.retry_times_input.setValue(config.retry_times)
        self.retry_interval_input.setValue(float(config.retry_interval))
        self.ai_workspace_root_input.setText(str(getattr(config, "ticket_ai_workspace_root", "") or ""))
        self.ai_local_repo_path_input.setText(str(getattr(config, "ticket_ai_local_repo_path", "") or ""))
        self.mac_value_label.setText(local_mac or "-")
        self._quick_save_guard = False

        self._update_server_meta()
        self._sync_server_manage_dialog_state()
        self._sync_browser_setting_dialog_state()
        self._apply_state_text(connection_state)

    def set_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.server_combo.setEnabled(not running)
        self.add_server_btn.setEnabled(not running)

    def set_request_text(self, text: str):
        self.request_log.set_text(text)

    def set_response_text(self, text: str):
        self.response_log.set_text(text)

    def append_response_text(self, text: str):
        """
        向响应日志追加文本。

        :param text: 追加的日志内容。
        """
        self.response_log.append_text(text)

    def clear_logs(self):
        self.request_log.clear()
        self.response_log.clear()

    def set_status_message(self, message: str):
        self.status_detail_label.setText(message or "-")

    def set_local_mac(self, local_mac: str):
        self.mac_value_label.setText(local_mac or "-")
        self._update_server_meta()

    def set_config_syncing(self, syncing: bool):
        self._sync_in_progress = syncing
        if self._server_manage_dialog:
            self._server_manage_dialog.set_config_syncing(syncing)

    def on_config_sync_result(self, success: bool, message: str):
        if success:
            self._sync_server_manage_dialog_state()
            return
        if self._server_manage_dialog:
            self._server_manage_dialog.set_sync_status_text(
                message,
                self._config_sync_url,
            )

    def current_server(self) -> str:
        return self.server_combo.currentText().strip()

    def _apply_server_options(self, current_server: str):
        current = (current_server or "").strip()
        urls = list(self._server_list.keys())
        if current and current not in self._server_list:
            urls.insert(0, current)

        self.server_combo.blockSignals(True)
        self.server_combo.clear()
        for url in urls:
            self.server_combo.addItem(url)

        if current:
            self.server_combo.setEditText(current)
        else:
            self.server_combo.setCurrentIndex(-1)
            self.server_combo.lineEdit().clear()
        self.server_combo.blockSignals(False)

    def _update_server_meta(self):
        server = self.current_server()
        alias = self._server_list.get(server) or "-"
        self.server_alias_label.setText(alias)
        self.ws_url_value_label.setText(self._build_ws_url(server))

    def _build_ws_url(self, server: str) -> str:
        base = (server or "").strip()
        if not base:
            return "-"

        mac = self.mac_value_label.text().strip()
        if not mac or mac == "-":
            return base.rstrip("/")

        return f"{base.rstrip('/')}/{mac}"

    def _apply_state_text(self, state: str):
        state_map = {
            "starting": ("连接中", True),
            "running": ("已连接", True),
            "stopping": ("断开中", True),
            "stopped": ("未连接", False),
        }
        text, running = state_map.get(state, ("未连接", False))
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(self._badge_style(running))

    def _badge_style(self, running: bool) -> str:
        background = "#2f855a" if running else "#718096"
        return (
            "padding: 4px 10px; "
            "border-radius: 10px; "
            f"background: {background}; "
            "color: white; "
            "font-weight: 600;"
        )

    def _apply_server_manage_dialog_data(self, dialog: AgentServerManageDialog):
        current_server, server_list, config_sync_url = dialog.get_data()
        self._server_list = dict(server_list or {})
        self._config_sync_url = (config_sync_url or "").strip()
        self._apply_server_options(current_server)
        self._update_server_meta()
        self._save_quick_settings()

    def _handle_server_manage_sync(self, dialog: AgentServerManageDialog):
        self._config_sync_url = dialog.get_config_sync_url()
        self._save_quick_settings()
        if not self._config_sync_url:
            dialog.set_sync_status_text("请先填写配置拉取地址")
            return
        dialog.set_sync_status_text("正在更新 Agent 配置...", self._config_sync_url)
        self.sync_config_clicked.emit()

    def _sync_server_manage_dialog_state(self):
        """
        同步服务器管理弹窗的状态标记。
        """
        if not self._server_manage_dialog:
            return
        self._server_manage_dialog.set_sync_state(
            self._config_sync_initialized,
            self._config_sync_last_sync_at,
            self._config_sync_url,
        )
        self._server_manage_dialog.set_config_syncing(self._sync_in_progress)

    def _sync_browser_setting_dialog_state(self):
        """
        同步浏览器设置弹窗的手动下载状态。
        """
        if not self._browser_setting_dialog:
            return
        self._browser_setting_dialog.set_manual_download_state(
            self._manual_download_in_progress,
            "下载中..." if self._manual_download_in_progress else "未开始",
        )

    def set_manual_downloading(self, downloading: bool, message: str = ""):
        """
        更新手动下载状态并回写到弹窗。

        :param downloading: 是否下载中。
        :param message: 要展示的状态文案。
        """
        self._manual_download_in_progress = bool(downloading)
        if self._browser_setting_dialog:
            self._browser_setting_dialog.set_manual_download_state(
                self._manual_download_in_progress,
                message or ("下载中..." if self._manual_download_in_progress else "未开始"),
            )

    def showEvent(self, event):
        super().showEvent(event)
        if self._runtime_initialized or self._runtime_init_scheduled:
            return
        self._runtime_init_scheduled = True
        QTimer.singleShot(0, self._initialize_runtime)

    def _initialize_runtime(self):
        if self._runtime_initialized:
            return
        try:
            from controller.agent_controller import AgentController

            self.controller = AgentController(self)
            self._runtime_initialized = True
        finally:
            self._runtime_init_scheduled = False
