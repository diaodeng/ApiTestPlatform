import os

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from model.config import PosConfigModel, PosParamsModel
from server.config import PosConfig
from server.pos_tool_config_server import PosToolConfigServer
from utils.common import kill_process_by_name


class LocalEnvDialog(QDialog):
    def __init__(self, pos_path: str, parent=None):
        super().__init__(parent)
        self.pos_path = pos_path
        self.setWindowTitle("切换本地环境")
        self.resize(520, 240)

        self.config = PosToolConfigServer.read_pos_tool_config()
        self._init_ui()
        self._load_current()
        self._load_backed_envs()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.current_env_view = QPlainTextEdit()
        self.current_env_view.setReadOnly(True)
        self.current_env_view.setFixedHeight(66)

        self.backed_env_combo = QComboBox()
        self.backed_env_combo.setEditable(False)

        form.addRow("当前环境", self.current_env_view)
        form.addRow("已备份环境", self.backed_env_combo)
        layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _load_current(self):
        self.current_env_view.setPlainText(self._get_current_env_info())

    def _load_backed_envs(self):
        self.backed_env_combo.clear()
        env_map = self._get_backed_env_map()
        for key, text in env_map.items():
            self.backed_env_combo.addItem(text, key)

    def _submit(self):
        target_env = self.backed_env_combo.currentData()
        if not target_env:
            QMessageBox.warning(self, "提示", "请先选择目标环境")
            return

        try:
            kill_process_by_name("CPOS-DF.exe")
        except Exception:
            pass

        ok, msg = PosConfig.change_pos_local_env(self.pos_path, target_env)
        if ok:
            QMessageBox.information(self, "成功", msg or "切换成功")
            self._load_current()
            self._load_backed_envs()
        else:
            QMessageBox.critical(self, "失败", msg or "切换失败")

    def _get_current_env_info(self) -> str:
        local_pos_env = PosConfig.get_local_pos_env(self.pos_path) or "-"
        pos_params = PosConfig.read_pos_params(self.pos_path, 1)
        if pos_params and isinstance(pos_params, PosParamsModel):
            env_local = "本地环境" if pos_params.is_local else "远端环境"
            env_group, _ = PosConfig.get_pos_group(pos_params.venderNo, local_pos_env)
            try:
                for store_info in self.config.data.store_list:
                    if (
                        store_info.vender_id == pos_params.venderNo
                        and store_info.env == env_group
                        and store_info.store_id == pos_params.orgNo
                    ):
                        return (
                            f"{env_local} {local_pos_env} -> {store_info.vender_name} -> "
                            f"{store_info.store_name} -> POS:{pos_params.posId}"
                        )
            except Exception:
                pass
            return (
                f"{env_local} 环境:{local_pos_env} 商家:{pos_params.venderNo} "
                f"门店:{pos_params.orgNo} POS:{pos_params.posId}"
            )
        return f"环境:{local_pos_env}，商家:无，门店:无"

    def _get_backed_env_map(self) -> dict[str, str]:
        cfg: PosConfigModel = PosConfig.read_pos_config()
        backed_env = ["RTA_TEST", "RTA_UAT", "RTA"]
        back_dir = os.path.join(os.path.dirname(self.pos_path), "pos_env_back")
        if os.path.exists(back_dir):
            subdirs = []
            for item in os.listdir(back_dir):
                item_path = os.path.join(back_dir, item)
                if os.path.isdir(item_path):
                    subdirs.append(item)
            subdirs.sort()
            backed_env.extend(subdirs)

        # 历史配置中记录过的环境也保留
        if cfg.backup_envs and self.pos_path in cfg.backup_envs:
            for e in cfg.backup_envs.get(self.pos_path, []):
                if e not in backed_env:
                    backed_env.append(e)

        env_map = {e: e for e in backed_env}
        current_enriched = {}
        for key in backed_env:
            parts = key.split("_")
            if len(parts) <= 2:
                continue
            current_env = "_".join(parts[:-2])
            vendor_id = parts[-2]
            store = parts[-1]
            env_group, _ = PosConfig.get_pos_group(vendor_id, current_env)
            for store_info in self.config.data.store_list:
                if (
                    store_info.vender_id == vendor_id
                    and store_info.env == env_group
                    and store_info.store_id == store
                ):
                    current_enriched[key] = (
                        f"{key} -> {store_info.vender_name} -> {store_info.store_name}"
                    )
                    break
        env_map.update(current_enriched)
        return env_map
