import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.dao.ticket_dao import TicketDao, _date_end, _date_start
from modules.ticket.entity.do.ticket_do import (
    KnowledgeArticle,
    Ticket,
    TicketAssignHistory,
    TicketComment,
    TicketEvent,
    TicketMessage,
    TicketRca,
    TicketSnapshot,
    TicketStatusHistory,
    WorkflowStatus,
    WorkflowTransition,
)
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullCreateModel
from modules.ticket.entity.vo.ticket_vo import (
    KnowledgeArticleModel,
    KnowledgeArticleQueryModel,
    TicketAiAnalysisRequestModel,
    TicketAssignModel,
    TicketCommentCreateModel,
    TicketCreateModel,
    TicketEventCreateModel,
    TicketMessageCreateModel,
    TicketQueryModel,
    TicketRcaModel,
    TicketSnapshotModel,
    TicketStatusChangeModel,
    TicketUpdateModel,
    WorkflowStatusModel,
    WorkflowTransitionModel,
)
from modules.ticket.enums.ticket_enums import TicketEventType, TicketStatus
from modules.ticket.service.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.ticket_prompt_service import TicketPromptService
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.snowflake import snowIdWorker


def _user_id(current_user: CurrentUserModel) -> int | None:
    """
    获取当前登录用户ID。
    :param current_user: 当前登录用户
    :return: 用户ID
    """
    return current_user.user.user_id if current_user and current_user.user else None


def _user_name(current_user: CurrentUserModel) -> str:
    """
    获取当前登录用户名。
    :param current_user: 当前登录用户
    :return: 用户名
    """
    if not current_user or not current_user.user:
        return ""
    return current_user.user.user_name or current_user.user.nick_name or ""


def _dump_model(model, *, exclude_none: bool = True) -> dict[str, Any]:
    """
    将 Pydantic 模型转换为数据库字段字典。
    :param model: Pydantic模型
    :param exclude_none: 是否排除空值
    :return: 字典
    """
    return model.model_dump(by_alias=False, exclude_none=exclude_none)


def _camelize(value):
    """
    递归转换字典键为小驼峰，保证接口返回与前端字段约定一致。
    :param value: 字典、列表或普通值
    :return: 转换后的结果
    """
    if isinstance(value, dict):
        return {CamelCaseUtil.snake_to_camel(key): _camelize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camelize(item) for item in value]
    return value


def _normalize_int_list(value: Any) -> list[int]:
    """
    将前端多选参数归一化为整数列表。
    :param value: 逗号分隔字符串、数组或单个值
    :return: 去重后的整数列表
    """
    if value is None or value == "":
        return []
    raw_items = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    normalized: list[int] = []
    for item in raw_items:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            item_id = int(text)
        except ValueError:
            continue
        if item_id not in normalized:
            normalized.append(item_id)
    return normalized


def _ticket_no() -> str:
    """
    生成工单编号。
    :return: 工单编号
    """
    return f"TK{datetime.now().strftime('%Y%m%d')}{snowIdWorker.get_id()}"


def _text_sha256(value: Any) -> str:
    """
    计算文本 SHA256，用于记录翻译来源快照。
    :param value: 原始文本
    :return: SHA256 摘要
    """
    return hashlib.sha256(str(value or "").strip().encode("utf-8")).hexdigest()


def _extract_ticket_version_key(extra_data: Any) -> str:
    """
    从工单扩展信息中提取版本号。
    :param extra_data: 工单扩展字段
    :return: 版本号
    """
    if not isinstance(extra_data, dict):
        return ""
    for key in ("versionKey", "version_key", "version", "deployVersion", "deploy_version", "appVersion"):
        value = extra_data.get(key)
        if str(value or "").strip():
            return str(value).strip()
    return ""


def _extract_ticket_origin_description(extra_data: Any) -> str:
    """
    从工单扩展信息中提取原始描述。
    :param extra_data: 工单扩展字段
    :return: 原始描述
    """
    if not isinstance(extra_data, dict):
        return ""
    return str(extra_data.get("origin_description") or "").strip()


def _resolve_ticket_original_description(ticket: Ticket) -> str:
    """
    解析工单原始描述，优先使用扩展字段中保存的原文。
    :param ticket: 工单对象
    :return: 工单原始描述
    """
    extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
    origin_description = str(
        extra_data.get("origin_description")
        or extra_data.get("original_description")
        or ""
    ).strip()
    if origin_description:
        return origin_description
    description = str(ticket.description or "").strip()
    if "【AI翻译】" in description:
        return description.split("【AI翻译】", 1)[0].strip()
    return description


def _extract_ticket_sync_summary(extra_data: Any) -> dict[str, Any] | None:
    """
    从扩展字段中提取同步摘要信息。
    :param extra_data: 工单扩展字段
    :return: 同步摘要
    """
    if not isinstance(extra_data, dict):
        return None
    sync_meta = extra_data.get("external_sync")
    if not isinstance(sync_meta, dict):
        sync_meta = extra_data.get("externalSync")
    if not isinstance(sync_meta, dict):
        return None
    sync_state = sync_meta.get("sync_state") if isinstance(sync_meta.get("sync_state"), dict) else {}
    if not isinstance(sync_state, dict):
        sync_state = sync_meta.get("syncState") if isinstance(sync_meta.get("syncState"), dict) else {}
    automation = sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {}
    source_payload = sync_meta.get("source") if isinstance(sync_meta.get("source"), dict) else {}
    external_create_time = (
        sync_meta.get("externalCreateTime")
        or sync_meta.get("external_create_time")
        or source_payload.get("externalCreateTime")
        or source_payload.get("external_create_time")
    )
    return {
        "revision": int(sync_meta.get("revision") or 0),
        "sourceSystem": sync_meta.get("sourceSystem") or source_payload.get("system"),
        "sourceRecordId": (
            sync_meta.get("sourceRecordId") or source_payload.get("recordId") or source_payload.get("record_id")
        ),
        "sourceRecordUrl": (
            sync_meta.get("sourceRecordUrl") or source_payload.get("recordUrl") or source_payload.get("record_url")
        ),
        "externalCreateTime": external_create_time,
        "status": sync_state.get("status") or "pending",
        "lastPulledAt": sync_state.get("last_pulled_at"),
        "lastConsumer": sync_state.get("last_consumer"),
        "lastBatchId": sync_state.get("last_batch_id"),
        "automationStatus": automation.get("status"),
        "automationStep": automation.get("current_step"),
        "automationError": automation.get("last_error"),
    }


def _resolve_ticket_submit_time(extra_data: Any, create_time: Any) -> Any:
    """
    解析工单提交时间：优先外部 createTime，缺失时回退本地创建时间。

    :param extra_data: 工单扩展字段。
    :param create_time: 本地创建时间。
    :return: 提交时间值。
    """
    sync_summary = _extract_ticket_sync_summary(extra_data) or {}
    external_create_time = str(sync_summary.get("externalCreateTime") or "").strip()
    if external_create_time:
        return external_create_time
    return create_time


