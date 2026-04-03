from PySide6.QtCore import Qt, Signal
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
from ui.dialogs.mitm_setting_dialog import MitmSettingDialog
from ui.widgets.mitm_flow_main_widget import FlowMainWidget
from ui.widgets.process_selector_widget import ProcessSelectorWidget


class MitmWidget(QWidget):
    start_clicked = Signal()
    stop_clicked = Signal()
    save_clicked = Signal(dict)

    def __init__(self):
        super().__init__()
        self.config = MitmproxyConfig.read()
        self.proxy_state = "stopped"
        self._quick_save_guard = False
        self._detail_visible = True

        self._init_ui()
        self.controller = MitmController(self)
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
        self.settings_btn = QPushButton("设置")
        self.stop_btn.setEnabled(False)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.title_label)
        action_layout.addSpacing(12)
        action_layout.addWidget(self.clear_btn)
        action_layout.addWidget(self.detail_toggle_btn)
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
        self.flow_count_label = QLabel("记录 0 条")
        self.port_value_label.setMinimumWidth(64)
        self.web_port_value_label.setMinimumWidth(64)
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
        info_layout.addWidget(QLabel("记录"))
        info_layout.addWidget(self.flow_count_label)
        info_layout.addWidget(QLabel("模式"))
        info_layout.addWidget(self.mode_select)
        info_layout.addWidget(self.mode_value_container)
        info_layout.addStretch()

        self.flow_widget = FlowMainWidget()

        main_layout.addLayout(action_layout)
        main_layout.addLayout(info_layout)
        main_layout.addWidget(self.flow_widget, 1)

    def _bind(self):
        self.start_btn.clicked.connect(self._handle_start_clicked)
        self.stop_btn.clicked.connect(self._handle_stop_clicked)
        self.clear_btn.clicked.connect(self._handle_clear_clicked)
        self.detail_toggle_btn.clicked.connect(self._toggle_detail)
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        self.mode_select.currentTextChanged.connect(self._on_mode_changed)
        self.mode_value_input.value_committed.connect(self._save_quick_settings)
        self.flow_widget.table.stats_changed.connect(self._update_flow_stats)

    def _handle_start_clicked(self, _checked=False):
        self._save_quick_settings()
        self.start_clicked.emit()

    def _toggle_detail(self, _checked=False):
        self._detail_visible = self.flow_widget.toggle_detail()
        self.detail_toggle_btn.setText(
            "隐藏详情" if self._detail_visible else "显示详情"
        )

    def _handle_stop_clicked(self, _checked=False):
        self.stop_clicked.emit()

    def _handle_clear_clicked(self, _checked=False):
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
        self._apply_state_text(proxy_state)

    def _update_flow_stats(self, visible_count: int, total_count: int):
        if visible_count == total_count:
            self.flow_count_label.setText(f"{total_count} 条")
            return
        self.flow_count_label.setText(f"{visible_count} / {total_count}")

    def _update_mode_input(self, mode: str):
        is_local = mode == "local"
        self.mode_value_container.setVisible(is_local)

    def set_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.mode_select.setEnabled(not running)
        self.mode_value_input.setEnabled(not running)
        if self.proxy_state in {"starting", "running", "stopping"}:
            self._apply_state_text(self.proxy_state)
        else:
            self._apply_state_text("running" if running else "stopped")

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
