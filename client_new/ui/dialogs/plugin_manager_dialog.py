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

from pathlib import Path

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

        # 下载源与安装目录配置
        source_box = QFormLayout()
        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(6)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "插件包下载源根地址，例如 https://example.com/qtr-plugins；"
            "留空时自动从 Gitee 下载与当前客户端版本一致的插件包"
        )
        self.save_url_button = QPushButton("保存下载源")
        source_layout.addWidget(self.url_input, 1)
        source_layout.addWidget(self.save_url_button)
        source_box.addRow("下载源", source_row)

        dir_row = QWidget()
        dir_layout = QHBoxLayout(dir_row)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(6)
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText(
            "插件安装根目录；留空使用默认目录（程序目录下 storage/plugins）"
        )
        self.browse_dir_button = QPushButton("浏览")
        self.save_dir_button = QPushButton("保存安装目录")
        dir_layout.addWidget(self.dir_input, 1)
        dir_layout.addWidget(self.browse_dir_button)
        dir_layout.addWidget(self.save_dir_button)
        source_box.addRow("安装目录", dir_row)
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
            "安装成功后需重启客户端生效；未安装插件时对应功能不可用，"
            "但其他功能不受影响。修改安装目录会影响已安装插件的生效位置，保存前请阅读影响提示。"
        )
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

    def _bind(self):
        self.save_url_button.clicked.connect(self._save_download_url)
        self.save_dir_button.clicked.connect(self._save_install_dir)
        self.browse_dir_button.clicked.connect(self._browse_install_dir)
        self._install_finished.connect(self._on_install_finished)

    def _load_download_url(self):
        self.url_input.setText(plugin_manager.read_download_base_url())
        self.dir_input.setText(str(plugin_manager.get_plugin_root()))

    def _browse_install_dir(self):
        chosen = QFileDialog.getExistingDirectory(self, "选择插件安装根目录")
        if chosen:
            self.dir_input.setText(chosen)

    def _save_install_dir(self):
        """
        保存插件安装目录；路径变化时展示影响提示，由用户决定是否迁移已装插件。
        :return:
        """
        new_dir = self.dir_input.text().strip()
        current_root = str(plugin_manager.get_plugin_root())
        normalized_new = str(Path(new_dir).expanduser()) if new_dir else ""
        if normalized_new == current_root:
            QMessageBox.information(self, "插件管理", "安装目录未变化。")
            return

        impact_text = (
            "修改插件安装目录的影响：\n\n"
            "1. 新下载/安装的插件将放入新目录；\n"
            "2. 默认目录随程序目录（拷贝程序目录可整体带走插件），"
            "自定义目录请自行保证其固定可用、不被清理；\n"
            "3. 若目录位于构建输出目录（dist/...）内，重新打包前需先停止 "
            "WinDivert 驱动（管理员执行 sc stop WinDivert）。\n\n"
            "是否把当前已安装的插件迁移到新目录？"
        )
        box = QMessageBox(QMessageBox.Question, "修改插件安装目录", impact_text, parent=self)
        migrate_button = box.addButton("迁移已装插件", QMessageBox.YesRole)
        keep_button = box.addButton("仅保存", QMessageBox.NoRole)
        box.addButton("取消", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked not in (migrate_button, keep_button):
            return
        migrate = clicked is migrate_button

        ok, message = plugin_manager.set_install_dir(new_dir, migrate)
        if ok:
            logger.info(f"插件安装目录已修改: {message}")
            QMessageBox.information(self, "插件管理", message)
            self._refresh_table()
        else:
            logger.warning(f"插件安装目录修改失败: {message}")
            QMessageBox.warning(self, "插件管理", message)

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
