import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from config.database import SessionLocal
from config.get_db import get_db
from module_hrm.entity.vo.agent_vo import AgentModel
from module_hrm.service.agent_service import AgentService
from module_hrm.service.desktop_case_service import DesktopCaseService
from module_hrm.service.web_case_service import WebCaseService
from module_hrm.utils.util import decompress_str_to_dict
from module_qtr.entity.vo.agent_dispatch_vo import AgentAiDispatchRequestModel
from module_qtr.service.agent_bootstrap_service import AgentBootstrapService
from module_qtr.service.agent_dispatch_service import AgentDispatchService
from module_qtr.service.agent_service import (
    AgentResponseEnum,
    HandleResponse,
    agent_loops,
    agents,
    handle_response,
    response_futures,
)
from module_qtr.service.agent_service import (
    send_message as agent_service_send_message,
)
from module_qtr.util.agent_dispatch_config import AGENT_AI_ANALYSIS_RESULT_TTL_SECONDS
from utils.log_util import logger
from utils.response_util import ResponseUtil
from utils.snowflake import snowIdWorker

agentController = APIRouter(prefix="/qtr/agent")

# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 30
# 分片注册表过期时间（秒）：超过该时间的未完成分片条目视为丢失（Agent 掉线、断流或分组异常），
# 由心跳任务定期清理，避免分片内容长期驻留内存造成缓慢泄漏。
CHUNK_REGISTRY_EXPIRE_SECONDS = 10 * 60
# 单个事件分片组允许的最大分片数：正常事件消息远小于该值，超限说明分片序列已异常，
# 直接丢弃整组，防止 Agent 异常高频上报导致单个 chunk_id 无限占用内存。
EVENT_CHUNK_MAX_PIECES = 2048
# 分片注册表单次清理的日志间隔（秒），避免心跳日志被清理动作刷屏。
CHUNK_REGISTRY_SWEEP_LOG_INTERVAL_SECONDS = 300

# agent状态
agent_status = defaultdict(dict)
# event_chunk 分片注册表：value 额外维护 first_seen_at 时间戳，供过期清理使用
event_chunks = defaultdict(lambda: {"chunks": {}, "total": 0, "first_seen_at": 0.0})
_event_chunks_last_sweep_log_at = {"ts": 0.0}

# 孤儿响应分片注册表：服务重启/等待方超时后，Agent 补交的响应没有等待者，
# 这里先在内存攒齐完整响应，再写入 Redis 结果缓存，供任务恢复逻辑补写回。
# 结构：request_id -> {"chunks": [...], "first_seen_at": monotonic, "redis": redis实例}
orphan_response_chunks: dict[str, dict[str, Any]] = {}


def _sweep_stale_event_chunks(now_ts: float) -> int:
    """
    清理过期的 event_chunk 分片组。

    触发条件：距首次收到分片超过 CHUNK_REGISTRY_EXPIRE_SECONDS 仍未凑齐，说明剩余分片
    已经丢失（断连、重传失败等），继续保留只会占用内存且永远无法组装成功。

    :param now_ts: 当前单调时间戳（time.monotonic）
    :return: 本次清理的分片组数量
    """
    expired_keys = [
        key
        for key, value in event_chunks.items()
        if now_ts - value.get("first_seen_at", 0.0) > CHUNK_REGISTRY_EXPIRE_SECONDS
    ]
    for key in expired_keys:
        event_chunks.pop(key, None)
    if expired_keys and now_ts - _event_chunks_last_sweep_log_at["ts"] > CHUNK_REGISTRY_SWEEP_LOG_INTERVAL_SECONDS:
        logger.warning(f"已清理过期的事件分片组 {len(expired_keys)} 个（未在限时内凑齐，判定为丢包）")
        _event_chunks_last_sweep_log_at["ts"] = now_ts
    return len(expired_keys)


