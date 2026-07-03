"""
工单 Webhook 控制器：飞书消息事件回调。
"""
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from modules.ticket.service.ticket_message_sync_service import TicketMessageSyncService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketWebhookController = APIRouter(prefix="/ticket/webhook")


@ticketWebhookController.post("/feishu/message")
async def receive_feishu_message_event(request: Request, query_db: Session = Depends(get_db)):
    """
    接收飞书消息事件订阅回调接口。
    :param request: 请求对象，飞书会推送 challenge 或 im.message.receive_v1 事件体。
    :param query_db: 数据库会话。
    :return: 飞书 challenge 响应或消息同步处理摘要。
    """
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            return ResponseUtil.failure(msg="飞书事件请求体必须是 JSON 对象")
        result = await run_in_threadpool(TicketMessageSyncService.handle_feishu_message_event, query_db, payload)
        if isinstance(result, dict) and "challenge" in result:
            return result
        return ResponseUtil.success(data=result)
    except Exception as e:
        query_db.rollback()
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
