import asyncio
import json
from collections import defaultdict

import websockets

from loguru import logger

from common.utils import compress_dict_to_str, decompress_str_to_dict

# websocket发送数据分片大小
MAX_MESSAGE_SIZE = 1024 * 16
# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 30


request_all_chunk = defaultdict(str)


class WebSocketClient:
    def __init__(self, uri, on_message):
        # self.uri = uri
        self.uri = "ws://localhost:9099/qtr/agent/ws/1111111"
        self.agent_code = self.uri.split('/')[-1]
        self.on_message = on_message
        # 客户端websocket是否已启动
        self.running = False
        self.websocket = None
        self.status = False
        self.loop = None
        self.websocket_client_thread = None

    async def connect(self):
        self.running = True
        self.status = True
        try:
            self.websocket = await websockets.connect(self.uri)
            while self.running:
                # await self.send_heart()
                message = await self.websocket.recv()
                # logger.info(f'收到的消息:{message}')
                msg = json.loads(message)
                if msg["type"] == "ping":
                    self.status = True
                    asyncio.create_task(self.send_heart())
                    # logger.info(msg.get('message'))
                else:
                    asyncio.create_task(self.handle_message_chunk(msg))
        except ConnectionRefusedError as e:
            logger.error(e)
            logger.info('连接异常断开，30秒后重新尝试连接')
            await self.reconnect(30)
        except websockets.exceptions.ConnectionClosedError:
            logger.info('服务端异常断开，5秒后重新尝试连接')
            await self.reconnect()
        except websockets.exceptions.ConnectionClosedOK:
            logger.info('连接异常断开，5秒后重新尝试连接')
            await self.reconnect()
        except TypeError as e:
            logger.error(e)
            logger.info('客户端数据处理异常,5秒后重新建立连接')
            await self.reconnect()
        except Exception as e:
            self.status = False
            logger.error(f'未知异常，连接中断：{e}')
            logger.exception(e)
            logger.info('未知异常,5秒后重新建立连接')
            await self.reconnect()
        finally:
            # logger.info(f"我是finally")
            self.status = False

    async def handle_message_chunk(self, message_dict):
        # 处理接收到的数据，并获取响应
        request_id = message_dict["request_id"]
        request_all_chunk[request_id] += message_dict["data"]
        if not message_dict["finished"]:
            return
        request_data = decompress_str_to_dict(request_all_chunk.pop(request_id))
        response = await self.on_message(request_data)
        response = compress_dict_to_str(response)
        # 如果响应不是None，则发送它回去
        if response is not None:
            # 分片发送
            response_chunks = [response[i:i + MAX_MESSAGE_SIZE] for i in range(0, len(response), MAX_MESSAGE_SIZE)]
            total_size = len(response_chunks) or 1
            for idx, chunk in enumerate(response_chunks):
                chunk_message = {
                    'type': 'response_chunk',
                    'index': idx,
                    'total': total_size,
                    'data': chunk,
                    "finished": (total_size == idx + 1)
                }
                # 发送分片消息
                await self.send_message(chunk_message)

    async def reconnect(self, interval_time=5):
        """
        重新建立连接
        :param interval_time: 时间间隔,默认5秒
        """
        try:
            self.update_status(False)
            await asyncio.sleep(interval_time)
            await self.connect()
        except ConnectionRefusedError as e:
            logger.info('远程计算机拒绝网络连接，30秒后重新尝试连接')
            await self.reconnect(30)

    async def send_message(self, message):
        """
        发送的消息体必须为字典类型
        :param message: 消息体
        """
        await self.websocket.send(json.dumps(message))

    async def send_close(self):
        """主动断开连接"""
        try:
            await self.websocket.close(code=1000, reason="关闭连接")
        except websockets.exceptions.ConnectionClosedOK:
            logger.info('连接已断开')

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
            await self.websocket.send(json.dumps({"type": "pong", "status": "ok", "message": f"client {self.agent_code} is alive"}))
            # await asyncio.sleep(HEARTBEAT_INTERVAL)
            self.status = True
        except Exception as e:
            logger.error(f'客户端向服务端发送心跳发送异常：{e}')
