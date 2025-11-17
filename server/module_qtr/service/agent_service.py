import asyncio
import base64
import datetime
import json
import re
import uuid
from collections import defaultdict
from typing import Any

import httpx
from fastapi import WebSocket
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from websockets import WebSocketClientProtocol

from module_hrm.enums.enums import TstepTypeEnum, AgentResponseEnum
from module_hrm.utils.util import compress_dict_to_str, decompress_str_to_dict
from utils.log_util import logger

# 存储agent的WebSocket连接和Future对象（用于HTTP请求等待WebSocket响应）
agents: dict = {}
response_futures = defaultdict(dict)
CHUNK_SIZE = 1024 * 16


async def send_message(agent_code: str, message: dict, request_id: str = None):
    logger.info(f"agent_code: {agent_code}")
    request_type = message.get('requestType')
    logger.info(f"转发类型: {request_type}")
    # 如果没有提供request_id，则生成一个唯一的标识符
    if not request_id:
        request_id = str(uuid.uuid4())
    message["request_id"] = request_id

    if agent_code in agents:
        # 创建一个Future对象来代表异步操作的结果
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # 将Future对象存储在字典中，以便稍后设置其结果
        response_futures[request_id]["future"] = future

        # 发送消息到WebSocket，并包含request_id以便客户端能够识别是哪个请求的响应
        compress_data = compress_dict_to_str(message)
        request_chunks = [compress_data[i:i+CHUNK_SIZE] for i in range(0, len(compress_data), CHUNK_SIZE)]
        total = len(request_chunks) or 1
        for idx, chunk in enumerate(request_chunks):
            message_data = {
                "type": "request_chunk",
                "index": idx,
                "total": total,
                "request_id": request_id,
                "data": chunk,
                "finished": (idx == total - 1),
                "binary": False,
                "meta": {}

            }
            await agents[agent_code].send_text(json.dumps(message_data))

        # 等待Future对象的结果（即WebSocket客户端的响应）
        try:
            response_data = await asyncio.wait_for(future, timeout=120)
            logger.info(f"response={response_data}")
            response = {}
            if response_data.get("Error", None):
                return handle_response((AgentResponseEnum.UNKNOWN_EXCEPTION.value, response_data, f"客户端中发生异常：{response_data.get('Error')}"))

            if response_data.get("request_type") == TstepTypeEnum.http.value:
                response = AgentResponse(response_data)
            elif response_data.get("request_type") == TstepTypeEnum.websocket.value:
                response = AgentResponseWebSocket(response_data)
                # logger.info(f"ws响应数据：{response}")
            else:
                return handle_response((AgentResponseEnum.UNKNOWN_EXCEPTION.value, response_data, f"响应数据类型【{response_data.get('request_type')}】不支持"))

            response = handle_response((AgentResponseEnum.SUCCESS.value, response, "操作成功"))
            return response
        except asyncio.TimeoutError as e:
            logger.error(f'websocket请求超时{e}，request_id：{request_id}')
            if request_type == TstepTypeEnum.http.value:
                response = handle_response((AgentResponseEnum.OPERATION_TIMEOUT.value, None, f'wobsocket请求超时{e}，request_id：{request_id}'))
                return response
            elif request_type == TstepTypeEnum.websocket.value:
                response = handle_response((AgentResponseEnum.OPERATION_TIMEOUT.value, None, f'wobsocket请求超时{e}，request_id：{request_id}'))
                return response
        except asyncio.CancelledError as e:
            logger.error(e)
            response = handle_response((AgentResponseEnum.TASK_CANCELLED.value, None, str(e.args)))
            return response
        except Exception as e:
            logger.error(e)
            response = handle_response((AgentResponseEnum.UNKNOWN_EXCEPTION.value, None, str(e.args)))
            return response
        finally:
            if future and not future.done():
                future.cancel()


    else:
        response = handle_response((AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value, None, f"【{agent_code}】Agent not connected，request_id：{request_id}"))
        return response