def _extract_ticket_automation_config(data: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
    """
    提取工单创建或编辑时携带的日志自动化配置。
    :param data: 工单字段字典
    :return: 是否启用日志拉取、日志拉取配置
    """
    need_log_pull = bool(data.pop("need_log_pull", False))
    log_pull_config = data.pop("log_pull_config", None)
    if isinstance(log_pull_config, dict):
        return need_log_pull, log_pull_config
    return need_log_pull, None


def _extract_ticket_manual_automation_config(data: dict[str, Any]) -> bool:
    """
    提取工单创建或编辑时的手动自动翻译开关。
    :param data: 工单字段字典
    :return: 是否自动翻译
    """
    return bool(data.pop("auto_translate", True))


def _is_end_status(status: str) -> bool:
    """
    判断状态是否为结束态。
    :param status: 状态编码
    :return: 是否结束态
    """
    return status in {
        TicketStatus.RESOLVED.value,
        TicketStatus.CLOSED.value,
        TicketStatus.REJECTED.value,
        TicketStatus.NON_PROBLEM.value,
        TicketStatus.DESIGN_AS_EXPECTED.value,
        TicketStatus.USER_MISOPERATION.value,
        TicketStatus.DUPLICATED.value,
    }


def _normalize_role_codes(raw_roles: Any) -> list[str]:
    """
    归一化流转规则中的角色编码列表。
    :param raw_roles: 原始角色数据
    :return: 去重后的角色编码列表
    """
    if not isinstance(raw_roles, list):
        return []
    normalized: list[str] = []
    for item in raw_roles:
        role_code = str(item or "").strip()
        if role_code and role_code not in normalized:
            normalized.append(role_code)
    return normalized


def _parse_transition_extension(raw_value: Any) -> dict[str, Any]:
    """
    从 `allowed_roles` JSON 中解析工单流转扩展配置。
    :param raw_value: 数据库中的 `allowed_roles`
    :return: 统一结构的扩展配置
    """
    extension = {
        "allowed_roles": [],
        "target_assignee_id": None,
        "target_assignee_name": "",
        "notify_enabled": False,
        "notify_remark": "",
    }
    if isinstance(raw_value, list):
        extension["allowed_roles"] = _normalize_role_codes(raw_value)
        return extension
    if not isinstance(raw_value, dict):
        return extension

    roles = raw_value.get("roles")
    if not isinstance(roles, list):
        roles = raw_value.get("allowedRoles")
    extension["allowed_roles"] = _normalize_role_codes(roles)

    assignee_payload = raw_value.get("assignee") if isinstance(raw_value.get("assignee"), dict) else {}
    extension["target_assignee_id"] = (
        assignee_payload.get("userId")
        or raw_value.get("targetAssigneeId")
        or raw_value.get("target_assignee_id")
    )
    extension["target_assignee_name"] = str(
        assignee_payload.get("userName")
        or raw_value.get("targetAssigneeName")
        or raw_value.get("target_assignee_name")
        or ""
    ).strip()

    notification_payload = raw_value.get("notification") if isinstance(raw_value.get("notification"), dict) else {}
    extension["notify_enabled"] = bool(
        notification_payload.get("enabled")
        if "enabled" in notification_payload
        else raw_value.get("notifyEnabled")
        or raw_value.get("notify_enabled")
    )
    extension["notify_remark"] = str(
        notification_payload.get("remark")
        or raw_value.get("notifyRemark")
        or raw_value.get("notify_remark")
        or ""
    ).strip()
    return extension


def _build_transition_storage_payload(transition_object: WorkflowTransitionModel) -> dict[str, Any]:
    """
    构建写入 `allowed_roles` JSON 列的流转扩展配置。
    :param transition_object: 流转规则入参
    :return: 可直接入库的 JSON 字典
    """
    role_source = transition_object.allowed_roles
    if isinstance(role_source, dict):
        role_source = _parse_transition_extension(role_source).get("allowed_roles")
    return {
        "roles": _normalize_role_codes(role_source),
        "assignee": {
            "userId": transition_object.target_assignee_id,
            "userName": (transition_object.target_assignee_name or "").strip(),
        },
        "notification": {
            "enabled": bool(transition_object.notify_enabled),
            "remark": (transition_object.notify_remark or "").strip(),
        },
    }


def _join_text_lines(values: list[Any], *, empty: str = "") -> str:
    """
    将字符串列表拼接为换行文本。
    :param values: 原始值列表
    :param empty: 空列表返回值
    :return: 换行文本
    """
    lines = [str(item).strip() for item in values if str(item or "").strip()]
    return "\n".join(lines) if lines else empty


class TicketService:
    """
    工单模块服务层，负责工单生命周期、状态机、事件和知识库业务逻辑。
    """

    @classmethod
    def init_default_workflow(cls, query_db: Session) -> None:
        """
        初始化默认工单工作流状态和流转配置。
        :param query_db: 数据库会话
        :return: 无
        """
        default_statuses = [
            (TicketStatus.PENDING.value, "待受理", True, False, 1),
            (TicketStatus.PROCESSING.value, "处理中", False, False, 2),
            (TicketStatus.WAIT_USER.value, "待用户反馈", False, False, 3),
            (TicketStatus.WAIT_DEV.value, "待开发", False, False, 4),
            (TicketStatus.WAIT_RELEASE.value, "待上线", False, False, 5),
            (TicketStatus.WAIT_VERIFY.value, "待验证", False, False, 6),
            (TicketStatus.RESOLVED.value, "已解决", False, True, 7),
            (TicketStatus.CLOSED.value, "已关闭", False, True, 8),
            (TicketStatus.REJECTED.value, "已驳回", False, True, 9),
            (TicketStatus.NON_PROBLEM.value, "非问题", False, True, 10),
            (TicketStatus.DESIGN_AS_EXPECTED.value, "设计如此", False, True, 11),
            (TicketStatus.USER_MISOPERATION.value, "用户误操作", False, True, 12),
            (TicketStatus.DUPLICATED.value, "重复工单", False, True, 13),
        ]
        existing_status_codes = {row.code for row in query_db.query(WorkflowStatus).all()}
        for code, name, is_start, is_end, order_num in default_statuses:
            if code not in existing_status_codes:
                query_db.add(
                    WorkflowStatus(code=code, name=name, is_start=is_start, is_end=is_end, order_num=order_num)
                )

        default_transitions = [
            (TicketStatus.PENDING.value, TicketStatus.PROCESSING.value, False, False),
            (TicketStatus.PENDING.value, TicketStatus.REJECTED.value, True, False),
            (TicketStatus.PENDING.value, TicketStatus.NON_PROBLEM.value, True, False),
            (TicketStatus.PROCESSING.value, TicketStatus.WAIT_USER.value, False, False),
            (TicketStatus.PROCESSING.value, TicketStatus.WAIT_DEV.value, False, False),
            (TicketStatus.PROCESSING.value, TicketStatus.WAIT_RELEASE.value, False, False),
            (TicketStatus.PROCESSING.value, TicketStatus.WAIT_VERIFY.value, False, False),
            (TicketStatus.PROCESSING.value, TicketStatus.RESOLVED.value, True, True),
            (TicketStatus.WAIT_USER.value, TicketStatus.PROCESSING.value, False, False),
            (TicketStatus.WAIT_DEV.value, TicketStatus.PROCESSING.value, False, False),
            (TicketStatus.WAIT_DEV.value, TicketStatus.WAIT_RELEASE.value, False, False),
            (TicketStatus.WAIT_RELEASE.value, TicketStatus.WAIT_VERIFY.value, False, False),
            (TicketStatus.WAIT_VERIFY.value, TicketStatus.RESOLVED.value, True, True),
            (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, False, False),
            (TicketStatus.PROCESSING.value, TicketStatus.DESIGN_AS_EXPECTED.value, True, False),
            (TicketStatus.PROCESSING.value, TicketStatus.USER_MISOPERATION.value, True, False),
            (TicketStatus.PROCESSING.value, TicketStatus.DUPLICATED.value, True, False),
        ]
        existing_transitions = {
            (row.from_status, row.to_status) for row in query_db.query(WorkflowTransition).all()
        }
        for from_status, to_status, need_comment, need_resolution in default_transitions:
            if (from_status, to_status) not in existing_transitions:
                query_db.add(
                    WorkflowTransition(
                        from_status=from_status,
                        to_status=to_status,
                        allowed_roles=[],
                        need_comment=need_comment,
                        need_resolution=need_resolution,
                )
                )
        query_db.commit()

    @classmethod
    def ensure_param_config_rows(cls, query_db: Session) -> None:
        """
        初始化工单翻译与轻量 AI 相关系统参数。
        :param query_db: 数据库会话
        :return: 无
        """
        from module_admin.entity.do.config_do import SysConfig

        defaults = [
            (
                "ticket.ai.translate.provider.code",
                "工单AI翻译Provider编码",
                "",
                "工单创建或编辑后执行轻量翻译时使用的AI Provider编码",
            ),
            (
                "ticket.ai.translate.prompt.code",
                "工单AI翻译提示词编码",
                "ticket_translate_default",
                "工单创建或编辑后执行轻量翻译时使用的提示词模板编码",
            ),
            (
                "ticket.ai.knowledge.provider.code",
                "工单知识提炼Provider编码",
                "",
                "工单关闭后自动提炼知识库案例时使用的AI Provider编码",
            ),
            (
                "ticket.ai.knowledge.prompt.code",
                "工单知识提炼提示词编码",
                "ticket_knowledge_extract_default",
                "工单关闭后自动提炼知识库案例时使用的提示词模板编码",
            ),
        ]
        now = datetime.now()
        for config_key, config_name, config_value, remark in defaults:
            existing = query_db.query(SysConfig).filter(SysConfig.config_key == config_key).first()
            if existing:
                continue
            query_db.add(
                SysConfig(
                    config_name=config_name,
                    config_key=config_key,
                    config_value=config_value,
                    config_type="Y",
                    create_by="system",
                    update_by="system",
                    create_time=now,
                    update_time=now,
                    remark=remark,
                )
            )
        query_db.flush()

    @staticmethod
    def _extract_version_key_from_text(text: str | None) -> str:
        """
        从工单正文或标题中提取版本号。
        :param text: 待分析文本
        :return: 版本号，未命中返回空字符串
        """
        return TicketLightAiService.extract_version_key_from_text(text)

    @classmethod
    def _decorate_ticket_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        """
        为工单返回结果补充项目名称兼容字段。
        :param item: 工单字典
        :return: 补充后的工单字典
        """
        project_name = str(item.get("projectName") or item.get("merchantName") or "").strip()
        item["projectName"] = project_name
        if "merchantName" not in item:
            item["merchantName"] = project_name
        extra_data = item.get("extraData")
        sync_summary = _extract_ticket_sync_summary(extra_data)
        item["versionKey"] = item.get("versionKey") or _extract_ticket_version_key(extra_data)
        if not str(item.get("ticketUrl") or "").strip() and isinstance(sync_summary, dict):
            item["ticketUrl"] = sync_summary.get("ticketUrl") or sync_summary.get("sourceRecordUrl")
        if isinstance(sync_summary, dict) and sync_summary.get("externalCreateTime"):
            item["externalCreateTime"] = sync_summary.get("externalCreateTime")
        item["submitTime"] = _resolve_ticket_submit_time(extra_data, item.get("createTime") or item.get("create_time"))
        origin_description = str(
            (extra_data or {}).get("origin_description")
            or (extra_data or {}).get("original_description")
            or ""
        ).strip()
        description = str(item.get("description") or "").strip()
        if not origin_description and "【AI翻译】" in description:
            origin_description = description.split("【AI翻译】", 1)[0].strip()
        item["originalDescription"] = origin_description or description
        item["aiTranslation"] = (extra_data or {}).get("ai_translation") or ""
        item["aiTranslationProviderCode"] = (extra_data or {}).get("ai_translation_provider_code") or ""
        item["aiTranslationPromptCode"] = (extra_data or {}).get("ai_translation_prompt_code") or ""
        item["syncSummary"] = sync_summary
        return item

    @classmethod
    def _attach_relation_codes(cls, query_db: Session, item: dict[str, Any]) -> dict[str, Any]:
        """
        根据项目/模块ID补充业务码，供外部同步链路传递。
        """
        project_id = item.get("projectId") or item.get("project_id")
        if project_id is not None:
            try:
                project = (
                    query_db.query(HrmProject)
                    .filter(
                        HrmProject.project_id == int(project_id),
                        HrmProject.status == QtrDataStatusEnum.normal.value,
                        HrmProject.del_flag == "0",
                    )
                    .first()
                )
                if project:
                    item["projectCode"] = str(getattr(project, "project_code", "") or "").strip()
            except Exception:
                pass

        module_id = item.get("moduleId") or item.get("module_id")
        if module_id is not None:
            try:
                module = (
                    query_db.query(HrmModule)
                    .filter(
                        HrmModule.module_id == int(module_id),
                        HrmModule.status == QtrDataStatusEnum.normal.value,
                    )
                    .first()
                )
                if module:
                    item["moduleCode"] = str(getattr(module, "module_code", "") or "").strip()
            except Exception:
                pass
        return item

    @classmethod
    def _resolve_ticket_relation_fields(
        cls, query_db: Session, data: dict[str, Any]
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        校验并回填工单关联的测试项目和模块名称。
        :param query_db: 数据库会话
        :param data: 工单字段字典
        :return: 校验结果、提示信息和需回填的字段
        """
        project_id = data.get("project_id")
        module_id = data.get("module_id")
        if not project_id:
            return False, "所属项目不能为空", {}

        project = (
            query_db.query(HrmProject)
            .filter(
                HrmProject.project_id == project_id,
                HrmProject.status == QtrDataStatusEnum.normal.value,
                HrmProject.del_flag == "0",
            )
            .first()
        )
        if not project:
            return False, "所属项目不存在或已停用", {}

        relation_fields = {
            "project_id": project.project_id,
            "merchant_name": project.project_name,
            "module_id": None,
            "module_name": str(data.get("module_name") or "").strip(),
        }

        if module_id:
            module = (
                query_db.query(HrmModule)
                .filter(
                    HrmModule.module_id == module_id,
                    HrmModule.status == QtrDataStatusEnum.normal.value,
                    HrmModule.project_id == project.project_id,
                )
                .first()
            )
            if not module:
                return False, "所属模块不存在、已停用或不属于当前项目", {}
            relation_fields["module_id"] = module.module_id
            relation_fields["module_name"] = module.module_name

        return True, "", relation_fields

    @classmethod
    def _resolve_transition_assignee_name(
        cls, query_db: Session, target_assignee_id: int | None, target_assignee_name: str | None
    ) -> str:
        """
        补齐流转规则中的默认处理人名称。
        :param query_db: 数据库会话
        :param target_assignee_id: 处理人ID
        :param target_assignee_name: 处理人名称
        :return: 最终名称
        """
        if str(target_assignee_name or "").strip():
            return str(target_assignee_name).strip()
        user = TicketDao.get_user_by_id(query_db, target_assignee_id)
        if not user:
            return ""
        return user.nick_name or user.user_name or ""

    @classmethod
    def _add_message(
        cls,
        query_db: Session,
        *,
        ticket_id: int,
        role: str,
        message_type: str,
        content: str,
        current_user: CurrentUserModel | None = None,
        attachments: Any = None,
        reference_type: str = "",
        reference_id: int | None = None,
        created_by_name: str | None = None,
        create_time: datetime | None = None,
    ) -> TicketMessage:
        """
        写入工单消息流。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param role: 消息角色
        :param message_type: 消息类型
        :param content: 消息内容
        :param current_user: 当前登录用户
        :param attachments: 附件或引用信息
        :param reference_type: 来源对象类型
        :param reference_id: 来源对象ID
        :param created_by_name: 自定义创建人名称
        :param create_time: 创建时间
        :return: 消息对象
        """
        return TicketDao.add_message(
            query_db,
            TicketMessage(
                ticket_id=ticket_id,
                role=str(role or "user").strip() or "user",
                message_type=str(message_type or "comment").strip() or "comment",
                content=content,
                attachments=attachments,
                reference_type=reference_type,
                reference_id=reference_id,
                created_by_id=_user_id(current_user) if current_user else None,
                created_by_name=created_by_name if created_by_name is not None else _user_name(current_user),
                create_time=create_time or datetime.now(),
            ),
        )

    @classmethod
    def _build_snapshot_payload_from_ticket(
        cls,
        ticket: Ticket,
        *,
        source_type: str = "manual",
        source_id: int | None = None,
        structured_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        基于工单当前态构建 ACR 快照数据。
        :param ticket: 工单对象
        :param source_type: 快照来源
        :param source_id: 来源对象ID
        :param structured_data: 结构化扩展数据
        :return: 快照字段
        """
        ai_payload = ticket.ai_analysis if isinstance(ticket.ai_analysis, dict) else {}
        next_steps = ai_payload.get("next_steps") or ai_payload.get("nextSteps") or []
        risk_items = ai_payload.get("risk_items") or ai_payload.get("riskItems") or []
        owner = (
            ai_payload.get("owner")
            or ai_payload.get("suggested_owner")
            or ai_payload.get("suggestedOwner")
            or ticket.current_assignee_name
            or ""
        )
        summary = ai_payload.get("analysis_summary") or ai_payload.get("analysisSummary") or ticket.description or ""
        root_cause = ticket.root_cause or str(ai_payload.get("root_cause") or ai_payload.get("rootCause") or "")
        solution = ticket.solution or str(ai_payload.get("fix_suggestion") or ai_payload.get("fixSuggestion") or "")
        return {
            "summary": str(summary),
            "root_cause": root_cause,
            "solution": solution,
            "prevention": _join_text_lines(next_steps) if isinstance(next_steps, list) else str(next_steps or ""),
            "risk": _join_text_lines(risk_items) if isinstance(risk_items, list) else str(risk_items or ""),
            "owner": str(owner or ""),
            "source_type": source_type,
            "source_id": source_id,
            "structured_data": structured_data or ai_payload or None,
        }

    @classmethod
    def create_snapshot(
        cls,
        query_db: Session,
        ticket_id: int,
        snapshot_object: TicketSnapshotModel | None = None,
        current_user: CurrentUserModel | None = None,
        *,
        source_type: str = "manual",
        source_id: int | None = None,
        structured_data: dict[str, Any] | None = None,
    ) -> CrudResponseModel:
        """
        创建工单 ACR 快照，并保持工单当前根因和方案为最新快照。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param snapshot_object: 快照参数；为空时从工单当前态生成
        :param current_user: 当前登录用户
        :param source_type: 快照来源
        :param source_id: 来源对象ID
        :param structured_data: 结构化快照数据
        :return: 操作结果
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        now = datetime.now()
        data = cls._build_snapshot_payload_from_ticket(
            ticket,
            source_type=source_type,
            source_id=source_id,
            structured_data=structured_data,
        )
        if snapshot_object:
            explicit = snapshot_object.model_dump(by_alias=False, exclude_none=True)
            explicit.pop("id", None)
            explicit.pop("ticket_id", None)
            explicit.pop("version", None)
            data.update(explicit)
        snapshot = TicketDao.add_snapshot(
            query_db,
            TicketSnapshot(
                ticket_id=ticket_id,
                version=TicketDao.get_next_snapshot_version(query_db, ticket_id),
                summary=data.get("summary"),
                root_cause=data.get("root_cause"),
                solution=data.get("solution"),
                prevention=data.get("prevention"),
                risk=data.get("risk"),
                owner=data.get("owner") or "",
                source_type=data.get("source_type") or source_type,
                source_id=data.get("source_id") or source_id,
                structured_data=data.get("structured_data"),
                created_by_id=_user_id(current_user) if current_user else None,
                created_by_name=_user_name(current_user) if current_user else "system",
                create_time=now,
            ),
        )
        update_data: dict[str, Any] = {
            "update_by": _user_name(current_user) if current_user else "system",
            "update_time": now,
        }
        if data.get("root_cause"):
            update_data["root_cause"] = data.get("root_cause")
        if data.get("solution"):
            update_data["solution"] = data.get("solution")
        TicketDao.update_ticket(query_db, ticket_id, update_data)
        cls._add_message(
            query_db,
            ticket_id=ticket_id,
            role="system",
            message_type="snapshot",
            content=f"ACR快照 V{snapshot.version} 已生成",
            current_user=current_user,
            reference_type="snapshot",
            reference_id=snapshot.id,
            create_time=now,
        )
        TicketDao.add_event(
            query_db,
            TicketEvent(
                ticket_id=ticket_id,
                event_type=TicketEventType.RCA.value,
                operator_id=_user_id(current_user) if current_user else None,
                operator_name=_user_name(current_user) if current_user else "system",
                content=f"ACR快照 V{snapshot.version} 已生成",
                event_data={
                    "snapshot_id": snapshot.id,
                    "version": snapshot.version,
                    "source_type": snapshot.source_type,
                },
                create_time=now,
            ),
        )
        return CrudResponseModel(
            is_success=True,
            message="快照生成成功",
            result=CamelCaseUtil.transform_result(snapshot),
        )

    @classmethod
    def _append_transition_assignment_and_notification(
        cls,
        query_db: Session,
        *,
        ticket: Ticket,
        ticket_id: int,
        transition: WorkflowTransition,
        target_status: str,
        current_user: CurrentUserModel,
        now: datetime,
        update_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        根据流转规则自动指派处理人，并写入通知占位事件。
        :param query_db: 数据库会话
        :param ticket: 当前工单对象
        :param ticket_id: 工单ID
        :param transition: 命中的流转规则
        :param target_status: 目标状态编码
        :param current_user: 当前登录用户
        :param now: 当前时间
        :param update_data: 工单待更新字段
        :return: 流转扩展结果
        """
        transition_extension = _parse_transition_extension(transition.allowed_roles)
        target_assignee_id = transition_extension.get("target_assignee_id")
        target_assignee_name = cls._resolve_transition_assignee_name(
            query_db,
            target_assignee_id=target_assignee_id,
            target_assignee_name=transition_extension.get("target_assignee_name"),
        )
        should_auto_assign = bool(target_assignee_id or target_assignee_name)
        assignee_changed = should_auto_assign and (
            int(target_assignee_id or 0) != int(ticket.current_assignee_id or 0)
            or str(target_assignee_name or "").strip() != str(ticket.current_assignee_name or "").strip()
        )

        if assignee_changed:
            assign_reason = f"状态流转到 {target_status} 后自动切换处理人"
            TicketDao.add_assign_history(
                query_db,
                TicketAssignHistory(
                    ticket_id=ticket_id,
                    from_user_id=ticket.current_assignee_id,
                    from_user_name=ticket.current_assignee_name,
                    to_user_id=target_assignee_id,
                    to_user_name=target_assignee_name,
                    assigned_by=_user_id(current_user),
                    assigned_by_name=_user_name(current_user),
                    reason=assign_reason,
                    assigned_at=now,
                ),
            )
            update_data["current_assignee_id"] = target_assignee_id
            update_data["current_assignee_name"] = target_assignee_name
            if not ticket.first_response_at:
                update_data["first_response_at"] = now
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.ASSIGNED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=assign_reason,
                    event_data={
                        "from_user_id": ticket.current_assignee_id,
                        "from_user_name": ticket.current_assignee_name,
                        "to_user_id": target_assignee_id,
                        "to_user_name": target_assignee_name,
                        "trigger_status": target_status,
                    },
                    create_time=now,
                ),
            )

        if transition_extension.get("notify_enabled") and (target_assignee_id or target_assignee_name):
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.NOTIFY_PENDING.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=f"状态流转通知待发送：{target_assignee_name or target_assignee_id}",
                    event_data={
                        "target_status": target_status,
                        "target_user_id": target_assignee_id,
                        "target_user_name": target_assignee_name,
                        "notify_remark": transition_extension.get("notify_remark"),
                        "notify_status": "pending_channel_implementation",
                    },
                    create_time=now,
                ),
            )

        return {
            "target_assignee_id": target_assignee_id,
            "target_assignee_name": target_assignee_name,
            "notify_enabled": bool(transition_extension.get("notify_enabled")),
            "notify_remark": transition_extension.get("notify_remark") or "",
            "allowed_roles": transition_extension.get("allowed_roles") or [],
        }

    @classmethod
    def create_ticket(
        cls, query_db: Session, ticket_object: TicketCreateModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        创建工单并写入初始状态历史和创建事件。
        :param query_db: 数据库会话
        :param ticket_object: 新增工单参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        try:
            now = datetime.now()
            data = _dump_model(ticket_object)
            data.pop("ticket_id", None)
            data.pop("project_name", None)
            auto_translate = _extract_ticket_manual_automation_config(data)
            need_log_pull, log_pull_config = _extract_ticket_automation_config(data)
            version_key = str(data.pop("version_key", "") or "").strip()
            original_description = str(data.get("description") or "").strip()
            extracted_version_key = version_key or cls._extract_version_key_from_text(
                "\n".join([str(data.get("title") or "").strip(), original_description]).strip()
            )
            extra_data = data.get("extra_data") if isinstance(data.get("extra_data"), dict) else {}
            manual_automation = (
                dict(extra_data.get("manual_automation") or {})
                if isinstance(extra_data.get("manual_automation"), dict)
                else {}
            )
            manual_automation["auto_translate"] = auto_translate
            extra_data["manual_automation"] = manual_automation
            if extracted_version_key:
                extra_data["version_key"] = extracted_version_key
            if log_pull_config:
                extra_data["ticket_automation"] = {
                    "need_log_pull": need_log_pull or bool(log_pull_config),
                    "log_pull_config": log_pull_config,
                }
            if auto_translate:
                translated_description, translation_meta = TicketLightAiService.translate_ticket_description(
                    query_db,
                    title=str(data.get("title") or "").strip(),
                    content=original_description,
                    source_type="ticket",
                    source_id=None,
                    source_ref=str(data.get("ticket_no") or "").strip() or None,
                    current_user_name=_user_name(current_user),
                )
                if translation_meta.get("skipped"):
                    data["description"] = original_description
                elif str(translation_meta.get("translated_text") or "").strip():
                    data["description"] = translated_description
                    extra_data["origin_description"] = original_description
                    extra_data["ai_translation"] = translation_meta.get("translated_text") or translated_description
                    if translation_meta.get("provider_code"):
                        extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
                    if translation_meta.get("prompt_code"):
                        extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
            data["extra_data"] = extra_data or None
            data.pop("auto_translate", None)
            is_valid, message, relation_fields = cls._resolve_ticket_relation_fields(query_db, data)
            if not is_valid:
                return CrudResponseModel(is_success=False, message=message)
            if not str(data.get("ticket_no") or "").strip():
                return CrudResponseModel(is_success=False, message="工单号不能为空")
            if TicketDao.get_ticket_by_no(query_db, str(data["ticket_no"]).strip()):
                return CrudResponseModel(is_success=False, message="工单号已存在")
            if need_log_pull or log_pull_config:
                if not log_pull_config:
                    return CrudResponseModel(is_success=False, message="启用日志拉取时需要填写日志拉取信息")
                TicketLogPullCreateModel.model_validate(log_pull_config)
            data.update(relation_fields)
            data["ticket_no"] = str(data.get("ticket_no") or "").strip()
            data["status"] = data.get("status") or TicketStatus.PENDING.value
            data["reporter_id"] = data.get("reporter_id") or _user_id(current_user)
            data["reporter_name"] = data.get("reporter_name") or _user_name(current_user)
            data["create_by"] = _user_name(current_user)
            data["update_by"] = _user_name(current_user)
            data["create_time"] = now
            data["update_time"] = now
            ticket = Ticket(**data)
            ticket = TicketDao.add_ticket(query_db, ticket)
            TicketDao.add_status_history(
                query_db,
                TicketStatusHistory(
                    ticket_id=ticket.ticket_id,
                    from_status=None,
                    to_status=ticket.status,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    started_at=now,
                    comment="工单创建",
                ),
            )
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=TicketEventType.TICKET_CREATED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content="工单创建",
                    event_data={
                        "ticket_no": ticket.ticket_no,
                        "status": ticket.status,
                        "need_log_pull": bool(need_log_pull or log_pull_config),
                    },
                    create_time=now,
                ),
            )
            cls._add_message(
                query_db,
                ticket_id=ticket.ticket_id,
                role="user",
                message_type="ticket_created",
                content=f"{ticket.title}\n\n{ticket.description or ''}".strip(),
                current_user=current_user,
                reference_type="ticket",
                reference_id=ticket.ticket_id,
                create_time=now,
            )
            query_db.commit()
            try:
                from modules.ticket.service.ticket_sync_service import TicketSyncService

                ticket, ai_stat_summary = TicketSyncService._run_auto_ticket_ai_classification(
                    query_db,
                    ticket=ticket,
                    title=str(ticket.title or "").strip(),
                    description=str(ticket.description or "").strip(),
                    current_user_name=_user_name(current_user),
                    source_type="ticket_manual_create_auto_category",
                    source_ref=ticket.ticket_no,
                    force_reclassify=False,
                    enabled_by_scene=True,
                )
                if ai_stat_summary.get("skipped"):
                    logger.info(f"工单[{ticket.ticket_id}]自动分类统计跳过: {ai_stat_summary.get('skipReason')}")
            except Exception as exc:
                query_db.rollback()
                logger.warning(f"工单[{ticket.ticket_id}]自动分类执行失败: {exc}")
            try:
                TicketEmbeddingService.vectorize_ticket_for_scene(query_db, ticket, "manualCreate")
                query_db.commit()
            except Exception as exc:
                query_db.rollback()
                logger.warning(f"工单[{ticket.ticket_id}]手动新增后向量刷新失败: {exc}")
            if need_log_pull or log_pull_config:
                try:
                    log_pull_result = TicketLogPullService.create_log_pull_services(
                        query_db,
                        ticket.ticket_id,
                        TicketLogPullCreateModel.model_validate(log_pull_config),
                        current_user,
                    )
                    if not log_pull_result.is_success:
                        logger.warning(f"工单[{ticket.ticket_id}]创建后自动提交日志拉取失败: {log_pull_result.message}")
                except Exception as exc:
                    logger.exception(f"工单[{ticket.ticket_id}]创建后自动提交日志拉取异常: {exc}")
            result = CamelCaseUtil.transform_result(ticket)
            cls._decorate_ticket_item(result)
            return CrudResponseModel(is_success=True, message="新增成功", result=result)
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def get_ticket_list_services(cls, query_db: Session, query: TicketQueryModel):
        """
        获取工单列表。
        :param query_db: 数据库会话
        :param query: 查询参数
        :return: 分页结果或列表
        """
        result = TicketDao.get_ticket_list(query_db, query)
        if query.is_page:
            rows = result.rows or []
            ticket_ids = [item.get("ticketId") for item in rows if isinstance(item, dict) and item.get("ticketId")]
            summary_map = TicketLogPullService.get_latest_summary_map(query_db, ticket_ids)
            ai_summary_map = TicketAiAnalysisService.get_latest_summary_map(query_db, ticket_ids)
            for item in rows:
                if isinstance(item, dict):
                    cls._decorate_ticket_item(item)
                    item["latestLogPull"] = summary_map.get(item.get("ticketId"))
                    item["latestAiAnalysis"] = ai_summary_map.get(item.get("ticketId"))
            return result
        ticket_ids = [item.get("ticketId") for item in result if isinstance(item, dict) and item.get("ticketId")]
        summary_map = TicketLogPullService.get_latest_summary_map(query_db, ticket_ids)
        ai_summary_map = TicketAiAnalysisService.get_latest_summary_map(query_db, ticket_ids)
        for item in result:
            if isinstance(item, dict):
                cls._decorate_ticket_item(item)
                item["latestLogPull"] = summary_map.get(item.get("ticketId"))
                item["latestAiAnalysis"] = ai_summary_map.get(item.get("ticketId"))
        return result

    @classmethod
    def get_ticket_detail_services(cls, query_db: Session, ticket_id: int) -> dict | None:
        """
        获取工单详情。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :return: 工单详情
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return None
        result = CamelCaseUtil.transform_result(ticket)
        cls._decorate_ticket_item(result)
        cls._attach_relation_codes(query_db, result)
        result["latestLogPull"] = TicketLogPullService.get_latest_summary(query_db, ticket_id)
        result["latestAiAnalysis"] = TicketAiAnalysisService.get_latest_summary(query_db, ticket_id)
        message_bundle = cls.get_messages_services(query_db, ticket_id) or {}
        result["messages"] = message_bundle.get("messages") or []
        result["snapshots"] = message_bundle.get("snapshots") or []
        result["latestSnapshot"] = message_bundle.get("latestSnapshot")
        result["similarTickets"] = message_bundle.get("similarTickets") or []
        result["aiPromptLayers"] = TicketPromptService.resolve_prompt_layers(query_db, ticket)
        return result

    @classmethod
    def update_ticket(
        cls, query_db: Session, ticket_object: TicketUpdateModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        更新工单基础信息并写入更新事件。
        :param query_db: 数据库会话
        :param ticket_object: 工单编辑参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_object.ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        try:
            data = _dump_model(ticket_object)
            data.pop("ticket_id", None)
            data.pop("project_code", None)
            data.pop("project_name", None)
            auto_translate = _extract_ticket_manual_automation_config(data)
            need_log_pull, log_pull_config = _extract_ticket_automation_config(data)
            version_key = str(data.pop("version_key", "") or "").strip()
            ticket_extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
            original_description = str(
                data.get("description") or ticket_extra_data.get("origin_description") or ""
            ).strip()
            extracted_version_key = version_key or cls._extract_version_key_from_text(
                "\n".join([str(data.get("title") or ticket.title or "").strip(), original_description]).strip()
            )
            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            form_extra_data = data.get("extra_data") if isinstance(data.get("extra_data"), dict) else {}
            extra_data.update(form_extra_data)
            manual_automation = (
                dict(extra_data.get("manual_automation") or {})
                if isinstance(extra_data.get("manual_automation"), dict)
                else {}
            )
            manual_automation["auto_translate"] = auto_translate
            extra_data["manual_automation"] = manual_automation
            if extracted_version_key:
                extra_data["version_key"] = extracted_version_key
            elif "version_key" in extra_data:
                extra_data.pop("version_key", None)
            if log_pull_config:
                extra_data["ticket_automation"] = {
                    "need_log_pull": need_log_pull or bool(log_pull_config),
                    "log_pull_config": log_pull_config,
                }
            elif "ticket_automation" in extra_data and not need_log_pull:
                extra_data.pop("ticket_automation", None)
            if auto_translate:
                translated_description, translation_meta = TicketLightAiService.translate_ticket_description(
                    query_db,
                    title=str(data.get("title") or ticket.title or "").strip(),
                    content=original_description,
                    source_type="ticket",
                    source_id=ticket.ticket_id,
                    source_ref=ticket.ticket_no,
                    current_user_name=_user_name(current_user),
                )
                if translation_meta.get("skipped"):
                    data["description"] = original_description
                elif str(translation_meta.get("translated_text") or "").strip():
                    data["description"] = translated_description
                    extra_data["origin_description"] = original_description
                    extra_data["ai_translation"] = translation_meta.get("translated_text") or translated_description
                    if translation_meta.get("provider_code"):
                        extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
                    if translation_meta.get("prompt_code"):
                        extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
            data["extra_data"] = extra_data or None
            data.pop("auto_translate", None)
            is_valid, message, relation_fields = cls._resolve_ticket_relation_fields(query_db, data)
            if not is_valid:
                return CrudResponseModel(is_success=False, message=message)
            ticket_no = str(data.get("ticket_no") or ticket.ticket_no or "").strip()
            if not ticket_no:
                return CrudResponseModel(is_success=False, message="工单号不能为空")
            existing = TicketDao.get_ticket_by_no(query_db, ticket_no)
            if existing and existing.ticket_id != ticket.ticket_id:
                return CrudResponseModel(is_success=False, message="工单号已存在")
            data.update(relation_fields)
            data["update_by"] = _user_name(current_user)
            data["update_time"] = datetime.now()
            data["ticket_no"] = ticket_no
            TicketDao.update_ticket(query_db, ticket.ticket_id, data)
            refreshed_ticket = TicketDao.get_ticket_by_id(query_db, ticket.ticket_id) or ticket
            try:
                TicketEmbeddingService.vectorize_ticket_for_scene(query_db, refreshed_ticket, "manualUpdate")
            except Exception as exc:
                logger.warning(f"工单[{ticket.ticket_id}]手动更新后向量刷新失败: {exc}")
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=TicketEventType.TICKET_UPDATED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content="工单基础信息更新",
                    event_data=data,
                ),
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="更新成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def translate_ticket_description_services(
        cls, query_db: Session, ticket_id: int, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        手动翻译工单描述，并将原文与译文分别保存到扩展字段。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param current_user: 当前登录用户
        :return: 翻译结果和刷新后的工单详情
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        original_description = _resolve_ticket_original_description(ticket)
        if not original_description:
            return CrudResponseModel(is_success=False, message="当前工单描述为空，无法翻译")
        try:
            translated_description, translation_meta = TicketLightAiService.translate_ticket_description(
                query_db,
                title=str(ticket.title or "").strip(),
                content=original_description,
                source_type="ticket_manual_translate",
                source_id=ticket.ticket_id,
                source_ref=ticket.ticket_no,
                current_user_name=_user_name(current_user),
            )
            translated_text = str(translation_meta.get("translated_text") or "").strip()
            if not translated_text:
                message = str(translation_meta.get("error") or "").strip()
                missing_translate_config = (
                    translation_meta.get("skipped")
                    or not translation_meta.get("provider_code")
                    or not translation_meta.get("prompt_code")
                )
                if missing_translate_config:
                    message = "未获取到自动翻译配置或翻译总开关未开启，请先配置翻译 Provider、提示词并开启翻译"
                return CrudResponseModel(is_success=False, message=message or "翻译未生成有效内容")
            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            extra_data["origin_description"] = original_description
            extra_data["ai_translation"] = translated_text
            extra_data["ai_translation_source_hash"] = _text_sha256(original_description)
            if translation_meta.get("provider_code"):
                extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
            if translation_meta.get("prompt_code"):
                extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
            TicketDao.update_ticket(
                query_db,
                ticket.ticket_id,
                {
                    "description": translated_description,
                    "extra_data": extra_data,
                    "update_by": _user_name(current_user),
                    "update_time": datetime.now(),
                },
            )
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=TicketEventType.TICKET_UPDATED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content="手动翻译工单描述",
                    event_data={
                        "provider_code": translation_meta.get("provider_code") or "",
                        "prompt_code": translation_meta.get("prompt_code") or "",
                    },
                ),
            )
            query_db.commit()
            detail = cls.get_ticket_detail_services(query_db, ticket.ticket_id)
            return CrudResponseModel(is_success=True, message="翻译成功", result=detail)
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def delete_ticket(cls, query_db: Session, ticket_id: int, current_user: CurrentUserModel) -> CrudResponseModel:
        """
        软删除工单并写入删除事件。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        try:
            now = datetime.now()
            TicketDao.delete_ticket(
                query_db,
                ticket_id,
                {"del_flag": "2", "update_by": _user_name(current_user), "update_time": now},
            )
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.TICKET_UPDATED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content="工单删除",
                    event_data={"del_flag": "2"},
                    create_time=now,
                ),
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def assign_ticket(
        cls, query_db: Session, ticket_id: int, assign_object: TicketAssignModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        指派工单处理人并记录指派历史和事件。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param assign_object: 指派参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        try:
            now = datetime.now()
            TicketDao.add_assign_history(
                query_db,
                TicketAssignHistory(
                    ticket_id=ticket_id,
                    from_user_id=ticket.current_assignee_id,
                    from_user_name=ticket.current_assignee_name,
                    to_user_id=assign_object.to_user_id,
                    to_user_name=assign_object.to_user_name,
                    assigned_by=_user_id(current_user),
                    assigned_by_name=_user_name(current_user),
                    reason=assign_object.reason,
                    assigned_at=now,
                ),
            )
            update_data = {
                "current_assignee_id": assign_object.to_user_id,
                "current_assignee_name": assign_object.to_user_name or "",
                "update_by": _user_name(current_user),
                "update_time": now,
            }
            if not ticket.started_at:
                update_data["started_at"] = now
            if not ticket.first_response_at:
                update_data["first_response_at"] = now
            TicketDao.update_ticket(query_db, ticket_id, update_data)
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.ASSIGNED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=assign_object.reason or "工单指派",
                    event_data={
                        "from_user_id": ticket.current_assignee_id,
                        "from_user_name": ticket.current_assignee_name,
                        "to_user_id": assign_object.to_user_id,
                        "to_user_name": assign_object.to_user_name,
                    },
                    create_time=now,
                ),
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="指派成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def change_ticket_status(
        cls, query_db: Session, ticket_id: int, status_object: TicketStatusChangeModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        按状态机流转工单状态，记录状态历史、事件和归档字段。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param status_object: 状态流转参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        if ticket.status == status_object.to_status:
            return CrudResponseModel(is_success=False, message="目标状态与当前状态一致")

        transition = TicketDao.get_transition(query_db, ticket.status, status_object.to_status)
        if not transition:
            message = f"不允许从 {ticket.status} 流转到 {status_object.to_status}"
            return CrudResponseModel(is_success=False, message=message)
        if transition.need_comment and not status_object.comment:
            return CrudResponseModel(is_success=False, message="该状态流转必须填写说明")
        if transition.need_resolution and not (status_object.solution or ticket.solution):
            return CrudResponseModel(is_success=False, message="该状态流转必须填写解决方案")

        try:
            now = datetime.now()
            TicketDao.close_open_status_history(query_db, ticket_id, now)
            TicketDao.add_status_history(
                query_db,
                TicketStatusHistory(
                    ticket_id=ticket_id,
                    from_status=ticket.status,
                    to_status=status_object.to_status,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    started_at=now,
                    comment=status_object.comment,
                ),
            )
            update_data: dict[str, Any] = {
                "status": status_object.to_status,
                "update_by": _user_name(current_user),
                "update_time": now,
            }
            if status_object.root_cause is not None:
                update_data["root_cause"] = status_object.root_cause
            if status_object.solution is not None:
                update_data["solution"] = status_object.solution
            if status_object.is_problem is not None:
                update_data["is_problem"] = status_object.is_problem
            if status_object.root_cause_type is not None:
                update_data["root_cause_type"] = status_object.root_cause_type
            if status_object.solution_type is not None:
                update_data["solution_type"] = status_object.solution_type
            if status_object.resolution_code is not None:
                update_data["resolution_code"] = status_object.resolution_code
            if status_object.resolution_name is not None:
                update_data["resolution_name"] = status_object.resolution_name
            if not ticket.started_at and status_object.to_status == TicketStatus.PROCESSING.value:
                update_data["started_at"] = now
            if _is_end_status(status_object.to_status):
                update_data["resolved_at"] = ticket.resolved_at or now
                if status_object.to_status == TicketStatus.CLOSED.value:
                    update_data["closed_at"] = now
                start_time = ticket.started_at or ticket.create_time
                update_data["total_process_seconds"] = max(int((now - start_time).total_seconds()), 0)
            transition_extension = cls._append_transition_assignment_and_notification(
                query_db,
                ticket=ticket,
                ticket_id=ticket_id,
                transition=transition,
                target_status=status_object.to_status,
                current_user=current_user,
                now=now,
                update_data=update_data,
            )
            TicketDao.update_ticket(query_db, ticket_id, update_data)
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.STATUS_CHANGED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=status_object.comment,
                    event_data={
                        "from_status": ticket.status,
                        "to_status": status_object.to_status,
                        "is_problem": status_object.is_problem,
                        "root_cause_type": status_object.root_cause_type,
                        "solution_type": status_object.solution_type,
                        "resolution_code": status_object.resolution_code,
                        "resolution_name": status_object.resolution_name,
                        "target_assignee_id": transition_extension.get("target_assignee_id"),
                        "target_assignee_name": transition_extension.get("target_assignee_name"),
                        "notify_enabled": transition_extension.get("notify_enabled"),
                        "notify_remark": transition_extension.get("notify_remark"),
                    },
                    create_time=now,
                ),
            )
            if _is_end_status(status_object.to_status):
                cls.create_snapshot(
                    query_db,
                    ticket_id,
                    current_user=current_user,
                    source_type="status",
                    structured_data={
                        "from_status": ticket.status,
                        "to_status": status_object.to_status,
                        "comment": status_object.comment,
                    },
                )
            if status_object.to_status == TicketStatus.CLOSED.value:
                try:
                    cls.create_knowledge_from_ticket(query_db, ticket_id, current_user)
                except Exception as exc:
                    logger.warning(f"工单[{ticket_id}]关闭后自动提炼知识库失败: {exc}")
            query_db.commit()
            return CrudResponseModel(is_success=True, message="状态流转成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def add_comment(
        cls, query_db: Session, ticket_id: int, comment_object: TicketCommentCreateModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        新增工单评论并写入评论事件。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param comment_object: 评论参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        if not TicketDao.get_ticket_by_id(query_db, ticket_id):
            return CrudResponseModel(is_success=False, message="工单不存在")
        try:
            comment = TicketDao.add_comment(
                query_db,
                TicketComment(
                    ticket_id=ticket_id,
                    user_id=_user_id(current_user),
                    user_name=_user_name(current_user),
                    content=comment_object.content,
                    is_internal=comment_object.is_internal,
                    attachments=comment_object.attachments,
                    source_type="local",
                ),
            )
            cls._add_message(
                query_db,
                ticket_id=ticket_id,
                role="user",
                message_type="comment",
                content=comment_object.content,
                current_user=current_user,
                attachments={
                    "is_internal": comment_object.is_internal,
                    "comment_attachments": comment_object.attachments,
                    "source_type": "local",
                },
                reference_type="comment",
                reference_id=comment.id,
                create_time=comment.create_time,
            )
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.COMMENTED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=comment_object.content,
                    event_data={
                        "comment_id": comment.id,
                        "is_internal": comment_object.is_internal,
                        "source_type": "local",
                    },
                ),
            )
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="评论成功",
                result=CamelCaseUtil.transform_result(comment),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def list_comment_services(cls, query_db: Session, ticket_id: int) -> list | None:
        """
        获取工单评论列表。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :return: 评论列表；工单不存在时返回 None
        """
        if not TicketDao.get_ticket_by_id(query_db, ticket_id):
            return None
        return CamelCaseUtil.transform_result(TicketDao.list_comments(query_db, ticket_id))

    @classmethod
    def upsert_synced_comment(
        cls,
        query_db: Session,
        *,
        ticket_id: int,
        content: str,
        user_name: str,
        source_type: str,
        source_system: str,
        source_record_id: str,
        source_field: str,
        source_segment_key: str,
        source_segment_index: int,
        source_content_hash: str,
        external_created_at: datetime | None = None,
        attachments: dict[str, Any] | list[dict[str, Any]] | None = None,
        is_internal: bool = False,
    ) -> tuple[TicketComment | None, str]:
        """
        按外部分段幂等键新增或更新同步评论，本地评论不会被覆盖。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param content: 评论内容
        :param user_name: 评论人名称
        :param source_type: 来源类型，如 feishu_bitable
        :param source_system: 来源系统
        :param source_record_id: 来源记录ID
        :param source_field: 来源字段
        :param source_segment_key: 外部分段幂等键
        :param source_segment_index: 外部分段序号
        :param source_content_hash: 外部内容哈希
        :param external_created_at: 外部评论时间
        :param attachments: 评论附件或引用
        :param is_internal: 是否内部评论
        :return: (评论对象, 动作 created/updated/skipped)
        """
        normalized_content = str(content or "").strip()
        normalized_key = str(source_segment_key or "").strip()
        if not normalized_content or not normalized_key:
            return None, "skipped"
        existing = TicketDao.get_comment_by_source_segment_key(
            query_db,
            ticket_id=ticket_id,
            source_segment_key=normalized_key,
        )
        now = datetime.now()
        source_payload = {
            "source_type": str(source_type or "external").strip() or "external",
            "source_system": str(source_system or "").strip(),
            "source_record_id": str(source_record_id or "").strip(),
            "source_field": str(source_field or "").strip(),
            "source_segment_key": normalized_key,
            "source_segment_index": int(source_segment_index or 0),
            "source_content_hash": str(source_content_hash or "").strip(),
            "external_created_at": external_created_at,
            "attachments": attachments,
            "is_internal": bool(is_internal),
        }
        if existing:
            if (
                str(existing.source_content_hash or "") == source_payload["source_content_hash"]
                and str(existing.content or "").strip() == normalized_content
                and (existing.attachments or None) == (attachments or None)
            ):
                return existing, "skipped"
            TicketDao.update_comment(
                query_db,
                existing.id,
                {
                    "user_name": str(user_name or "").strip() or existing.user_name or "外部同步",
                    "content": normalized_content,
                    **source_payload,
                },
            )
            TicketDao.update_message_by_reference(
                query_db,
                reference_type="comment",
                reference_id=existing.id,
                data={
                    "content": normalized_content,
                    "attachments": {
                        "is_internal": bool(is_internal),
                        "source_type": source_payload["source_type"],
                        "source_system": source_payload["source_system"],
                        "source_record_id": source_payload["source_record_id"],
                        "source_field": source_payload["source_field"],
                        "source_segment_key": normalized_key,
                        "source_segment_index": source_payload["source_segment_index"],
                        "source_content_hash": source_payload["source_content_hash"],
                        "comment_attachments": attachments,
                    },
                    "created_by_name": str(user_name or "").strip() or existing.user_name or "外部同步",
                },
            )
            query_db.flush()
            refreshed = TicketDao.get_comment_by_source_segment_key(
                query_db,
                ticket_id=ticket_id,
                source_segment_key=normalized_key,
            )
            return refreshed or existing, "updated"

        comment = TicketDao.add_comment(
            query_db,
            TicketComment(
                ticket_id=ticket_id,
                user_id=None,
                user_name=str(user_name or "").strip() or "外部同步",
                content=normalized_content,
                create_time=external_created_at or now,
                **source_payload,
            ),
        )
        cls._add_message(
            query_db,
            ticket_id=ticket_id,
            role="user",
            message_type="external_comment",
            content=normalized_content,
            current_user=None,
            attachments={
                "is_internal": bool(is_internal),
                "source_type": source_payload["source_type"],
                "source_system": source_payload["source_system"],
                "source_record_id": source_payload["source_record_id"],
                "source_field": source_payload["source_field"],
                "source_segment_key": normalized_key,
                "source_segment_index": source_payload["source_segment_index"],
                "source_content_hash": source_payload["source_content_hash"],
                "comment_attachments": attachments,
            },
            reference_type="comment",
            reference_id=comment.id,
            create_time=comment.create_time,
        )
        TicketDao.add_event(
            query_db,
            TicketEvent(
                ticket_id=ticket_id,
                event_type=TicketEventType.COMMENTED.value,
                operator_id=None,
                operator_name=str(user_name or "").strip() or "外部同步",
                content=normalized_content,
                event_data={
                    "comment_id": comment.id,
                    "is_internal": bool(is_internal),
                    "source_type": source_payload["source_type"],
                    "source_record_id": source_payload["source_record_id"],
                    "source_segment_key": normalized_key,
                },
                create_time=comment.create_time,
            ),
        )
        return comment, "created"

    @classmethod
    def add_event(
        cls, query_db: Session, ticket_id: int, event_object: TicketEventCreateModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        新增工单结构化事件，用于排查过程、复现步骤、日志分析、修复和验证记录。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param event_object: 事件参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        if not TicketDao.get_ticket_by_id(query_db, ticket_id):
            return CrudResponseModel(is_success=False, message="工单不存在")
        try:
            event = TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=event_object.event_type,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=event_object.content,
                    event_data=event_object.event_data,
                ),
            )
            if event_object.content:
                cls._add_message(
                    query_db,
                    ticket_id=ticket_id,
                    role="developer",
                    message_type=str(event_object.event_type or "action").lower(),
                    content=event_object.content,
                    current_user=current_user,
                    attachments=event_object.event_data,
                    reference_type="event",
                    reference_id=event.id,
                    create_time=event.create_time,
                )
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="事件记录成功",
                result=CamelCaseUtil.transform_result(event),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def get_timeline_services(cls, query_db: Session, ticket_id: int) -> dict | None:
        """
        获取工单完整生命周期时间线。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :return: 时间线数据
        """
        if not TicketDao.get_ticket_by_id(query_db, ticket_id):
            return None
        timeline = TicketDao.get_timeline(query_db, ticket_id, include_comments=False)
        return {key: CamelCaseUtil.transform_result(value) for key, value in timeline.items()}

    @classmethod
    def get_messages_services(cls, query_db: Session, ticket_id: int) -> dict | None:
        """
        获取工单协同消息、ACR快照和相似工单推荐。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :return: 消息流、快照、最新快照和相似工单
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return None
        search_text = " ".join(
            str(item)
            for item in [
                ticket.title,
                ticket.description,
                ticket.root_cause,
                ticket.solution,
                ticket.module_name,
                ticket.category_name,
            ]
            if item
        )
        similar_tickets = [
            item
            for item in TicketEmbeddingService.search_tickets(query_db, search_text, 6)
            if item.get("ticketId") != ticket_id
        ]
        snapshots = TicketDao.list_snapshots(query_db, ticket_id)
        return {
            "messages": CamelCaseUtil.transform_result(TicketDao.list_messages(query_db, ticket_id)),
            "snapshots": CamelCaseUtil.transform_result(snapshots),
            "latestSnapshot": CamelCaseUtil.transform_result(snapshots[0]) if snapshots else None,
            "similarTickets": similar_tickets[:5],
        }

    @classmethod
    def add_message(
        cls,
        query_db: Session,
        ticket_id: int,
        message_object: TicketMessageCreateModel,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """
        新增工单协同消息；可选同步提交 AI 追问任务。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param message_object: 消息内容、角色、类型和 AI 追问参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        content = str(message_object.content or "").strip()
        if not content:
            return CrudResponseModel(is_success=False, message="消息内容不能为空")
        try:
            now = datetime.now()
            message = cls._add_message(
                query_db,
                ticket_id=ticket_id,
                role=message_object.role,
                message_type=message_object.message_type,
                content=content,
                current_user=current_user,
                attachments=message_object.attachments,
                create_time=now,
            )
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.COMMENTED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=content,
                    event_data={
                        "message_id": message.id,
                        "role": message.role,
                        "message_type": message.message_type,
                        "run_ai": message_object.run_ai,
                    },
                    create_time=now,
                ),
            )
            query_db.commit()
            ai_result = None
            ai_message = ""
            ai_success = False
            if message_object.run_ai:
                try:
                    version_key = (
                        str(message_object.version_key or "").strip()
                        or _extract_ticket_version_key(ticket.extra_data)
                        or ""
                    )
                    if not version_key:
                        ai_message = "当前工单缺少版本号，未发起AI追问"
                    else:
                        ai_request = TicketAiAnalysisRequestModel(
                            versionKey=version_key,
                            agentCode=message_object.agent_code,
                            aiProviderCode=message_object.ai_provider_code,
                            forceRefresh=True,
                            extraInstruction=content,
                        )
                        ai_result = TicketAiAnalysisService.create_analysis_task_services(
                            query_db,
                            ticket_id,
                            ai_request,
                            current_user,
                        )
                        ai_success = bool(ai_result.is_success)
                        ai_message = ai_result.message
                except Exception as exc:
                    ai_message = f"AI追问提交失败: {exc}"
            return CrudResponseModel(
                is_success=True,
                message=(
                    "消息提交成功，AI追问任务已提交"
                    if ai_success
                    else f"消息已保存，但AI追问未发起：{ai_message}"
                    if message_object.run_ai and ai_message
                    else "消息提交成功"
                ),
                result={
                    "message": CamelCaseUtil.transform_result(message),
                    "aiTask": (
                        CamelCaseUtil.transform_result(ai_result.result)
                        if ai_result and ai_result.is_success
                        else None
                    ),
                    "aiTriggered": bool(message_object.run_ai),
                    "aiMessage": ai_message,
                    "aiSuccess": ai_success,
                },
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def create_knowledge_from_ticket(
        cls, query_db: Session, ticket_id: int, current_user: CurrentUserModel | None = None
    ) -> CrudResponseModel:
        """
        从已处理工单自动生成知识库案例文章并刷新工单向量。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        existing_articles = (
            query_db.query(KnowledgeArticle)
            .filter(KnowledgeArticle.del_flag == "0")
            .order_by(KnowledgeArticle.update_time.desc(), KnowledgeArticle.create_time.desc())
            .all()
        )
        for article in existing_articles:
            related_ids = article.related_ticket_ids or []
            if isinstance(related_ids, dict):
                related_ids = related_ids.get("ids") or []
            if ticket_id in related_ids:
                return CrudResponseModel(
                    is_success=True,
                    message="知识库案例已存在",
                    result=CamelCaseUtil.transform_result(article),
                )
        timeline = TicketDao.get_timeline(query_db, ticket_id)
        rca = timeline.get("rca")
        messages = timeline.get("messages") or []
        events = timeline.get("events") or []
        ai_payload = ticket.ai_analysis if isinstance(ticket.ai_analysis, dict) else {}
        ai_case_data: dict[str, Any] = {}
        ai_case_meta: dict[str, Any] = {}
        try:
            ai_case_data, ai_case_meta = TicketLightAiService.generate_ticket_knowledge_case(
                query_db,
                ticket=ticket,
                timeline=timeline,
                current_user_name=_user_name(current_user) if current_user else "system",
            )
        except Exception as exc:
            logger.warning(f"工单[{ticket_id}]知识提炼AI执行失败，已回退规则方案: {exc}")
        investigation_lines = [
            f"- {item.create_time:%Y-%m-%d %H:%M:%S} {item.event_type}: {item.content or ''}"
            for item in events[-20:]
        ]
        message_lines = [
            f"- {item.create_time:%Y-%m-%d %H:%M:%S} [{item.role}/{item.message_type}] {item.content}"
            for item in messages[-20:]
        ]
        origin_description = _extract_ticket_origin_description(ticket.extra_data) or ticket.description or ""
        symptom = (
            ai_case_data.get("symptom")
            or getattr(rca, "symptom", None)
            or origin_description
            or ai_payload.get("analysis_summary")
            or ""
        )
        root_cause = (
            ai_case_data.get("root_cause")
            or getattr(rca, "root_cause_detail", None)
            or ticket.root_cause
            or ai_payload.get("root_cause")
            or ""
        )
        solution = (
            ai_case_data.get("solution")
            or getattr(rca, "fix_solution", None)
            or ticket.solution
            or ai_payload.get("fix_suggestion")
            or ""
        )
        prevention = (
            ai_case_data.get("prevention")
            or getattr(rca, "prevention_solution", None)
            or _join_text_lines(ai_payload.get("next_steps") or [])
        )
        summary = ai_case_data.get("summary") or ai_payload.get("analysis_summary") or ""
        title_suffix = ai_case_data.get("title_suffix") or ""
        article_title = f"{ticket.ticket_no} {ticket.title}".strip()
        if title_suffix:
            article_title = f"{article_title} - {title_suffix}".strip()
        content_sections = [
            f"# {ticket.title}",
        ]
        if summary:
            content_sections.extend(["", "## 提炼摘要", str(summary)])
        content_sections.extend(
            [
                "",
                "## 问题现象",
                str(symptom or "-"),
                "",
                "## 根因",
                str(root_cause or "-"),
                "",
                "## 解决方案",
                str(solution or "-"),
                "",
                "## 排查过程",
                _join_text_lines(investigation_lines, empty="-"),
                "",
                "## 协同消息",
                _join_text_lines(message_lines, empty="-"),
                "",
                "## 验证与预防",
                str(getattr(rca, "verify_method", None) or "-"),
                "",
                str(prevention or "-"),
            ]
        )
        if ai_case_meta.get("status") == "success":
            content_sections.extend(
                [
                    "",
                    "## AI提炼信息",
                    f"Provider：{ai_case_meta.get('provider_code') or '-'}",
                    f"Prompt：{ai_case_meta.get('prompt_code') or '-'}",
                ]
            )
        content = "\n".join(content_sections)
        tags = [
            item
            for item in {
                *(ai_case_data.get("tags") or []),
                ticket.merchant_name,
                ticket.module_name,
                ticket.category_name,
                getattr(rca, "root_cause_category", None) if rca else None,
                "工单案例",
            }
            if item
        ]
        article = TicketDao.add_knowledge(
            query_db,
            KnowledgeArticle(
                title=article_title,
                content=content,
                category=ticket.category_name or "工单案例",
                tags=tags,
                related_ticket_ids=[ticket_id],
                embedding_status="pending",
                created_by_id=_user_id(current_user) if current_user else None,
                created_by_name=_user_name(current_user) if current_user else "system",
                create_time=datetime.now(),
                update_time=datetime.now(),
            ),
        )
        TicketDao.add_event(
            query_db,
            TicketEvent(
                ticket_id=ticket_id,
                event_type=TicketEventType.AI_RECOMMENDED.value,
                operator_id=_user_id(current_user) if current_user else None,
                operator_name=_user_name(current_user) if current_user else "system",
                content="工单关闭后自动生成知识库案例",
                event_data={"article_id": article.article_id},
            ),
        )
        try:
            TicketEmbeddingService.vectorize_ticket_for_scene(query_db, ticket, "closeKnowledge")
        except Exception as exc:
            logger.warning(f"工单[{ticket_id}]向量刷新失败: {exc}")
        return CrudResponseModel(
            is_success=True,
            message="知识库案例生成成功",
            result=CamelCaseUtil.transform_result(article),
        )

    @classmethod
    def upsert_rca(
        cls, query_db: Session, ticket_id: int, rca_object: TicketRcaModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        新增或更新工单 RCA，并同步工单最终根因和解决方案。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param rca_object: RCA 参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        if not TicketDao.get_ticket_by_id(query_db, ticket_id):
            return CrudResponseModel(is_success=False, message="工单不存在")
        try:
            data = _dump_model(rca_object)
            data.pop("id", None)
            data["ticket_id"] = ticket_id
            data["created_by_id"] = data.get("created_by_id") or _user_id(current_user)
            data["created_by_name"] = data.get("created_by_name") or _user_name(current_user)
            rca = TicketDao.upsert_rca(query_db, TicketRca(**data))
            ticket_update: dict[str, Any] = {"update_by": _user_name(current_user), "update_time": datetime.now()}
            if rca.root_cause_detail:
                ticket_update["root_cause"] = rca.root_cause_detail
            if rca.root_cause_category:
                ticket_update["root_cause_type"] = rca.root_cause_category
            if rca.fix_solution:
                ticket_update["solution"] = rca.fix_solution
            TicketDao.update_ticket(query_db, ticket_id, ticket_update)
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.RCA.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content="RCA记录更新",
                    event_data={"rca_id": rca.id, "root_cause_category": rca.root_cause_category},
                ),
            )
            cls.create_snapshot(
                query_db,
                ticket_id,
                TicketSnapshotModel(
                    summary=rca.symptom,
                    root_cause=rca.root_cause_detail,
                    solution=rca.fix_solution,
                    prevention=rca.prevention_solution,
                    structured_data=rca.structured_data,
                ),
                current_user,
                source_type="rca",
                source_id=rca.id,
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="RCA保存成功", result=CamelCaseUtil.transform_result(rca))
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def get_workflow_services(cls, query_db: Session) -> dict:
        """
        获取工单工作流状态和流转配置。
        :param query_db: 数据库会话
        :return: 工作流配置
        """
        transition_rows = []
        for transition in TicketDao.list_workflow_transition(query_db):
            item = CamelCaseUtil.transform_result(transition)
            extension = _parse_transition_extension(transition.allowed_roles)
            item["allowedRoles"] = extension["allowed_roles"]
            item["targetAssigneeId"] = extension["target_assignee_id"]
            item["targetAssigneeName"] = extension["target_assignee_name"]
            item["notifyEnabled"] = extension["notify_enabled"]
            item["notifyRemark"] = extension["notify_remark"]
            transition_rows.append(item)
        return {
            "statuses": CamelCaseUtil.transform_result(TicketDao.list_workflow_status(query_db)),
            "transitions": transition_rows,
        }

    @classmethod
    def save_workflow_status(cls, query_db: Session, status_object: WorkflowStatusModel) -> CrudResponseModel:
        """
        新增或更新工作流状态节点。
        :param query_db: 数据库会话
        :param status_object: 状态节点参数
        :return: 操作结果
        """
        try:
            data = _dump_model(status_object)
            status_id = data.pop("id", None)
            same_code = TicketDao.get_workflow_status_by_code(query_db, status_object.code)
            if same_code and same_code.id != status_id:
                return CrudResponseModel(is_success=False, message="状态编码已存在")
            if status_id:
                if not TicketDao.get_workflow_status_by_id(query_db, status_id):
                    return CrudResponseModel(is_success=False, message="状态节点不存在")
                TicketDao.update_workflow_status(query_db, status_id, data)
                query_db.commit()
                return CrudResponseModel(is_success=True, message="状态节点更新成功")
            status = TicketDao.add_workflow_status(query_db, WorkflowStatus(**data))
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="状态节点新增成功",
                result=CamelCaseUtil.transform_result(status),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def delete_workflow_status(cls, query_db: Session, status_id: int) -> CrudResponseModel:
        """
        删除工作流状态节点，已被工单、历史或流转规则引用时禁止删除。
        :param query_db: 数据库会话
        :param status_id: 状态ID
        :return: 操作结果
        """
        status = TicketDao.get_workflow_status_by_id(query_db, status_id)
        if not status:
            return CrudResponseModel(is_success=False, message="状态节点不存在")
        if TicketDao.count_status_usage(query_db, status.code) > 0:
            return CrudResponseModel(is_success=False, message="状态已被工单、历史或流转规则引用，不能删除")
        try:
            TicketDao.delete_workflow_status(query_db, status_id)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="状态节点删除成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def save_workflow_transition(
        cls,
        query_db: Session,
        transition_object: WorkflowTransitionModel,
    ) -> CrudResponseModel:
        """
        新增或更新工作流流转规则。
        :param query_db: 数据库会话
        :param transition_object: 流转规则参数
        :return: 操作结果
        """
        if transition_object.from_status == transition_object.to_status:
            return CrudResponseModel(is_success=False, message="原状态和目标状态不能相同")
        if not TicketDao.get_workflow_status_by_code(query_db, transition_object.from_status):
            return CrudResponseModel(is_success=False, message="原状态不存在")
        if not TicketDao.get_workflow_status_by_code(query_db, transition_object.to_status):
            return CrudResponseModel(is_success=False, message="目标状态不存在")

        try:
            data = {
                "from_status": transition_object.from_status,
                "to_status": transition_object.to_status,
                "allowed_roles": _build_transition_storage_payload(transition_object),
                "need_comment": transition_object.need_comment,
                "need_resolution": transition_object.need_resolution,
            }
            transition_id = transition_object.id
            same_transition = TicketDao.get_transition(
                query_db, transition_object.from_status, transition_object.to_status
            )
            if same_transition and same_transition.id != transition_id:
                return CrudResponseModel(is_success=False, message="该流转规则已存在")
            if transition_id:
                if not TicketDao.get_workflow_transition_by_id(query_db, transition_id):
                    return CrudResponseModel(is_success=False, message="流转规则不存在")
                TicketDao.update_workflow_transition(query_db, transition_id, data)
                query_db.commit()
                return CrudResponseModel(is_success=True, message="流转规则更新成功")
            transition = TicketDao.add_workflow_transition(query_db, WorkflowTransition(**data))
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="流转规则新增成功",
                result=CamelCaseUtil.transform_result(transition),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def delete_workflow_transition(cls, query_db: Session, transition_id: int) -> CrudResponseModel:
        """
        删除工作流流转规则。
        :param query_db: 数据库会话
        :param transition_id: 流转规则ID
        :return: 操作结果
        """
        if not TicketDao.get_workflow_transition_by_id(query_db, transition_id):
            return CrudResponseModel(is_success=False, message="流转规则不存在")
        try:
            TicketDao.delete_workflow_transition(query_db, transition_id)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="流转规则删除成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def get_user_options_services(cls, query_db: Session, keyword: str | None = None, limit: int = 20) -> list[dict]:
        """
        获取工单指派用户选项。
        :param query_db: 数据库会话
        :param keyword: 用户名、昵称或手机号关键字
        :param limit: 返回数量限制
        :return: 用户选项列表
        """
        safe_limit = min(max(limit or 20, 1), 100)
        users = TicketDao.get_user_options(query_db, keyword, safe_limit)
        return [
            {
                "userId": user.user_id,
                "userName": user.user_name,
                "nickName": user.nick_name,
                "phonenumber": user.phonenumber,
                "label": f"{user.nick_name or user.user_name}（{user.user_name}）",
            }
            for user in users
        ]

    @classmethod
    def get_project_options_services(cls, query_db: Session) -> list[dict[str, Any]]:
        """
        获取工单可选测试项目列表。
        :param query_db: 数据库会话
        :return: 项目选项列表
        """
        projects = (
            query_db.query(HrmProject)
            .filter(
                HrmProject.status == QtrDataStatusEnum.normal.value,
                HrmProject.del_flag == "0",
            )
            .order_by(HrmProject.order_num.asc(), HrmProject.create_time.desc())
            .all()
        )
        return [
            {
                "projectId": project.project_id,
                "projectName": project.project_name,
                "label": project.project_name,
            }
            for project in projects
        ]

    @classmethod
    def get_module_options_services(cls, query_db: Session, project_id: int | None = None) -> list[dict[str, Any]]:
        """
        获取工单可选测试模块列表。
        :param query_db: 数据库会话
        :param project_id: 目标项目ID；为空时返回空列表
        :return: 模块选项列表
        """
        if not project_id:
            return []
        query = query_db.query(HrmModule).filter(HrmModule.status == QtrDataStatusEnum.normal.value)
        query = query.filter(HrmModule.project_id == project_id)
        modules = query.order_by(HrmModule.sort.asc(), HrmModule.create_time.desc()).all()
        seen_module_ids: set[int] = set()
        unique_modules = []
        for module in modules:
            if module.module_id in seen_module_ids:
                continue
            seen_module_ids.add(module.module_id)
            unique_modules.append(module)
        return [
            {
                "moduleId": module.module_id,
                "moduleName": module.module_name,
                "projectId": module.project_id,
                "label": module.module_name,
            }
            for module in unique_modules
        ]

    @classmethod
    def create_knowledge(
        cls, query_db: Session, article_object: KnowledgeArticleModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        创建知识库文章。
        :param query_db: 数据库会话
        :param article_object: 文章参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        try:
            data = _dump_model(article_object)
            data.pop("article_id", None)
            data["created_by_id"] = data.get("created_by_id") or _user_id(current_user)
            data["created_by_name"] = data.get("created_by_name") or _user_name(current_user)
            article = TicketDao.add_knowledge(query_db, KnowledgeArticle(**data))
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="新增成功",
                result=CamelCaseUtil.transform_result(article),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def get_knowledge_list_services(cls, query_db: Session, query: KnowledgeArticleQueryModel):
        """
        获取知识库文章列表。
        :param query_db: 数据库会话
        :param query: 查询参数
        :return: 分页结果或列表
        """
        return TicketDao.get_knowledge_list(query_db, query)

    @classmethod
    def get_knowledge_detail_services(cls, query_db: Session, article_id: int) -> dict | None:
        """
        获取知识库文章详情。
        :param query_db: 数据库会话
        :param article_id: 文章ID
        :return: 文章详情
        """
        article = TicketDao.get_knowledge(query_db, article_id)
        return CamelCaseUtil.transform_result(article) if article else None

    @classmethod
    def update_knowledge(
        cls, query_db: Session, article_object: KnowledgeArticleModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        更新知识库文章。
        :param query_db: 数据库会话
        :param article_object: 文章参数
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        if not article_object.article_id or not TicketDao.get_knowledge(query_db, article_object.article_id):
            return CrudResponseModel(is_success=False, message="知识库文章不存在")
        try:
            data = _dump_model(article_object)
            data.pop("article_id", None)
            data["update_time"] = datetime.now()
            TicketDao.update_knowledge(query_db, article_object.article_id, data)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="更新成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def delete_knowledge(
        cls, query_db: Session, article_id: int, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """
        软删除知识库文章。
        :param query_db: 数据库会话
        :param article_id: 文章ID
        :param current_user: 当前登录用户
        :return: 操作结果
        """
        if not TicketDao.get_knowledge(query_db, article_id):
            return CrudResponseModel(is_success=False, message="知识库文章不存在")
        try:
            TicketDao.update_knowledge(
                query_db,
                article_id,
                {
                    "del_flag": "2",
                    "created_by_name": _user_name(current_user),
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def get_statistics_services(
        cls,
        query_db: Session,
        begin_time=None,
        end_time=None,
        project_ids: Any = None,
        module_ids: Any = None,
    ) -> dict:
        """
        获取工单实时统计数据。
        :param query_db: 数据库会话
        :param begin_time: 开始时间
        :param end_time: 结束时间
        :param project_ids: 项目ID多选过滤
        :param module_ids: 模块ID多选过滤
        :return: 统计结果
        """
        statistics = TicketDao.get_ticket_statistics(
            query_db,
            _date_start(begin_time),
            _date_end(end_time),
            _normalize_int_list(project_ids),
            _normalize_int_list(module_ids),
        )
        return _camelize(statistics)
