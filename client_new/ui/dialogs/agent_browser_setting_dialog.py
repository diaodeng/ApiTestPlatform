from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    manual_download_requested = Signal(str, dict)

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
        main_layout.addWidget(self._build_download_group())
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
        self.download_host_input = QLineEdit()
        self.download_host_input.setPlaceholderText("例如: https://npmmirror.com/mirrors/playwright")
        self.download_proxy_input = QLineEdit()
        self.download_proxy_input.setPlaceholderText("例如: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080")

        install_dir_row = QWidget()
        install_dir_layout = QHBoxLayout(install_dir_row)
        install_dir_layout.setContentsMargins(0, 0, 0, 0)
        install_dir_layout.setSpacing(6)
        install_dir_layout.addWidget(self.install_dir_input, 1)
        install_dir_layout.addWidget(self.install_dir_btn)

        layout.addRow("", self.auto_install_checkbox)
        layout.addRow("安装目录", install_dir_row)
        layout.addRow("默认目录", self.default_dir_label)
        layout.addRow("下载源", self.download_host_input)
        layout.addRow("下载代理", self.download_proxy_input)

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

    def _build_download_group(self):
        """
        构建手动下载区域。

        :return: 手动下载区域组件。
        """
        box = QGroupBox("手动下载浏览器")
        layout = QFormLayout(box)

        self.download_browser_combo = QComboBox()
        self.download_browser_combo.addItem("Chromium", "chromium")
        self.download_browser_combo.addItem("Firefox", "firefox")
        self.download_browser_combo.addItem("WebKit", "webkit")
        self.download_browser_combo.addItem("Chrome", "chrome")
        self.download_browser_combo.addItem("Microsoft Edge", "msedge")

        self.manual_download_btn = QPushButton("手动下载")
        self.manual_download_status = QLabel("未开始")
        self.manual_download_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.manual_download_status.setWordWrap(True)

        download_row = QWidget()
        download_row_layout = QHBoxLayout(download_row)
        download_row_layout.setContentsMargins(0, 0, 0, 0)
        download_row_layout.setSpacing(6)
        download_row_layout.addWidget(self.download_browser_combo, 1)
        download_row_layout.addWidget(self.manual_download_btn)

        layout.addRow("目标浏览器", download_row)
        layout.addRow("下载状态", self.manual_download_status)

        self.manual_download_btn.clicked.connect(self._request_manual_download)
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
        """
        将当前配置绑定到界面控件。
        """
        self.auto_install_checkbox.setChecked(self.config.auto_install)
        self.install_dir_input.setText(self.config.install_dir)
        self.download_host_input.setText(self.config.playwright_download_host)
        self.download_proxy_input.setText(self.config.playwright_download_proxy)
        self.chromium_path_input.setText(self.config.chromium_executable_path)
        self.firefox_path_input.setText(self.config.firefox_executable_path)
        self.webkit_path_input.setText(self.config.webkit_executable_path)

    def _browse_install_dir(self):
        """
        打开目录选择器并回填安装目录。
        """
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择浏览器安装目录",
            self.install_dir_input.text().strip() or str(get_default_playwright_install_dir()),
        )
        if selected:
            self.install_dir_input.setText(selected)

    def _browse_file(self, target_input: QLineEdit, title: str):
        """
        打开文件选择器并回填浏览器可执行路径。

        :param target_input: 目标输入框。
        :param title: 对话框标题。
        """
        selected, _ = QFileDialog.getOpenFileName(
            self,
            title,
            target_input.text().strip(),
            "可执行文件 (*.exe);;所有文件 (*)",
        )
        if selected:
            target_input.setText(selected)

    def _collect_data(self):
        """
        收集当前界面上的浏览器配置。

        :return: 浏览器配置字典。
        """
        return {
            "auto_install": self.auto_install_checkbox.isChecked(),
            "install_dir": self.install_dir_input.text().strip(),
            "playwright_download_host": self.download_host_input.text().strip(),
            "playwright_download_proxy": self.download_proxy_input.text().strip(),
            "chromium_executable_path": self.chromium_path_input.text().strip(),
            "firefox_executable_path": self.firefox_path_input.text().strip(),
            "webkit_executable_path": self.webkit_path_input.text().strip(),
        }

    def _save(self):
        """
        保存配置并关闭对话框。
        """
        try:
            self._saved_data = self._collect_data()
        except Exception as exc:
            QMessageBox.warning(self, "配置错误", str(exc))
            return
        self.accept()

    def get_data(self):
        """
        获取用户点击保存后的配置结果。

        :return: 保存后的配置字典，未保存时返回 None。
        """
        return self._saved_data

    def _request_manual_download(self):
        """
        触发手动下载请求事件。
        """
        try:
            payload = self._collect_data()
        except Exception as exc:
            QMessageBox.warning(self, "配置错误", str(exc))
            return

        browser_name = str(self.download_browser_combo.currentData() or "chromium").strip().lower()
        self.manual_download_requested.emit(browser_name, payload)

    def set_manual_download_state(self, downloading: bool, status_text: str = ""):
        """
        设置手动下载控件状态。

        :param downloading: 是否下载中。
        :param status_text: 要展示的状态文案。
        """
        self.download_browser_combo.setEnabled(not downloading)
        self.manual_download_btn.setEnabled(not downloading)
        self.manual_download_btn.setText("下载中..." if downloading else "手动下载")
        self.manual_download_status.setText(status_text or ("下载中" if downloading else "未开始"))
