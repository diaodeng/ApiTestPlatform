import json
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DetailCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("detailCard")
        self.setStyleSheet(
            "#detailCard {"
            " background: #ffffff;"
            " border: 1px solid #e2e8f0;"
            " border-radius: 10px;"
            "}"
        )

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 600;")

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addLayout(self.content_layout)


class InfoCard(DetailCard):
    def __init__(self, title: str, fields: list[tuple[str, str]], parent=None):
        super().__init__(title, parent)
        self._fields = {}

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        form.setHorizontalSpacing(12)

        for key, label in fields:
            value_label = QLabel("-")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label, value_label)
            self._fields[key] = value_label

        self.content_layout.addLayout(form)

    def set_values(self, values: dict):
        for key, label in self._fields.items():
            value = values.get(key, "-")
            label.setText(str(value if value not in (None, "") else "-"))


class StructuredTextCard(DetailCard):
    def __init__(self, title: str, min_height: int = 96, parent=None):
        super().__init__(title, parent)
        self._raw_value = ""
        self._json_available = False

        self.copy_btn = QPushButton("复制")
        self.expand_btn = QPushButton("展开 JSON")
        self.collapse_btn = QPushButton("折叠 JSON")

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.copy_btn)
        toolbar_layout.addWidget(self.expand_btn)
        toolbar_layout.addWidget(self.collapse_btn)

        self.view_tabs = QTabWidget()
        self.view_tabs.setDocumentMode(True)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text.setMinimumHeight(min_height)
        self.text.setPlaceholderText("暂无内容")

        self.json_tree = QTreeWidget()
        self.json_tree.setHeaderLabels(["Key", "Value"])
        self.json_tree.setRootIsDecorated(True)
        self.json_tree.setAlternatingRowColors(True)
        self.json_tree.setMinimumHeight(min_height)

        font = QFont("Consolas")
        if not font.exactMatch():
            font = QFont("Courier New")
        self.text.setFont(font)

        self.content_layout.addLayout(toolbar_layout)
        self.view_tabs.addTab(self.text, "文本")
        self.view_tabs.addTab(self.json_tree, "JSON")
        self.content_layout.addWidget(self.view_tabs)

        self.copy_btn.clicked.connect(self._copy_text)
        self.expand_btn.clicked.connect(self._expand_json)
        self.collapse_btn.clicked.connect(self._collapse_json)

        self._set_json_available(False)

    def set_text(self, value: str):
        text = value or "-"
        parsed = self._try_parse_json(text)
        if parsed is None:
            self._raw_value = text
            self.text.setPlainText(text)
            self.json_tree.clear()
            self._set_json_available(False)
            self.view_tabs.setCurrentIndex(0)
            return

        formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
        self._raw_value = formatted
        self.text.setPlainText(formatted)
        self._populate_json_tree(parsed)
        self._set_json_available(True)
        self.view_tabs.setCurrentIndex(1)

    def clear(self):
        self._raw_value = ""
        self.text.clear()
        self.json_tree.clear()
        self._set_json_available(False)
        self.view_tabs.setCurrentIndex(0)

    def text_value(self) -> str:
        return self._raw_value or self.text.toPlainText()

    def _set_json_available(self, available: bool):
        self._json_available = available
        self.view_tabs.setTabEnabled(1, available)
        self.expand_btn.setEnabled(available)
        self.collapse_btn.setEnabled(available)
        if not available:
            self.view_tabs.setTabText(1, "JSON")
            return
        self.view_tabs.setTabText(1, "JSON树")

    def _try_parse_json(self, text: str):
        raw = (text or "").strip()
        if not raw or raw == "-" or raw.startswith("<binary content:"):
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _populate_json_tree(self, data):
        self.json_tree.clear()
        if isinstance(data, dict):
            for key, child_value in data.items():
                item = QTreeWidgetItem([str(key), self._display_value(child_value)])
                self.json_tree.addTopLevelItem(item)
                self._populate_node(item, child_value)
        elif isinstance(data, list):
            for index, child_value in enumerate(data):
                item = QTreeWidgetItem([f"[{index}]", self._display_value(child_value)])
                self.json_tree.addTopLevelItem(item)
                self._populate_node(item, child_value)
        else:
            self.json_tree.addTopLevelItem(
                QTreeWidgetItem(["value", self._display_value(data)])
            )

        self._collapse_json()
        self.json_tree.resizeColumnToContents(0)

    def _populate_node(self, parent: QTreeWidgetItem, value):
        if isinstance(value, dict):
            for key, child_value in value.items():
                item = QTreeWidgetItem([str(key), self._display_value(child_value)])
                parent.addChild(item)
                self._populate_node(item, child_value)
        elif isinstance(value, list):
            for index, child_value in enumerate(value):
                item = QTreeWidgetItem([f"[{index}]", self._display_value(child_value)])
                parent.addChild(item)
                self._populate_node(item, child_value)

    def _display_value(self, value) -> str:
        if isinstance(value, (dict, list)):
            return ""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _copy_text(self):
        QApplication.clipboard().setText(self.text_value())

    def _expand_json(self):
        if self._json_available:
            self.json_tree.expandAll()

    def _collapse_json(self):
        if not self._json_available and self.json_tree.topLevelItemCount() == 0:
            return
        self.json_tree.collapseAll()
        for index in range(self.json_tree.topLevelItemCount()):
            item = self.json_tree.topLevelItem(index)
            if item:
                item.setExpanded(True)


class ScrollTabPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.container = QWidget()
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch()

        self.scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def add_widget(self, widget: QWidget):
        self.content_layout.insertWidget(self.content_layout.count() - 1, widget)


class FlowDetailWidget(QWidget):
    def __init__(self):
        super().__init__()

        self._current_flow = None

        # self.title_label = QLabel("详情")
        # self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # self.title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.copy_menu_btn = QToolButton()
        self.copy_menu_btn.setText("复制请求")
        self.copy_menu_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.copy_menu = QMenu(self.copy_menu_btn)
        self.copy_request_action = self.copy_menu.addAction("复制请求")
        self.copy_request_headers_action = self.copy_menu.addAction("复制请求头")
        self.copy_response_action = self.copy_menu.addAction("复制响应")
        self.copy_response_headers_action = self.copy_menu.addAction("复制响应头")
        self.copy_all_action = self.copy_menu.addAction("复制全部")
        self.copy_curl_action = self.copy_menu.addAction("复制 cURL")
        self.copy_menu_btn.setMenu(self.copy_menu)
        self.export_curl_btn = QPushButton("导出 cURL")

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        # header_layout.addWidget(self.title_label)
        # header_layout.addSpacing(12)
        header_layout.addWidget(self.copy_menu_btn)
        header_layout.addWidget(self.export_curl_btn)
        header_layout.addStretch()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.overview_tab = ScrollTabPage()
        self.request_tab = ScrollTabPage()
        self.response_tab = ScrollTabPage()
        self.tabs.addTab(self.overview_tab, "总览")
        self.tabs.addTab(self.request_tab, "请求")
        self.tabs.addTab(self.response_tab, "响应")

        self.summary_card = DetailCard("摘要")
        self.summary_label = QLabel(
            "选择左侧抓包记录后，在这里查看完整请求与响应详情。"
        )
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.summary_card.content_layout.addWidget(self.summary_label)

        self.overview_card = InfoCard(
            "总览信息",
            [
                ("time", "时间"),
                ("method", "方法"),
                ("url", "URL"),
                ("host", "域名"),
                ("path", "路径"),
                ("status", "状态"),
                ("reason", "响应说明"),
                ("duration", "耗时"),
                ("size", "响应大小"),
                ("client", "客户端"),
                ("server", "服务端"),
                ("scheme", "协议"),
                ("port", "端口"),
                ("request_http_version", "请求版本"),
                ("response_http_version", "响应版本"),
                ("request_content_type", "请求类型"),
                ("response_content_type", "响应类型"),
            ],
        )

        self.request_meta_card = InfoCard(
            "请求信息",
            [
                ("request_line", "Request Line"),
                ("url", "URL"),
                ("scheme", "Scheme"),
                ("host", "Host"),
                ("port", "Port"),
                ("http_version", "HTTP Version"),
                ("content_type", "Content-Type"),
            ],
        )
        self.request_query_card = StructuredTextCard("Query Parameters", 88)
        self.request_cookie_card = StructuredTextCard("Cookies", 88)
        self.request_form_card = StructuredTextCard("Form Data", 88)
        self.request_header_card = StructuredTextCard("Headers", 140)
        self.request_body_card = StructuredTextCard("Body", 220)

        self.response_meta_card = InfoCard(
            "响应信息",
            [
                ("response_line", "Response Line"),
                ("status", "Status"),
                ("reason", "Reason"),
                ("duration", "耗时"),
                ("http_version", "HTTP Version"),
                ("content_type", "Content-Type"),
                ("size", "Size"),
            ],
        )
        self.response_header_card = StructuredTextCard("Headers", 140)
        self.response_body_card = StructuredTextCard("Body", 220)

        self.overview_tab.add_widget(self.summary_card)
        self.overview_tab.add_widget(self.overview_card)

        self.request_tab.add_widget(self.request_meta_card)
        self.request_tab.add_widget(self.request_query_card)
        self.request_tab.add_widget(self.request_cookie_card)
        self.request_tab.add_widget(self.request_form_card)
        self.request_tab.add_widget(self.request_header_card)
        self.request_tab.add_widget(self.request_body_card)

        self.response_tab.add_widget(self.response_meta_card)
        self.response_tab.add_widget(self.response_header_card)
        self.response_tab.add_widget(self.response_body_card)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(header_layout)
        layout.addWidget(self.tabs)

        self._bind()
        self.clear()

    def _bind(self):
        self.copy_menu_btn.clicked.connect(self._copy_request)
        self.copy_request_action.triggered.connect(self._copy_request)
        self.copy_request_headers_action.triggered.connect(self._copy_request_headers)
        self.copy_response_action.triggered.connect(self._copy_response)
        self.copy_response_headers_action.triggered.connect(self._copy_response_headers)
        self.copy_all_action.triggered.connect(self._copy_all)
        self.copy_curl_action.triggered.connect(self._copy_curl)
        self.export_curl_btn.clicked.connect(self._export_curl)

    def show_flow(self, flow):
        self._current_flow = flow

        status_text = flow.status_code if flow.status_code is not None else "-"
        # self.title_label.setText(f"详情 - {flow.method} {flow.path or '/'}")
        self.summary_label.setText(
            " | ".join(
                [
                    flow.time.strftime("%Y-%m-%d %H:%M:%S"),
                    flow.method or "-",
                    f"状态 {status_text}",
                    self._format_duration(flow.duration_ms),
                    flow.url or "-",
                ]
            )
        )

        self.overview_card.set_values(
            {
                "time": flow.time.strftime("%Y-%m-%d %H:%M:%S"),
                "method": flow.method or "-",
                "url": flow.url or "-",
                "host": flow.request_host or "-",
                "path": flow.path or "-",
                "status": status_text,
                "reason": flow.response_reason or "-",
                "duration": self._format_duration(flow.duration_ms),
                "size": flow.size,
                "client": flow.client_address or "-",
                "server": flow.server_address or "-",
                "scheme": flow.request_scheme or "-",
                "port": flow.request_port or "-",
                "request_http_version": flow.request_http_version or "-",
                "response_http_version": flow.response_http_version or "-",
                "request_content_type": flow.request_content_type or "-",
                "response_content_type": flow.response_content_type or "-",
            }
        )

        self.request_meta_card.set_values(
            {
                "request_line": " ".join(
                    [
                        flow.method or "-",
                        flow.path or "/",
                        flow.request_http_version or "-",
                    ]
                ),
                "url": flow.url or "-",
                "scheme": flow.request_scheme or "-",
                "host": flow.request_host or "-",
                "port": flow.request_port or "-",
                "http_version": flow.request_http_version or "-",
                "content_type": flow.request_content_type or "-",
            }
        )
        self.request_query_card.set_text(flow.request_query or "-")
        self.request_cookie_card.set_text(flow.request_cookies or "-")
        self.request_form_card.set_text(flow.request_form or "-")
        self.request_header_card.set_text(flow.request_headers or "-")
        self.request_body_card.set_text(flow.request_body or "-")

        self.response_meta_card.set_values(
            {
                "response_line": " ".join(
                    [
                        flow.response_http_version or "-",
                        str(status_text),
                        flow.response_reason or "-",
                    ]
                ),
                "status": status_text,
                "reason": flow.response_reason or "-",
                "duration": self._format_duration(flow.duration_ms),
                "http_version": flow.response_http_version or "-",
                "content_type": flow.response_content_type or "-",
                "size": flow.size,
            }
        )
        self.response_header_card.set_text(flow.response_headers or "-")
        self.response_body_card.set_text(flow.response_body or "-")
        self._set_actions_enabled(True)

    def clear(self):
        self._current_flow = None
        # self.title_label.setText("详情")
        self.summary_label.setText("选择左侧抓包记录后，在这里查看完整请求与响应详情。")
        self.overview_card.set_values({})
        self.request_meta_card.set_values({})
        self.response_meta_card.set_values({})
        self.request_query_card.clear()
        self.request_cookie_card.clear()
        self.request_form_card.clear()
        self.request_header_card.clear()
        self.request_body_card.clear()
        self.response_header_card.clear()
        self.response_body_card.clear()
        self.tabs.setCurrentIndex(0)
        self._set_actions_enabled(False)

    def _set_actions_enabled(self, enabled: bool):
        self.copy_menu_btn.setEnabled(enabled)
        self.export_curl_btn.setEnabled(enabled)

    def _copy_request(self):
        if self._current_flow:
            QApplication.clipboard().setText(
                self._build_request_text(self._current_flow)
            )

    def _copy_request_headers(self):
        if self._current_flow:
            QApplication.clipboard().setText(self._current_flow.request_headers or "")

    def _copy_response(self):
        if self._current_flow:
            QApplication.clipboard().setText(
                self._build_response_text(self._current_flow)
            )

    def _copy_response_headers(self):
        if self._current_flow:
            QApplication.clipboard().setText(self._current_flow.response_headers or "")

    def _copy_all(self):
        if self._current_flow:
            QApplication.clipboard().setText(self._build_full_text(self._current_flow))

    def _copy_curl(self):
        if self._current_flow:
            QApplication.clipboard().setText(self._build_curl(self._current_flow))

    def _export_curl(self):
        if not self._current_flow:
            return

        default_name = self._build_export_name(self._current_flow)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 cURL",
            default_name,
            "Text Files (*.txt);;PowerShell Files (*.ps1);;All Files (*)",
        )
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self._build_curl(self._current_flow))

    def _build_request_text(self, flow) -> str:
        request_line = " ".join(
            [
                flow.method or "-",
                flow.path or "/",
                flow.request_http_version or "-",
            ]
        )
        return "\n\n".join(
            [
                "[Request Line]\n"
                + "\n".join(
                    [
                        request_line,
                        f"URL: {flow.url or '-'}",
                        f"Scheme: {flow.request_scheme or '-'}",
                        f"Host: {flow.request_host or '-'}",
                        f"Port: {flow.request_port or '-'}",
                        f"Content-Type: {flow.request_content_type or '-'}",
                    ]
                ),
                f"[Query Parameters]\n{flow.request_query or '-'}",
                f"[Cookies]\n{flow.request_cookies or '-'}",
                f"[Form Data]\n{flow.request_form or '-'}",
                f"[Headers]\n{flow.request_headers or '-'}",
                f"[Body]\n{flow.request_body or '-'}",
            ]
        )

    def _build_response_text(self, flow) -> str:
        status_text = flow.status_code if flow.status_code is not None else "-"
        response_line = " ".join(
            [
                flow.response_http_version or "-",
                str(status_text),
                flow.response_reason or "-",
            ]
        )
        return "\n\n".join(
            [
                "[Response Line]\n"
                + "\n".join(
                    [
                        response_line,
                        f"Content-Type: {flow.response_content_type or '-'}",
                        f"Duration: {self._format_duration(flow.duration_ms)}",
                        f"Size: {flow.size}",
                    ]
                ),
                f"[Headers]\n{flow.response_headers or '-'}",
                f"[Body]\n{flow.response_body or '-'}",
            ]
        )

    def _build_full_text(self, flow) -> str:
        status_text = flow.status_code if flow.status_code is not None else "-"
        overview = "\n".join(
            [
                "[Overview]",
                f"Time: {flow.time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Method: {flow.method or '-'}",
                f"URL: {flow.url or '-'}",
                f"Host: {flow.request_host or '-'}",
                f"Path: {flow.path or '-'}",
                f"Status: {status_text}",
                f"Reason: {flow.response_reason or '-'}",
                f"Duration: {self._format_duration(flow.duration_ms)}",
                f"Size: {flow.size}",
                f"Client: {flow.client_address or '-'}",
                f"Server: {flow.server_address or '-'}",
                f"Scheme: {flow.request_scheme or '-'}",
                f"Port: {flow.request_port or '-'}",
                f"Request HTTP Version: {flow.request_http_version or '-'}",
                f"Response HTTP Version: {flow.response_http_version or '-'}",
            ]
        )
        return "\n\n".join(
            [
                overview,
                self._build_request_text(flow),
                self._build_response_text(flow),
            ]
        )

    def _build_curl(self, flow) -> str:
        lines = [
            "curl.exe",
            f"-X {self._quote_powershell(flow.method or 'GET')}",
            f"--url {self._quote_powershell(flow.url or '')}",
        ]

        for header in self._normalize_headers(flow.request_headers):
            lines.append(f"-H {self._quote_powershell(header)}")

        body = self._select_curl_body(flow)
        if body:
            lines.append(f"--data-raw {self._quote_powershell(body)}")

        return " `\n".join([lines[0], *[f"  {line}" for line in lines[1:]]])

    def _select_curl_body(self, flow) -> str:
        body = (flow.request_body or "").strip()
        if body.startswith("<binary content:"):
            body = ""
        if not body:
            body = (flow.request_form or "").strip()
        return body

    def _normalize_headers(self, raw_headers: str) -> list[str]:
        headers = []
        for line in (raw_headers or "").splitlines():
            item = line.strip()
            if not item:
                continue
            lowered = item.lower()
            if lowered.startswith("content-length:"):
                continue
            headers.append(item)
        return headers

    def _quote_powershell(self, value: str) -> str:
        return "'" + (value or "").replace("'", "''") + "'"

    def _build_export_name(self, flow) -> str:
        base = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            f"{flow.method}_{(flow.path or 'request').strip('/')}",
        ).strip("_")
        base = base or "request"
        return f"{base[:80]}.txt"

    def _format_duration(self, duration_ms: int | None) -> str:
        if duration_ms is None:
            return "-"
        if duration_ms < 1000:
            return f"{duration_ms} ms"
        return f"{duration_ms / 1000:.2f} s"
