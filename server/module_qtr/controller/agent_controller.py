import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.orm import Session

from config.database import SessionLocal
from config.get_db import get_db
from module_hrm.entity.vo.agent_vo import AgentModel
from module_hrm.service.agent_service import AgentService
from module_hrm.utils.util import decompress_str_to_dict
from module_qtr.service.agent_bootstrap_service import AgentBootstrapService
from module_qtr.service.agent_service import (
    agents,
    send_message as agent_service_send_message,
    response_futures,
)
from module_hrm.service.desktop_case_service import DesktopCaseService
from module_hrm.service.web_case_service import WebCaseService
from utils.log_util import logger
from utils.response_util import ResponseUtil
from utils.snowflake import snowIdWorker

agentController = APIRouter(prefix="/qtr/agent")

# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 30
# agent状态
agent_status = defaultdict(dict)
event_chunks = defaultdict(lambda: {"chunks": {}, "total": 0})


def _sanitize_log_value(value, *, key: str | None = None):
    normalized_key = str(key or "").lower()
    if normalized_key in {"imagebase64", "image_base64"}:
        return f"<base64 len={len(str(value or ''))}>"
    if normalized_key == "data" and isinstance(value, str):
        return f"<chunk len={len(value)}>"
    if isinstance(value, dict):
        return {k: _sanitize_log_value(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_log_value(item) for item in value]
    if isinstance(value, str) and len(value) > 240:
        return f"<str len={len(value)}>"
    return value


def _summarize_message(message: Any) -> str:
    if isinstance(message, str):
        if len(message) > 240:
            return f"<raw len={len(message)}>"
        return message
    return json.dumps(_sanitize_log_value(message or {}), ensure_ascii=False)


def _dispatch_agent_event(agent_code: str, message_data: dict[str, Any]) -> bool:
    """
    分发 Agent 事件到对应业务处理器（使用短生命周期数据库会话）。

    说明：
    WebSocket 链路是长连接，若复用同一个数据库会话，可能在某些数据库隔离级别下
    读不到连接建立后新写入的记录（例如新建录制会话），导致“录制会话不存在”误判。
    因此这里为每条事件创建独立会话，确保读取到最新已提交数据。

    :param agent_code: Agent 编码。
    :param message_data: Agent 上报的事件消息体。
    :return: 是否已识别并处理该事件类型。
    """
    message_type = message_data.get("type")
    known_types = {
        "record_event",
        "record_status",
        "record_finished",
        "record_error",
        "web_run_step",
        "web_run_status",
        "web_run_finished",
        "web_run_error",
        "desktop_record_event",
        "desktop_record_status",
        "desktop_record_finished",
        "desktop_record_error",
    }
    if message_type not in known_types:
        return False

    event_db = SessionLocal()
    try:
        if message_type in ("record_event", "record_status", "record_finished", "record_error"):
            WebCaseService.handle_agent_recording_event(event_db, agent_code, message_data)
            return True
        if message_type in ("web_run_step", "web_run_status", "web_run_finished", "web_run_error"):
            WebCaseService.handle_agent_run_event(event_db, agent_code, message_data)
            return True
        if message_type in (
            "desktop_record_event",
            "desktop_record_status",
            "desktop_record_finished",
            "desktop_record_error",
        ):
            DesktopCaseService.handle_agent_recording_event(event_db, agent_code, message_data)
            return True
    except Exception as exc:
        event_db.rollback()
        logger.exception(f"处理Agent事件失败，agent={agent_code}, type={message_type}, error={exc}")
    finally:
        event_db.close()
    return True


def change_agent_status(current_db, agent):
    try:
        agent_info = AgentService.get_agent_detail_services_controller(current_db, agent)
        if agent_info:
            agent_info.status = 1
            agent_info.offline_time = datetime.now()
            AgentService.edit_agent_services_controller(current_db, agent_info)
    except Exception as e:
        logger.error(f"改变agent状态失败:{e}")


class ConnectionManager:
    def __init__(self):
        self.agents = agents

    async def connect(self, agent_code: str, websocket: WebSocket):
        await websocket.accept()
        self.agents[agent_code] = websocket
        agents[agent_code] = websocket
        agent_status.setdefault(agent_code, {})
        logger.info(f"Client connected: {self.agents[agent_code].client_state}")

    async def disconnect(self, agent_code: str, close_code):
        websocket = self.agents.pop(agent_code, None)
        if websocket is None:
            return
        try:
            logger.info(f"Client disconnected: {getattr(websocket, 'client_state', None)}, close code: {close_code}")
            await websocket.close(code=close_code)
        except Exception:
            pass

    async def send_heartbeat(self):
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)  # 每30秒发送一次心跳
                # logger.info(f'开始向客户端发送心跳信息：{self.agents}')
                invalid_agent_key = []
                for k, v in agent_status.items():
                    if len(v) > 0:
                        # logger.info(agent_status)
                        if datetime.now() - v.get("heart_time") > timedelta(seconds=(HEARTBEAT_INTERVAL + 5)):
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
                            agent_status[agent_code]["heart_time"] = datetime.now()
                            agent_status[agent_code]["heart_status"] = False
                            try:
                                await self.agents[agent_code].send_text(
                                    json.dumps({"type": "ping", "status": "ok", "message": "service is alive"})
                                )
                            except Exception:
                                change_agent_status(current_db, agent_code)
                        else:
                            logger.info(f"客户端{agent_code}已断开连接，从内存中移除")
                            del self.agents[agent_code]
                finally:
                    current_db.close()
            except Exception:
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


