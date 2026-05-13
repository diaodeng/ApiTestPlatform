from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller.mitm_controller import MitmController
from server.config import MitmproxyConfig
from ui.dialogs.mitm_breakpoint_edit_dialog import MitmBreakpointEditDialog
from ui.dialogs.mitm_setting_dialog import MitmSettingDialog
from ui.widgets.mitm_flow_main_widget import FlowMainWidget
from ui.widgets.process_selector_widget import ProcessSelectorWidget


class MitmWidget(QWidget):
    start_clicked = Signal()
    stop_clicked = Signal()
    save_clicked = Signal(dict)
    install_cert_clicked = Signal()
    open_web_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = MitmproxyConfig.read()
        self.proxy_state = "stopped"
        self._quick_save_guard = False
        self._detail_visible = True
        self._current_web_url = ""
        self._app_flow_visible = True
        self._runtime_initialized = False
        self._runtime_init_scheduled = False
        self.flow_widget: FlowMainWidget | None = None
        self.controller: MitmController | None = None

        self._init_ui()
        self._bind()
        self.apply_config(self.config, self.proxy_state)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.title_label = QLabel("mitmproxy")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        self.start_btn = QPushButton("启动")
        self.stop_btn = QPushButton("停止")
        self.clear_btn = QPushButton("清空")
        self.detail_toggle_btn = QPushButton("隐藏详情")
        self.open_web_btn = QPushButton("打开 Web 页面")
        self.settings_btn = QPushButton("设置")
        self.clear_btn.setEnabled(False)
        self.detail_toggle_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.title_label)
        action_layout.addSpacing(12)
        action_layout.addWidget(self.clear_btn)
        action_layout.addWidget(self.detail_toggle_btn)
        action_layout.addWidget(self.open_web_btn)
        action_layout.addWidget(self.settings_btn)
        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        action_layout.addStretch()

        self.status_badge = QLabel("未启动")
        self.status_badge.setStyleSheet(self._badge_style(False))
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFixedWidth(72)

        self.port_value_label = QLabel("-")
        self.web_port_value_label = QLabel("-")
        self.startup_mode_value_label = QLabel("-")
        self.flow_count_label = QLabel("记录 0 条")
        self.mode_hint_label = QLabel("当前模式说明：-")
        self.mode_hint_label.setWordWrap(True)
        self.mode_hint_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.cert_status_label = QLabel("证书状态：-")
        self.cert_status_label.setWordWrap(True)
        self.cert_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.install_cert_btn = QPushButton("安装当前用户证书")
        self.port_value_label.setMinimumWidth(64)
        self.web_port_value_label.setMinimumWidth(64)
        self.startup_mode_value_label.setMinimumWidth(64)
        self.flow_count_label.setMinimumWidth(120)
        self.mode_select = QComboBox()
        self.mode_select.addItems(["local", "regular", "wireguard", "socks5", "dns"])
        self.mode_select.setFixedWidth(120)
        self.mode_value_input = ProcessSelectorWidget(
            "输入或选择进程名，例如：CPOS-DF.exe"
        )

        self.mode_value_container = QWidget()
        mode_value_layout = QHBoxLayout(self.mode_value_container)
        mode_value_layout.setContentsMargins(0, 0, 0, 0)
        mode_value_layout.setSpacing(6)
        mode_value_layout.addWidget(QLabel("应用"))
        mode_value_layout.addWidget(self.mode_value_input)

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        info_layout.addWidget(QLabel("状态"))
        info_layout.addWidget(self.status_badge)
        info_layout.addWidget(QLabel("代理端口"))
        info_layout.addWidget(self.port_value_label)
        info_layout.addWidget(QLabel("Web端口"))
        info_layout.addWidget(self.web_port_value_label)
        info_layout.addWidget(QLabel("启动方式"))
        info_layout.addWidget(self.startup_mode_value_label)
        info_layout.addWidget(QLabel("记录"))
        info_layout.addWidget(self.flow_count_label)
        info_layout.addWidget(QLabel("模式"))
        info_layout.addWidget(self.mode_select)
        info_layout.addWidget(self.mode_value_container)
        info_layout.addStretch()

        cert_layout = QHBoxLayout()
        cert_layout.setContentsMargins(0, 0, 0, 0)
        cert_layout.setSpacing(8)
        cert_layout.addWidget(self.cert_status_label, 1)
        cert_layout.addWidget(self.install_cert_btn)

        self.loading_label = QLabel("mitmproxy 页面初始化中...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setWordWrap(True)
        self.loading_label.setStyleSheet(
            "padding: 24px; border: 1px dashed #a0aec0; border-radius: 10px;"
        )

        self.flow_placeholder = QLabel()
        self.flow_placeholder.setAlignment(Qt.AlignCenter)
        self.flow_placeholder.setWordWrap(True)
        self.flow_placeholder.setStyleSheet(
            "padding: 24px; border: 1px dashed #a0aec0; border-radius: 10px;"
        )
        self.flow_placeholder.hide()

        self.flow_container = QWidget()
        self.flow_container_layout = QVBoxLayout(self.flow_container)
        self.flow_container_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_container_layout.setSpacing(10)
        self.flow_container_layout.addWidget(self.loading_label, 1)
        self.flow_container_layout.addWidget(self.flow_placeholder, 1)

        main_layout.addLayout(action_layout)
        main_layout.addLayout(info_layout)
        main_layout.addWidget(self.mode_hint_label)
        main_layout.addLayout(cert_layout)
        main_layout.addWidget(self.flow_container, 1)

    def _bind(self):
        self.start_btn.clicked.connect(self._handle_start_clicked)
        self.stop_btn.clicked.connect(self._handle_stop_clicked)
        self.clear_btn.clicked.connect(self._handle_clear_clicked)
        self.detail_toggle_btn.clicked.connect(self._toggle_detail)
        self.open_web_btn.clicked.connect(
            lambda _checked=False: self.open_web_clicked.emit()
        )
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        self.install_cert_btn.clicked.connect(
            lambda _checked=False: self.install_cert_clicked.emit()
        )
        self.mode_select.currentTextChanged.connect(self._on_mode_changed)
        self.mode_value_input.value_committed.connect(self._save_quick_settings)

    def _handle_start_clicked(self, _checked=False):
        if self.controller is None and not self._runtime_initialized:
            self._initialize_runtime()
        if self._should_show_app_flows():
            self._ensure_flow_widget()
        self._save_quick_settings()
        self.start_clicked.emit()

    def _toggle_detail(self, _checked=False):
        if not self._app_flow_visible or self.flow_widget is None:
            return
        self._detail_visible = self.flow_widget.toggle_detail()
        self.detail_toggle_btn.setText(
            "隐藏详情" if self._detail_visible else "显示详情"
        )

    def _handle_stop_clicked(self, _checked=False):
        self.stop_clicked.emit()

    def _handle_clear_clicked(self, _checked=False):
        if not self._app_flow_visible or self.flow_widget is None:
            return
        self.flow_widget.clear()

    def _open_settings_dialog(self, _checked=False):
        dialog = MitmSettingDialog(self.config, self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                self.save_clicked.emit(data)

    def _on_mode_changed(self, mode: str):
        self._update_mode_input(mode)
        self._save_quick_settings()

    def _save_quick_settings(self, *_args):
        if self._quick_save_guard:
            return

        data = self.config.model_dump()
        data["proxy_model"] = self.mode_select.currentText()
        data["proxy_model_value"] = self.mode_value_input.value()
        self.save_clicked.emit(data)

    def apply_config(self, config, proxy_state: str = "stopped"):
        self.config = config
        self.proxy_state = proxy_state

        self._quick_save_guard = True
        self.mode_select.setCurrentText(config.proxy_model)
        self.mode_value_input.set_value(config.proxy_model_value)
        self._update_mode_input(config.proxy_model)
        self._quick_save_guard = False

        self.port_value_label.setText(str(config.port))
        self.web_port_value_label.setText(str(config.web_port))
        self.startup_mode_value_label.setText(
            str(getattr(config, "startup_mode", "dump") or "dump").strip().lower()
        )
        self._update_mode_hint(config)
        self._update_app_flow_visibility(config)
        if self.flow_widget is not None:
            self.flow_widget.table.set_record_limit(
                int(getattr(config, "flow_record_limit", 500) or 500)
            )
            self.flow_widget.table.set_breakpoint_rule(
                bool(getattr(config, "breakpoint_enabled", False)),
                str(getattr(config, "breakpoint_pattern", "") or ""),
            )
        self._refresh_web_controls()
        self._apply_state_text(proxy_state)

    def _update_flow_stats(self, visible_count: int, total_count: int):
        if not self._app_flow_visible:
            self.flow_count_label.setText("Web 查看")
            return
        if visible_count == total_count:
            self.flow_count_label.setText(f"{total_count} 条")
            return
        self.flow_count_label.setText(f"{visible_count} / {total_count}")

    def _update_mode_input(self, mode: str):
        is_local = mode == "local"
        self.mode_value_container.setVisible(is_local)

    def _update_mode_hint(self, config):
        mode = str(config.proxy_model or "").strip()
        startup_mode = str(getattr(config, "startup_mode", "dump") or "dump").strip().lower()
        show_in_app = bool(getattr(config, "web_show_in_app", True))
        if mode == "local":
            target = str(config.proxy_model_value or "").strip() or "指定进程"
            message = (
                f"当前模式说明：local 会自动拦截本机进程 {target} 的流量。"
                "Windows 下通常需要管理员权限；HTTPS 网站仍需要先信任 mitmproxy CA。"
            )
        elif mode == "regular":
            message = (
                f"当前模式说明：regular 不会自动抓包，需要把浏览器或系统代理手动指向 "
                f"127.0.0.1:{config.port}。"
            )
        elif mode:
            message = (
                f"当前模式说明：{mode} 模式需要按 mitmproxy 的该模式完成代理接入，"
                "HTTPS 网站仍需要先信任 mitmproxy CA。"
            )
        else:
            message = "当前模式说明：尚未配置代理模式。"
        if startup_mode == "web":
            browser_hint = (
                "启动后会自动打开 Web 页面。"
                if bool(getattr(config, "web_open_browser", False))
                else "启动后可点击“打开 Web 页面”查看或重新打开浏览器页面。"
            )
            display_hint = (
                "同时会同步显示在当前应用界面。"
                if show_in_app
                else "当前应用界面不显示流量，请在 Web 页面查看。"
            )
            message = f"{message}\n当前运行方式：web。{browser_hint}{display_hint}"
        else:
            message = f"{message}\n当前运行方式：dump，流量会显示在当前应用界面。"
        self.mode_hint_label.setText(message)

    def _should_show_app_flows(self, config=None) -> bool:
        cfg = config or self.config
        startup_mode = str(getattr(cfg, "startup_mode", "dump") or "dump").strip().lower()
        if startup_mode != "web":
            return True
        return bool(getattr(cfg, "web_show_in_app", True))

    def _update_app_flow_visibility(self, config):
        should_show = self._should_show_app_flows(config)
        if self._app_flow_visible and not should_show and self.flow_widget is not None:
            self.flow_widget.clear()
        self._app_flow_visible = should_show
        if not self._runtime_initialized:
            self.loading_label.setVisible(True)
            self.flow_placeholder.hide()
            return

        if self.flow_widget is not None:
            self.flow_widget.setVisible(should_show)
        self.loading_label.hide()
        self.flow_placeholder.setVisible(False)
        self.clear_btn.setEnabled(should_show and self.flow_widget is not None)
        self.detail_toggle_btn.setEnabled(should_show and self.flow_widget is not None)
        if should_show:
            if self.flow_widget is None:
                self.flow_placeholder.setText(
                    "启动 mitmproxy 后将在这里显示流量列表。\n"
                    "当前尚未初始化流量视图。"
                )
                self.flow_placeholder.show()
                self.detail_toggle_btn.setText("隐藏详情")
                return
            if self.flow_widget is not None:
                self.flow_widget.set_detail_visible(self._detail_visible)
            self.detail_toggle_btn.setText(
                "隐藏详情" if self._detail_visible else "显示详情"
            )
            return

        self.flow_placeholder.setText(
            "当前为 Web 模式，应用内流量列表已关闭。\n"
            "可点击“打开 Web 页面”在浏览器中查看 mitmweb 数据。"
        )
        self.flow_count_label.setText("Web 查看")

    def set_cert_status(
        self,
        message: str,
        trusted: bool,
        can_install: bool,
        cert_path: str = "",
    ):
        prefix = "证书状态"
        if cert_path:
            prefix = f"证书状态（{cert_path}）"
        self.cert_status_label.setText(f"{prefix}：{message}")
        if trusted:
            color = "#2f855a"
        elif can_install:
            color = "#dd6b20"
        else:
            color = "#c53030"
        self.cert_status_label.setStyleSheet(f"color: {color};")
        self.install_cert_btn.setEnabled(can_install)

    def set_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.mode_select.setEnabled(not running)
        self.mode_value_input.setEnabled(not running)
        self._refresh_web_controls()
        if self.proxy_state in {"starting", "running", "stopping"}:
            self._apply_state_text(self.proxy_state)
        else:
            self._apply_state_text("running" if running else "stopped")

    def set_web_url(self, web_url: str):
        self._current_web_url = str(web_url or "").strip()
        self._refresh_web_controls()

    def _refresh_web_controls(self):
        startup_mode = str(getattr(self.config, "startup_mode", "dump") or "dump").strip().lower()
        is_web_mode = startup_mode == "web"
        is_running = self.proxy_state == "running"
        self.open_web_btn.setVisible(is_web_mode)
        self.open_web_btn.setEnabled(is_web_mode and is_running)
        self.open_web_btn.setToolTip(self._current_web_url if self._current_web_url else "")

    def _apply_state_text(self, state: str):
        state_map = {
            "starting": ("启动中", True),
            "running": ("运行中", True),
            "stopping": ("停止中", True),
            "stopped": ("未启动", False),
        }
        text, running = state_map.get(state, ("未启动", False))
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
            self.controller = MitmController(self)
            self._runtime_initialized = True
            self._runtime_init_scheduled = False
            self.loading_label.hide()
            self.apply_config(self.config, self.proxy_state)
        except Exception as e:
            self.loading_label.setText(f"mitmproxy 页面初始化失败：{e}")
            self.loading_label.show()
            if self.flow_widget is not None:
                self.flow_widget.deleteLater()
                self.flow_widget = None
            self.controller = None
            self._runtime_init_scheduled = False

    def _ensure_flow_widget(self):
        if self.flow_widget is not None:
            return self.flow_widget

        self.flow_widget = FlowMainWidget(self.flow_container)
        self.flow_widget.table.stats_changed.connect(self._update_flow_stats)
        self.flow_widget.table.breakpoint_rule_changed.connect(
            self._on_breakpoint_rule_changed
        )
        self.flow_widget.table.breakpoint_continue_requested.connect(
            self._on_breakpoint_continue_requested
        )
        self.flow_container_layout.insertWidget(0, self.flow_widget, 1)
        self.flow_placeholder.hide()
        self.clear_btn.setEnabled(self._app_flow_visible)
        self.detail_toggle_btn.setEnabled(self._app_flow_visible)
        self.flow_widget.set_detail_visible(self._detail_visible)
        self.flow_widget.table.set_record_limit(
            int(getattr(self.config, "flow_record_limit", 500) or 500)
        )
        self.flow_widget.table.set_breakpoint_rule(
            bool(getattr(self.config, "breakpoint_enabled", False)),
            str(getattr(self.config, "breakpoint_pattern", "") or ""),
        )
        return self.flow_widget

    def _on_breakpoint_rule_changed(self, enabled: bool, pattern: str):
        """
        断点规则变更后同步保存配置并下发给运行时。
        :param enabled: 是否启用断点
        :param pattern: 断点匹配关键字
        :return:
        """
        data = self.config.model_dump()
        data["breakpoint_enabled"] = bool(enabled)
        data["breakpoint_pattern"] = str(pattern or "")
        self.save_clicked.emit(data)

    def _on_breakpoint_continue_requested(self, flow_item):
        """
        处理流量行的断点放行请求，弹窗编辑后通知 controller 放行。
        :param flow_item: 当前流量对象
        :return:
        """
        if not flow_item:
            return
        if not self.controller:
            return
        stage = str(getattr(flow_item, "breakpoint_stage", "") or "").strip().lower()
        if stage not in {"request", "response"}:
            return
        dialog = MitmBreakpointEditDialog(flow_item, self)
        if not dialog.exec():
            return
        self.controller.continue_flow_breakpoint(
            str(getattr(flow_item, "id", "") or ""),
            stage,
            dialog.get_payload(),
        )

    def shutdown(self):
        """
        关闭 mitmproxy 页面相关后台资源。

        :return:
        """
        if self.controller is None:
            return
        try:
            self.controller.shutdown()
        except Exception:
            pass
