from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from server.config import SearchConfig


class WorkDirDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("工作目录管理")
        self.resize(500, 400)

        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 扫描配置（低频配置放到工作目录弹窗）
        self.file_pattern_input = QLineEdit()
        self.dir_pattern_input = QLineEdit()
        self.depth_input = QSpinBox()
        self.depth_input.setRange(1, 20)

        config_layout = QFormLayout()
        config_layout.addRow(QLabel("文件名模式"), self.file_pattern_input)
        config_layout.addRow(QLabel("目录名模式"), self.dir_pattern_input)
        config_layout.addRow(QLabel("递归深度"), self.depth_input)
        layout.addLayout(config_layout)

        # 列表
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # 按钮
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("添加目录")
        self.remove_btn = QPushButton("删除选中")
        self.save_btn = QPushButton("保存配置")
        self.close_btn = QPushButton("关闭")

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        # 绑定
        self.add_btn.clicked.connect(self.add_dir)
        self.remove_btn.clicked.connect(self.remove_dir)
        self.save_btn.clicked.connect(self.save_scan_config)
        self.close_btn.clicked.connect(self.accept)

    def _load_data(self):
        self.list_widget.clear()
        dirs = SearchConfig.read_work_dir()
        cfg = SearchConfig.read()

        self.file_pattern_input.setText(cfg.file_pattern or "cpos-*.exe")
        self.dir_pattern_input.setText(cfg.dir_pattern or "*")
        try:
            self.depth_input.setValue(max(1, int(cfg.max_depth)))
        except Exception:
            self.depth_input.setValue(3)

        for d in dirs:
            self.list_widget.addItem(d)

    def add_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择目录")
        if not dir_path:
            return

        # 去重
        dirs = SearchConfig.read_work_dir()
        if dir_path in dirs:
            QMessageBox.warning(self, "提示", "目录已存在")
            return

        SearchConfig.add_work_dir(dir_path)
        self._load_data()

    def remove_dir(self):
        item = self.list_widget.currentItem()
        if not item:
            return

        dir_path = item.text()

        SearchConfig.remove_work_dir(dir_path)
        self._load_data()

    def save_scan_config(self):
        cfg = SearchConfig.read()
        cfg.file_pattern = (self.file_pattern_input.text() or "cpos-*.exe").strip()
        cfg.dir_pattern = (self.dir_pattern_input.text() or "*").strip()
        cfg.max_depth = str(self.depth_input.value())
        SearchConfig.write(cfg)
        QMessageBox.information(self, "成功", "扫描配置已保存")

    def accept(self):
        cfg = SearchConfig.read()
        cfg.file_pattern = (self.file_pattern_input.text() or "cpos-*.exe").strip()
        cfg.dir_pattern = (self.dir_pattern_input.text() or "*").strip()
        cfg.max_depth = str(self.depth_input.value())
        SearchConfig.write(cfg)
        super().accept()
