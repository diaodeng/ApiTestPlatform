import json
import os

from loguru import logger
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from controller.pos_controller import PosController
from models.pos_state import PosChangeState
from server.config import PosConfig
from server.pos_tool_config_server import PosToolConfigServer
from ui.widgets.env_vendor_store_selector import EnvVendorStoreSelector
from utils.common import get_active_mac, get_local_ip


class ChangePosDialog(QDialog):
    STATE_PATH = "storage/data/pos_change_state.json"

    def __init__(self, parent=None, pos_path: str = ""):
        super().__init__(parent)

        self.setWindowTitle("在线切换POS")
        self.pos_path = pos_path

        self.controller = PosController()
        self.config = None

        self.state = PosChangeState(pos_mac=get_active_mac(), pos_ip=get_local_ip())
        self._load_last_state()
        self._fill_from_pos_path()

        self._init_ui()
        self._apply_state_to_ui()
        self._on_mode_change()
        QTimer.singleShot(0, self._load_selector_config)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # 三级联动
        self.selector = EnvVendorStoreSelector(None)
        form.addRow("环境/商家/门店", self.selector)

        # 模式
        self.switch_combo = QComboBox()
        self.switch_combo.addItem("指定MAC", "1")
        self.switch_combo.addItem("指定POS_ID", "2")
        form.addRow("模式", self.switch_combo)

        # 输入
        self.mac_input = QLineEdit(self.state.pos_mac)
        self.pos_input = QLineEdit()
        self.pos_row_label = QLabel("POS_ID")

        self.ip_input = QLineEdit(self.state.pos_ip)
        self.pos_type_combo = QComboBox()
        self.pos_type_combo.addItem("人工收银", "1")
        self.pos_type_combo.addItem("SCO", "2")
        self.pos_type_combo.addItem("Combined", "4")
        self.pos_group_input = QLineEdit()
        self.pos_group_input.setPlaceholderText("POS机台组(可选)")

        form.addRow(self.pos_row_label, self.pos_input)
        form.addRow("MAC", self.mac_input)
        form.addRow("IP", self.ip_input)
        form.addRow("POS类型", self.pos_type_combo)
        form.addRow("POS机台组", self.pos_group_input)

        layout.addLayout(form)

        # 按钮
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)

        layout.addWidget(self.buttons)

        self.switch_combo.currentIndexChanged.connect(self._on_mode_change)
        self.selector.env_combo.currentIndexChanged.connect(self._persist_state)
        self.selector.vendor_combo.currentIndexChanged.connect(self._persist_state)
        self.selector.store_combo.currentIndexChanged.connect(self._persist_state)
        self.mac_input.editingFinished.connect(self._persist_state)
        self.pos_input.editingFinished.connect(self._persist_state)
        self.ip_input.editingFinished.connect(self._persist_state)
        self.pos_type_combo.currentIndexChanged.connect(self._persist_state)
        self.pos_group_input.editingFinished.connect(self._persist_state)

        self.controller.status_signal.connect(self._on_status)
        # self.controller.log_signal.connect(self._on_log)

    def _load_selector_config(self):
        try:
            self.config = PosToolConfigServer.read_pos_tool_config()
        except Exception as exc:
            logger.warning(f"加载POS切换配置失败: {exc}")
            self.config = None

        if hasattr(self, "selector"):
            self.selector.set_config(self.config)
            self._apply_state_to_ui()

    def _on_mode_change(self):
        mode = self.switch_combo.currentData()
        show_pos = mode != "1"
        self.pos_row_label.setVisible(show_pos)
        self.pos_input.setVisible(show_pos)
        self._persist_state()

    def _collect(self):
        selector_data = self.selector.get_value()

        return {
            "env": selector_data["env"],
            "venderId": selector_data["vendor_id"],
            "orgNo": selector_data["store_id"],
            "switchMode": self.switch_combo.currentData(),
            "pos_mac": self.mac_input.text(),
            "pos_no": self.pos_input.text(),
            "pos_ip": self.ip_input.text(),
            "pos_type": self.pos_type_combo.currentData(),
            "pos_group": self.pos_group_input.text().strip(),
        }

    def submit(self):
        data = self._collect()
        self._persist_state()

        self.buttons.setDisabled(True)

        self.controller.change_pos(data)

    def _on_success(self, _):
        QMessageBox.information(self, "成功", "POS切换成功")
        self.accept()

    def _on_error(self, msg):
        QMessageBox.critical(self, "错误", msg)
        self.buttons.setDisabled(False)

    def _on_status(self, msg):
        if "成功" in msg:
            self._persist_state()
            QMessageBox.information(self, "成功", msg)
            self.accept()
        elif "错误" in msg:
            QMessageBox.critical(self, "错误", msg)
            self.buttons.setDisabled(False)
        else:
            # 可以做 loading 提示
            print(msg)

    def _apply_state_to_ui(self):
        if self.state.switch_mode == "2":
            self.switch_combo.setCurrentIndex(1)
        else:
            self.switch_combo.setCurrentIndex(0)
        self.mac_input.setText(self.state.pos_mac or "")
        self.pos_input.setText(self.state.pos_no or "")
        self.ip_input.setText(self.state.pos_ip or "")
        idx_type = self.pos_type_combo.findData(self.state.pos_type or "1")
        self.pos_type_combo.setCurrentIndex(idx_type if idx_type >= 0 else 0)
        self.pos_group_input.setText(self.state.pos_group or "")

        self.selector.set_value(
            self.state.env, self.state.vendor_id, self.state.store_id
        )

    def _persist_state(self):
        data = self._collect()
        state = {
            "env": data.get("env") or "",
            "vendor_id": data.get("venderId") or "",
            "store_id": data.get("orgNo") or "",
            "switch_mode": data.get("switchMode") or "1",
            "pos_mac": data.get("pos_mac") or "",
            "pos_no": data.get("pos_no") or "",
            "pos_ip": data.get("pos_ip") or "",
            "pos_type": data.get("pos_type") or "1",
            "pos_group": data.get("pos_group") or "",
        }
        os.makedirs(os.path.dirname(self.STATE_PATH), exist_ok=True)
        with open(self.STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _load_last_state(self):
        if not os.path.exists(self.STATE_PATH):
            return
        try:
            with open(self.STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.state.env = data.get("env") or None
            self.state.vendor_id = data.get("vendor_id") or None
            self.state.store_id = data.get("store_id") or None
            self.state.switch_mode = data.get("switch_mode") or "1"
            self.state.pos_mac = self.state.pos_mac or data.get("pos_mac")
            self.state.pos_no = data.get("pos_no") or ""
            self.state.pos_ip = self.state.pos_ip or data.get("pos_ip")
            self.state.pos_type = data.get("pos_type") or "1"
            self.state.pos_group = data.get("pos_group") or ""
        except Exception:
            pass

    def _fill_from_pos_path(self):
        if not self.pos_path:
            return
        try:
            params = PosConfig.read_pos_params(self.pos_path, 1)
            env = PosConfig.get_local_pos_env(self.pos_path) or ""
            if params:
                self.state.vendor_id = str(params.venderNo or "")
                self.state.store_id = str(params.orgNo or "")
                self.state.pos_no = str(params.posId or "")
                self.state.pos_group = str(params.posGroupNo or "")
                self.state.pos_type = str(params.posType or "1")
            if env:
                group, _ = (
                    PosConfig.get_pos_group(str(params.venderNo or ""), env)
                    if params
                    else (None, None)
                )
                if group:
                    self.state.env = group
        except Exception:
            pass
