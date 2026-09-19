"""配置任务资源接口：只负责路由、鉴权、线程池包装和响应转换。"""

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.configuration_task.entity.vo.resource_vo import (
    ResourceCreateModel,
    ResourceQueryModel,
    ResourceReadyModel,
    ResourceTransferBeginModel,
    ResourceTransferChunkModel,
    ResourceTransferCommitModel,
)
from modules.configuration_task.service.resource_service import ResourceService
from modules.configuration_task.service.resource_transfer_service import ResourceTransferService
from utils.response_util import ResponseUtil

resourceController = APIRouter(
    prefix="/configuration-tasks/resources",
    dependencies=[Depends(LoginService.get_current_user)],
)


def _result_response(result):
    """将资源服务结果转换成统一响应。"""
    return (
        ResponseUtil.success(msg=result.message, data=result.result)
        if result.is_success
        else ResponseUtil.failure(msg=result.message, data=result.result)
    )


@resourceController.get("", dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:list"))])
async def list_resources(
    request: Request,
    query: ResourceQueryModel = Depends(ResourceQueryModel.as_query),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """查询资源元数据列表，不返回文件内容。"""
    data = await run_in_threadpool(ResourceService.list_resources, query_db, query, current_user)
    return ResponseUtil.success(data=data)


@resourceController.get(
    "/{resource_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:query"))],
)
async def get_resource(
    request: Request,
    resource_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """查询资源元数据详情，resourceId 按字符串返回。"""
    data = await run_in_threadpool(ResourceService.get_resource, query_db, resource_id, current_user)
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
    return _result_response(result)


@resourceController.post(
    "/{resource_id}/transfers",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:transfer"))],
)
async def begin_resource_transfer(
    request: Request,
    resource_id: int,
    model: ResourceTransferBeginModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """创建或复用资源传输，并让 Agent 准备接收分片。"""
    result = await run_in_threadpool(
        ResourceTransferService.begin,
        query_db,
        resource_id,
        model,
        current_user,
    )
    return _result_response(result)


@resourceController.post(
    "/{resource_id}/transfers/{transfer_id}/chunks",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:transfer"))],
)
async def send_resource_transfer_chunk(
    request: Request,
    resource_id: int,
    transfer_id: str,
    model: ResourceTransferChunkModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """提交一个受限 Base64 资源分片。"""
    result = await run_in_threadpool(
        ResourceTransferService.chunk,
        query_db,
        resource_id,
        transfer_id,
        model,
        current_user,
    )
    return _result_response(result)


@resourceController.post(
    "/{resource_id}/transfers/{transfer_id}/commit",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:transfer"))],
)
async def commit_resource_transfer(
    request: Request,
    resource_id: int,
    transfer_id: str,
    model: ResourceTransferCommitModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """要求 Agent 完成文件校验后提交资源。"""
    result = await run_in_threadpool(
        ResourceTransferService.commit,
        query_db,
        resource_id,
        transfer_id,
        model,
        current_user,
    )
    return _result_response(result)


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
    """兼容旧 ready 入口，但不允许绕过 Agent 传输 commit。"""
    result = await run_in_threadpool(ResourceService.mark_ready, query_db, resource_id, model, current_user)
    return _result_response(result)
