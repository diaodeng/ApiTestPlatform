import html
import os
import re
import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _FileTailThread(QThread):
    MAX_EMITTED_LINE_LENGTH = 16 * 1024

    line_read = Signal(str)
    status = Signal(str)

    def __init__(self, file_path: str, poll_interval: float = 0.25, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.poll_interval = poll_interval
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        last_size = 0
        self.status.emit(f"开始监控文件: {self.file_path}")
        while self._running:
            try:
                if not os.path.exists(self.file_path):
                    self.msleep(500)
                    continue

                current_size = os.path.getsize(self.file_path)
                if current_size < last_size:
                    last_size = 0

                if current_size > last_size:
                    with open(
                        self.file_path, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        if last_size > 0:
                            f.seek(last_size)
                        content = f.read(current_size - last_size)
                        last_size = current_size
                        if content:
                            for line in content.splitlines():
                                line = line.strip()
                                if line:
                                    self.line_read.emit(self._truncate_line(line))

                self.msleep(int(self.poll_interval * 1000))
            except Exception as e:
                self.status.emit(f"文件监控异常: {e}")
                self.msleep(1000)

    def _truncate_line(self, line: str) -> str:
        """
        截断发送到 UI 的超长日志行，避免 QTextEdit 处理大响应正文。

        :param line: 从日志文件读取的一行原始文本。
        :return: 可安全传递到 UI 线程的日志文本。
        """
        if len(line) <= self.MAX_EMITTED_LINE_LENGTH:
            return line

        omitted = len(line) - self.MAX_EMITTED_LINE_LENGTH
        return (
            f"{line[:self.MAX_EMITTED_LINE_LENGTH]}"
            f" ... [日志单行过长，已截断 {omitted} 个字符]"
        )


class LogViewPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_log_lines = 1000
        self.log_entries: list[str] = []

        self.local_tail_thread: _FileTailThread | None = None
        self.app_tail_thread: _FileTailThread | None = None

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        tabs = QTabWidget()
        tabs.addTab(self._build_ssh_tab(), "SSH日志")
        tabs.addTab(self._build_local_tab(), "本地日志")
        tabs.addTab(self._build_app_tab(), "程序日志")

        root.addWidget(tabs)

    def _build_ssh_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        row1 = QHBoxLayout()
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("主机地址")
        self.port_input = QLineEdit("22")
        self.port_input.setMaximumWidth(90)
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("用户名")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("密码")
        row1.addWidget(QLabel("主机"))
        row1.addWidget(self.host_input)
        row1.addWidget(QLabel("端口"))
        row1.addWidget(self.port_input)
        row1.addWidget(QLabel("用户"))
        row1.addWidget(self.user_input)
        row1.addWidget(QLabel("密码"))
        row1.addWidget(self.password_input)

        row2 = QHBoxLayout()
        self.ssh_path_input = QLineEdit("/var/log/syslog")
        self.ssh_btn = QPushButton("连接SSH")
        self.ssh_btn.clicked.connect(self._toggle_ssh)
        self.ssh_status = QLabel("未连接")
        row2.addWidget(QLabel("日志路径"))
        row2.addWidget(self.ssh_path_input, 1)
        row2.addWidget(self.ssh_btn)
        row2.addWidget(self.ssh_status)

        self.ssh_log_text = QTextEdit()
        self.ssh_log_text.setReadOnly(True)
        self.ssh_log_text.setPlaceholderText("SSH日志内容显示区")

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self.ssh_log_text, 1)
        return widget

    def _build_local_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        top = QHBoxLayout()
        self.local_path_input = QLineEdit()
        self.local_path_input.setReadOnly(True)
        browse_btn = QPushButton("浏览文件")
        browse_btn.clicked.connect(self._pick_local_file)
        self.watch_local_checkbox = QCheckBox("启用文件监控")
        self.watch_local_checkbox.setChecked(True)
        self.auto_scroll_checkbox = QCheckBox("自动滚动")
        self.auto_scroll_checkbox.setChecked(True)
        top.addWidget(QLabel("文件"))
        top.addWidget(self.local_path_input, 1)
        top.addWidget(browse_btn)
        top.addWidget(self.watch_local_checkbox)
        top.addWidget(self.auto_scroll_checkbox)

        tools = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("过滤关键词/正则")
        apply_filter_btn = QPushButton("应用过滤")
        apply_filter_btn.clicked.connect(self._refresh_local_log_view)

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._clear_local_log)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索日志")
        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._search_local_log)

        self.max_lines_input = QSpinBox()
        self.max_lines_input.setRange(100, 200000)
        self.max_lines_input.setValue(1000)
        self.max_lines_input.valueChanged.connect(self._on_max_lines_changed)

        tools.addWidget(QLabel("过滤"))
        tools.addWidget(self.filter_input, 1)
        tools.addWidget(apply_filter_btn)
        tools.addWidget(clear_btn)
        tools.addWidget(QLabel("搜索"))
        tools.addWidget(self.search_input)
        tools.addWidget(search_btn)
        tools.addWidget(QLabel("最大行数"))
        tools.addWidget(self.max_lines_input)

        self.local_log_text = QTextEdit()
        self.local_log_text.setReadOnly(True)
        self.local_log_text.setPlaceholderText("日志内容将在这里显示")

        self.local_status = QLabel("就绪")

        layout.addLayout(top)
        layout.addLayout(tools)
        layout.addWidget(self.local_log_text, 1)
        layout.addWidget(self.local_status)
        return widget

    def _build_app_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        row = QHBoxLayout()
        self.watch_app_checkbox = QCheckBox("监控日志")
        self.watch_app_checkbox.toggled.connect(self._toggle_app_log_watch)
        row.addWidget(self.watch_app_checkbox)
        row.addStretch()

        self.app_log_text = QTextEdit()
        self.app_log_text.setReadOnly(True)
        self.app_log_text.setPlaceholderText("程序运行日志显示区")

        self.app_status = QLabel("就绪")

        layout.addLayout(row)
        layout.addWidget(self.app_log_text, 1)
        layout.addWidget(self.app_status)
        return widget

    def _toggle_ssh(self):
        self.ssh_status.setText("未实现")
        self.ssh_log_text.append("当前版本未启用 SSH 实时日志功能")

    def _pick_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择日志文件",
            "",
            "Log Files (*.log *.txt);;All Files (*)",
        )
        if not path:
            return

        self.local_path_input.setText(path)
        self.log_entries.clear()
        self.local_log_text.clear()
        self._start_local_tail(path)

    def _start_local_tail(self, path: str):
        self._stop_local_tail()

        self.local_tail_thread = _FileTailThread(path)
        self.local_tail_thread.line_read.connect(self._on_local_log_line)
        self.local_tail_thread.status.connect(self.local_status.setText)
        self.local_tail_thread.start()

    def _stop_local_tail(self):
        if self.local_tail_thread:
            self.local_tail_thread.stop()
            self.local_tail_thread.wait(1500)
            self.local_tail_thread = None

    def _on_local_log_line(self, line: str):
        if not self.watch_local_checkbox.isChecked():
            return

        self.log_entries.append(line)
        if len(self.log_entries) > self.max_log_lines:
            self.log_entries = self.log_entries[-self.max_log_lines :]

        self._refresh_local_log_view(incremental_line=line)

    def _refresh_local_log_view(self, _=None, incremental_line: str | None = None):
        pattern = self.filter_input.text().strip()

        if incremental_line is not None and not pattern:
            self.local_log_text.append(html.escape(incremental_line))
            if self.auto_scroll_checkbox.isChecked():
                self.local_log_text.moveCursor(QTextCursor.End)
            return

        self.local_log_text.clear()
        for line in self.log_entries:
            rendered = self._render_line(line, pattern)
            if rendered:
                self.local_log_text.append(rendered)

        if self.auto_scroll_checkbox.isChecked():
            self.local_log_text.moveCursor(QTextCursor.End)

    def _render_line(self, line: str, pattern: str) -> str | None:
        if not pattern:
            return html.escape(line)

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            if pattern.lower() not in line.lower():
                return None
            escaped = html.escape(line)
            escaped_pattern = html.escape(pattern)
            return escaped.replace(
                escaped_pattern,
                f"<span style='color:#e53e3e;font-weight:600'>{escaped_pattern}</span>",
            )

        matches = list(regex.finditer(line))
        if not matches:
            return None

        parts = []
        last_end = 0
        for m in matches:
            if m.start() > last_end:
                parts.append(html.escape(line[last_end : m.start()]))
            parts.append(
                f"<span style='color:#e53e3e;font-weight:600'>{html.escape(line[m.start() : m.end()])}</span>"
            )
            last_end = m.end()
        if last_end < len(line):
            parts.append(html.escape(line[last_end:]))

        return "".join(parts)

    def _on_max_lines_changed(self, value: int):
        self.max_log_lines = max(100, int(value))
        if len(self.log_entries) > self.max_log_lines:
            self.log_entries = self.log_entries[-self.max_log_lines :]
            self._refresh_local_log_view()

    def _clear_local_log(self):
        self.log_entries.clear()
        self.local_log_text.clear()
        self.local_status.setText("文件日志已清空")

    def _search_local_log(self):
        key = self.search_input.text().strip()
        if not key:
            self.local_status.setText("请输入搜索内容")
            return

        matched = 0
        try:
            regex = re.compile(key, re.IGNORECASE)
            for line in self.log_entries:
                if regex.search(line):
                    matched += 1
        except re.error:
            for line in self.log_entries:
                if key.lower() in line.lower():
                    matched += 1

        self.local_status.setText(f"搜索完成: {matched} 条匹配")

    def _toggle_app_log_watch(self, checked: bool):
        if checked:
            log_file = os.path.join(
                "logs", time.strftime("%Y-%m-%d", time.localtime()) + ".log"
            )
            self._start_app_tail(log_file)
        else:
            self._stop_app_tail()
            self.app_status.setText("停止监控程序日志")

    def _start_app_tail(self, path: str):
        self._stop_app_tail()

        self.app_tail_thread = _FileTailThread(path)
        self.app_tail_thread.line_read.connect(self.app_log_text.append)
        self.app_tail_thread.status.connect(self.app_status.setText)
        self.app_tail_thread.start()

    def _stop_app_tail(self):
        if self.app_tail_thread:
            self.app_tail_thread.stop()
            self.app_tail_thread.wait(1500)
            self.app_tail_thread = None

    def shutdown(self):
        self._stop_local_tail()
        self._stop_app_tail()
