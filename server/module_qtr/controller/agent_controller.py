import base64
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio
from fastapi import APIRouter, WebSocket, Depends
import json
import uuid

from sqlalchemy.orm import Session

from module_hrm.enums.enums import TstepTypeEnum, AgentResponseEnum
from module_hrm.utils.util import decompress_text, decompress_str_to_dict, compress_dict_to_str
from utils.log_util import logger
from config.get_db import get_db
from config.database import SessionLocal
from module_qtr.service.agent_service import agents, response_futures, AgentResponse, \
    AgentResponseWebSocket, handle_response
from module_hrm.entity.vo.agent_vo import AgentModel
from module_hrm.service.agent_service import AgentService
from utils.snowflake import snowIdWorker


agentController = APIRouter(prefix='/qtr/agent')

# websocket发送数据分片大小
MAX_MESSAGE_SIZE = 1024 * 16
# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 30
# agent状态
agent_status = defaultdict(dict)

def change_agent_status(current_db, agent):
    try:
        agent_info = AgentService.get_agent_detail_services_controller(current_db, agent)
        if agent_info:
            agent_info.status = 1
            agent_info.offline_time = datetime.now()
            AgentService.edit_agent_services_controller(current_db, agent_info)
    except Exception as e:
        logger.error(f'改变agent状态失败:{e}')

class ConnectionManager:
    def __init__(self):
        self.agents = agents

    async def connect(self, agent_code: str, websocket: WebSocket):
        await websocket.accept()
        self.agents[agent_code] = websocket
        agents[agent_code] = websocket
        agent_status.setdefault(agent_code, {})
        logger.info(f'Client connected: {self.agents[agent_code].client_state}')

    async def disconnect(self, agent_code: str, close_code):
        if agent_code in self.agents:
            logger.info(self.agents[agent_code])
            self.agents.pop(agent_code).close()
            logger.info(f'Client disconnected: {self.agents[agent_code].client_state}, close code: {close_code}')
            del self.agents[agent_code]

    async def send_heartbeat(self):
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)  # 每30秒发送一次心跳
                # logger.info(f'开始向客户端发送心跳信息：{self.agents}')
                invalid_agent_key = []
                for k, v in agent_status.items():
                    if len(v) > 0:
                        # logger.info(agent_status)
                        if datetime.now() - v.get('heart_time') > timedelta(seconds=(HEARTBEAT_INTERVAL + 5)):
                            invalid_agent_key.append(k)
                current_db = SessionLocal()
                try:
                    for agent in invalid_agent_key:
                        logger.info(f"agent【{agent}】已经离线")
                        del agent_status[agent]
                        if self.agents.get(agent):
                            del self.agents[agent]
                        change_agent_status(current_db, agent)

                    for agent_code, _ in list(self.agents.items()):
                        if self.agents[agent_code].client_state.value == 1:
                            # logger.info(f'当前发送心跳信息的客户端为：{agent_code}')
                            agent_status[agent_code]['heart_time'] = datetime.now()
                            agent_status[agent_code]['heart_status'] = False
                            try:
                                await self.agents[agent_code].send_text(json.dumps({"type": "ping", "status": "ok", "message": "service is alive"}))
                            except Exception as e:
                                change_agent_status(current_db, agent_code)
                        else:
                            logger.info(f'客户端{agent_code}已断开连接，从内存中移除')
                            del self.agents[agent_code]
                finally:
                    current_db.close()
            except Exception as e:
                pass

manager = ConnectionManager()

# 这是您的检查函数，它应该是异步的
async def check_dictionary():
    # print("Checking dictionary...")
    # 这里执行您的检查逻辑
    # print(agents)
    # print(response_futures)
    pass
    # ...
    # print("Dictionary check completed.")

# 这是一个后台任务，它会定期调用检查函数
async def background_task():
    while True:
        await check_dictionary()
        await asyncio.sleep(10)  # 等待5秒钟后再次调用检查函数

# 应用启动事件处理器
async def startup_handler():
    # 在启动时创建一个后台任务
    # asyncio.create_task(background_task())
    asyncio.create_task(manager.send_heartbeat())
    logger.info("Agent manager background task started.")

