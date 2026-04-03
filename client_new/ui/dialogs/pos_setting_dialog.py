import json

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
from utils.common import get_active_mac, get_local_ip, kill_process_by_name
from utils.pos_network import (
    change_pos_from_network,
    pos_account_logout,
    pos_tool_init,
    reset_account_password,
    update_network_host,
)


class PosSettingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("POS设置")
        self.resize(1000, 700)

        self.config_data = PosConfig.read_pos_config()

        self._init_ui()
        self._bind_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

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
        try:
            PosConfig.save_pos_config(self.config_data)
            update_network_host(self.config_data)

            QMessageBox.information(self, "成功", "POS配置保存成功")

        except Exception as e:
            QMessageBox.critical(self, "失败", f"POS配置保存失败：{str(e)}")
