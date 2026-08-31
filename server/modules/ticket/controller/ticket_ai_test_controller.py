"""工单轻量 AI 手动测试控制器：提供测试选项、工单搜索和试运行接口。"""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_ai_test_vo import (
    TicketAiTestRunModel,
)
from modules.ticket.service.ai.ticket_light_ai_test_service import TicketLightAiTestService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketAiTestController = APIRouter(prefix="/ticket/ai-test", dependencies=[Depends(LoginService.get_current_user)])


@ticketAiTestController.get("/options", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:test:run"))])
async def get_ticket_ai_test_options(query_db: Session = Depends(get_db)):
    """
    获取测试工作台选项：任务类型、Provider、模型目录和提示词模板。
    """
    try:
        result = await run_in_threadpool(TicketLightAiTestService.get_test_options, query_db)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiTestController.get("/tickets", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:test:run"))])
async def search_tickets_for_ai_test(
    keyword: str,
    query_db: Session = Depends(get_db),
):
    """
    按工单号或标题关键字搜索工单，供测试工作台选择。
    """
    try:
        rows = await run_in_threadpool(TicketLightAiTestService.search_tickets, query_db, keyword)
        return ResponseUtil.success(data={"rows": rows})
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiTestController.get("/context", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:test:run"))])
async def get_ticket_ai_test_context(
    ticketNo: str,
    query_db: Session = Depends(get_db),
):
    """
    获取工单测试上下文（标题、描述、原始入参和当前字段），供前端回填与展示。
    """
    try:
        result = await run_in_threadpool(TicketLightAiTestService.get_ticket_test_context, query_db, ticketNo)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiTestController.get("/prompt-content", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:test:run"))])
async def get_ticket_ai_test_prompt_content(
    templateCode: str,
    query_db: Session = Depends(get_db),
):
    """
    按模板编码获取提示词内容，供前端选择模板后回填编辑区。
    """
    try:
        result = await run_in_threadpool(
            TicketLightAiTestService.get_prompt_template_content, query_db, templateCode
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiTestController.post("/run", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:test:run"))])
async def run_ticket_ai_test(
    run_object: TicketAiTestRunModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    执行一次轻量 AI 测试（信息提取/分类统计/翻译/标题总结/知识提炼）。

    测试不读取场景开关和提取缓存，不回写工单业务字段；审计记录任务类型追加 _test 后缀。
    """
    try:
        current_user_name = current_user.user.user_name
        result = await run_in_threadpool(
            TicketLightAiTestService.run_test,
            query_db,
            run_object,
            current_user_name,
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
