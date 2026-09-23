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
    ResourceDeleteModel,
    ResourceQueryModel,
    ResourceReadyModel,
    ResourceSftpCreateModel,
    ResourceSftpUploadModel,
    ResourceTransferBeginModel,
    ResourceTransferChunkModel,
    ResourceTransferCommitModel,
)
from modules.configuration_task.service.resource_extended_service import ResourceExtendedService
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


@resourceController.post(
    "/sftp",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:sftp"))],
)
async def upload_sftp_resource(
    request: Request,
    model: ResourceSftpCreateModel,
    upload: ResourceSftpUploadModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """上传文件到 SFTP 并登记资源；文件正文为受限 Base64。"""
    result = await run_in_threadpool(
        ResourceExtendedService.upload_sftp_resource, query_db, model, upload, current_user
    )
    return _result_response(result)


@resourceController.get(
    "/{resource_id}/download",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:download"))],
)
async def download_resource(
    request: Request,
    resource_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """下载回传资源内容：SFTP 资源走服务端直连，agent_local 资源走 Agent file_read。"""
    result = await run_in_threadpool(ResourceExtendedService.download_resource, query_db, resource_id, current_user)
    return _result_response(result)


@resourceController.post(
    "/{resource_id}/delete",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:delete"))],
)
async def delete_resource(
    request: Request,
    resource_id: int,
    model: ResourceDeleteModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """删除资源（带引用保护）；被产物引用时需管理员 force。"""
    result = await run_in_threadpool(
        ResourceExtendedService.delete_resource, query_db, resource_id, model, current_user
    )
    return _result_response(result)
