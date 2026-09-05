"""资源采集服务管理接口：只做路由、参数模型校验、权限和响应转换。"""

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.metrics.entity.vo.metrics_vo import (
    MetricsCollectorResponseModel,
    MetricsCollectorRuntimeResponseModel,
    MetricsCollectorSaveModel,
    MetricsCollectorStatusModel,
)
from modules.metrics.service.metrics_collector_config_service import MetricsCollectorConfigService
from modules.metrics.service.metrics_collector_runtime_service import MetricsCollectorRuntimeService
from utils.response_util import ResponseUtil

metricsCollectorController = APIRouter(prefix="/monitor/metrics-collectors", dependencies=[Depends(LoginService.get_current_user)])


@metricsCollectorController.get("", dependencies=[Depends(CheckUserInterfaceAuth("monitor:metrics_collector:list"))])
async def list_metrics_collectors(request: Request, query_db: Session = Depends(get_db)):
    """获取全部采集服务配置（含最近推送状态），密码不回显。"""
    return ResponseUtil.success(data=await run_in_threadpool(MetricsCollectorConfigService.list_collectors, query_db))


@metricsCollectorController.get("/runtime", response_model=MetricsCollectorRuntimeResponseModel, dependencies=[Depends(CheckUserInterfaceAuth("monitor:metrics_collector:list"))])
async def get_metrics_collector_runtime(request: Request):
    """获取当前进程的采集线程运行状态。"""
    return ResponseUtil.success(data=await run_in_threadpool(MetricsCollectorRuntimeService.describe_runtime))


@metricsCollectorController.get("/{profile_id}", response_model=MetricsCollectorResponseModel, dependencies=[Depends(CheckUserInterfaceAuth("monitor:metrics_collector:query"))])
async def get_metrics_collector(request: Request, profile_id: int, query_db: Session = Depends(get_db)):
    """获取指定采集服务配置详情，密码不回显。"""
    result = await run_in_threadpool(MetricsCollectorConfigService.get_collector, query_db, profile_id)
    return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="采集服务不存在")


@metricsCollectorController.post("", dependencies=[Depends(CheckUserInterfaceAuth("monitor:metrics_collector:add"))])
@log_decorator(title="资源采集服务管理", business_type=1)
async def create_metrics_collector(request: Request, model: MetricsCollectorSaveModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """新增采集服务。"""
    result = await run_in_threadpool(MetricsCollectorConfigService.create_collector, query_db, model, current_user.user.user_name)
    return ResponseUtil.success(msg=result.message, data=result.result) if result.is_success else ResponseUtil.failure(msg=result.message)


@metricsCollectorController.put("/{profile_id}", dependencies=[Depends(CheckUserInterfaceAuth("monitor:metrics_collector:edit"))])
@log_decorator(title="资源采集服务管理", business_type=2)
async def update_metrics_collector(request: Request, profile_id: int, model: MetricsCollectorSaveModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """修改采集服务配置，修改后采集线程热生效。"""
    result = await run_in_threadpool(MetricsCollectorConfigService.update_collector, query_db, profile_id, model, current_user.user.user_name)
    return ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)


@metricsCollectorController.put("/{profile_id}/status", dependencies=[Depends(CheckUserInterfaceAuth("monitor:metrics_collector:edit"))])
@log_decorator(title="资源采集服务管理", business_type=2)
async def change_metrics_collector_status(request: Request, profile_id: int, model: MetricsCollectorStatusModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """启动或停止采集服务。"""
    result = await run_in_threadpool(MetricsCollectorConfigService.update_collector_status, query_db, profile_id, model.enabled, current_user.user.user_name)
    return ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)


@metricsCollectorController.delete("/{profile_id}", dependencies=[Depends(CheckUserInterfaceAuth("monitor:metrics_collector:remove"))])
@log_decorator(title="资源采集服务管理", business_type=3)
async def delete_metrics_collector(request: Request, profile_id: int, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """删除采集服务，运行中的通道会在下一轮轮询自动停止。"""
    result = await run_in_threadpool(MetricsCollectorConfigService.delete_collector, query_db, profile_id, current_user.user.user_name)
    return ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)
