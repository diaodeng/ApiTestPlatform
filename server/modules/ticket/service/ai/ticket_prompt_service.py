from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.entity.do.ticket_do import Ticket


class TicketPromptService:
    """
    工单 AI 提示词组装服务。
    """

    @staticmethod
    def _join_text(parts: list[str], *, separator: str = "\n") -> str:
        """
        拼接多行文本。
        :param parts: 文本片段列表。
        :param separator: 拼接分隔符。
        :return: 合并后的文本。
        """
        values = [str(item).strip() for item in parts if str(item or "").strip()]
        return separator.join(values)

    @staticmethod
    def _build_prompt_block(title: str, lines: list[str]) -> str:
        """
        构建提示词区块。
        :param title: 区块标题。
        :param lines: 区块内容行。
        :return: 格式化后的区块文本。
        """
        content = TicketPromptService._join_text(lines)
        if not content:
            return ""
        return "\n".join([f"【{title}】", content])

    @classmethod
    def _resolve_project_prompt(cls, project: HrmProject | None) -> str:
        """
        组装项目默认提示词。
        :param project: 项目对象。
        :return: 项目默认提示词。
        """
        if not project:
            return ""
        return cls._build_prompt_block(
            "项目默认提示词",
            [
                f"项目名称: {project.project_name or ''}",
                f"负责人: {project.responsible_name or ''}",
                f"发布应用: {project.publish_app or ''}",
                f"简要描述: {project.simple_desc or ''}",
                f"其他信息: {project.other_desc or ''}",
                "分析时请优先结合该项目的业务边界、发布应用和历史故障特征。",
            ],
        )

    @classmethod
    def _resolve_module_prompt(cls, module: HrmModule | None) -> str:
        """
        组装模块默认提示词。
        :param module: 模块对象。
        :return: 模块默认提示词。
        """
        if not module:
            return ""
        return cls._build_prompt_block(
            "模块默认提示词",
            [
                f"模块名称: {module.module_name or ''}",
                f"测试负责人: {module.test_user or ''}",
                f"简要描述: {module.simple_desc or ''}",
                f"其他信息: {module.other_desc or ''}",
                f"备注: {module.remark or ''}",
                "分析时请优先聚焦该模块相关链路、依赖、调用路径和已知问题。",
            ],
        )

    @classmethod
    def resolve_prompt_layers(
        cls,
        db: Session,
        ticket: Ticket,
    ) -> dict[str, Any]:
        """
        解析工单对应的提示词分层内容。
        :param db: 数据库会话。
        :param ticket: 工单对象。
        :return: 提示词分层数据。
        """
        project = None
        module = None
        if ticket.project_id:
            project = (
                db.query(HrmProject)
                .filter(
                    HrmProject.project_id == ticket.project_id,
                    HrmProject.status == QtrDataStatusEnum.normal.value,
                    HrmProject.del_flag == "0",
                )
                .first()
            )
        if ticket.module_id:
            module = (
                db.query(HrmModule)
                .filter(
                    HrmModule.module_id == ticket.module_id,
                    HrmModule.status == QtrDataStatusEnum.normal.value,
                    HrmModule.project_id == ticket.project_id,
                )
                .first()
            )

        project_prompt = cls._resolve_project_prompt(project)
        module_prompt = cls._resolve_module_prompt(module)
        default_prompt = cls._join_text([project_prompt, module_prompt], separator="\n\n")

        return {
            "project": {
                "projectId": getattr(project, "project_id", None),
                "projectName": getattr(project, "project_name", "") or "",
                "promptText": project_prompt,
            },
            "module": {
                "moduleId": getattr(module, "module_id", None),
                "moduleName": getattr(module, "module_name", "") or "",
                "promptText": module_prompt,
            },
            "defaultPromptText": default_prompt,
            "hasDefaultPrompt": bool(default_prompt.strip()),
        }

