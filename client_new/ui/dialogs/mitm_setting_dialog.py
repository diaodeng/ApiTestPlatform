from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.process_selector_widget import ProcessSelectorWidget


class MitmSettingDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._saved_data = None

        self.setWindowTitle("mitmproxy 设置")
        self.resize(1000, 760)
        self.setMinimumSize(920, 680)

        self._init_ui()
        self._bind_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)

        self.content_layout.addWidget(self._build_basic_group())
        self.content_layout.addWidget(self._build_mock_group())
        self.content_layout.addWidget(self._build_filter_group())
        self.content_layout.addWidget(self._build_delay_group())
        self.content_layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_close = QPushButton("关闭")
        self.btn_save = QPushButton("保存")

        self.btn_close.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._save)

        button_layout.addWidget(self.btn_close)
        button_layout.addWidget(self.btn_save)
        main_layout.addLayout(button_layout)

    def _build_basic_group(self):
        box = QGroupBox("基础配置")
        layout = QFormLayout(box)

        self.port_input = QLineEdit()
        self.web_port_input = QLineEdit()
        self.startup_mode_select = QComboBox()
        self.startup_mode_select.addItem("dump", "dump")
        self.startup_mode_select.addItem("web", "web")
        self.mode_select = QComboBox()
        self.mode_select.addItems(["local", "regular", "wireguard", "socks5", "dns"])
        self.mode_select.setFixedWidth(120)
        self.mode_value_input = ProcessSelectorWidget(
            "输入或选择进程名，例如：CPOS-DF.exe"
        )
        self.mode_value_container = QWidget()
        mode_value_container_layout = QHBoxLayout(self.mode_value_container)
        mode_value_container_layout.setContentsMargins(0, 0, 0, 0)
        mode_value_container_layout.setSpacing(6)
        mode_value_container_layout.addWidget(QLabel("应用"))
        mode_value_container_layout.addWidget(self.mode_value_input)
        self.config_dir_input = QLineEdit()
        self.cert_path_input = QLineEdit()
        self.script_path_input = QLineEdit()
        self.ssl_insecure_checkbox = QCheckBox("忽略 SSL 校验")
        self.web_open_browser_checkbox = QCheckBox("启动后打开浏览器")
        self.web_show_in_app_checkbox = QCheckBox("Web 模式下同步显示到应用界面")

        mode_row = QWidget()
        mode_row_layout = QHBoxLayout(mode_row)
        mode_row_layout.setContentsMargins(0, 0, 0, 0)
        mode_row_layout.setSpacing(6)
        mode_row_layout.addWidget(self.mode_select)
        mode_row_layout.addWidget(self.mode_value_container)
        mode_row_layout.addStretch()

        layout.addRow("代理端口", self.port_input)
        layout.addRow("Web 端口", self.web_port_input)
        layout.addRow("启动方式", self.startup_mode_select)
        layout.addRow("模式", mode_row)
        layout.addRow("配置目录", self.config_dir_input)
        layout.addRow("证书路径", self.cert_path_input)
        layout.addRow("脚本路径", self.script_path_input)
        layout.addRow("", self.ssl_insecure_checkbox)
        layout.addRow("", self.web_open_browser_checkbox)
        layout.addRow("", self.web_show_in_app_checkbox)

        self.mode_select.currentTextChanged.connect(self._update_mode_value_state)
        self.startup_mode_select.currentTextChanged.connect(self._update_startup_mode_state)
        return box

    def _build_mock_group(self):
        box = QGroupBox("Mock 与请求改写")
        layout = QFormLayout(box)

        self.is_mock_checkbox = QCheckBox("启用 mock")
        self.mock_server_input = QLineEdit()
        self.headers_input = QTextEdit()
        self.headers_input.setMinimumHeight(90)
        self.body_input = QTextEdit()
        self.body_input.setMinimumHeight(90)

        layout.addRow("", self.is_mock_checkbox)
        layout.addRow("Mock 服务器", self.mock_server_input)
        layout.addRow("附加请求头", self.headers_input)
        layout.addRow("附加 Body", self.body_input)

        return box

    def _build_filter_group(self):
        box = QGroupBox("路径匹配")
        layout = QFormLayout(box)

        self.include_checkbox = QCheckBox("启用包含规则")
        self.exclude_checkbox = QCheckBox("启用排除规则")
        self.include_input = QTextEdit()
        self.include_input.setMinimumHeight(90)
        self.exclude_input = QTextEdit()
        self.exclude_input.setMinimumHeight(90)

        layout.addRow("", self.include_checkbox)
        layout.addRow("包含路径", self.include_input)
        layout.addRow("", self.exclude_checkbox)
        layout.addRow("排除路径", self.exclude_input)

        return box

    def _build_delay_group(self):
        box = QGroupBox("延迟配置")
        layout = QFormLayout(box)

        self.req_delay_enabled = QCheckBox("启用请求延迟")
        self.req_delay_input = QLineEdit()
        self.req_delay_paths = QTextEdit()
        self.req_delay_paths.setMinimumHeight(70)

        self.res_delay_enabled = QCheckBox("启用响应延迟")
        self.res_delay_input = QLineEdit()
        self.res_delay_paths = QTextEdit()
        self.res_delay_paths.setMinimumHeight(70)

        layout.addRow("", self.req_delay_enabled)
        layout.addRow("请求延迟秒数", self.req_delay_input)
        layout.addRow("请求延迟路径", self.req_delay_paths)
        layout.addRow("", self.res_delay_enabled)
        layout.addRow("响应延迟秒数", self.res_delay_input)
        layout.addRow("响应延迟路径", self.res_delay_paths)

        return box

    def _bind_data(self):
        d = self.config

        self.port_input.setText(str(d.port))
        self.web_port_input.setText(str(d.web_port))
        self.startup_mode_select.setCurrentText(
            str(getattr(d, "startup_mode", "dump") or "dump")
        )
        self.mode_select.setCurrentText(d.proxy_model)
        self.mode_value_input.set_value(d.proxy_model_value)
        self.config_dir_input.setText(d.mitmproxy_config_dir)
        self.cert_path_input.setText(d.cert_path)
        self.script_path_input.setText(d.script_path)
        self.ssl_insecure_checkbox.setChecked(d.ssl_insecure)
        self.web_open_browser_checkbox.setChecked(d.web_open_browser)
        self.web_show_in_app_checkbox.setChecked(
            bool(getattr(d, "web_show_in_app", True))
        )

        self.is_mock_checkbox.setChecked(d.is_mock)
        self.mock_server_input.setText(d.mock_server)
        self.headers_input.setPlainText(d.add_headers)
        self.body_input.setPlainText(d.add_body)

        self.include_checkbox.setChecked(d.open_include)
        self.exclude_checkbox.setChecked(d.open_exclude)
        self.include_input.setPlainText(d.include)
        self.exclude_input.setPlainText(d.exclude)

        self.req_delay_enabled.setChecked(d.request_delay.enabled)
        self.req_delay_input.setText(str(d.request_delay.delay))
        self.req_delay_paths.setPlainText("\n".join(d.request_delay.delay_path))

        self.res_delay_enabled.setChecked(d.response_delay.enabled)
        self.res_delay_input.setText(str(d.response_delay.delay))
        self.res_delay_paths.setPlainText("\n".join(d.response_delay.delay_path))

        self._update_mode_value_state(d.proxy_model)
        self._update_startup_mode_state(
            str(getattr(d, "startup_mode", "dump") or "dump")
        )

    def _update_mode_value_state(self, mode: str):
        is_local = mode == "local"
        self.mode_value_container.setVisible(is_local)

    def _update_startup_mode_state(self, mode: str):
        is_web = (mode or "").strip().lower() == "web"
        self.web_open_browser_checkbox.setEnabled(is_web)
        self.web_show_in_app_checkbox.setEnabled(is_web)

    def _save(self):
        try:
            self._saved_data = self._collect_data()
        except Exception as e:
            QMessageBox.warning(self, "配置错误", str(e))
            return

        self.accept()

    def _collect_data(self):
        data = self.config.model_dump()
        data.update(
            {
                "port": int(self.port_input.text()),
                "web_port": int(self.web_port_input.text()),
                "startup_mode": self.startup_mode_select.currentData(),
                "proxy_model": self.mode_select.currentText(),
                "proxy_model_value": self.mode_value_input.value(),
                "mitmproxy_config_dir": self.config_dir_input.text().strip(),
                "cert_path": self.cert_path_input.text().strip(),
                "script_path": self.script_path_input.text().strip(),
                "ssl_insecure": self.ssl_insecure_checkbox.isChecked(),
                "web_open_browser": self.web_open_browser_checkbox.isChecked(),
                "web_show_in_app": self.web_show_in_app_checkbox.isChecked(),
                "is_mock": self.is_mock_checkbox.isChecked(),
                "mock_server": self.mock_server_input.text().strip(),
                "add_headers": self.headers_input.toPlainText(),
                "add_body": self.body_input.toPlainText(),
                "open_include": self.include_checkbox.isChecked(),
                "open_exclude": self.exclude_checkbox.isChecked(),
                "include": self.include_input.toPlainText(),
                "exclude": self.exclude_input.toPlainText(),
                "request_delay": {
                    "enabled": self.req_delay_enabled.isChecked(),
                    "delay": float(self.req_delay_input.text() or 0),
                    "delay_path": self._parse_lines(self.req_delay_paths.toPlainText()),
                },
                "response_delay": {
                    "enabled": self.res_delay_enabled.isChecked(),
                    "delay": float(self.res_delay_input.text() or 0),
                    "delay_path": self._parse_lines(self.res_delay_paths.toPlainText()),
                },
            }
        )

        return data

    def get_data(self):
        return self._saved_data

    def _parse_lines(self, value: str) -> list[str]:
        items = []
        for line in value.splitlines():
            for part in line.split(","):
                part = part.strip()
                if part:
                    items.append(part)
        return items
