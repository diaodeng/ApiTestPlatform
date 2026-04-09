import json
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme_manager import ThemeManager, color_to_hex


class DetailCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("detailCard")
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme()

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

    def _apply_theme(self, *_args):
        tokens = ThemeManager.instance().tokens()
        self.setStyleSheet(
            f"""
            #detailCard {{
                background: {color_to_hex(tokens.surface)};
                border: 1px solid {color_to_hex(tokens.border)};
                border-radius: 10px;
            }}
            """
        )


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


class StructuredTextCard(QWidget):
    PARSER_PLAIN = "plain"
    PARSER_JSON = "json"
    PARSER_HEADERS = "headers"
    PARSER_PAIRS = "pairs"

    def __init__(
        self,
        title: str,
        min_height: int = 96,
        *,
        parser_mode: str = PARSER_PLAIN,
        allow_format_switch: bool = False,
        allow_json_copy: bool = False,
        allow_search: bool = False,
        collapsible: bool = False,
        start_collapsed: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._raw_value = ""
        self._display_value = "-"
        self._parser_mode = parser_mode
        self._allow_format_switch = allow_format_switch
        self._allow_json_copy = allow_json_copy
        self._allow_search = allow_search
        self._collapsible = collapsible
        self._is_collapsed = False

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600;")

        self.toggle_btn = QToolButton()
        self.toggle_btn.setVisible(self._collapsible)
        self.toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.format_label = QLabel("格式")
        self.format_combo = QComboBox()
        self.format_combo.addItem("文本", "text")
        if self._allow_format_switch:
            self.format_combo.addItem("JSON", "json")
        self.format_label.setVisible(self._allow_format_switch)
        self.format_combo.setVisible(self._allow_format_switch)

        self.copy_btn = QPushButton("复制")
        self.copy_json_btn = QPushButton("复制 JSON")
        self.copy_json_btn.setVisible(self._allow_json_copy)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)
        toolbar_layout.addWidget(self.title_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.toggle_btn)
        toolbar_layout.addWidget(self.format_label)
        toolbar_layout.addWidget(self.format_combo)
        toolbar_layout.addWidget(self.copy_btn)
        toolbar_layout.addWidget(self.copy_json_btn)

        self.search_container = QWidget()
        search_layout = QHBoxLayout(self.search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)
        self.search_label = QLabel("搜索")
        self.search_input = QLineEdit()
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText(f"输入关键字过滤 {title}")
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input, 1)
        self.search_container.setVisible(self._allow_search)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text.setMinimumHeight(min_height)
        self.text.setPlaceholderText("暂无内容")

        font = QFont("Consolas")
        if not font.exactMatch():
            font = QFont("Courier New")
        self.text.setFont(font)

        self.body_container = QWidget()
        body_layout = QVBoxLayout(self.body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(6)
        body_layout.addWidget(self.search_container)
        body_layout.addWidget(self.text)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.body_container)

        self.copy_btn.clicked.connect(self._copy_current_text)
        self.copy_json_btn.clicked.connect(self._copy_json_text)
        self.format_combo.currentIndexChanged.connect(self._refresh_display)
        self.search_input.textChanged.connect(self._refresh_display)
        self.toggle_btn.clicked.connect(self._toggle_collapsed)
        if self._collapsible:
            self._set_collapsed(start_collapsed)
        self._refresh_display()

    def set_text(self, value: str):
        self._raw_value = value or "-"
        self._refresh_display()

    def clear(self):
        self._raw_value = ""
        self._refresh_display()

    def text_value(self) -> str:
        return self._display_value or self.text.toPlainText()

    def _refresh_display(self):
        raw_text = self._normalized_text(self._raw_value)
        mode = self.format_combo.currentData() if self._allow_format_switch else "text"

        if mode == "json":
            json_text, error = self._build_json_text(raw_text)
            if error:
                display_text = f"格式化失败: {error}\n\n原始内容:\n{raw_text}"
            else:
                display_text = json_text
        else:
            display_text = raw_text

        display_text = self._filter_display_text(display_text)
        self._display_value = display_text
        self.text.setPlainText(display_text)

        if self._allow_json_copy:
            json_text, error = self._build_json_text(raw_text)
            self.copy_json_btn.setEnabled(
                bool(json_text and not error and json_text != "-")
            )

    def _filter_display_text(self, text: str) -> str:
        if not self._allow_search:
            return text

        keyword = (self.search_input.text() or "").strip().lower()
        if not keyword:
            return text

        normalized = (text or "").strip()
        if not normalized or normalized == "-":
            return text

        matched_lines = [line for line in text.splitlines() if keyword in line.lower()]
        if matched_lines:
            return "\n".join(matched_lines)
        return f"未匹配到内容：{self.search_input.text().strip()}"

    def _normalized_text(self, value: str) -> str:
        text = value if value not in (None, "") else "-"
        return str(text)

    def _build_json_text(self, raw_text: str) -> tuple[str, str]:
        normalized = (raw_text or "").strip()
        if not normalized or normalized == "-":
            return "-", ""

        try:
            if self._parser_mode == self.PARSER_JSON:
                if normalized.startswith("<binary content:"):
                    raise ValueError("二进制内容不支持 JSON 格式化")
                parsed = json.loads(normalized)
            elif self._parser_mode == self.PARSER_HEADERS:
                parsed = self._parse_pair_lines(normalized, ":")
            elif self._parser_mode == self.PARSER_PAIRS:
                parsed = self._parse_pair_lines(normalized, "=")
            else:
                raise ValueError("当前内容不支持 JSON 格式化")
        except Exception as exc:
            return "", str(exc)

        return json.dumps(parsed, indent=2, ensure_ascii=False), ""

    def _parse_pair_lines(self, text: str, separator: str) -> dict:
        result: dict[str, object] = {}
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped == "-":
                continue
            if separator not in stripped:
                raise ValueError(f"第 {line_no} 行缺少分隔符 {separator!r}")

            key, value = stripped.split(separator, 1)
            key = key.strip()
            value = value.strip()
            if not key:
                raise ValueError(f"第 {line_no} 行键名为空")

            existing = result.get(key)
            if existing is None:
                result[key] = value
            elif isinstance(existing, list):
                existing.append(value)
            else:
                result[key] = [existing, value]
        return result

    def _copy_current_text(self):
        QApplication.clipboard().setText(self.text_value())

    def _copy_json_text(self):
        json_text, error = self._build_json_text(self._normalized_text(self._raw_value))
        if error:
            QApplication.clipboard().setText(f"格式化失败: {error}")
            return
        QApplication.clipboard().setText(json_text)

    def _toggle_collapsed(self, *_args):
        self._set_collapsed(not self._is_collapsed)

    def _set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        self.body_container.setVisible(not collapsed)
        if self._collapsible:
            self.toggle_btn.setArrowType(Qt.RightArrow if collapsed else Qt.DownArrow)
            self.toggle_btn.setText("展开" if collapsed else "收起")


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
                # ("scheme", "Scheme"),
                ("host", "Host"),
                # ("port", "Port"),
                # ("http_version", "HTTP Version"),
                ("content_type", "Content-Type"),
            ],
        )
        self.request_form_card = StructuredTextCard("Form Data", 72)
        self.request_header_card = StructuredTextCard(
            "Headers",
            100,
            parser_mode=StructuredTextCard.PARSER_HEADERS,
            allow_json_copy=True,
            allow_search=True,
            collapsible=True,
            start_collapsed=True,
        )
        self.request_body_card = StructuredTextCard(
            "Body",
            220,
            parser_mode=StructuredTextCard.PARSER_JSON,
            allow_format_switch=True,
        )

        self.response_meta_card = InfoCard(
            "响应信息",
            [
                ("response_line", "Response Line"),
                # ("status", "Status"),
                # ("reason", "Reason"),
                ("duration", "耗时"),
                # ("http_version", "HTTP Version"),
                ("content_type", "Content-Type"),
                ("size", "Size"),
            ],
        )
        self.response_header_card = StructuredTextCard(
            "Headers",
            100,
            parser_mode=StructuredTextCard.PARSER_HEADERS,
            allow_json_copy=True,
            allow_search=True,
            collapsible=True,
            start_collapsed=True,
        )
        self.response_body_card = StructuredTextCard(
            "Body",
            220,
            parser_mode=StructuredTextCard.PARSER_JSON,
            allow_format_switch=True,
        )

        self.overview_tab.add_widget(self.summary_card)
        self.overview_tab.add_widget(self.overview_card)

        self.request_tab.add_widget(self.request_meta_card)
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
        self._set_optional_text_card(self.request_form_card, flow.request_form)
        self._set_optional_text_card(self.request_header_card, flow.request_headers)
        self._set_optional_text_card(
            self.request_body_card,
            self._request_body_for_display(flow),
        )

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
        self._set_optional_text_card(self.response_header_card, flow.response_headers)
        self._set_optional_text_card(self.response_body_card, flow.response_body)
        self._set_actions_enabled(True)

    def clear(self):
        self._current_flow = None
        # self.title_label.setText("详情")
        self.summary_label.setText("选择左侧抓包记录后，在这里查看完整请求与响应详情。")
        self.overview_card.set_values({})
        self.request_meta_card.set_values({})
        self.response_meta_card.set_values({})
        self._set_optional_text_card(self.request_form_card, "", visible=False)
        self._set_optional_text_card(self.request_header_card, "", visible=False)
        self._set_optional_text_card(self.request_body_card, "", visible=False)
        self._set_optional_text_card(self.response_header_card, "", visible=False)
        self._set_optional_text_card(self.response_body_card, "", visible=False)
        self.tabs.setCurrentIndex(0)
        self._set_actions_enabled(False)

    def _set_optional_text_card(
        self, card: StructuredTextCard, value: str, *, visible: bool | None = None
    ):
        card.set_text(value or "")
        if visible is None:
            visible = self._has_meaningful_content(value)
        card.setVisible(visible)

    def _has_meaningful_content(self, value: str | None) -> bool:
        return bool(str(value or "").strip())

    def _request_body_for_display(self, flow) -> str:
        if "x-www-form-urlencoded" in str(
            flow.request_content_type or ""
        ).strip().lower() and self._has_meaningful_content(flow.request_form):
            return ""
        return flow.request_body or ""

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
        sections = [
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
            )
        ]

        if self._has_meaningful_content(flow.request_form):
            sections.append(f"[Form Data]\n{flow.request_form}")
        if self._has_meaningful_content(flow.request_headers):
            sections.append(f"[Headers]\n{flow.request_headers}")

        request_body = self._request_body_for_display(flow)
        if self._has_meaningful_content(request_body):
            sections.append(f"[Body]\n{request_body}")

        return "\n\n".join(sections)

    def _build_response_text(self, flow) -> str:
        status_text = flow.status_code if flow.status_code is not None else "-"
        response_line = " ".join(
            [
                flow.response_http_version or "-",
                str(status_text),
                flow.response_reason or "-",
            ]
        )
        sections = [
            "[Response Line]\n"
            + "\n".join(
                [
                    response_line,
                    f"Content-Type: {flow.response_content_type or '-'}",
                    f"Duration: {self._format_duration(flow.duration_ms)}",
                    f"Size: {flow.size}",
                ]
            )
        ]

        if self._has_meaningful_content(flow.response_headers):
            sections.append(f"[Headers]\n{flow.response_headers}")
        if self._has_meaningful_content(flow.response_body):
            sections.append(f"[Body]\n{flow.response_body}")

        return "\n\n".join(sections)

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
