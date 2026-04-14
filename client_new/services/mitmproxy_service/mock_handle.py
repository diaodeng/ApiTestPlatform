import asyncio
import json
import uuid
from datetime import datetime
from urllib.parse import urlsplit

import httpx
from loguru import logger
from mitmproxy.http import HTTPFlow, Response

from models.mitmproxy_common import FlowItem
from utils.http_defaults import DEFAULT_HTTP_TIMEOUT

from .runtime_config import RuntimeConfig


class MockHandle:
    def __init__(self, flow_dispatcher=None, emit_flows: bool = True):
        self._flow_dispatcher = flow_dispatcher
        self._emit_flows = emit_flows

    def _emit_flow(self, event_type: str, item: FlowItem):
        if not self._emit_flows:
            return
        if self._flow_dispatcher:
            self._flow_dispatcher(event_type, item)
            return

        # 延迟导入，避免 helper 子进程对 Qt emitter 形成硬依赖。
        try:
            from emitter.mitm_flow_emitter import flow_emitter

            if event_type == "new":
                flow_emitter.new_flow.emit(item)
            else:
                flow_emitter.update_flow.emit(item)
        except Exception as e:
            logger.debug(f"flow 事件分发失败: {e}")

    async def request(self, flow: HTTPFlow):
        flow.id = str(uuid.uuid4())
        item = FlowItem(
            id=flow.id,
            method=flow.request.method,
            url=flow.request.pretty_url,
            path=flow.request.path,
            status_code=None,
            size=0,
            time=datetime.now(),
            request_scheme=flow.request.scheme,
            request_host=self._resolve_request_host(flow),
            request_port=flow.request.port,
            request_http_version=flow.request.http_version,
            request_query=self._format_query(flow),
            request_headers=self._format_headers(
                self._iter_items(flow.request.headers)
            ),
            request_cookies=self._format_headers(
                self._iter_items(flow.request.cookies), separator="="
            ),
            request_form=self._format_headers(
                self._iter_items(flow.request.urlencoded_form),
                separator="=",
            ),
            request_body=self._format_content(
                self._resolve_message_content(flow.request),
                flow.request.headers.get("content-type", ""),
            ),
            request_content_type=flow.request.headers.get("content-type", ""),
            client_address=self._format_address(flow.client_conn.peername),
            server_address=self._format_address(flow.server_conn.address),
        )

        flow.metadata["ui_item"] = item

        self._emit_flow("new", item)

        config = RuntimeConfig.get()
        if not config:
            return

        path = flow.request.path

        # ===== 请求延迟 =====
        if config.request_delay.enabled and path in config.request_delay.delay_path:
            await asyncio.sleep(config.request_delay.delay)

        # ===== mock开关 =====
        if not config.is_mock:
            return

        # ===== include/exclude =====
        include_paths = self._split_paths(config.include)
        exclude_paths = self._split_paths(config.exclude)

        if config.open_include and path not in include_paths:
            return

        if config.open_exclude and path in exclude_paths:
            return

        try:
            json_data, form_data = self._build_mock_payload(flow, config.add_body)
            headers = self._parse_key_values(config.add_headers)

            async with httpx.AsyncClient(
                timeout=DEFAULT_HTTP_TIMEOUT,
                follow_redirects=True,
            ) as client:
                resp = await client.post(
                    f"{config.mock_server}{path}",
                    json=json_data,
                    data=form_data,
                    headers=headers,
                )

            if resp.status_code == 505:
                logger.info(f"mock 未命中规则，继续真实请求: {path}")
                return

            flow.response = Response.make(
                resp.status_code,
                resp.content,
                {"Content-Type": resp.headers.get("Content-Type", "application/json")},
            )

        except Exception as e:
            logger.exception(e)

    async def response(self, flow: HTTPFlow):
        item = flow.metadata.get("ui_item")
        if item:
            duration_ms = self._calculate_duration_ms(flow, item)
            item.status_code = flow.response.status_code
            item.size = len(flow.response.content or b"")
            item.response_reason = getattr(flow.response, "reason", "")
            item.response_http_version = getattr(flow.response, "http_version", "")
            item.response_headers = self._format_headers(
                self._iter_items(flow.response.headers)
            )
            item.response_body = self._format_content(
                self._resolve_message_content(flow.response),
                flow.response.headers.get("content-type", ""),
            )
            item.response_content_type = flow.response.headers.get("content-type", "")
            item.duration_ms = duration_ms

            self._emit_flow("update", item)

        config = RuntimeConfig.get()
        if not config:
            return

        path = flow.request.path

        if config.response_delay.enabled and path in config.response_delay.delay_path:
            await asyncio.sleep(config.response_delay.delay)

    def _format_address(self, address) -> str:
        if not address:
            return ""
        if len(address) >= 2:
            return f"{address[0]}:{address[1]}"
        return str(address)

    def _format_query(self, flow: HTTPFlow) -> str:
        return self._format_headers(self._iter_items(flow.request.query), separator="=")

    def _resolve_request_host(self, flow: HTTPFlow) -> str:
        request = flow.request
        candidates = [
            self._host_from_url(getattr(request, "pretty_url", "")),
            str(getattr(request, "pretty_host", "") or "").strip(),
            self._host_from_authority(getattr(request, "host_header", "")),
            self._host_from_authority(request.headers.get("host", "")),
            str(getattr(request, "host", "") or "").strip(),
        ]
        for candidate in candidates:
            if candidate:
                return candidate
        return ""

    def _host_from_url(self, url: str) -> str:
        raw_url = str(url or "").strip()
        if not raw_url:
            return ""
        try:
            return str(urlsplit(raw_url).hostname or "").strip()
        except Exception:
            return ""

    def _host_from_authority(self, authority: str) -> str:
        raw_authority = str(authority or "").strip()
        if not raw_authority:
            return ""
        if "://" not in raw_authority:
            raw_authority = f"tcp://{raw_authority}"
        try:
            return str(urlsplit(raw_authority).hostname or "").strip()
        except Exception:
            return ""

    def _calculate_duration_ms(self, flow: HTTPFlow, item: FlowItem) -> int | None:
        request_start = getattr(flow.request, "timestamp_start", None)
        response_end = getattr(flow.response, "timestamp_end", None) or getattr(
            flow.response, "timestamp_start", None
        )
        if request_start and response_end and response_end >= request_start:
            return int((response_end - request_start) * 1000)

        elapsed = datetime.now() - item.time
        return max(int(elapsed.total_seconds() * 1000), 0)

    def _split_paths(self, raw_value: str) -> list[str]:
        paths = []
        for line in (raw_value or "").splitlines():
            for item in line.split(","):
                value = item.strip()
                if value:
                    paths.append(value)
        return paths

    def _parse_key_values(self, raw_value: str) -> dict[str, str]:
        values = {}
        for line in (raw_value or "").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key:
                values[key] = value
        return values

    def _build_mock_payload(self, flow: HTTPFlow, extra_body_raw: str):
        extra_body = self._parse_key_values(extra_body_raw)
        form_data = dict(flow.request.urlencoded_form)

        json_data = None
        try:
            parsed = flow.request.json()
            json_data = parsed if parsed is not None else None
        except Exception:
            json_data = None

        if isinstance(json_data, dict) and extra_body:
            json_data = {**json_data, **extra_body}
        elif form_data and extra_body:
            form_data = {**form_data, **extra_body}
        elif extra_body and json_data is None:
            form_data = extra_body

        return json_data, form_data or None

    def _iter_items(self, mapping):
        try:
            return list(mapping.items(multi=True))
        except TypeError:
            return list(mapping.items())

    def _resolve_message_content(self, message) -> bytes:
        """获取 HTTP 消息内容，优先使用 mitmproxy 解码后的 body，失败时回退原始字节。"""
        if message is None:
            return b""

        get_content = getattr(message, "get_content", None)
        if callable(get_content):
            content = None
            try:
                content = get_content(strict=False)
            except TypeError:
                try:
                    content = get_content()
                except Exception:
                    content = None
            except Exception:
                content = None
            if isinstance(content, bytes):
                return content
            if isinstance(content, bytearray):
                return bytes(content)
            if isinstance(content, str):
                return content.encode("utf-8", errors="replace")

        content = getattr(message, "content", None)
        if isinstance(content, bytes):
            return content
        if isinstance(content, bytearray):
            return bytes(content)
        if isinstance(content, str):
            return content.encode("utf-8", errors="replace")

        raw_content = getattr(message, "raw_content", None)
        if isinstance(raw_content, bytes):
            return raw_content
        if isinstance(raw_content, bytearray):
            return bytes(raw_content)
        if isinstance(raw_content, str):
            return raw_content.encode("utf-8", errors="replace")
        return b""

    def _format_headers(self, items, separator=": ") -> str:
        lines = []
        for key, value in items:
            lines.append(f"{key}{separator}{value}")
        return "\n".join(lines)

    def _format_content(self, content: bytes, content_type: str) -> str:
        if not content:
            return ""

        normalized_type = (content_type or "").lower()
        if self._is_textual_content(normalized_type):
            text = content.decode("utf-8", errors="replace")
            if "json" in normalized_type:
                try:
                    parsed = json.loads(text)
                    return json.dumps(parsed, indent=2, ensure_ascii=False)
                except Exception:
                    return text
            return text

        try:
            text = content.decode("utf-8")
            printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
            if printable / max(len(text), 1) > 0.9:
                return text
        except Exception:
            pass

        return f"<binary content: {len(content)} bytes>"

    def _is_textual_content(self, content_type: str) -> bool:
        return any(
            marker in content_type
            for marker in (
                "json",
                "xml",
                "html",
                "text/",
                "javascript",
                "x-www-form-urlencoded",
                "graphql",
                "svg",
            )
        )