def _prune_response_future_chunks(now_ts: float) -> int:
    """
    清理长时间只攒了分片却未等到完整响应帧的请求状态。

    场景：Agent 开始回送 response_chunk 后连接中断，发送方 Future 超时只取消等待，
    已接收的分片内容仍挂在 response_futures 条目里；连接正常关闭时才会在 finally 中移除。
    这里按首见时间兜底清理：
    - Future 已结束（超时/取消/完成）：弹出整个条目；
    - Future 仍在等待（异常长请求）：只回收分片内容，保留 Future 本身。

    :param now_ts: 当前单调时间戳（time.monotonic）
    :return: 清理的条目数量
    """
    removed = 0
    for request_id, request_state in list(response_futures.items()):
        if not request_state.get("chunks"):
            continue
        if now_ts - request_state.get("chunks_first_seen_at", 0.0) <= CHUNK_REGISTRY_EXPIRE_SECONDS:
            continue
        future_obj = request_state.get("future")
        future_pending = bool(future_obj is not None and not future_obj.done())
        request_state.pop("chunks", None)
        request_state.pop("chunks_first_seen_at", None)
        removed += 1
        if not future_pending:
            # 等待方已不存在，完整移除该请求条目。
            response_futures.pop(request_id, None)
    return removed


async def _stash_orphan_response_chunk(
    agent_code: str,
    request_id: str,
    message_data: dict[str, Any],
    websocket: WebSocket,
) -> None:
    """
    处理没有等待者的迟到响应分片：在内存攒齐完整响应后写入 Redis 结果缓存。

    场景：服务端重启或等待方超时后，Agent 补交的响应找不到对应的 Future。
    此前这些响应被直接丢弃，导致 Agent 实际执行成功的任务永远无法恢复。
    现在攒齐后写入 Redis（key 与调度侧结果缓存一致），任务恢复/重试时读取补写回。

    :param agent_code: Agent 编码
    :param request_id: 请求ID
    :param message_data: 响应分片消息体
    :param websocket: 当前 WebSocket 连接（仅用于 app 引用获取 Redis）
    :return: 无
    """
    # 服务重启后尚无 Redis 可用时无法缓存，只能丢弃并告警。
    app_state = getattr(websocket, "app", None)
    redis = getattr(getattr(app_state, "state", None), "redis", None)
    if redis is None:
        logger.warning(f"收到孤儿响应分片且 Redis 不可用，已丢弃: agent={agent_code}, request_id={request_id}")
        return

    entry = orphan_response_chunks.get(request_id)
    if entry is None:
        entry = {"chunks": [], "first_seen_at": time.monotonic()}
        orphan_response_chunks[request_id] = entry
    entry["chunks"].append(message_data.get("data") or "")

    if not message_data.get("finished"):
        return

    # 已凑齐：解压并写入 Redis 结果缓存，随后清理内存条目。
    orphan_response_chunks.pop(request_id, None)
    try:
        complete_payload = "".join(entry["chunks"])
        response_data = decompress_str_to_dict(complete_payload)
        validated = HandleResponse.validate_transport_payload(response_data)
        # 与调度侧 _store_result 保持相同序列化方式，确保缓存格式一致。
        serialized = json.dumps(jsonable_encoder(validated), ensure_ascii=False)
        await redis.set(
            AgentDispatchService._result_key(request_id),
            serialized,
            # 与调度侧正常结果缓存使用同一 TTL，保证恢复窗口内均可读取。
            ex=AGENT_AI_ANALYSIS_RESULT_TTL_SECONDS,
        )
        logger.info(
            f"迟到响应已写入结果缓存，等待任务恢复读取: agent={agent_code}, request_id={request_id}"
        )
    except Exception as exc:
        logger.warning(
            f"迟到响应写入结果缓存失败，已丢弃: agent={agent_code}, request_id={request_id}, error={exc}"
        )


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
        "ai_analysis_step",
        "ai_analysis_status",
        "ai_analysis_finished",
        "ai_analysis_error",
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
        if message_type in ("ai_analysis_step", "ai_analysis_status", "ai_analysis_finished", "ai_analysis_error"):
            logger.info(
                f"AI分析Agent事件，agent={agent_code}, type={message_type}, "
                f"data={_summarize_message(message_data)}"
            )
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


