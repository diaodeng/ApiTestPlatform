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
    TicketRca,
    TicketStatusHistory,
    WorkflowStatus,
    WorkflowTransition,
)
from modules.ticket.entity.vo.ticket_vo import (
    KnowledgeArticleModel,
    KnowledgeArticleQueryModel,
    TicketAssignModel,
    TicketCommentCreateModel,
    TicketCreateModel,
    TicketEventCreateModel,
    TicketQueryModel,
    TicketRcaModel,
    TicketStatusChangeModel,
    TicketUpdateModel,
    WorkflowStatusModel,
    WorkflowTransitionModel,
)
from modules.ticket.enums.ticket_enums import TicketEventType, TicketStatus
from modules.ticket.service.ticket_log_pull_service import TicketLogPullService
from utils.common_util import CamelCaseUtil
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


def _ticket_no() -> str:
    """
    生成工单编号。
    :return: 工单编号
    """
    return f"TK{datetime.now().strftime('%Y%m%d')}{snowIdWorker.get_id()}"


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
            "module_name": "",
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
            is_valid, message, relation_fields = cls._resolve_ticket_relation_fields(query_db, data)
            if not is_valid:
                return CrudResponseModel(is_success=False, message=message)
            data.update(relation_fields)
            data["ticket_no"] = data.get("ticket_no") or _ticket_no()
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
                    event_data={"ticket_no": ticket.ticket_no, "status": ticket.status},
                    create_time=now,
                ),
            )
            query_db.commit()
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
            for item in rows:
                if isinstance(item, dict):
                    cls._decorate_ticket_item(item)
                    item["latestLogPull"] = summary_map.get(item.get("ticketId"))
            return result
        ticket_ids = [item.get("ticketId") for item in result if isinstance(item, dict) and item.get("ticketId")]
        summary_map = TicketLogPullService.get_latest_summary_map(query_db, ticket_ids)
        for item in result:
            if isinstance(item, dict):
                cls._decorate_ticket_item(item)
                item["latestLogPull"] = summary_map.get(item.get("ticketId"))
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
        result["latestLogPull"] = TicketLogPullService.get_latest_summary(query_db, ticket_id)
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
            data.pop("ticket_no", None)
            data.pop("project_name", None)
            is_valid, message, relation_fields = cls._resolve_ticket_relation_fields(query_db, data)
            if not is_valid:
                return CrudResponseModel(is_success=False, message=message)
            data.update(relation_fields)
            data["update_by"] = _user_name(current_user)
            data["update_time"] = datetime.now()
            TicketDao.update_ticket(query_db, ticket.ticket_id, data)
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
                        "target_assignee_id": transition_extension.get("target_assignee_id"),
                        "target_assignee_name": transition_extension.get("target_assignee_name"),
                        "notify_enabled": transition_extension.get("notify_enabled"),
                        "notify_remark": transition_extension.get("notify_remark"),
                    },
                    create_time=now,
                ),
            )
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
                ),
            )
            TicketDao.add_event(
                query_db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.COMMENTED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=comment_object.content,
                    event_data={"comment_id": comment.id, "is_internal": comment_object.is_internal},
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
        timeline = TicketDao.get_timeline(query_db, ticket_id)
        return {key: CamelCaseUtil.transform_result(value) for key, value in timeline.items()}

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
        :param project_id: 目标项目ID；为空时返回全部有效模块
        :return: 模块选项列表
        """
        query = query_db.query(HrmModule).filter(HrmModule.status == QtrDataStatusEnum.normal.value)
        if project_id:
            query = query.filter(HrmModule.project_id == project_id)
        modules = query.order_by(HrmModule.sort.asc(), HrmModule.create_time.desc()).all()
        return [
            {
                "moduleId": module.module_id,
                "moduleName": module.module_name,
                "projectId": module.project_id,
                "label": module.module_name,
            }
            for module in modules
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
    def get_statistics_services(cls, query_db: Session, begin_time=None, end_time=None) -> dict:
        """
        获取工单实时统计数据。
        :param query_db: 数据库会话
        :param begin_time: 开始时间
        :param end_time: 结束时间
        :return: 统计结果
        """
        statistics = TicketDao.get_ticket_statistics(query_db, _date_start(begin_time), _date_end(end_time))
        return _camelize(statistics)
