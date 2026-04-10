import asyncio

from loguru import logger
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from utils import VERSION
from utils.common import (
    check_app_has_new,
    get_client_update_runtime_profile,
    perform_update_with_powershell,
)


class _CheckUpdateThread(QThread):
    done = Signal(bool, str, str)

    def run(self):
        try:
            has_new, info = asyncio.run(check_app_has_new())
            if has_new:
                msg = f"当前版本: {VERSION}  新版本: {has_new}"
                self.done.emit(True, msg, info or "")
            else:
                msg = f"当前版本: {VERSION}，已经是最新版本"
                self.done.emit(False, msg, info or "")
        except Exception as e:
            logger.exception(e)
            self.done.emit(False, f"检查更新失败: {e}", "")


class _UpdateThread(QThread):
    progress = Signal(str)
    done = Signal(bool, str)

    def __init__(self, force_update: bool):
        super().__init__()
        self.force_update = force_update

    def run(self):
        try:
            if not self.force_update:
                has_new, _ = asyncio.run(check_app_has_new())
                if not has_new:
                    self.done.emit(False, f"当前版本 {VERSION} 已是最新")
                    return

            def _on_progress(text: str):
                self.progress.emit(text)

            success, message = asyncio.run(
                perform_update_with_powershell(
                    _on_progress,
                    force=self.force_update,
                )
            )
            self.done.emit(success, message)
        except Exception as e:
            logger.exception(e)
            self.done.emit(False, f"更新失败: {e}")


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.check_thread: _CheckUpdateThread | None = None
        self.update_thread: _UpdateThread | None = None
        self.runtime_profile = get_client_update_runtime_profile()

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        runtime_label = self.runtime_profile["package_mode_label"]
        preferred_asset_label = self.runtime_profile["preferred_asset_label"]
        tips = QLabel(
            "更新过程中不要离开当前页面。"
            f"当前运行形态：{runtime_label}，将优先选择 {preferred_asset_label} 更新包。"
            "支持单文件和连续分片文件更新，分片建议使用 .001、.002 这类命名。"
        )
        tips.setWordWrap(True)
        tips.setStyleSheet("color:#c53030;font-weight:600;")

        row = QHBoxLayout()
        self.title = QLabel("QTRClient 客户端")
        self.check_btn = QPushButton("检查更新")
        self.update_btn = QPushButton("更新")
        self.force_update = QCheckBox("强制更新")
        self.progress_label = QLabel("-")
        self.version_tip = QLabel(f"当前版本: {VERSION}")

        self.check_btn.clicked.connect(self._check_update)
        self.update_btn.clicked.connect(self._start_update)

        row.addWidget(self.title)
        row.addWidget(self.check_btn)
        row.addWidget(self.update_btn)
        row.addWidget(self.force_update)
        row.addWidget(QLabel("下载进度"))
        row.addWidget(self.progress_label, 1)
        row.addWidget(self.version_tip)

        self.update_info = QTextBrowser()
        self.update_info.setOpenExternalLinks(True)

        root.addWidget(tips)
        root.addLayout(row)
        root.addWidget(self.update_info, 1)

    def _check_update(self):
        if self.check_thread and self.check_thread.isRunning():
            return

        self.check_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self.force_update.setEnabled(False)
        self.check_thread = _CheckUpdateThread()
        self.check_thread.done.connect(self._on_check_done)
        self.check_thread.start()

    def _on_check_done(self, _has_new: bool, message: str, info: str):
        self.version_tip.setText(message)
        self.update_info.setMarkdown(info or "")
        self.check_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        self.force_update.setEnabled(True)

    def _start_update(self):
        if self.update_thread and self.update_thread.isRunning():
            return

        self.update_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.force_update.setEnabled(False)
        self.progress_label.setText(
            f"准备更新... 当前形态: {self.runtime_profile['package_mode_label']}"
        )

        self.update_thread = _UpdateThread(force_update=self.force_update.isChecked())
        self.update_thread.progress.connect(self.progress_label.setText)
        self.update_thread.done.connect(self._on_update_done)
        self.update_thread.start()

    def _on_update_done(self, success: bool, message: str):
        self.progress_label.setText(message)
        self.update_btn.setEnabled(True)
        self.check_btn.setEnabled(True)
        self.force_update.setEnabled(True)
        if success and self.window():
            window = self.window()
            if hasattr(window, "close_for_update"):
                window.close_for_update()
            else:
                window.close()

    def shutdown(self):
        for thread in [self.check_thread, self.update_thread]:
            if thread and thread.isRunning():
                thread.quit()
                thread.wait(1000)