def _count_pending_requests(agent_code: str) -> int:
    """
    统计指定 Agent 当前未完成的请求数。
    :param agent_code: Agent 编码
    :return: 未完成请求数
    """
    return sum(1 for request_state in response_futures.values() if request_state.get("agent_code") == agent_code)


def _resolve_future_loop(request_state: dict[str, Any] | None):
    """
    获取 Future 所属事件循环。
    :param request_state: 请求状态缓存
    :return: Future 对应的事件循环
    """
    if not request_state:
        return None
    return request_state.get("loop")


def _complete_future_threadsafe(request_state: dict[str, Any], response_data: dict[str, Any]) -> None:
    """
    线程安全地回写 Future 结果。
    :param request_state: 请求状态缓存
    :param response_data: 完整响应数据
    :return: 无
    """
    response_future = request_state.get("future")
    if not response_future or response_future.done():
        return
    future_loop = _resolve_future_loop(request_state)
    if future_loop and not future_loop.is_closed():
        future_loop.call_soon_threadsafe(response_future.set_result, response_data)
        return
    response_future.set_result(response_data)


def _cancel_future_threadsafe(request_state: dict[str, Any]) -> None:
    """
    线程安全地取消 Future。
    :param request_state: 请求状态缓存
    :return: 无
    """
    response_future = request_state.get("future")
    if not response_future or response_future.done():
        return
    future_loop = _resolve_future_loop(request_state)
    if future_loop and not future_loop.is_closed():
        future_loop.call_soon_threadsafe(response_future.cancel)
        return
    response_future.cancel()


