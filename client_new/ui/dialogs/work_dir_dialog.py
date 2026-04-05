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
from ui.utils.icon_util import apply_window_icon


class WorkDirDialog(QDialog):
    def __init__(self, parent=None, mode: str = "pos"):
        super().__init__(parent)
        self.mode = mode if mode in {"pos", "sqlite"} else "pos"

        self.setWindowTitle("SQLite 工作目录管理" if self.mode == "sqlite" else "工作目录管理")
        self.resize(500, 400)
        apply_window_icon(self)

        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        if self.mode == "sqlite":
            self.note_label.setText(
                "SQLite 页面复用工作目录和递归深度设置。扫描时按文件头识别，兼容 .sqlite / .sqlite3 / .db 等文件，不依赖扩展名。"
            )
        else:
            self.note_label.setText("配置 POS 扫描的文件名模式、目录模式和递归深度。")
        layout.addWidget(self.note_label)

        # 扫描配置（低频配置放到工作目录弹窗）
        self.file_pattern_input = QLineEdit()
        self.dir_pattern_input = QLineEdit()
        self.depth_input = QSpinBox()
        self.depth_input.setRange(1, 20)

        config_layout = QFormLayout()
        if self.mode != "sqlite":
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

        if self.mode != "sqlite":
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
        self._persist_config()
        QMessageBox.information(self, "成功", "扫描配置已保存")

    def accept(self):
        self._persist_config()
        super().accept()

    def _persist_config(self):
        cfg = SearchConfig.read()
        if self.mode != "sqlite":
            cfg.file_pattern = (self.file_pattern_input.text() or "cpos-*.exe").strip()
            cfg.dir_pattern = (self.dir_pattern_input.text() or "*").strip()
        cfg.max_depth = str(self.depth_input.value())
        SearchConfig.write(cfg)
