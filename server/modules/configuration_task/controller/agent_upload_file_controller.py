"""Agent 受控上传目录浏览接口：只负责路由、鉴权、线程池包装和响应转换。"""

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService
from modules.configuration_task.entity.vo.agent_upload_file_vo import AgentUploadFileQueryModel
from modules.configuration_task.service.agent_upload_file_service import AgentUploadFileService
from utils.response_util import ResponseUtil

agentUploadFileController = APIRouter(
    prefix="/configuration-tasks/agent-upload-files",
    dependencies=[Depends(LoginService.get_current_user)],
)


@agentUploadFileController.get(
    "",
    dependencies=[Depends(CheckUserInterfaceAuth("configuration_task:resource:query"))],
)
async def list_agent_upload_files(
    request: Request,
    query: AgentUploadFileQueryModel = Depends(AgentUploadFileQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """查询指定 Agent 受控上传目录的条目，只返回相对路径与元数据。"""
    result = await run_in_threadpool(AgentUploadFileService.list_agent_upload_files, query_db, query)
    if not result.is_success:
        return ResponseUtil.failure(msg=result.message)
    return ResponseUtil.success(
        msg=result.message,
        data={
            "prefix": result.prefix,
            "entries": [entry.model_dump(by_alias=True) for entry in result.entries],
        },
    )
