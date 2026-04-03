import asyncio

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from model.pos_network_model import PosLogoutModel, PosResetAccountRequestModel
from server.config import PosConfig
from server.pos_tool_config_server import PosToolConfigServer
from utils.pos_network import pos_account_logout, reset_account_password
from workers.worker import Worker


class PosAccountDialog(QDialog):
    def __init__(self, parent=None, pos_path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("POS账号处理")
        self.resize(520, 220)
        self.pool = QThreadPool.globalInstance()
        self.config = PosToolConfigServer.read_pos_tool_config()
        self.pos_path = pos_path

        self._init_ui()
        self._fill_default()

    def _init_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.env_combo = QComboBox()
        for item in self.config.data.env_list:
            self.env_combo.addItem(item.env_name, item.env_code)

        self.cashier_input = QLineEdit()
        self.cashier_input.setPlaceholderText("收银员账号")

        form.addRow("环境", self.env_combo)
        form.addRow("收银员账号", self.cashier_input)
        root.addLayout(form)

        btn_layout = QHBoxLayout()
        self.btn_logout = QPushButton("退出账号")
        self.btn_reset = QPushButton("重置密码")
        self.btn_close = QPushButton("关闭")
        btn_layout.addWidget(self.btn_logout)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        root.addLayout(btn_layout)

        self.btn_logout.clicked.connect(self._logout)
        self.btn_reset.clicked.connect(self._reset_password)
        self.btn_close.clicked.connect(self.accept)

    def _fill_default(self):
        if not self.pos_path:
            return
        try:
            pos_params = PosConfig.read_pos_params(self.pos_path, 1)
            pos_env = PosConfig.get_local_pos_env(self.pos_path)
            vendor_id = str(pos_params.venderNo or "") if pos_params else ""
            env_group, account = PosConfig.get_pos_group(vendor_id, pos_env)

            if env_group:
                idx = self.env_combo.findData(env_group)
                if idx >= 0:
                    self.env_combo.setCurrentIndex(idx)
            if account:
                self.cashier_input.setText(str(account))
        except Exception:
            pass

    def _collect_data(self):
        cashier = (self.cashier_input.text() or "").strip()
        return {
            "env": self.env_combo.currentData() or "",
            "cashierNo": cashier,
        }

    def _set_busy(self, busy: bool):
        self.btn_logout.setEnabled(not busy)
        self.btn_reset.setEnabled(not busy)
        self.btn_close.setEnabled(not busy)

    def _logout(self):
        data = self._collect_data()
        if not data["env"] or not data["cashierNo"]:
            QMessageBox.warning(self, "提示", "环境和收银员账号不能为空")
            return

        self._set_busy(True)

        def run():
            req = PosLogoutModel(env=data["env"], cashierNo=data["cashierNo"])
            return pos_account_logout(req)

        worker = Worker(run)
        worker.signals.finished.connect(self._on_logout_done)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_logout_done(self, result):
        ok, msg = result
        self._set_busy(False)
        if ok:
            QMessageBox.information(self, "成功", msg or "退出账号成功")
        else:
            QMessageBox.critical(self, "失败", msg or "退出账号失败")

    def _reset_password(self):
        data = self._collect_data()
        if not data["env"] or not data["cashierNo"]:
            QMessageBox.warning(self, "提示", "环境和收银员账号不能为空")
            return

        self._set_busy(True)

        def run():
            req = PosResetAccountRequestModel(
                env=data["env"],
                cashierNo=data["cashierNo"],
            )
            return asyncio.run(reset_account_password(req))

        worker = Worker(run)
        worker.signals.finished.connect(self._on_reset_done)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_reset_done(self, result):
        ok, msg = result
        self._set_busy(False)
        if ok:
            QMessageBox.information(self, "成功", msg or "重置密码成功")
        else:
            QMessageBox.critical(self, "失败", msg or "重置密码失败")

    def _on_error(self, err: str):
        self._set_busy(False)
        QMessageBox.critical(self, "错误", str(err))
