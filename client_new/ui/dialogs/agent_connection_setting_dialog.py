from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class AgentConnectionSettingDialog(QDialog):
    """
    Agent 连接参数设置弹窗。

    收敛 Agent 页面顶栏的低频配置项（单条消息发送上限、断线重连策略），
    页面顶栏只保留高频操作；弹窗内按“主开关联动子项”展示：
    未勾选自动重试时重试次数/间隔禁用，未勾选低频永续重连时低频间隔禁用。
    """

    def __init__(self, values: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("连接设置")
        self.setMinimumWidth(460)
        self._saved_data: dict | None = None

        self._init_ui()
        self._bind()
        self.set_values(values or {})

    def _init_ui(self):
        layout = QVBoxLayout(self)

        tip = QLabel(
            "发送上限保存后立即生效；重连参数在下次连接或重连时生效。"
            "高频重试用尽后会按低频间隔继续重连，直到手动停止。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #4a5568;")
        layout.addWidget(tip)

        send_box = QGroupBox("发送")
        send_form = QFormLayout(send_box)
        self.max_send_size_input = QSpinBox()
        self.max_send_size_input.setRange(1, 1024 * 1024)
        self.max_send_size_input.setSuffix(" KB")
        self.max_send_size_input.setToolTip("单条日志/消息发送给服务端的最大体积，超过会被拆分或截断")
        send_form.addRow("单条消息上限", self.max_send_size_input)
        layout.addWidget(send_box)

        retry_box = QGroupBox("断线重连")
        retry_form = QFormLayout(retry_box)

        self.retry_checkbox = QCheckBox("连接失败后自动重试")
        self.retry_times_input = QSpinBox()
        self.retry_times_input.setRange(0, 999)
        self.retry_times_input.setToolTip("高频重试窗口的最大次数，0 表示不重试")
        self.retry_interval_input = QDoubleSpinBox()
        self.retry_interval_input.setRange(0.1, 3600.0)
        self.retry_interval_input.setDecimals(1)
        self.retry_interval_input.setSingleStep(0.5)
        self.retry_interval_input.setSuffix(" s")
        self.retry_interval_input.setToolTip("高频重试窗口内的重试间隔")

        self.retry_forever_checkbox = QCheckBox("高频重试用尽后低频永续重连")
        self.retry_forever_interval_input = QDoubleSpinBox()
        self.retry_forever_interval_input.setRange(1.0, 86400.0)
        self.retry_forever_interval_input.setDecimals(0)
        self.retry_forever_interval_input.setSingleStep(30.0)
        self.retry_forever_interval_input.setSuffix(" s")
        self.retry_forever_interval_input.setToolTip("低频永续重连的间隔，直到手动停止为止")

        retry_form.addRow(self.retry_checkbox)
        retry_form.addRow("重试次数", self.retry_times_input)
        retry_form.addRow("重试间隔", self.retry_interval_input)
        retry_form.addRow(self.retry_forever_checkbox)
        retry_form.addRow("低频间隔", self.retry_forever_interval_input)
        layout.addWidget(retry_box)

        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _bind(self):
        # 主开关联动：未启用的重连方式其子参数一并禁用，避免无效配置项干扰
        self.retry_checkbox.toggled.connect(self._update_retry_enabled)
        self.retry_forever_checkbox.toggled.connect(self._update_forever_enabled)

    def _update_retry_enabled(self):
        enabled = self.retry_checkbox.isChecked()
        self.retry_times_input.setEnabled(enabled)
        self.retry_interval_input.setEnabled(enabled)

    def _update_forever_enabled(self):
        self.retry_forever_interval_input.setEnabled(
            self.retry_forever_checkbox.isChecked()
        )

    def set_values(self, values: dict):
        """
        将页面当前配置渲染到弹窗控件。

        :param values: 配置键值，支持 max_send_size_kb/retry/retry_times/
            retry_interval/retry_forever/retry_forever_interval。
        """
        self.max_send_size_input.setValue(max(1, int(values.get("max_send_size_kb", 5) or 5)))
        self.retry_checkbox.setChecked(bool(values.get("retry", False)))
        self.retry_times_input.setValue(int(values.get("retry_times", 0) or 0))
        self.retry_interval_input.setValue(float(values.get("retry_interval", 5) or 5))
        self.retry_forever_checkbox.setChecked(bool(values.get("retry_forever", False)))
        self.retry_forever_interval_input.setValue(
            float(values.get("retry_forever_interval", 300) or 300)
        )
        self._update_retry_enabled()
        self._update_forever_enabled()

    def _save(self):
        """
        保存配置并关闭弹窗。
        """
        self._saved_data = {
            "max_send_size_kb": int(self.max_send_size_input.value()),
            "retry": self.retry_checkbox.isChecked(),
            "retry_times": int(self.retry_times_input.value()),
            "retry_interval": float(self.retry_interval_input.value()),
            "retry_forever": self.retry_forever_checkbox.isChecked(),
            "retry_forever_interval": float(self.retry_forever_interval_input.value()),
        }
        self.accept()

    def get_data(self) -> dict | None:
        """
        获取用户点击保存后的配置结果。

        :return: 保存后的配置字典，未保存时返回 None。
        """
        return self._saved_data
