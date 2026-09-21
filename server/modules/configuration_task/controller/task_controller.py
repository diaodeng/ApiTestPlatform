"""配置任务运行域接口：只负责路由、鉴权、线程池包装和响应转换。"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.configuration_task.dao.stage_artifact_dao import ConfigurationTaskStageDao
from modules.configuration_task.dao.task_dao import ConfigurationTaskVersionDao
from modules.configuration_task.entity.vo.task_vo import (
    AgentStepScreenshotModel,
    ConfigurationTaskCreateModel,
    ConfigurationTaskUpdateModel,
    RecordingToTemplateModel,
    StageApproveModel,
    StageSplitRuleModel,
    TaskRunCreateModel,
    TaskRunQueryModel,
    TaskRunStopModel,
    TaskScheduleModel,
    TaskVersionCreateModel,
    TaskVersionUpdateModel,
)
from modules.configuration_task.service.artifact_access_service import (
    ConfigurationTaskArtifactAccessService,
)
from modules.configuration_task.service.artifact_service import ConfigurationTaskArtifactService
from modules.configuration_task.service.report_service import ConfigurationTaskReportService
from modules.configuration_task.service.stage_service import ConfigurationTaskStageService
from modules.configuration_task.service.task_run_service import ConfigurationTaskRunService
from modules.configuration_task.service.task_schedule_service import (
    ConfigurationTaskScheduleService,
    ConfigurationTaskTemplateService,
)
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


@taskController.post(
    "/runs/{task_run_id}/stop",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:run"))],
)
async def stop_task_run(
    request: Request,
    task_run_id: int,
    model: TaskRunStopModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """停止或取消运行。"""
    result = await ConfigurationTaskRunService.stop_run(query_db, task_run_id, model, current_user)
    return _result_response(result)


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


@taskController.post(
    "/versions/{version_id}/stages",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:edit"))],
)
async def save_version_stages(
    request: Request,
    version_id: int,
    rules: list[StageSplitRuleModel],
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """保存版本阶段切分；仅草稿可改。"""
    version = ConfigurationTaskVersionDao.get_version(query_db, version_id)
    if not version:
        return ResponseUtil.failure(msg="版本不存在")
    result = await run_in_threadpool(
        ConfigurationTaskStageService.save_version_stages,
        query_db,
        version,
        rules,
        ConfigurationTaskStageService._operator(current_user),
    )
    return _result_response(result)


@taskController.get(
    "/versions/{version_id}/stages",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:query"))],
)
async def list_version_stages(
    request: Request,
    version_id: int,
    query_db: Session = Depends(get_db),
):
    """查询版本阶段定义。"""
    stages = await run_in_threadpool(ConfigurationTaskStageDao.list_version_stages, query_db, version_id)
    return ResponseUtil.success(data=[ConfigurationTaskStageService.to_stage_def_model(row) for row in stages])


@taskController.get(
    "/runs/{task_run_id}/stages",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:query"))],
)
async def list_run_stages(
    request: Request,
    task_run_id: int,
    query_db: Session = Depends(get_db),
):
    """查询运行阶段列表。"""
    data = await run_in_threadpool(ConfigurationTaskStageService.list_run_stages, query_db, task_run_id)
    return ResponseUtil.success(data=data)


@taskController.post(
    "/runs/stages/{run_stage_id}/approve",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:approve"))],
)
async def approve_run_stage(
    request: Request,
    run_stage_id: int,
    model: StageApproveModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """审批 WRITE 阶段（通过或拒绝）。"""
    result = await run_in_threadpool(
        ConfigurationTaskStageService.approve_stage, query_db, run_stage_id, model, current_user
    )
    return _result_response(result)


@taskController.post(
    "/runs/stages/{run_stage_id}/retry",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:run"))],
)
async def retry_run_stage(
    request: Request,
    run_stage_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """重试失败阶段；WRITE 阶段重试需重新审批。"""
    result = await run_in_threadpool(
        ConfigurationTaskStageService.retry_stage, query_db, run_stage_id, current_user
    )
    return _result_response(result)


@taskController.get(
    "/runs/{task_run_id}/artifacts",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:artifact:query"))],
)
async def list_run_artifacts(
    request: Request,
    task_run_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """按任务和运行归属查询运行产物元数据。"""
    success, message, data = await run_in_threadpool(
        ConfigurationTaskArtifactAccessService.list_artifacts,
        query_db,
        task_run_id,
        current_user,
    )
    return ResponseUtil.success(msg=message, data=data) if success else ResponseUtil.failure(msg=message)

@taskController.get(
    "/artifacts/{artifact_id}/preview",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:artifact:preview"))],
)
async def preview_artifact(
    request: Request,
    artifact_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """按 artifact_id 受控预览安全 MIME 产物正文。"""
    result = await run_in_threadpool(
        ConfigurationTaskArtifactAccessService.access_artifact,
        query_db,
        artifact_id,
        current_user,
        "preview",
    )
    if not result.is_success or not result.result:
        return ResponseUtil.failure(
            msg=result.message,
            dict_content={"errorCode": result.error_code or "ARTIFACT_ACCESS_FAILED"},
        )
    content = result.result
    return StreamingResponse(
        iter([content.content]),
        media_type=content.mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(content.file_name)}",
            "Content-Length": str(content.file_size),
            "X-Artifact-Id": str(content.artifact_id),
            "X-Artifact-SHA256": content.sha256,
            "X-Content-Type-Options": "nosniff",
        },
    )


@taskController.get(
    "/artifacts/{artifact_id}/download",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:artifact:download"))],
)
async def download_artifact(
    request: Request,
    artifact_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """按 artifact_id 受控下载产物正文，不接受 resourceId 或 objectKey 授权。"""
    result = await run_in_threadpool(
        ConfigurationTaskArtifactAccessService.access_artifact,
        query_db,
        artifact_id,
        current_user,
        "download",
    )
    if not result.is_success or not result.result:
        return ResponseUtil.failure(
            msg=result.message,
            dict_content={"errorCode": result.error_code or "ARTIFACT_ACCESS_FAILED"},
        )
    content = result.result
    return StreamingResponse(
        iter([content.content]),
        media_type=content.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(content.file_name)}",
            "Content-Length": str(content.file_size),
            "X-Artifact-Id": str(content.artifact_id),
            "X-Artifact-SHA256": content.sha256,
            "X-Content-Type-Options": "nosniff",
        },
    )


@taskController.post(
    "/runs/artifacts/agent-report",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:artifact:upload"))],
)
async def agent_report_step_artifact(
    request: Request,
    model: AgentStepScreenshotModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """Agent 上报步骤截图/日志产物。"""
    result = await run_in_threadpool(
        ConfigurationTaskArtifactService.register_agent_screenshot, query_db, model, current_user
    )
    return _result_response(result)


@taskController.post(
    "/runs/{task_run_id}/report",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:report:generate"))],
)
async def generate_run_report(
    request: Request,
    task_run_id: int,
    notify_feishu: bool = False,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """生成并归档运行报告（Word 兼容文件），可选飞书通知。"""
    result = await ConfigurationTaskReportService.generate_run_report(
        task_run_id, current_user, notify_feishu=notify_feishu
    )
    return _result_response(result)


@taskController.post(
    "/templates/from-recording",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:edit"))],
)
async def convert_recording_to_version(
    request: Request,
    model: RecordingToTemplateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """把录制会话转成任务版本草稿（录制→模板转换器）。"""
    result = await run_in_threadpool(
        ConfigurationTaskTemplateService.convert_recording_to_version, query_db, model, current_user
    )
    return _result_response(result)


@taskController.get(
    "/{task_id}/schedule",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:query"))],
)
async def get_task_schedule(
    request: Request,
    task_id: int,
    query_db: Session = Depends(get_db),
):
    """查询任务定时触发配置。"""
    data = await run_in_threadpool(ConfigurationTaskScheduleService.get_schedule, query_db, task_id)
    return ResponseUtil.success(data=data)


@taskController.put(
    "/{task_id}/schedule",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:task:edit"))],
)
async def save_task_schedule(
    request: Request,
    task_id: int,
    model: TaskScheduleModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """保存任务定时触发配置（启用时校验版本与 Agent 可用）。"""
    result = await run_in_threadpool(
        ConfigurationTaskScheduleService.save_schedule, query_db, task_id, model, current_user
    )
    return _result_response(result)
