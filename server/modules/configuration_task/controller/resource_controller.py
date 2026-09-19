"""配置任务资源接口：只负责路由、鉴权、线程池包装和响应转换。"""

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.configuration_task.entity.vo.resource_vo import ResourceCreateModel, ResourceQueryModel, ResourceReadyModel
from modules.configuration_task.service.resource_service import ResourceService
from utils.response_util import ResponseUtil

resourceController = APIRouter(
    prefix="/configuration-tasks/resources",
    dependencies=[Depends(LoginService.get_current_user)],
)


@resourceController.get("", dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:list"))])
async def list_resources(
    request: Request,
    query: ResourceQueryModel = Depends(ResourceQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """查询资源元数据列表，不返回文件内容。"""
    data = await run_in_threadpool(ResourceService.list_resources, query_db, query)
    return ResponseUtil.success(data=data)


@resourceController.get(
    "/{resource_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:query"))],
)
async def get_resource(request: Request, resource_id: int, query_db: Session = Depends(get_db)):
    """查询资源元数据详情，resourceId 按字符串返回。"""
    data = await run_in_threadpool(ResourceService.get_resource, query_db, resource_id)
    return ResponseUtil.success(data=data) if data else ResponseUtil.failure(msg="资源不存在")


@resourceController.post("", dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:add"))])
async def create_resource(
    request: Request,
    model: ResourceCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """登记 Agent 本地资源元数据，不接收或转发文件内容。"""
    result = await run_in_threadpool(ResourceService.create_resource, query_db, model, current_user)
    return (
        ResponseUtil.success(msg=result.message, data=result.result)
        if result.is_success
        else ResponseUtil.failure(msg=result.message)
    )


@resourceController.post(
    "/{resource_id}/ready",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:edit"))],
)
async def mark_resource_ready(
    request: Request,
    resource_id: int,
    model: ResourceReadyModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """确认 Agent 侧资源元数据，校验通过后将资源置为 READY。"""
    result = await run_in_threadpool(ResourceService.mark_ready, query_db, resource_id, model, current_user)
    return (
        ResponseUtil.success(msg=result.message, data=result.result)
        if result.is_success
        else ResponseUtil.failure(msg=result.message)
    )
