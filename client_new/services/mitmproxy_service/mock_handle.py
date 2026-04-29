import asyncio
import json
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import httpx
from loguru import logger
from mitmproxy.http import HTTPFlow, Response

from models.mitmproxy_common import FlowItem
from utils.http_defaults import DEFAULT_HTTP_TIMEOUT

from .runtime_config import RuntimeConfig


class MockHandle:
    BREAKPOINT_WAIT_TIMEOUT_SECONDS = 180.0
    BREAKPOINT_MOCK_PROBE_TIMEOUT_SECONDS = 0.2

    def __init__(
        self,
        flow_dispatcher=None,
        emit_flows: bool = True,
        breakpoint_manager=None,
    ):
        self._flow_dispatcher = flow_dispatcher
        self._emit_flows = emit_flows
        self._breakpoint_manager = breakpoint_manager

    def _emit_flow(self, event_type: str, item: FlowItem):
        """
        分发流量事件到上层。
        :param event_type: 事件类型（new/update）
        :param item: 流量对象
        :return:
        """
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
        """
        处理请求阶段：记录流量、按规则执行断点、再执行 mock/真实请求逻辑。
        :param flow: mitmproxy 请求流
        :return:
        """
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
        flow.metadata["breakpoint_matched"] = False

        self._emit_flow("new", item)

        config = RuntimeConfig.get()
        if not config:
            return

        if self._is_breakpoint_match(config, flow):
            flow.metadata["breakpoint_matched"] = True
            try:
                item.breakpoint_matched = True
                item.breakpoint_stage = "request"
                item.breakpoint_paused = True
                item.breakpoint_status_text = "请求已暂停，等待放行"
                self._emit_flow("update", item)

                pause_started_at = datetime.now()
                override_payload = await self._wait_for_breakpoint_continue(
                    flow.id, "request"
                )
                wait_ms = int((datetime.now() - pause_started_at).total_seconds() * 1000)
                flow.metadata["breakpoint_wait_ms"] = wait_ms
                self._apply_request_override(flow, override_payload)
                self._update_request_item(item, flow)
                item.breakpoint_stage = "request"
                item.breakpoint_paused = False
                item.breakpoint_status_text = "请求已放行，等待响应"
                self._emit_flow("update", item)
                logger.info(
                    f"断点请求已放行 flow_id={flow.id}, wait_ms={wait_ms}"
                )
            except Exception as e:
                item.breakpoint_stage = "request"
                item.breakpoint_paused = False
                item.breakpoint_status_text = f"请求断点处理异常，已自动放行: {e}"
                self._emit_flow("update", item)
                logger.exception(f"请求断点处理异常 flow_id={flow.id}: {e}")

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
            probe_timeout = DEFAULT_HTTP_TIMEOUT
            if flow.metadata.get("breakpoint_matched"):
                probe_timeout = self.BREAKPOINT_MOCK_PROBE_TIMEOUT_SECONDS
            json_data, form_data = self._build_mock_payload(flow, config.add_body)
            headers = self._parse_key_values(config.add_headers)

            async with httpx.AsyncClient(
                timeout=probe_timeout,
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

        except httpx.TimeoutException:
            logger.info(
                f"mock 规则探测超时，继续真实请求: {path}, timeout={probe_timeout}s"
            )
            return
        except Exception as e:
            logger.exception(e)

    async def response(self, flow: HTTPFlow):
        """
        处理响应阶段：记录响应详情并在断点命中时暂停，支持放行前修改响应。
        :param flow: mitmproxy 请求流
        :return:
        """
        logger.info(
            f"收到响应 flow_id={flow.id}, path={flow.request.path}, status={getattr(flow.response, 'status_code', None)}"
        )
        item = flow.metadata.get("ui_item")
        if item:
            self._update_response_item(item, flow)
            self._emit_flow("update", item)

        config = RuntimeConfig.get()
        if not config:
            return

        path = flow.request.path
        if config.response_delay.enabled and path in config.response_delay.delay_path:
            await asyncio.sleep(config.response_delay.delay)

        if not item:
            return

        if not flow.metadata.get("breakpoint_matched"):
            return

        try:
            item.breakpoint_matched = True
            item.breakpoint_stage = "response"
            item.breakpoint_paused = True
            item.breakpoint_status_text = "响应已暂停，等待放行"
            self._emit_flow("update", item)

            override_payload = await self._wait_for_breakpoint_continue(flow.id, "response")
            self._apply_response_override(flow, override_payload)
            self._update_response_item(item, flow)
            item.breakpoint_stage = "response"
            item.breakpoint_paused = False
            item.breakpoint_status_text = "响应已放行"
            self._emit_flow("update", item)
            logger.info(f"断点响应已放行 flow_id={flow.id}")
        except Exception as e:
            item.breakpoint_stage = "response"
            item.breakpoint_paused = False
            item.breakpoint_status_text = f"响应断点处理异常，已自动放行: {e}"
            self._emit_flow("update", item)
            logger.exception(f"响应断点处理异常 flow_id={flow.id}: {e}")

    async def error(self, flow: HTTPFlow):
        """
        处理请求错误（如连接失败/超时），避免界面看起来“无响应”。
        :param flow: mitmproxy 请求流
        :return:
        """
        error_message = str(getattr(flow, "error", "") or "")
        logger.warning(
            f"请求异常 flow_id={flow.id}, path={flow.request.path}, error={error_message}"
        )
        item = flow.metadata.get("ui_item")
        if not item:
            return

        item.status_code = 0
        item.response_reason = "ERROR"
        item.response_http_version = ""
        item.response_headers = ""
        item.response_body = error_message
        item.response_content_type = "text/plain"
        item.duration_ms = self._calculate_duration_ms(flow, item)
        item.breakpoint_paused = False
        item.breakpoint_stage = ""
        item.breakpoint_status_text = f"请求失败: {error_message}"
        self._emit_flow("update", item)

    async def _wait_for_breakpoint_continue(self, flow_id: str, stage: str) -> dict:
        """
        等待 UI 放行断点。
        :param flow_id: 流量id
        :param stage: 断点阶段（request/response）
        :return: 覆盖数据
        """
        manager = self._breakpoint_manager
        if not manager:
            return {}
        try:
            payload = await asyncio.wait_for(
                manager.wait_for_continue(flow_id, stage),
                timeout=self.BREAKPOINT_WAIT_TIMEOUT_SECONDS,
            )
            return payload if isinstance(payload, dict) else {}
        except asyncio.TimeoutError:
            logger.warning(
                f"断点等待超时，自动放行 flow_id={flow_id}, stage={stage}, timeout={self.BREAKPOINT_WAIT_TIMEOUT_SECONDS}s"
            )
            return {}
        except Exception as e:
            logger.warning(f"断点等待异常 flow_id={flow_id}, stage={stage}, err={e}")
            return {}

    def _is_breakpoint_match(self, config: Any, flow: HTTPFlow) -> bool:
        """
        判断当前请求是否命中断点规则。
        :param config: 运行时配置
        :param flow: mitmproxy 请求流
        :return: 是否命中
        """
        enabled = bool(getattr(config, "breakpoint_enabled", False))
        raw_pattern = str(getattr(config, "breakpoint_pattern", "") or "").strip()
        if not enabled or not raw_pattern:
            return False

        patterns = self._split_paths(raw_pattern)
        if not patterns:
            return False

        url = str(flow.request.pretty_url or "")
        path = str(flow.request.path or "")
        for pattern in patterns:
            if pattern and (pattern in url or pattern in path):
                return True
        return False

    def _update_request_item(self, item: FlowItem, flow: HTTPFlow):
        """
        按当前 flow 更新请求侧展示字段。
        :param item: 流量对象
        :param flow: mitmproxy 请求流
        :return:
        """
        item.method = flow.request.method
        item.url = flow.request.pretty_url
        item.path = flow.request.path
        item.request_scheme = flow.request.scheme
        item.request_host = self._resolve_request_host(flow)
        item.request_port = flow.request.port
        item.request_http_version = flow.request.http_version
        item.request_query = self._format_query(flow)
        item.request_headers = self._format_headers(self._iter_items(flow.request.headers))
        item.request_cookies = self._format_headers(
            self._iter_items(flow.request.cookies),
            separator="=",
        )
        item.request_form = self._format_headers(
            self._iter_items(flow.request.urlencoded_form),
            separator="=",
        )
        item.request_body = self._format_content(
            self._resolve_message_content(flow.request),
            flow.request.headers.get("content-type", ""),
        )
        item.request_content_type = flow.request.headers.get("content-type", "")

    def _update_response_item(self, item: FlowItem, flow: HTTPFlow):
        """
        按当前 flow 更新响应侧展示字段。
        :param item: 流量对象
        :param flow: mitmproxy 请求流
        :return:
        """
        duration_ms = self._calculate_duration_ms(flow, item)
        item.status_code = flow.response.status_code
        item.size = len(flow.response.content or b"")
        item.response_reason = getattr(flow.response, "reason", "")
        item.response_http_version = getattr(flow.response, "http_version", "")
        item.response_headers = self._format_headers(self._iter_items(flow.response.headers))
        item.response_body = self._format_content(
            self._resolve_message_content(flow.response),
            flow.response.headers.get("content-type", ""),
        )
        item.response_content_type = flow.response.headers.get("content-type", "")
        item.duration_ms = duration_ms

    def _apply_request_override(self, flow: HTTPFlow, payload: dict):
        """
        应用请求阶段的编辑结果。
        :param flow: mitmproxy 请求流
        :param payload: 覆盖数据
        :return:
        """
        if not isinstance(payload, dict):
            return

        method = str(payload.get("method", "") or "").strip().upper()
        if method:
            flow.request.method = method

        request_url = str(payload.get("url", "") or "").strip()
        if request_url:
            flow.request.url = request_url

        if "headers" in payload:
            self._set_message_headers(flow.request, str(payload.get("headers", "") or ""))

        if "body" in payload:
            self._set_message_body(flow.request, payload.get("body"))

    def _apply_response_override(self, flow: HTTPFlow, payload: dict):
        """
        应用响应阶段的编辑结果。
        :param flow: mitmproxy 请求流
        :param payload: 覆盖数据
        :return:
        """
        if not isinstance(payload, dict) or not flow.response:
            return

        status_code_raw = payload.get("status_code")
        if status_code_raw not in (None, ""):
            try:
                status_code = int(status_code_raw)
                if status_code > 0:
                    flow.response.status_code = status_code
            except Exception:
                logger.warning(f"忽略非法响应状态码: {status_code_raw}")

        if "reason" in payload:
            reason = str(payload.get("reason", "") or "").strip()
            if reason:
                try:
                    flow.response.reason = reason
                except Exception:
                    pass

        if "headers" in payload:
            self._set_message_headers(flow.response, str(payload.get("headers", "") or ""))

        if "body" in payload:
            self._set_message_body(flow.response, payload.get("body"))

    def _set_message_headers(self, message: Any, raw_headers: str):
        """
        用编辑后的文本覆盖消息头。
        :param message: HTTP 请求或响应对象
        :param raw_headers: 文本头，按行分隔
        :return:
        """
        parsed_headers = self._parse_header_lines(raw_headers)
        if not parsed_headers:
            return
        try:
            message.headers.clear()
            for key, value in parsed_headers:
                message.headers.add(key, value)
        except Exception as e:
            logger.warning(f"覆盖消息头失败: {e}")

    def _set_message_body(self, message: Any, raw_body: Any):
        """
        用编辑后的文本覆盖消息体。
        :param message: HTTP 请求或响应对象
        :param raw_body: 文本消息体
        :return:
        """
        if raw_body is None:
            return
        body_text = str(raw_body)
        try:
            if hasattr(message, "set_text"):
                message.set_text(body_text)
            else:
                message.content = body_text.encode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"覆盖消息体失败: {e}")

    def _parse_header_lines(self, raw_headers: str) -> list[tuple[str, str]]:
        """
        解析多行请求头文本。
        :param raw_headers: 文本头，支持 `Key: Value`
        :return: 键值对列表
        """
        result: list[tuple[str, str]] = []
        for line in (raw_headers or "").splitlines():
            current_line = line.strip()
            if not current_line:
                continue
            if ":" in current_line:
                key, value = current_line.split(":", 1)
            elif "=" in current_line:
                key, value = current_line.split("=", 1)
            else:
                continue
            key = key.strip()
            value = value.strip()
            if key:
                result.append((key, value))
        return result

    def _format_address(self, address) -> str:
        """
        格式化连接地址。
        :param address: 地址元组
        :return: host:port 文本
        """
        if not address:
            return ""
        if len(address) >= 2:
            return f"{address[0]}:{address[1]}"
        return str(address)

    def _format_query(self, flow: HTTPFlow) -> str:
        """
        格式化请求 query 参数。
        :param flow: mitmproxy 请求流
        :return: 文本 query
        """
        return self._format_headers(self._iter_items(flow.request.query), separator="=")

    def _resolve_request_host(self, flow: HTTPFlow) -> str:
        """
        解析请求 host。
        :param flow: mitmproxy 请求流
        :return: host 文本
        """
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
        """
        从 URL 提取 host。
        :param url: URL 文本
        :return: host
        """
        raw_url = str(url or "").strip()
        if not raw_url:
            return ""
        try:
            return str(urlsplit(raw_url).hostname or "").strip()
        except Exception:
            return ""

    def _host_from_authority(self, authority: str) -> str:
        """
        从 authority 提取 host。
        :param authority: host[:port] 文本
        :return: host
        """
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
        """
        计算请求耗时（毫秒）。
        :param flow: mitmproxy 请求流
        :param item: 流量对象
        :return: 耗时毫秒
        """
        request_start = getattr(flow.request, "timestamp_start", None)
        response_end = getattr(flow.response, "timestamp_end", None) or getattr(
            flow.response, "timestamp_start", None
        )
        if request_start and response_end and response_end >= request_start:
            return int((response_end - request_start) * 1000)

        elapsed = datetime.now() - item.time
        return max(int(elapsed.total_seconds() * 1000), 0)

    def _split_paths(self, raw_value: str) -> list[str]:
        """
        按换行与逗号拆分路径列表。
        :param raw_value: 原始文本
        :return: 路径列表
        """
        paths = []
        for line in (raw_value or "").splitlines():
            for item in line.split(","):
                value = item.strip()
                if value:
                    paths.append(value)
        return paths

    def _parse_key_values(self, raw_value: str) -> dict[str, str]:
        """
        解析 `k=v` 形式文本为字典。
        :param raw_value: 原始文本
        :return: 字典
        """
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
        """
        构造发送到 mock 服务器的请求负载。
        :param flow: mitmproxy 请求流
        :param extra_body_raw: 额外 body 文本
        :return: (json_data, form_data)
        """
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
        """
        兼容 mitmproxy 映射对象迭代。
        :param mapping: mapping 对象
        :return: 键值对列表
        """
        try:
            return list(mapping.items(multi=True))
        except TypeError:
            return list(mapping.items())

    def _resolve_message_content(self, message) -> bytes:
        """
        获取 HTTP 消息内容，优先使用 mitmproxy 解码后的 body，失败时回退原始字节。
        :param message: 请求或响应对象
        :return: 原始字节
        """
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
        """
        格式化键值对文本。
        :param items: 键值对可迭代对象
        :param separator: 分隔符
        :return: 多行文本
        """
        lines = []
        for key, value in items:
            lines.append(f"{key}{separator}{value}")
        return "\n".join(lines)

    def _format_content(self, content: bytes, content_type: str) -> str:
        """
        将字节内容格式化为可展示文本。
        :param content: 原始字节
        :param content_type: Content-Type
        :return: 文本内容
        """
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
        """
        判断 Content-Type 是否文本类型。
        :param content_type: Content-Type
        :return: 是否文本类型
        """
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
