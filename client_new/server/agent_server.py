import asyncio
import json
import traceback
import uuid
from collections import defaultdict
from enum import Enum
from typing import Any, Awaitable, Callable

import httpx
import websockets
from httpx import HTTPError
from loguru import logger
from websockets.exceptions import InvalidStatus
from websockets.protocol import State

from services.desktop_test_service import DesktopTestService
from services.web_test_service import WebTestService
from utils.common import compress_dict_to_str, decompress_str_to_dict

# websocket发送数据分片大小
DEFAULT_MESSAGE_SIZE = 5 * 1024
MAX_MESSAGE_SIZE = DEFAULT_MESSAGE_SIZE
EVENT_CHUNK_TYPE = "event_chunk"
# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 30

request_all_chunk = defaultdict(str)


def _is_websocket_open(websocket) -> bool:
    if websocket is None:
        return False

    closed = getattr(websocket, "closed", None)
    if closed is not None:
        return not closed

    state = getattr(websocket, "state", None)
    if state is None:
        return True

    return state == State.OPEN or getattr(state, "name", None) == "OPEN"


def _get_websocket_response_headers(websocket) -> dict:
    response_headers = getattr(websocket, "response_headers", None)
    if response_headers is not None:
        return dict(response_headers)

    response = getattr(websocket, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        return dict(headers)

    return {}


def clamp_message_size(value: Any) -> int:
    try:
        size = int(value)
    except Exception:
        size = DEFAULT_MESSAGE_SIZE
    return max(1024, size)


def _split_payload(payload: str, chunk_size: int) -> list[str]:
    safe_chunk_size = clamp_message_size(chunk_size)
    if not payload:
        return [""]
    return [payload[i : i + safe_chunk_size] for i in range(0, len(payload), safe_chunk_size)]


class RequestByInput:
    def __init__(self):
        pass

    @classmethod
    async def forward_by_rules(
        cls,
        message_data_dict: dict,
        http_client: httpx.AsyncClient,
        event_sender: Callable[[dict], Awaitable[None]] | None = None,
    ) -> (dict, bool):
        """根据入参转发请求"""
        logger.info(f"请求数据：{json.dumps(message_data_dict, ensure_ascii=True)}")
        client_status = True

        request_type = message_data_dict.pop("requestType")
        request_id = message_data_dict.pop("request_id")
        res_data = {}
        if request_type == RequestTypeEnum.http.value:
            try:
                res_response = await http_client.request(**message_data_dict)
                res_data = cls.serialize_response(res_response)
            except HTTPError as e:
                logger.error(e)
                res_data["Error"] = f"HTTPError：【{type(e).__name__}】{e}"
                # client_status = False
            except Exception as e:
                logger.error(e)
                res_data["Error"] = "".join(traceback.format_exception(e))
                # client_status = False
            res_data["request_id"] = request_id
            res_data["request_type"] = request_type
            return res_data, client_status
        elif request_type == RequestTypeEnum.websocket.value:
            try:
                ws_res_data, response_headers = await cls.websocket_agent(
                    message_data_dict
                )
                res_data = {
                    "ws_res_data": ws_res_data,
                    "response_headers": response_headers,
                }
                logger.info(f"ws响应数据：{res_data},ws响应headers:{response_headers}")
            except InvalidStatus as e:
                logger.error(e.args)
                res_data["Error"] = "".join(traceback.format_exception(e))
                # client_status = False
            except Exception as e:
                logger.error(e.args)
                res_data["Error"] = "".join(traceback.format_exception(e))
                # client_status = False
            res_data["request_id"] = request_id
            res_data["request_type"] = request_type
            return res_data, client_status
        elif request_type == RequestTypeEnum.webui.value:
            try:
                res_data = await WebTestService.handle_request(message_data_dict, event_sender)
            except Exception as e:
                logger.exception(e)
                res_data = {"Error": "".join(traceback.format_exception(e))}
            res_data["request_id"] = request_id
            res_data["request_type"] = request_type
            return res_data, client_status
        elif request_type == RequestTypeEnum.desktopui.value:
            try:
                res_data = await DesktopTestService.handle_request(message_data_dict, event_sender)
            except Exception as e:
                logger.exception(e)
                res_data = {"Error": "".join(traceback.format_exception(e))}
            res_data["request_id"] = request_id
            res_data["request_type"] = request_type
            return res_data, client_status
        else:
            res_data = {
                "request_id": request_id,
                "request_type": request_type,
                "message": f"请求类型错误:{get_enum_name(RequestTypeEnum, request_type)}",
            }
            return res_data, client_status

    @classmethod
    async def websocket_agent(cls, req_data: dict):
        uri = req_data["url"]
        logger.info(f"ws请求地址:{uri}")
        ws_req_data = req_data.get("data")
        logger.info(f"ws请求入参:{ws_req_data}")
        recv_num = req_data.get("recv_num")
        logger.info(f"ws接收数据条数:{recv_num}")
        try:
            async with websockets.connect(uri) as websocket:
                await websocket.send(ws_req_data)
                res_data = []
                for i in range(recv_num):
                    response = await websocket.recv()
                    res_data.append(response)
                logger.info(f"响应数据{res_data}")
                response_headers = json.dumps(_get_websocket_response_headers(websocket))
                return res_data, response_headers
        except ConnectionError as e:
            logger.error(e)
            return json.dumps({"message": f"ConnectionError:{e}"}), None

    @classmethod
    def serialize_response(cls, response: httpx.Response):
        """httpx.Response对象转字典"""
        response_property = {
            "elapsed": cls.timedelta_to_str(response.elapsed),
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "cookies": dict(response.cookies),
            "text": response.text,
            # "json": json_data,
            "content": response.content.decode("utf-8"),
            "url": cls.serialize_url(response.url),
            "request": cls.serialize_request(response.request),
            "http_version": response.http_version,
            "reason_phrase": response.reason_phrase,
            "encoding": response.encoding,
            "charset_encoding": response.charset_encoding,
            "is_informational": response.is_informational,
            "is_success": response.is_success,
            "is_redirect": response.is_redirect,
            "is_client_error": response.is_client_error,
            "is_server_error": response.is_server_error,
            "is_error": response.is_error,
            "has_redirect_location": response.has_redirect_location,
            "links": dict(response.links),
            "num_bytes_downloaded": response.num_bytes_downloaded,
        }
        return response_property

    @classmethod
    def serialize_url(cls, url: httpx.URL):
        """httpx.URL对象转字典"""
        url_property = {
            "host": url.host,
            "path": url.path,
            "scheme": url.scheme,
            "query": url.query.decode("utf-8"),
            "fragment": url.fragment,
        }
        return url_property

    @classmethod
    def serialize_request(cls, request: httpx.Request):
        """httpx.Request对象转字典"""
        request_property = {
            "url": cls.serialize_url(request.url),
            "method": request.method,
            # "headers": request.headers
        }
        return request_property

    @classmethod
    def timedelta_to_str(cls, delta):
        """timedelta转字符串"""
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        microseconds = delta.microseconds // 1000  # 将微秒转换为毫秒（可选）
        return f"{days} days, {hours}:{minutes}:{seconds}.{microseconds}"


class WebSocketClient:
    def __init__(
        self,
        uri,
        before_request_call=None,
        after_request_call=None,
        status_callback: Callable[[str, str], None] | None = None,
    ):
        self.uri = uri or ""
        self.agent_code = self.uri.split("/")[-1]
        self.retry_num = 0
        self.max_retry_num = 0
        self.retry = False
        self.interval_time = 5
        self.running = False
        self.websocket = None
        self.status = False
        self.loop = None
        self.websocket_client_thread = None
        self.manual_stop = False

        self.before_request_call = before_request_call
        self.after_request_call = after_request_call
        self.status_callback = status_callback

    async def connect(
        self,
        uri=None,
        retry_num=None,
        retry=None,
        interval_time=None,
        is_retry=False,
    ):
        if not is_retry:
            self.retry_num = 0
            self.manual_stop = False
        self.uri = uri or self.uri
        self.agent_code = self.uri.split("/")[-1] if self.uri else ""
        self.max_retry_num = retry_num if retry_num is not None else self.max_retry_num
        self.retry = retry if retry is not None else self.retry
        self.interval_time = (
            interval_time if interval_time is not None else self.interval_time
        )
        self.running = True
        self.status = True
        try:
            self.websocket = await websockets.connect(self.uri, max_size=None)
            logger.info(f"服务链接成功：{self.uri}")
            self._notify_status("connected", f"服务连接成功：{self.uri}")
            async with httpx.AsyncClient(verify=False) as http_client:
                while self.running:
                    message = await self.websocket.recv()
                    msg = json.loads(message)
                    if msg["type"] == "ping":
                        self.status = True
                        asyncio.create_task(self.send_heart())
                    elif msg.get("type") == "request_chunk":
                        asyncio.create_task(self.handle_message_chunk(msg, http_client))
                    else:
                        logger.warning(f"收到未知消息类型: {msg.get('type')}")
        except ConnectionRefusedError as e:
            logger.error(e)
            self._notify_status("error", f"连接被拒绝：{e}")
            logger.info(
                f"连接异常断开，需要重试：{self.retry and self.max_retry_num > self.retry_num}，"
                f"{self.interval_time}秒后重新尝试连接, {self.uri}"
            )
            await self.reconnect()
        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(e)
            self._notify_status("error", f"服务端异常断开：{e}")
            logger.info(
                f"服务端异常断开，需要重试：{self.retry and self.max_retry_num > self.retry_num},"
                f"{self.interval_time}秒后重新尝试连接, {self.uri}"
            )
            await self.reconnect()
        except websockets.exceptions.ConnectionClosedOK as e:
            logger.info(f"连接关闭：{e}")
            await self.reconnect()
        except asyncio.CancelledError:
            logger.info("Agent 客户端协程已取消")
            raise
        except Exception as e:
            self.status = False
            logger.error(f"未知异常，连接中断：{e}")
            logger.exception(e)
            self._notify_status("error", f"未知异常，连接中断：{e}")
            await self.reconnect()
        finally:
            self.status = False
            self.websocket = None
            if self.manual_stop or not self.running:
                self._notify_status("stopped", "连接已停止")
            else:
                self._notify_status("disconnected", f"服务连接已断开：{self.uri}")

    async def handle_message_chunk(self, message_dict, http_client: httpx.AsyncClient):
        # 处理接收到的数据，并获取响应
        request_id = message_dict["request_id"]
        request_all_chunk[request_id] += message_dict["data"]
        if not message_dict["finished"]:
            return
        request_data = decompress_str_to_dict(request_all_chunk.pop(request_id))
        if self.before_request_call:
            self._safe_invoke(self.before_request_call, request_data)
        response, _ = await RequestByInput.forward_by_rules(request_data, http_client, self.send_event_message)
        if self.after_request_call:
            self._safe_invoke(self.after_request_call, response)
        response = compress_dict_to_str(response)
        # 如果响应不是None，则发送它回去
        if response is not None:
            await self._send_chunked_message(
                response,
                chunk_type="response_chunk",
                extra={"request_id": request_id},
            )

    async def _send_chunked_message(
        self,
        payload: str,
        *,
        chunk_type: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        chunks = _split_payload(payload, MAX_MESSAGE_SIZE)
        total_size = len(chunks) or 1
        for idx, chunk in enumerate(chunks):
            chunk_message = {
                "type": chunk_type,
                "index": idx,
                "total": total_size,
                "data": chunk,
                "finished": idx == total_size - 1,
                **(extra or {}),
            }
            await self.send_message(chunk_message)

    async def send_event_message(self, message: dict[str, Any]) -> None:
        payload = compress_dict_to_str(message)
        await self._send_chunked_message(
            payload,
            chunk_type=EVENT_CHUNK_TYPE,
            extra={
                "chunk_id": uuid.uuid4().hex,
                "message_type": message.get("type"),
                "recording_id": message.get("recording_id") or message.get("recordingId"),
            },
        )

    async def reconnect(self):
        """
        重新建立连接
        :param interval_time: 时间间隔,默认5秒
        """
        if (
            self.retry
            and self.max_retry_num > self.retry_num
            and self.running
            and not self.manual_stop
        ):
            self.retry_num += 1
            self.update_status(False)
            self._notify_status(
                "retry",
                f"连接已断开，{self.interval_time} 秒后重试 ({self.retry_num}/{self.max_retry_num})",
            )
            await asyncio.sleep(self.interval_time)
            await self.connect(is_retry=True)

    async def send_message(self, message):
        """
        发送的消息体必须为字典类型
        :param message: 消息体
        """
        if not _is_websocket_open(self.websocket):
            raise RuntimeError("WebSocket 未连接，无法发送消息")
        await self.websocket.send(json.dumps(message, ensure_ascii=False, separators=(",", ":")))

    async def send_close(self):
        """主动断开连接"""
        self.manual_stop = True
        self.running = False
        try:
            await WebTestService.shutdown_all_sessions()
        except Exception as e:
            logger.exception(f"关闭 Web 录制会话失败: {e}")
        try:
            await DesktopTestService.shutdown_all_sessions()
        except Exception as e:
            logger.exception(f"关闭 Desktop 录制会话失败: {e}")
        try:
            if _is_websocket_open(self.websocket):
                await self.websocket.close(code=1000, reason="关闭连接")
        except websockets.exceptions.ConnectionClosedOK:
            logger.info("连接已断开")

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect())

    # 更新状态标签的函数
    def update_status(self, status):
        self.status = status

    async def send_heart(self):
        """向服务端发送心跳"""
        try:
            # 发送心跳
            await self.websocket.send(
                json.dumps(
                    {
                        "type": "pong",
                        "status": "ok",
                        "message": f"client {self.agent_code} is alive",
                    }
                )
            )
            # await asyncio.sleep(HEARTBEAT_INTERVAL)
            self.status = True
        except Exception as e:
            logger.error(f"客户端向服务端发送心跳发送异常：{e}")

    def _notify_status(self, event_type: str, message: str):
        if not self.status_callback:
            return
        self._safe_invoke(self.status_callback, event_type, message)

    def _safe_invoke(self, callback, *args):
        try:
            callback(*args)
        except Exception as e:
            logger.exception(f"Agent 客户端回调执行失败: {e}")


class RequestTypeEnum(Enum):
    http = 1
    websocket = 2
    webui = 3
    folder = 4
    desktopui = 5


# 根据枚举值获取枚举名称
def get_enum_name(enum_class, enum_value):
    try:
        # 通过枚举的值获取枚举成员
        enum_member = enum_class(enum_value)
        # 返回枚举成员的名称
        return enum_member.name
    except ValueError:
        # 如果值不在枚举中，捕获异常并处理
        return None


class AgentResponseEnum(Enum):
    SUCCESS = 200  # 转发操作成功完成
    FAILURE = 400  # 转发操作失败
    OPERATION_TIMEOUT = 407  # 异步操作未在预定时间内完成，导致超时
    CONNECTION_TIMEOUT = 408  # 在尝试建立连接时超过了预定的时间限制，连接未能成功建立
    TRANSFER_TIMEOUT = (
        409  # 在数据传输过程中超过了预定的时间限制，数据未能完全传输到目标地址
    )
    CONNECTION_EXCEPTION = (
        410  # 在建立连接或维持连接过程中出现了异常，如网络错误、协议不匹配等
    )
    TASK_CANCELLED = 418  # 任务被取消
    UNKNOWN_EXCEPTION = 500  # 发生了未预期的异常
    WEBSOCKET_NOT_CONNECTED = 5008  # WebSocket 连接尚未建立或已断开，无法进行通信
