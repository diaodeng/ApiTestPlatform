from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from model.config import AgentBrowserConfigModel
from services.playwright_browser_runtime import get_default_playwright_install_dir


class AgentBrowserSettingDialog(QDialog):
    def __init__(self, config: AgentBrowserConfigModel | None = None, parent=None):
        super().__init__(parent)
        self.config = config.model_copy(deep=True) if config else AgentBrowserConfigModel()
        self._saved_data = None

        self.setWindowTitle("浏览器设置")
        self.resize(820, 420)

        self._init_ui()
        self._bind_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        tip = QLabel(
            "留空时优先使用当前环境已安装的 Playwright 浏览器；若浏览器缺失且启用了自动安装，"
            "会安装到你指定的目录，未指定时默认安装到客户端目录下的 storage/runtime/playwright-browsers。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #4a5568;")
        main_layout.addWidget(tip)

        main_layout.addWidget(self._build_install_group())
        main_layout.addWidget(self._build_manual_group())
        main_layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.close_btn = QPushButton("关闭")
        self.save_btn = QPushButton("保存")

        self.close_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._save)

        button_layout.addWidget(self.close_btn)
        button_layout.addWidget(self.save_btn)
        main_layout.addLayout(button_layout)

    def _build_install_group(self):
        box = QGroupBox("自动安装")
        layout = QFormLayout(box)

        self.auto_install_checkbox = QCheckBox("浏览器缺失时自动安装")
        self.install_dir_input = QLineEdit()
        self.install_dir_input.setPlaceholderText("留空则使用客户端默认目录")
        self.install_dir_btn = QPushButton("选择目录")

        self.default_dir_label = QLabel(str(get_default_playwright_install_dir()))
        self.default_dir_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.default_dir_label.setWordWrap(True)

        install_dir_row = QWidget()
        install_dir_layout = QHBoxLayout(install_dir_row)
        install_dir_layout.setContentsMargins(0, 0, 0, 0)
        install_dir_layout.setSpacing(6)
        install_dir_layout.addWidget(self.install_dir_input, 1)
        install_dir_layout.addWidget(self.install_dir_btn)

        layout.addRow("", self.auto_install_checkbox)
        layout.addRow("安装目录", install_dir_row)
        layout.addRow("默认目录", self.default_dir_label)

        self.install_dir_btn.clicked.connect(self._browse_install_dir)
        return box

    def _build_manual_group(self):
        box = QGroupBox("手动浏览器路径")
        layout = QFormLayout(box)

        self.chromium_path_input = QLineEdit()
        self.chromium_path_input.setPlaceholderText("留空则使用 Playwright 的 chromium")
        self.chromium_path_btn = QPushButton("选择文件")

        self.firefox_path_input = QLineEdit()
        self.firefox_path_input.setPlaceholderText("留空则使用 Playwright 的 firefox")
        self.firefox_path_btn = QPushButton("选择文件")

        self.webkit_path_input = QLineEdit()
        self.webkit_path_input.setPlaceholderText("留空则使用 Playwright 的 webkit")
        self.webkit_path_btn = QPushButton("选择文件")

        layout.addRow("Chromium", self._build_file_row(self.chromium_path_input, self.chromium_path_btn))
        layout.addRow("Firefox", self._build_file_row(self.firefox_path_input, self.firefox_path_btn))
        layout.addRow("WebKit", self._build_file_row(self.webkit_path_input, self.webkit_path_btn))

        self.chromium_path_btn.clicked.connect(
            lambda: self._browse_file(self.chromium_path_input, "选择 Chromium 可执行文件")
        )
        self.firefox_path_btn.clicked.connect(
            lambda: self._browse_file(self.firefox_path_input, "选择 Firefox 可执行文件")
        )
        self.webkit_path_btn.clicked.connect(
            lambda: self._browse_file(self.webkit_path_input, "选择 WebKit 可执行文件")
        )
        return box

    def _build_file_row(self, line_edit: QLineEdit, button: QPushButton):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return row

    def _bind_data(self):
        self.auto_install_checkbox.setChecked(self.config.auto_install)
        self.install_dir_input.setText(self.config.install_dir)
        self.chromium_path_input.setText(self.config.chromium_executable_path)
        self.firefox_path_input.setText(self.config.firefox_executable_path)
        self.webkit_path_input.setText(self.config.webkit_executable_path)

    def _browse_install_dir(self):
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择浏览器安装目录",
            self.install_dir_input.text().strip() or str(get_default_playwright_install_dir()),
        )
        if selected:
            self.install_dir_input.setText(selected)

    def _browse_file(self, target_input: QLineEdit, title: str):
        selected, _ = QFileDialog.getOpenFileName(
            self,
            title,
            target_input.text().strip(),
            "可执行文件 (*.exe);;所有文件 (*)",
        )
        if selected:
            target_input.setText(selected)

    def _collect_data(self):
        return {
            "auto_install": self.auto_install_checkbox.isChecked(),
            "install_dir": self.install_dir_input.text().strip(),
            "chromium_executable_path": self.chromium_path_input.text().strip(),
            "firefox_executable_path": self.firefox_path_input.text().strip(),
            "webkit_executable_path": self.webkit_path_input.text().strip(),
        }

    def _save(self):
        try:
            self._saved_data = self._collect_data()
        except Exception as exc:
            QMessageBox.warning(self, "配置错误", str(exc))
            return
        self.accept()

    def get_data(self):
        return self._saved_data
