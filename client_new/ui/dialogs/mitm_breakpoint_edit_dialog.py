from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class MitmBreakpointEditDialog(QDialog):
    def __init__(self, flow_item, parent=None):
        """
        断点放行编辑弹窗。
        :param flow_item: 当前断点流量对象
        :param parent: 父组件
        """
        super().__init__(parent)
        self._flow_item = flow_item
        self._payload = {}
        self._stage = str(getattr(flow_item, "breakpoint_stage", "") or "").strip().lower()
        self._original_request_method = str(getattr(self._flow_item, "method", "") or "").strip()
        self._original_request_url = str(getattr(self._flow_item, "url", "") or "").strip()
        self._original_request_headers = str(getattr(self._flow_item, "request_headers", "") or "")
        self._original_request_body = str(getattr(self._flow_item, "request_body", "") or "")
        status_code = getattr(self._flow_item, "status_code", "")
        self._original_response_status = str(status_code if status_code is not None else "").strip()
        self._original_response_reason = str(getattr(self._flow_item, "response_reason", "") or "").strip()
        self._original_response_headers = str(getattr(self._flow_item, "response_headers", "") or "")
        self._original_response_body = str(getattr(self._flow_item, "response_body", "") or "")
        self._init_ui()

    def _init_ui(self):
        """
        初始化弹窗 UI。
        :return:
        """
        self.setWindowTitle("断点放行编辑")
        self.resize(860, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        summary = QLabel(
            f"流量ID：{getattr(self._flow_item, 'id', '-')}\n"
            f"接口：{getattr(self._flow_item, 'method', '')} {getattr(self._flow_item, 'path', '')}"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        editor = self._build_request_editor() if self._stage == "request" else self._build_response_editor()
        layout.addWidget(editor, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton("取消")
        continue_btn = QPushButton("继续放行")
        cancel_btn.clicked.connect(self.reject)
        continue_btn.clicked.connect(self._handle_continue)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(continue_btn)
        layout.addLayout(button_layout)

    def _build_request_editor(self) -> QWidget:
        """
        构建请求断点编辑区域。
        :return: 编辑组件
        """
        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        self.request_method_input = QLineEdit(self._original_request_method)
        self.request_url_input = QLineEdit(self._original_request_url)
        self.request_headers_input = QTextEdit()
        self.request_headers_input.setMinimumHeight(220)
        self.request_headers_input.setPlainText(self._original_request_headers)
        self.request_body_input = QTextEdit()
        self.request_body_input.setMinimumHeight(260)
        self.request_body_input.setPlainText(self._original_request_body)

        form.addRow("请求方法", self.request_method_input)
        form.addRow("请求 URL", self.request_url_input)
        form.addRow("请求头", self.request_headers_input)
        form.addRow("请求体", self.request_body_input)
        return container

    def _build_response_editor(self) -> QWidget:
        """
        构建响应断点编辑区域。
        :return: 编辑组件
        """
        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        self.response_status_input = QLineEdit(self._original_response_status)
        self.response_reason_input = QLineEdit(self._original_response_reason)
        self.response_headers_input = QTextEdit()
        self.response_headers_input.setMinimumHeight(220)
        self.response_headers_input.setPlainText(self._original_response_headers)
        self.response_body_input = QTextEdit()
        self.response_body_input.setMinimumHeight(260)
        self.response_body_input.setPlainText(self._original_response_body)

        form.addRow("状态码", self.response_status_input)
        form.addRow("响应说明", self.response_reason_input)
        form.addRow("响应头", self.response_headers_input)
        form.addRow("响应体", self.response_body_input)
        return container

    def _handle_continue(self):
        """
        校验并确认放行。
        :return:
        """
        try:
            self._payload = self._collect_payload()
        except Exception as e:
            QMessageBox.warning(self, "断点放行", str(e))
            return
        self.accept()

    def _collect_payload(self) -> dict:
        """
        采集编辑结果并生成放行 payload。
        :return: payload 字典
        """
        if self._stage == "request":
            payload = {}
            current_method = self.request_method_input.text().strip()
            current_url = self.request_url_input.text().strip()
            current_headers = self.request_headers_input.toPlainText()
            current_body = self.request_body_input.toPlainText()
            if current_method != self._original_request_method:
                payload["method"] = current_method
            if current_url != self._original_request_url:
                payload["url"] = current_url
            if current_headers != self._original_request_headers:
                payload["headers"] = current_headers
            if current_body != self._original_request_body:
                payload["body"] = current_body
            return payload

        status_code_raw = self.response_status_input.text().strip()
        if status_code_raw:
            try:
                int(status_code_raw)
            except Exception as e:
                raise ValueError("状态码必须是整数") from e
        payload = {}
        current_reason = self.response_reason_input.text().strip()
        current_headers = self.response_headers_input.toPlainText()
        current_body = self.response_body_input.toPlainText()
        if status_code_raw != self._original_response_status:
            payload["status_code"] = status_code_raw
        if current_reason != self._original_response_reason:
            payload["reason"] = current_reason
        if current_headers != self._original_response_headers:
            payload["headers"] = current_headers
        if current_body != self._original_response_body:
            payload["body"] = current_body
        return payload

    def get_payload(self) -> dict:
        """
        获取确认后的放行 payload。
        :return: payload 字典
        """
        return self._payload
