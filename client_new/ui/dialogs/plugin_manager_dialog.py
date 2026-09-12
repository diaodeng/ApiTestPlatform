from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from loguru import logger
from plugins.manager import PLUGIN_DEFINITIONS, plugin_manager
from ui.utils.icon_util import apply_window_icon


class PluginManagerDialog(QDialog):
    """
    插件管理对话框。

    展示各插件状态，支持在线下载与本地 zip 安装；
    所有安装动作在后台线程执行，结果通过信号回 UI 线程，
    插件异常只弹提示与记日志，不影响主窗口。
    """

    _install_finished = Signal(str, bool, str)  # 插件名 / 是否成功 / 消息

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running_tasks: set[str] = set()

        self.setWindowTitle("插件管理")
        self.resize(760, 420)
        apply_window_icon(self)

        self._init_ui()
        self._bind()
        self._load_download_url()
        self._refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 下载源配置
        source_box = QFormLayout()
        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(6)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "插件包下载源根地址，例如 https://example.com/qtr-plugins（留空则无法在线下载）"
        )
        self.save_url_button = QPushButton("保存下载源")
        source_layout.addWidget(self.url_input, 1)
        source_layout.addWidget(self.save_url_button)
        source_box.addRow("下载源", source_row)
        layout.addLayout(source_box)

        # 插件列表
        self.table = QTableWidget(len(PLUGIN_DEFINITIONS), 4)
        self.table.setHorizontalHeaderLabels(["插件", "说明", "状态", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        for row, definition in enumerate(PLUGIN_DEFINITIONS.values()):
            name_item = QTableWidgetItem(definition.display_name)
            name_item.setData(Qt.UserRole, definition.name)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(definition.description))
            self.table.setItem(row, 2, QTableWidgetItem(""))

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)
            download_button = QPushButton("在线下载")
            download_button.clicked.connect(
                lambda _=False, plugin=definition.name: self._download_plugin(plugin)
            )
            local_button = QPushButton("本地安装")
            local_button.clicked.connect(
                lambda _=False, plugin=definition.name: self._install_local(plugin)
            )
            actions_layout.addWidget(download_button)
            actions_layout.addWidget(local_button)
            self.table.setCellWidget(row, 3, actions)

            # 记录按钮便于执行时禁用
            self.table.item(row, 0).setData(
                Qt.UserRole + 1, (download_button, local_button)
            )

        layout.addWidget(self.table, 1)

        self.hint_label = QLabel(
            "插件目录：storage/plugins/。安装成功后需重启客户端生效；"
            "未安装插件时对应功能不可用，但其他功能不受影响。"
        )
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

    def _bind(self):
        self.save_url_button.clicked.connect(self._save_download_url)
        self._install_finished.connect(self._on_install_finished)

    def _load_download_url(self):
        self.url_input.setText(plugin_manager.read_download_base_url())

    def _save_download_url(self):
        ok, message = plugin_manager.save_download_base_url(self.url_input.text())
        if ok:
            QMessageBox.information(self, "插件管理", message)
        else:
            QMessageBox.warning(self, "插件管理", message)

    def _refresh_table(self):
        for row, definition in enumerate(PLUGIN_DEFINITIONS.values()):
            status = plugin_manager.describe_status(definition.name)
            self.table.item(row, 2).setText(status)
            enabled = definition.name not in self._running_tasks
            download_button, local_button = self.table.item(row, 0).data(
                Qt.UserRole + 1
            )
            download_button.setEnabled(enabled)
            local_button.setEnabled(enabled)

    def _download_plugin(self, plugin_name: str):
        if plugin_name in self._running_tasks:
            return
        if not self.url_input.text().strip():
            QMessageBox.warning(
                self, "插件管理", "请先填写并保存插件下载源，或使用「本地安装」。"
            )
            return

        self._running_tasks.add(plugin_name)
        self._refresh_table()
        logger.info(f"开始在线安装插件 name={plugin_name}")

        import threading

        def _task():
            ok, message = plugin_manager.download_and_install(plugin_name)
            self._install_finished.emit(plugin_name, ok, message)

        threading.Thread(
            target=_task, name=f"plugin-download-{plugin_name}", daemon=True
        ).start()

    def _install_local(self, plugin_name: str):
        if plugin_name in self._running_tasks:
            return
        zip_path, _selected_filter = QFileDialog.getOpenFileName(
            self, "选择插件包", "", "插件包 (*.zip)"
        )
        if not zip_path:
            return

        self._running_tasks.add(plugin_name)
        self._refresh_table()
        logger.info(f"开始本地安装插件 name={plugin_name}, file={zip_path}")

        import threading

        def _task():
            ok, message = plugin_manager.install_from_zip(plugin_name, zip_path)
            self._install_finished.emit(plugin_name, ok, message)

        threading.Thread(
            target=_task, name=f"plugin-install-{plugin_name}", daemon=True
        ).start()

    def _on_install_finished(self, plugin_name: str, ok: bool, message: str):
        self._running_tasks.discard(plugin_name)
        self._refresh_table()
        if ok:
            QMessageBox.information(self, "插件管理", message)
        else:
            logger.warning(f"插件安装失败 name={plugin_name}: {message}")
            QMessageBox.warning(self, "插件管理", message)
