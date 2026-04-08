import json

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
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

from model.config import (
    PosChangeParamsModel,
    PosConfigModel,
    PosParamsModel,
    VendorConfigModel,
)
from model.pos_network_model import (
    PosInitRespModel,
    PosLogoutModel,
    PosResetAccountRequestModel,
)
from server.config import PosConfig
from server.pos_tool_config_server import PosToolConfigServer
from server.remote_config_server import RemoteConfigServer
from utils.common import get_active_mac, get_local_ip, kill_process_by_name
from utils.pos_network import (
    change_pos_from_network,
    pos_account_logout,
    pos_tool_init,
    reset_account_password,
    update_network_host,
)


class _PosConfigSyncThread(QThread):
    done = Signal(bool, object, str)

    def __init__(self, config_url: str):
        super().__init__()
        self.config_url = (config_url or "").strip()

    def run(self):
        try:
            result = RemoteConfigServer.sync_pos_config(self.config_url)
            self.done.emit(True, result, "")
        except Exception as e:
            self.done.emit(False, None, str(e))


class PosSettingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("POS设置")
        self.resize(1000, 700)

        self.config_data = PosConfig.read_pos_config()
        self._original_sync_url = (self.config_data.config_sync_url or "").strip()
        self._field_widgets: dict[str, QLineEdit | QTextEdit] = {}
        self._sync_thread: _PosConfigSyncThread | None = None

        self._init_ui()
        self._bind_data()
        self._apply_sync_state(self.config_data)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        sync_layout = QHBoxLayout()
        sync_layout.addWidget(QLabel("配置拉取地址"))
        self.config_sync_url_input = QLineEdit(self.config_data.config_sync_url or "")
        self.config_sync_url_input.setClearButtonEnabled(True)
        self.config_sync_url_input.setPlaceholderText(
            "输入 HTTP 配置拉取地址，例如: http://127.0.0.1:9099/qtr/agent/bootstrap/config/agent_pos_config"
        )
        self.sync_config_btn = QPushButton("更新配置")
        sync_layout.addWidget(self.config_sync_url_input, 1)
        sync_layout.addWidget(self.sync_config_btn)

        sync_status_layout = QHBoxLayout()
        sync_status_layout.addWidget(QLabel("同步状态"))
        self.sync_status_label = QLabel("未同步")
        self.sync_status_label.setWordWrap(True)
        sync_status_layout.addWidget(self.sync_status_label, 1)

        main_layout.addLayout(sync_layout)
        main_layout.addLayout(sync_status_layout)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        self.form_layout = QVBoxLayout(container)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_close = QPushButton("关闭")
        self.btn_save = QPushButton("保存")

        btn_layout.addWidget(self.btn_close)
        btn_layout.addWidget(self.btn_save)

        self.btn_close.clicked.connect(self.close)
        self.btn_save.clicked.connect(self._save)
        self.sync_config_btn.clicked.connect(self._sync_remote_config)
        self.config_sync_url_input.editingFinished.connect(
            lambda: self._on_change("config_sync_url", self.config_sync_url_input.text())
        )

        main_layout.addLayout(btn_layout)

    def _add_input(self, label, key, value, multiline=False):
        label_widget = QLabel(label)

        if multiline:
            input_widget = QTextEdit()
            input_widget.setPlainText(value)
            input_widget.focusOutEvent = lambda e, k=key, w=input_widget: (
                self._on_change(k, w.toPlainText())
            )
        else:
            input_widget = QLineEdit()
            input_widget.setText(value)
            input_widget.editingFinished.connect(
                lambda k=key, w=input_widget: self._on_change(k, w.text())
            )

        self._field_widgets[key] = input_widget
        self.form_layout.addWidget(label_widget)
        self.form_layout.addWidget(input_widget)

    def _bind_data(self):
        d = self.config_data

        self._add_input("Tbox测试环境host", "pos_tool_test_host", d.pos_tool_test_host)
        self._add_input("Tbox UAT host", "pos_tool_uat_host", d.pos_tool_uat_host)
        self._add_input("POS TEST接口host", "pos_test_host", d.pos_test_host)
        self._add_input("POS UAT接口host", "pos_uat_host", d.pos_uat_host)
        self._add_input("POS PRO接口host", "pos_pro_host", d.pos_pro_host)

        self._add_input(
            "支付MOCK驱动目录", "payment_mock_driver_path", d.payment_mock_driver_path
        )
        self._add_input(
            "支付驱动备份目录",
            "payment_driver_back_up_path",
            d.payment_driver_back_up_path,
        )

        self._add_input(
            "环境文件",
            "env_files",
            json.dumps(d.env_files, indent=4, ensure_ascii=False),
            multiline=True,
        )

        self._add_input(
            "缓存文件",
            "cache_files",
            json.dumps(d.cache_files, indent=4, ensure_ascii=False),
            multiline=True,
        )

        self._add_input(
            "商家分组",
            "env_group_vendor",
            json.dumps(d.env_group_vendor, indent=4, ensure_ascii=False),
            multiline=True,
        )

        self._add_input(
            "商家POS账号",
            "vendor_config",
            json.dumps(
                [i.model_dump() for i in d.vendor_config], indent=4, ensure_ascii=False
            ),
            multiline=True,
        )

    def _on_change(self, key, value):
        try:
            if key in [
                "payment_mock_driver_path",
                "payment_driver_back_up_path",
                "pos_tool_test_host",
                "pos_tool_uat_host",
                "pos_test_host",
                "pos_uat_host",
                "pos_pro_host",
                "config_sync_url",
            ]:
                setattr(self.config_data, key, value)

            elif key == "vendor_config":
                if not value:
                    self.config_data.vendor_config = []
                    return
                data = json.loads(value)
                self.config_data.vendor_config = [
                    VendorConfigModel.model_validate(i) for i in data
                ]

            else:
                setattr(self.config_data, key, json.loads(value))

        except Exception as e:
            QMessageBox.warning(self, "格式错误", f"{key} 解析失败：{str(e)}")

    def _save(self):
        if not self._persist_config(show_success=True):
            return
        self._apply_sync_state(self.config_data)

    def _persist_config(self, show_success: bool = False) -> bool:
        try:
            self._on_change("config_sync_url", self.config_sync_url_input.text())
            if (self.config_data.config_sync_url or "").strip() != self._original_sync_url:
                self.config_data.config_sync_initialized = False
                self.config_data.config_sync_last_sync_at = ""
            PosConfig.save_pos_config(self.config_data)
            self._original_sync_url = (self.config_data.config_sync_url or "").strip()
            update_network_host(self.config_data)
            if show_success:
                QMessageBox.information(self, "成功", "POS配置保存成功")
            return True
        except Exception as e:
            QMessageBox.critical(self, "失败", f"POS配置保存失败：{str(e)}")
            return False

    def _sync_remote_config(self):
        if self._sync_thread and self._sync_thread.isRunning():
            return

        self._on_change("config_sync_url", self.config_sync_url_input.text())
        config_url = (self.config_data.config_sync_url or "").strip()
        if not config_url:
            self.set_sync_status_text("请先填写配置拉取地址")
            return

        if not self._persist_config(show_success=False):
            return

        self.set_config_syncing(True)
        self.set_sync_status_text("正在更新 POS 配置...", config_url)

        self._sync_thread = _PosConfigSyncThread(config_url)
        self._sync_thread.done.connect(self._on_sync_done)
        self._sync_thread.finished.connect(self._on_sync_finished)
        self._sync_thread.start()

    def _on_sync_done(self, success: bool, result: object, message: str):
        if success and isinstance(result, dict):
            merged_config = result.get("merged_config")
            if isinstance(merged_config, PosConfigModel):
                self.config_data = merged_config.model_copy(deep=True)
            else:
                self.config_data = PosConfig.read_pos_config()
            self._refresh_form_values()
            self._apply_sync_state(self.config_data)
            return

        self.set_sync_status_text(f"更新失败: {message}", self.config_data.config_sync_url)

    def _on_sync_finished(self):
        self.set_config_syncing(False)
        self._sync_thread = None

    def _refresh_form_values(self):
        d = self.config_data
        self.config_sync_url_input.setText(d.config_sync_url or "")
        self._set_field_value("pos_tool_test_host", d.pos_tool_test_host)
        self._set_field_value("pos_tool_uat_host", d.pos_tool_uat_host)
        self._set_field_value("pos_test_host", d.pos_test_host)
        self._set_field_value("pos_uat_host", d.pos_uat_host)
        self._set_field_value("pos_pro_host", d.pos_pro_host)
        self._set_field_value("payment_mock_driver_path", d.payment_mock_driver_path)
        self._set_field_value("payment_driver_back_up_path", d.payment_driver_back_up_path)
        self._set_field_value(
            "env_files",
            json.dumps(d.env_files, indent=4, ensure_ascii=False),
        )
        self._set_field_value(
            "cache_files",
            json.dumps(d.cache_files, indent=4, ensure_ascii=False),
        )
        self._set_field_value(
            "env_group_vendor",
            json.dumps(d.env_group_vendor, indent=4, ensure_ascii=False),
        )
        self._set_field_value(
            "vendor_config",
            json.dumps(
                [i.model_dump() for i in d.vendor_config], indent=4, ensure_ascii=False
            ),
        )

    def _set_field_value(self, key: str, value: str):
        widget = self._field_widgets.get(key)
        if widget is None:
            return
        if isinstance(widget, QTextEdit):
            widget.setPlainText(value)
            return
        widget.setText(value)

    def _apply_sync_state(self, config: PosConfigModel):
        sync_url = (getattr(config, "config_sync_url", "") or "").strip()
        if getattr(config, "config_sync_initialized", False):
            text = "已同步"
            sync_at = str(getattr(config, "config_sync_last_sync_at", "") or "").strip()
            if sync_at:
                text = f"{text} {sync_at}"
        else:
            text = "未同步"
        self.set_sync_status_text(text, sync_url)

    def set_sync_status_text(self, text: str, tooltip: str = ""):
        self.sync_status_label.setText(text or "-")
        self.sync_status_label.setToolTip((tooltip or "").strip())

    def set_config_syncing(self, syncing: bool):
        self.sync_config_btn.setEnabled(not syncing)
        self.sync_config_btn.setText("更新中..." if syncing else "更新配置")
        self.btn_save.setEnabled(not syncing)
        self.btn_close.setEnabled(not syncing)

    def reject(self):
        if self._sync_thread and self._sync_thread.isRunning():
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent):
        if self._sync_thread and self._sync_thread.isRunning():
            event.ignore()
            return
        super().closeEvent(event)
