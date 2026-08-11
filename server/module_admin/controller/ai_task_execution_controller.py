from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.ai_task_execution_vo import AiTaskExecutionQueryModel
from module_admin.service.ai_task_execution_service import AiTaskExecutionService
from module_admin.service.login_service import CurrentUserModel, LoginService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

aiTaskExecutionController = APIRouter(prefix="/system/aitaskexecution", dependencies=[Depends(LoginService.get_current_user)])


@aiTaskExecutionController.get(
    "/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("system:aitaskexecution:list"))],
)
async def get_ai_task_execution_list(
    request: Request,
    ai_task_execution_query: AiTaskExecutionQueryModel = Depends(AiTaskExecutionQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取 AI 执行审计分页列表。
    :param request: Request对象
    :param ai_task_execution_query: AI执行审计分页查询对象
    :param query_db: orm对象
    :return: AI执行审计分页列表
    """
    try:
        execution_list = AiTaskExecutionService.get_ai_task_execution_list_services(query_db, ai_task_execution_query)
        return ResponseUtil.success(model_content=execution_list)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiTaskExecutionController.get(
    "/{execution_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aitaskexecution:query"))],
)
async def get_ai_task_execution_detail(
    request: Request,
    execution_id: int,
    query_db: Session = Depends(get_db),
):
    """
    获取 AI 执行审计详情。
    :param request: Request对象
    :param execution_id: 执行ID
    :param query_db: orm对象
    :return: 执行审计详情
    """
    try:
        execution_detail = AiTaskExecutionService.get_ai_task_execution_detail_services(query_db, execution_id)
        if not execution_detail:
            return ResponseUtil.failure(msg="审计记录不存在")
        return ResponseUtil.success(data=execution_detail)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))
