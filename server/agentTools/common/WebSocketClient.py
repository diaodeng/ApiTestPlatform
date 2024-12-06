import asyncio
import json

import websockets

from loguru import logger

# websocket发送数据分片大小
MAX_MESSAGE_SIZE = 1024
# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 30


class WebSocketClient:
    def __init__(self, uri, on_message):
        self.uri = uri
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
                # msg = json.loads(message)
                if 'ok' and "200" in message:
                    self.status = True
                    # logger.info(msg.get('message'))
                else:
                    # 处理接收到的数据，并获取响应
                    response = await self.on_message(message)
                    # 如果响应不是None，则发送它回去
                    if response is not None:
                        # 分片发送
                        chunk_size = MAX_MESSAGE_SIZE
                        total_size = len(response)
                        num_chunks = (total_size + chunk_size - 1) // chunk_size  # 向上取整计算分片数

                        for i in range(num_chunks):
                            start = i * chunk_size
                            end = min(start + chunk_size, total_size)
                            chunk = response[start:end]
                            # 创建一个包含分片信息的新消息
                            chunk_message = {
                                'type': 'chunk',
                                'index': i,
                                'total': num_chunks,
                                'data': chunk
                            }
                            # 发送分片消息
                            await self.send_message(chunk_message)
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
            logger.info('未知异常,5秒后重新建立连接')
            await self.reconnect()
        finally:
            # logger.info(f"我是finally")
            self.status = False

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
            await self.websocket.send(
                json.dumps({"code": 200, "status": "ok", "message": f"client {self.agent_code} is alive"}))
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            self.status = True
        except Exception as e:
            pass