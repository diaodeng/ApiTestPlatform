"""Agent 受控上传目录文件查询编排。

只负责把编辑器的目录浏览请求通过资源控制命令通道转发到指定 Agent，
并把 Agent 返回的受控条目收敛为接口契约；不直接读取文件系统。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger
from sqlalchemy.orm import Session

from module_hrm.dao.agent_dao import AgentDao
from module_qtr.service.agent_file_transfer_service import AgentFileTransferService
from module_qtr.service.agent_service import agents
from modules.configuration_task.entity.vo.agent_upload_file_vo import (
    AgentUploadFileEntryModel,
    AgentUploadFileQueryModel,
)


@dataclass
class AgentUploadFileQueryResult:
    """目录浏览查询结果。"""

    is_success: bool
    message: str
    prefix: str = ""
    entries: list[AgentUploadFileEntryModel] = field(default_factory=list)


class AgentUploadFileService:
    """转发受控上传目录列表查询，路径逃逸等校验由 Agent 侧负责。"""

    @classmethod
    def list_agent_upload_files(
        cls, db: Session, query: AgentUploadFileQueryModel
    ) -> AgentUploadFileQueryResult:
        """校验 Agent 在线后转发 file_list 命令，返回受控条目列表。"""
        agent = AgentDao.get_agent_by_code(db, query.agent_code)
        if not agent or agent.status != 2 or query.agent_code not in agents:
            return AgentUploadFileQueryResult(False, f"Agent {query.agent_code} 未在线，无法浏览上传目录")
        command_result = AgentFileTransferService.send_command(
            query.agent_code,
            "file_list",
            {"prefix": query.prefix},
        )
        if not command_result.success:
            logger.warning(
                f"Agent上传目录查询失败: agent_code={query.agent_code}, "
                f"error_code={command_result.error_code}, error_message={command_result.error_message}"
            )
            return AgentUploadFileQueryResult(
                False, command_result.error_message or "Agent 上传目录查询失败"
            )
        entries: list[AgentUploadFileEntryModel] = []
        for item in command_result.data.get("entries") or []:
            if not isinstance(item, dict):
                continue
            entries.append(
                AgentUploadFileEntryModel(
                    path=str(item.get("path") or "").strip(),
                    type=item.get("type") if item.get("type") in {"file", "directory"} else "file",
                    size=int(item.get("size") or 0),
                    modified_at=int(item.get("modified_at") or 0),
                )
            )
        prefix = str(command_result.data.get("prefix") or "").strip()
        logger.info(
            f"Agent上传目录查询成功: agent_code={query.agent_code}, prefix={prefix or '/'}, entries={len(entries)}"
        )
        return AgentUploadFileQueryResult(True, "查询成功", prefix=prefix, entries=entries)
