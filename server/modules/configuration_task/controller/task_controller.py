"""配置任务运行域接口：只负责路由、鉴权、线程池包装和响应转换。"""

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.configuration_task.entity.vo.task_vo import (
    ConfigurationTaskCreateModel,
    ConfigurationTaskUpdateModel,
    TaskRunCreateModel,
    TaskRunQueryModel,
    TaskVersionCreateModel,
    TaskVersionUpdateModel,
)
from modules.configuration_task.service.task_run_service import ConfigurationTaskRunService
from modules.configuration_task.service.task_service import ConfigurationTaskService
from utils.response_util import ResponseUtil

taskController = APIRouter(prefix="/configuration-tasks", dependencies=[Depends(LoginService.get_current_user)])


def _result_response(result):
    """将任务服务结果转换成统一响应。"""
    return (
        ResponseUtil.success(msg=result.message, data=result.result)
        if result.is_success
        else ResponseUtil.failure(msg=result.message, data=result.result)
    )


@taskController.get("", dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:list"))])
async def list_tasks(
    request: Request,
    keyword: str = "",
    limit: int = 50,
    query_db: Session = Depends(get_db),
):
    """查询配置任务列表。"""
    data = await run_in_threadpool(ConfigurationTaskService.list_tasks, query_db, keyword, limit)
    return ResponseUtil.success(data=data)


@taskController.post("", dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:add"))])
async def create_task(
    request: Request,
    model: ConfigurationTaskCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """创建配置任务。"""
    result = await run_in_threadpool(ConfigurationTaskService.create_task, query_db, model, current_user)
    return _result_response(result)


@taskController.get("/{task_id}", dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:query"))])
async def get_task(
    request: Request,
    task_id: int,
    query_db: Session = Depends(get_db),
):
    """查询任务详情。"""
    data = await run_in_threadpool(ConfigurationTaskService.get_task, query_db, task_id)
    return ResponseUtil.success(data=data) if data else ResponseUtil.failure(msg="任务不存在")


@taskController.put("/{task_id}", dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:edit"))])
async def update_task(
    request: Request,
    task_id: int,
    model: ConfigurationTaskUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """更新任务基础信息。"""
    result = await run_in_threadpool(ConfigurationTaskService.update_task, query_db, task_id, model, current_user)
    return _result_response(result)


@taskController.post(
    "/{task_id}/versions",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:edit"))],
)
async def create_task_version(
    request: Request,
    task_id: int,
    model: TaskVersionCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """创建任务版本草稿。"""
    result = await run_in_threadpool(ConfigurationTaskService.create_version, query_db, task_id, model, current_user)
    return _result_response(result)


@taskController.get(
    "/{task_id}/versions",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:query"))],
)
async def list_task_versions(
    request: Request,
    task_id: int,
    limit: int = 50,
    query_db: Session = Depends(get_db),
):
    """查询任务版本列表。"""
    data = await run_in_threadpool(ConfigurationTaskService.list_versions, query_db, task_id, limit)
    return ResponseUtil.success(data=data)


@taskController.get(
    "/versions/{version_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:query"))],
)
async def get_task_version(
    request: Request,
    version_id: int,
    query_db: Session = Depends(get_db),
):
    """查询版本详情。"""
    data = await run_in_threadpool(ConfigurationTaskService.get_version, query_db, version_id)
    return ResponseUtil.success(data=data) if data else ResponseUtil.failure(msg="版本不存在")


@taskController.put(
    "/versions/{version_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:edit"))],
)
async def update_task_version(
    request: Request,
    version_id: int,
    model: TaskVersionUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """更新版本草稿。"""
    result = await run_in_threadpool(ConfigurationTaskService.update_version, query_db, version_id, model, current_user)
    return _result_response(result)


@taskController.post(
    "/versions/{version_id}/publish",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:publish"))],
)
async def publish_task_version(
    request: Request,
    version_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """发布任务版本。"""
    result = await run_in_threadpool(ConfigurationTaskService.publish_version, query_db, version_id, current_user)
    return _result_response(result)


@taskController.post(
    "/{task_id}/runs",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:run"))],
)
async def create_task_run(
    request: Request,
    task_id: int,
    model: TaskRunCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """创建配置任务运行并同步执行。"""
    result = await ConfigurationTaskRunService.create_run_and_execute(query_db, task_id, model, current_user)
    return _result_response(result)


@taskController.get(
    "/{task_id}/runs",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:query"))],
)
async def list_task_runs(
    request: Request,
    task_id: int,
    task_run_query: TaskRunQueryModel = Depends(),
    query_db: Session = Depends(get_db),
):
    """查询任务运行列表。"""
    data = await run_in_threadpool(
        ConfigurationTaskRunService.list_runs,
        query_db,
        str(task_id),
        task_run_query.agent_code,
        task_run_query.status,
        task_run_query.limit,
    )
    return ResponseUtil.success(data=data)


@taskController.get(
    "/runs/{task_run_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:query"))],
)
async def get_task_run(
    request: Request,
    task_run_id: int,
    query_db: Session = Depends(get_db),
):
    """查询运行详情。"""
    data = await run_in_threadpool(ConfigurationTaskRunService.get_run, query_db, task_run_id)
    return ResponseUtil.success(data=data) if data else ResponseUtil.failure(msg="运行记录不存在")
