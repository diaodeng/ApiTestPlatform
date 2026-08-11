from PySide6.QtWidgets import QComboBox, QVBoxLayout, QWidget


class EnvVendorStoreSelector(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)

        self.config = config

        self.env_combo = QComboBox()
        self.vendor_combo = QComboBox()
        self.store_combo = QComboBox()

        layout = QVBoxLayout(self)
        layout.addWidget(self.env_combo)
        layout.addWidget(self.vendor_combo)
        layout.addWidget(self.store_combo)

        self._init_data()
        self._bind()

    def _init_data(self):
        self.env_combo.blockSignals(True)
        self.vendor_combo.blockSignals(True)
        self.store_combo.blockSignals(True)
        self.env_combo.clear()
        env_list = []
        if self.config and getattr(self.config, "data", None):
            env_list = getattr(self.config.data, "env_list", []) or []

        for item in env_list:
            self.env_combo.addItem(item.env_name, item.env_code)

        if self.env_combo.count() > 0:
            self._refresh_vendor()
        else:
            self.vendor_combo.clear()
            self.store_combo.clear()

        self.env_combo.blockSignals(False)
        self.vendor_combo.blockSignals(False)
        self.store_combo.blockSignals(False)

    def _bind(self):
        self.env_combo.currentIndexChanged.connect(self._refresh_vendor)
        self.vendor_combo.currentIndexChanged.connect(self._refresh_store)

    def _refresh_vendor(self):
        self.vendor_combo.blockSignals(True)
        self.store_combo.blockSignals(True)
        self.vendor_combo.clear()
        env = self.env_combo.currentData()
        store_list = []
        if self.config and getattr(self.config, "data", None):
            store_list = getattr(self.config.data, "store_list", []) or []

        vendors = {}
        for item in store_list:
            if item.env == env:
                vendors[item.vender_id] = item.vender_name

        for k, v in sorted(vendors.items()):
            self.vendor_combo.addItem(v, k)

        self._refresh_store()
        self.vendor_combo.blockSignals(False)
        self.store_combo.blockSignals(False)

    def _refresh_store(self):
        self.store_combo.blockSignals(True)
        self.store_combo.clear()
        store_list = []
        if self.config and getattr(self.config, "data", None):
            store_list = getattr(self.config.data, "store_list", []) or []

        env = self.env_combo.currentData()
        vendor = self.vendor_combo.currentData()

        for item in store_list:
            if item.env == env and item.vender_id == vendor:
                self.store_combo.addItem(item.store_name, item.store_id)
        self.store_combo.blockSignals(False)

    def set_config(self, config):
        self.config = config
        self._init_data()
        if self.config and getattr(self.config, "data", None):
            self.set_value(None, None, None)

    def set_value(self, env: str | None, vendor_id: str | None, store_id: str | None):
        if env:
            idx = self.env_combo.findData(env)
            if idx >= 0:
                self.env_combo.setCurrentIndex(idx)

        if vendor_id:
            idx = self.vendor_combo.findData(vendor_id)
            if idx >= 0:
                self.vendor_combo.setCurrentIndex(idx)

        if store_id:
            idx = self.store_combo.findData(store_id)
            if idx >= 0:
                self.store_combo.setCurrentIndex(idx)

    def get_value(self):
        return {
            "env": self.env_combo.currentData(),
            "vendor_id": self.vendor_combo.currentData(),
            "store_id": self.store_combo.currentData(),
        }