class ConnectionManager:
    def __init__(self):
        self.agents = agents

    async def connect(self, agent_code: str, websocket: WebSocket):
        await websocket.accept()
        self.agents[agent_code] = websocket
        agents[agent_code] = websocket
        agent_loops[agent_code] = asyncio.get_running_loop()
        agent_status.setdefault(agent_code, {})
        logger.info(f"Client connected: {self.agents[agent_code].client_state}")

    async def disconnect(self, agent_code: str, close_code):
        websocket = self.agents.pop(agent_code, None)
        agent_loops.pop(agent_code, None)
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
                # 顺带清理分片注册表：未凑齐且超时的 event_chunk 组、长时间无完整响应帧的响应分片。
                now_mono = time.monotonic()
                _sweep_stale_event_chunks(now_mono)
                _prune_response_future_chunks(now_mono)
                for k, v in agent_status.items():
                    if len(v) > 0:
                        # logger.info(agent_status)
                        pending_request_count = _count_pending_requests(k)
                        heart_time = v.get("heart_time")
                        if not heart_time:
                            continue
                        if pending_request_count > 0:
                            logger.info(
                                "agent【%s】存在 %s 个未完成请求，跳过离线判定，heart_time=%s",
                                k,
                                pending_request_count,
                                heart_time,
                            )
                            continue
                        if datetime.now() - heart_time > timedelta(seconds=(HEARTBEAT_INTERVAL + 5)):
                            invalid_agent_key.append(k)
                current_db = SessionLocal()
                try:
                    for agent in invalid_agent_key:
                        logger.info(f"agent【{agent}】已经离线")
                        del agent_status[agent]
                        if self.agents.get(agent):
                            del self.agents[agent]
                        agent_loops.pop(agent, None)
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
                            agent_loops.pop(agent_code, None)
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
    """
    处理 Agent WebSocket 长连接。
    :param agent_code: Agent 编码，用于路由请求和回传结果
    :param websocket: 当前 WebSocket 连接
    :param db: 数据库会话
    :return: 无
    """
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
            current_websocket = manager.agents.get(agent_code)
            if current_websocket is None:
                logger.info(f"agent {agent_code} 已从连接表移除，结束 WebSocket 循环")
                break
            data = await current_websocket.receive_text()
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
                    # 等待方已不存在（服务重启/超时/取消/断连清理）：不再直接丢弃，
                    # 攒齐完整响应后写入 Redis 结果缓存，供任务恢复逻辑补写回，
                    # 否则 Agent 断连期间执行成功的任务结果会永久丢失。
                    await _stash_orphan_response_chunk(agent_code, request_id, message_data, current_websocket)
                    continue

                # 将分片存储在字典中
                if "chunks" not in request_state:
                    request_state["chunks"] = []
                    request_state["chunks_first_seen_at"] = time.monotonic()

                # 存储分片数据
                request_state["chunks"].append(data_chunk)

                # 检查是否收到了所有的分片
                if message_data["finished"]:
                    # 重新组装消息
                    current_finished_request = response_futures.pop(request_id, None)
                    if not current_finished_request:
                        continue
                    try:
                        chunks = current_finished_request.pop("chunks", [])
                        current_finished_request.pop("chunks_first_seen_at", None)
                        complete_message = "".join(chunks)
                        response_data = decompress_str_to_dict(complete_message)
                        response_keys = (
                            list(response_data.keys()) if isinstance(response_data, dict) else type(response_data)
                        )

                        # 检查是否有等待这个响应的Future对象
                        response_future = current_finished_request["future"]
                        logger.info(
                            f"收到完整响应，准备回写 Future | agent={agent_code}, request_id={request_id}, "
                            f"future_done={response_future.done() if response_future else None}, "
                            f"response_keys={response_keys}"
                        )
                        if response_future and not response_future.done():
                            # Future 由发送方线程创建，这里必须按所属事件循环线程安全回写。
                            _complete_future_threadsafe(current_finished_request, response_data)
                        del complete_message
                        del response_data
                    finally:
                        current_finished_request.pop("chunks", None)
                        current_finished_request.pop("chunks_first_seen_at", None)
            elif message_data.get("type") == "event_chunk":
                chunk_id = f"{agent_code}:{message_data.get('chunk_id')}"
                now_mono = time.monotonic()
                if chunk_id not in event_chunks:
                    event_chunks[chunk_id] = {"chunks": {}, "total": 0, "first_seen_at": now_mono}
                current_event = event_chunks[chunk_id]
                total = int(message_data.get("total") or 0)
                index = int(message_data.get("index") or 0)
                # 分片数超限视为异常上报（正常事件消息不会超过 EVENT_CHUNK_MAX_PIECES 片），
                # 整组丢弃，防止单个 chunk_id 无限占用内存。
                if total > EVENT_CHUNK_MAX_PIECES or len(current_event["chunks"]) >= EVENT_CHUNK_MAX_PIECES:
                    logger.warning(
                        f"事件分片数超过保护上限，整组丢弃 | agent={agent_code}, chunk_id={chunk_id}, "
                        f"declared_total={total}, received={len(current_event['chunks'])}, "
                        f"max={EVENT_CHUNK_MAX_PIECES}"
                    )
                    event_chunks.pop(chunk_id, None)
                    continue
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

    except WebSocketDisconnect as e:
        logger.info(f"Agent {agent_code} WebSocket 已断开: {e}")
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error with {agent_code}: connection closed, {e}")
    finally:
        try:
            for request_id, request_state in list(response_futures.items()):
                if request_state.get("agent_code") != agent_code:
                    continue
                _cancel_future_threadsafe(request_state)
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


@agentController.post("/ai-analysis/send/{agent_code}")
async def send_ai_analysis_message(
    agent_code: str,
    payload: AgentAiDispatchRequestModel,
    request: Request,
):
    """
    将 AI 分析请求按 Agent 并发上限排队后发送到本地 Agent。
    :param agent_code: 目标 Agent 编码
    :param payload: AI 分析请求、请求ID和超时参数
    :param request: 当前请求对象，用于读取 Redis
    :return: Agent 响应结果
    """
    try:
        result = await AgentDispatchService.send_ai_analysis_message(
            request.app.state.redis,
            agent_code,
            payload.message,
            payload.request_id,
            payload.timeout_seconds,
        )
        return result
    except Exception as exc:
        logger.exception(exc)
        return handle_response((AgentResponseEnum.UNKNOWN_EXCEPTION.value, None, str(exc)))






