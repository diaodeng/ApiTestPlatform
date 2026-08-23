from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from module_hrm.dao.module_common_prompt_dao import ModuleCommonPromptDao
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.entity.do.ticket_do import Ticket
from utils.log_util import logger


class TicketPromptService:
    """
    工单 AI 提示词组装服务。

    项目提示词描述项目边界，模块通用说明按 module_code 跨项目复用，
    项目模块说明只描述当前项目的差异，三者在这里统一解析和拼装。
    """

    @staticmethod
    def _join_text(parts: list[str], *, separator: str = "\n") -> str:
        """拼接非空文本片段。"""
        values = [str(item).strip() for item in parts if str(item or "").strip()]
        return separator.join(values)

    @staticmethod
    def _build_prompt_block(title: str, lines: list[str]) -> str:
        """构建带标题的提示词区块。"""
        content = TicketPromptService._join_text(lines)
        if not content:
            return ""
        return "\n".join([f"【{title}】", content])

    @staticmethod
    def _serialize_id(value: Any) -> str | None:
        """将数据库主键转换为对外稳定的字符串。"""
        return str(value) if value is not None else None

    @classmethod
    def _resolve_project_prompt(cls, project: HrmProject | None) -> str:
        """组装项目默认提示词。"""
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
    def _resolve_module_project_prompt(cls, module: HrmModule | None) -> str:
        """组装当前项目独有的模块说明。"""
        if not module:
            return ""
        return cls._build_prompt_block(
            "项目模块说明",
            [
                f"模块名称: {module.module_name or ''}",
                f"模块编码: {module.module_code or ''}",
                f"测试负责人: {module.test_user or ''}",
                f"简要描述: {module.simple_desc or ''}",
                f"其他信息: {module.other_desc or ''}",
                f"备注: {module.remark or ''}",
                "分析时请优先聚焦该项目中此模块的专属链路、依赖、调用路径和已知问题。",
            ],
        )

    @classmethod
    def _resolve_module_common_prompt(cls, db: Session, module: HrmModule | None) -> tuple[dict[str, Any], str]:
        """
        按当前模块编码解析跨项目通用说明。
        :return: 通用说明层和对应提示词正文。
        """
        empty_layer: dict[str, Any] = {
            "promptId": None,
            "moduleCode": str(getattr(module, "module_code", "") or "").strip(),
            "promptText": "",
            "matched": False,
        }
        if not module:
            empty_layer["reason"] = "项目模块不存在或关联不匹配"
            return empty_layer, ""
        module_code = str(module.module_code or "").strip()
        if not module_code:
            empty_layer["reason"] = "项目模块未配置模块编码"
            logger.info(
                f"工单AI提示词未加载模块通用说明: module_id={module.module_id}, reason=module_code_empty"
            )
            return empty_layer, ""
        empty_layer["moduleCode"] = module_code
        common_prompt = ModuleCommonPromptDao.get_by_code(db, module_code, enabled_only=True)
        if not common_prompt:
            empty_layer["reason"] = "模块编码未配置启用的通用说明"
            logger.info(f"工单AI提示词未命中模块通用说明: module_code={module_code}")
            return empty_layer, ""
        prompt_text = cls._build_prompt_block("模块通用说明", [common_prompt.prompt_content])
        layer = {
            "promptId": cls._serialize_id(common_prompt.prompt_id),
            "moduleCode": module_code,
            "promptText": prompt_text,
            "matched": True,
            "updatedAt": common_prompt.update_time.isoformat() if common_prompt.update_time else None,
        }
        return layer, prompt_text

    @classmethod
    def resolve_prompt_layers(cls, db: Session, ticket: Ticket) -> dict[str, Any]:
        """
        解析工单对应的项目、模块通用和项目模块三层提示词。
        :param db: 数据库会话
        :param ticket: 工单对象
        :return: 提示词分层数据
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
        module_common_layer, module_common_prompt = cls._resolve_module_common_prompt(db, module)
        module_project_prompt = cls._resolve_module_project_prompt(module)
        project_layer = {
            "projectId": cls._serialize_id(getattr(project, "project_id", None)),
            "projectName": getattr(project, "project_name", "") or "",
            "promptText": project_prompt,
            "matched": bool(project_prompt),
        }
        module_project_layer = {
            "moduleId": cls._serialize_id(getattr(module, "module_id", None)),
            "projectId": cls._serialize_id(getattr(module, "project_id", None)),
            "moduleCode": str(getattr(module, "module_code", "") or "").strip(),
            "moduleName": getattr(module, "module_name", "") or "",
            "promptText": module_project_prompt,
            "matched": bool(module_project_prompt),
        }
        if not module:
            module_project_layer["reason"] = "项目模块不存在或关联不匹配"
        default_prompt = cls._join_text(
            [project_prompt, module_common_prompt, module_project_prompt],
            separator="\n\n",
        )
        return {
            "project": project_layer,
            "moduleCommon": module_common_layer,
            "moduleProject": module_project_layer,
            "defaultPromptText": default_prompt,
            "hasDefaultPrompt": bool(default_prompt.strip()),
        }