class Request:
    def __init__(self, message: dict, request_id: str = None):
        self.message = message
        self.request_id = request_id

    @property
    def url(self):
        return self.message.get('url').get('url')


class URL:
    def __init__(self, message: dict, request_id: str = None):
        self.message = message
        self.request_id = request_id


class AgentResponse(httpx.Response):

    def __init__(self, message: dict,  request_id: str = None):
        self.message = message
        self.request_id = request_id

    @property
    def status_code(self):
        return self.message.get('status_code')

    @property
    def elapsed(self) -> datetime.timedelta|None:
        # 正则表达式匹配字符串，提取天数、小时、分钟、秒和微秒（可选）
        s = self.message.get('elapsed', None)
        if s is None:
            return None
        pattern = re.compile(r"(?:(\d+) days, )?(\d+):(\d+):(\d+)(?:\.(\d+))?")
        match = pattern.match(s)
        if not match:
            raise ValueError("Invalid timedelta string format")

        # 提取匹配到的组（如果存在的话）
        days, hours, minutes, seconds, microseconds = match.groups()

        # 将提取到的字符串转换为整数（如果存在的话），否则为0
        days = int(days) if days else 0
        hours = int(hours) if hours else 0
        minutes = int(minutes) if minutes else 0
        seconds = int(seconds) if seconds else 0
        microseconds = int(microseconds) if microseconds else 0

        # 根据提取到的信息创建timedelta对象
        return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds,
                                  microseconds=microseconds * 1000)  # 注意：将毫秒转换回微秒

    @property
    def request(self) -> Request:
        return Request(self.message, self.request_id)

    @property
    def headers(self) -> dict:
        return self.message.get('headers')

    @property
    def http_version(self) -> str:
        return self.message.get('http_version')

    @property
    def reason_phrase(self) -> str:
        return self.message.get('reason_phrase')

    @property
    def url(self):
        return self.message.get('url')

    @property
    def content(self) -> bytes:
        return self.message.get('content').encode('utf-8')

    @property
    def text(self) -> str:
        return self.message.get('text')

    @property
    def encoding(self) -> str | None:
        return self.message.get('encoding')

    @property
    def charset_encoding(self) -> str | None:
        return self.message.get('charset_encoding')

    @property
    def is_informational(self) -> bool:
        return self.message.get('is_informational')

    @property
    def is_success(self) -> bool:
        return self.message.get('is_success')

    @property
    def is_redirect(self) -> bool:
        return self.message.get('is_redirect')

    @property
    def is_client_error(self) -> bool:
        return self.message.get('is_client_error')

    @property
    def is_server_error(self) -> bool:
        return self.message.get('is_server_error')

    @property
    def is_error(self) -> bool:
        return self.message.get('is_error')

    @property
    def has_redirect_location(self) -> bool:
        return self.message.get('has_redirect_location')

    @property
    def cookies(self):
        return self.message.get('cookies')

    @property
    def links(self) -> dict[str | None, dict[str, str]]:
        return self.message.get('links')

    @property
    def num_bytes_downloaded(self) -> int:
        return self.message.get('num_bytes_downloaded')

    def json(self):
        return json.loads(self.text)


class AgentResponseWebSocket(WebSocketClientProtocol):
    def __init__(self, message: dict, request_id: str = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.message = message
        self.request_id = request_id

    @property
    def websocket_data(self):
        return self.message.get('ws_res_data')

    @property
    def response_headers(self):
        return json.loads(self.message.get('response_headers'))


class HandleResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, arbitrary_types_allowed=True)
    status_code: int = 200
    response: AgentResponse | AgentResponseWebSocket | None = None
    message: str = None


def handle_response(args: tuple) -> HandleResponse:
    res_data = {
        "statusCode": args[0],
        "response": args[1],
        "message": args[2],
    }
    res_data = HandleResponse(**res_data)
    return res_data