@agentController.websocket("/ws/{agent_code}")
async def websocket_endpoint(agent_code: str, websocket: WebSocket, db: Session = Depends(get_db)):
    # await websocket.accept()
    await manager.connect(agent_code, websocket)
    # agents[agent_code] = websocket
    # 当有新的WebSocket连接时，初始化一个空的字典来存储该agent的待处理Future对象
    if agent_code not in response_futures:
        response_futures[agent_code] = {}
        agent_obj = AgentModel()
        agent_obj.agent_code = snowIdWorker.get_id()
        agent_obj.agent_code = agent_code
        agent_obj.agent_name = agent_code
        add_agent_result = AgentService.add_agent_services(db, agent_obj)
        if add_agent_result.is_success:
            logger.info(add_agent_result.message)
        else:
            # logger.warning(add_agent_result.message)
            # logger.info(f'{add_agent_result.message},agent_code:{agent_code}')
            agent_info = AgentService.get_agent_detail_services(db, agent_code)
            # logger.info(f'agent_info:{agent_info},agent_code:{agent_code}')
            if agent_info:
                agent_info.status = 2
                agent_info.online_time = datetime.now()
                AgentService.edit_agent_services(db, agent_info)
                logger.info(f'agent:{agent_code} 状态为：{agent_info.status}')

    try:
        while True:
            data = await manager.agents[agent_code].receive_text()
            agent_status[agent_code]['heart_status'] = True
            agent_status[agent_code]['heart_time'] = datetime.now()
            # 解析接收到的消息
            logger.debug(f"收到消息：{data}")
            message_data = json.loads(data)
            if message_data.get("type") in ("ping", "pong"):
                agent_status[agent_code]['heart_status'] = True
                # logger.info(message_data.get("message"))
            # 检查消息类型是否为分片
            elif message_data.get('type') == 'response_chunk':
                # 获取分片信息
                request_id = message_data["request_id"]
                data_chunk = message_data['data']

                # 将分片存储在字典中
                if "chunks" not in response_futures[request_id]:
                    response_futures[request_id]["chunks"] = []

                # 存储分片数据
                response_futures[request_id]["chunks"].append(data_chunk)

                # 检查是否收到了所有的分片
                logger.debug(f"收到消息： {message_data}")
                if message_data["finished"]:
                    # 重新组装消息
                    current_finished_request = response_futures.pop(request_id)
                    try:
                        complete_message = ''.join(current_finished_request['chunks'])
                        response_data = decompress_str_to_dict(complete_message)

                        # 检查是否有等待这个响应的Future对象
                        response_future = current_finished_request["future"]
                        logger.debug(f"response_future状态： {response_future.done()}")
                        if response_future and not response_future.done():
                            # 设置Future对象的结果
                            response_future.set_result(response_data)
                        del complete_message
                        del response_data
                    finally:
                        del current_finished_request['chunks']
            else:
                # 如果不是分片消息，则直接处理（这里可以根据需要添加逻辑）
                pass

    except Exception as e:
        logger.exception(e)
        logger.error(f"Error with {agent_code}: connection closed, {e}")
    finally:
        try:
            # del agents[agent_code]
            del manager.agents[agent_code]
            # 取消所有未处理的Future对象
            if agent_code in response_futures:
                for future in response_futures[agent_code].values():
                    future.cancel()
                del response_futures[agent_code]
            await manager.agents[agent_code].close()
        except Exception as e:
            pass
        finally:
            await manager.disconnect(agent_code, close_code=1000)
            agent_info = AgentService.get_agent_detail_services(db, agent_code)
            if agent_info:
                agent_info.status = 1
                agent_info.offline_time = datetime.now()
                AgentService.edit_agent_services(db, agent_info)
            logger.info(f"Connection closed for agent: {agent_code}")


@agentController.post("/send/{agent_code}")
async def send_message(agent_code: str, message: dict, request_id: str = None):
    logger.info(f"agent_code: {agent_code}")
    request_type = message.get('requestType')
    logger.info(f"转发类型: {request_type}")
    # 如果没有提供request_id，则生成一个唯一的标识符
    if not request_id:
        request_id = str(uuid.uuid4())

    if agent_code in agents:
        # 创建一个Future对象来代表异步操作的结果
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # 将Future对象存储在字典中，以便稍后设置其结果
        if agent_code not in response_futures:
            response_futures[agent_code] = {}
        response_futures[agent_code][request_id] = future

        # 发送消息到WebSocket，并包含request_id以便客户端能够识别是哪个请求的响应
        message['request_id'] = request_id

        message = compress_dict_to_str(message)
        await agents[agent_code].send_text(json.dumps(message))

        # 等待Future对象的结果（即WebSocket客户端的响应）
        try:
            response = await asyncio.wait_for(future, timeout=10)
            logger.info(f"response={response}")
            if response.get("request_type") == TstepTypeEnum.http.value:
                response = AgentResponse(response)
            elif response.get("request_type") == TstepTypeEnum.websocket.value:
                response = AgentResponseWebSocket(response)
                logger.info(f"ws响应数据：{response}")
            response = handle_response((AgentResponseEnum.SUCCESS.value, response, "操作成功"))
            return response
        except asyncio.TimeoutError as e:
            logger.error(f'wobsocket请求超时{e}')
            # 如果超时，取消Future对象
            if agent_code in response_futures and request_id in response_futures[agent_code]:
                response_futures[agent_code][request_id].cancel()
                del response_futures[agent_code][request_id]
            if request_type == TstepTypeEnum.http.value:
                response = handle_response((AgentResponseEnum.OPERATION_TIMEOUT.value, None, f'wobsocket请求超时{e}'))
                return response
            elif request_type == TstepTypeEnum.websocket.value:
                response = handle_response((AgentResponseEnum.OPERATION_TIMEOUT.value, None, f'wobsocket请求超时{e}'))
                return response
        except asyncio.CancelledError as e:
            logger.error(e)
            # 如果超时，取消Future对象
            if agent_code in response_futures and request_id in response_futures[agent_code]:
                response_futures[agent_code][request_id].cancel()
                del response_futures[agent_code][request_id]
            response = handle_response((AgentResponseEnum.TASK_CANCELLED.value, None, str(e.args)))
            return response
        except Exception as e:
            logger.error(e)
            # 如果超时，取消Future对象
            if agent_code in response_futures and request_id in response_futures[agent_code]:
                response_futures[agent_code][request_id].cancel()
                del response_futures[agent_code][request_id]
            response = handle_response((AgentResponseEnum.UNKNOWN_EXCEPTION.value, None, str(e.args)))
            return response

    else:
        response = handle_response((AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value, None, "Agent not connected"))
        return response