@agentController.get("/bootstrap/pos-config")
async def get_agent_pos_config(query_db: Session = Depends(get_db)):
    try:
        payload = AgentBootstrapService.get_pos_config_services(query_db)
        return ResponseUtil.success(data=payload)
    except ValueError as exc:
        logger.warning(exc)
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@agentController.get("/bootstrap/config/{config_key}")
async def get_agent_config_by_key(config_key: str, query_db: Session = Depends(get_db)):
    try:
        payload = AgentBootstrapService.get_config_services(query_db, config_key)
        return ResponseUtil.success(data=payload)
    except ValueError as exc:
        logger.warning(exc)
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@agentController.websocket("/ws/{agent_code}")
async def websocket_endpoint(agent_code: str, websocket: WebSocket, db: Session = Depends(get_db)):
    # await websocket.accept()
    await manager.connect(agent_code, websocket)
    # agents[agent_code] = websocket
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
            logger.info(f"agent:{agent_code} 状态为：{agent_info.status}")

    try:
        while True:
            data = await manager.agents[agent_code].receive_text()
            agent_status[agent_code]["heart_status"] = True
            agent_status[agent_code]["heart_time"] = datetime.now()
            # 解析接收到的消息
            message_data = json.loads(data)
            logger.debug(f"收到消息：{_summarize_message(message_data)}")
            if message_data.get("type") in ("ping", "pong"):
                agent_status[agent_code]["heart_status"] = True
            elif _dispatch_agent_event(agent_code, message_data):
                continue
            # 检查消息类型是否为分片
            elif message_data.get("type") == "response_chunk":
                # 获取分片信息
                request_id = message_data["request_id"]
                data_chunk = message_data["data"]
                request_state = response_futures.get(request_id)
                if not request_state:
                    logger.warning(f"收到未知响应分片，request_id={request_id}")
                    continue

                # 将分片存储在字典中
                if "chunks" not in request_state:
                    request_state["chunks"] = []

                # 存储分片数据
                request_state["chunks"].append(data_chunk)

                # 检查是否收到了所有的分片
                if message_data["finished"]:
                    # 重新组装消息
                    current_finished_request = response_futures.pop(request_id, None)
                    if not current_finished_request:
                        continue
                    try:
                        complete_message = "".join(current_finished_request["chunks"])
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
                        del current_finished_request["chunks"]
            elif message_data.get("type") == "event_chunk":
                chunk_id = f"{agent_code}:{message_data.get('chunk_id')}"
                current_event = event_chunks[chunk_id]
                total = int(message_data.get("total") or 0)
                index = int(message_data.get("index") or 0)
                current_event["chunks"][index] = message_data.get("data") or ""
                current_event["total"] = max(total, int(current_event.get("total") or 0))
                if (
                    message_data.get("finished")
                    and current_event["total"] > 0
                    and len(current_event["chunks"]) >= current_event["total"]
                ):
                    try:
                        complete_message = "".join(
                            current_event["chunks"].get(i, "") for i in range(current_event["total"])
                        )
                        event_data = decompress_str_to_dict(complete_message)
                        if not _dispatch_agent_event(agent_code, event_data):
                            logger.warning(f"收到未知事件分片类型: {event_data.get('type')}")
                    finally:
                        event_chunks.pop(chunk_id, None)
            else:
                # 如果不是分片消息，则直接处理（这里可以根据需要添加逻辑）
                pass

    except Exception as e:
        logger.exception(e)
        logger.error(f"Error with {agent_code}: connection closed, {e}")
    finally:
        try:
            for request_id, request_state in list(response_futures.items()):
                if request_state.get("agent_code") != agent_code:
                    continue
                future = request_state.get("future")
                if future and not future.done():
                    future.cancel()
                response_futures.pop(request_id, None)
            for chunk_key in [key for key in event_chunks.keys() if str(key).startswith(f"{agent_code}:")]:
                event_chunks.pop(chunk_key, None)
        except Exception:
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
    return await agent_service_send_message(agent_code, message, request_id)






