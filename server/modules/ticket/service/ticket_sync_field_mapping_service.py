"""
工单字段映射与人员解析服务：外部字段到内部字段的映射匹配、项目/模块/供应商/门店/状态解析、人员分配识别。
从 TicketSyncService 中提取。
"""
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from module_admin.entity.do.user_do import SysUser
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullProjectVendorMap, TicketLogPullStoreConfig
from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.enums.ticket_enums import TicketStatus
from modules.ticket.util.sync_util import SyncUtil


class TicketSyncFieldMappingService:
    """工单外部字段映射与人员解析。"""

    @classmethod
    def _extract_external_mapping_fields(cls, sync_object: TicketExternalSyncUpsertModel) -> dict[str, str]:
        """
        提取外部同步字段映射上下文。
        :param sync_object: 外部同步模型
        :return: 字段映射字典
        """
        raw_payload = sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {}
        extra_data = sync_object.extra_data if isinstance(sync_object.extra_data, dict) else {}
        mapping_payload = (
            extra_data.get("external_field_mapping")
            if isinstance(extra_data.get("external_field_mapping"), dict)
            else {}
        )
        ticket_vender = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "ticketVender",
                "ticket_vender",
                default=SyncUtil.payload_field_value(mapping_payload, "ticketVender", "ticket_vender", default=""),
            )
            or ""
        ).strip()
        ticket_modle = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "ticketModle",
                "ticket_modle",
                default=SyncUtil.payload_field_value(mapping_payload, "ticketModle", "ticket_modle", default=""),
            )
            or ""
        ).strip()
        ticket_status = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "ticketStatus",
                "ticket_status",
                default=SyncUtil.payload_field_value(raw_payload, "status", "status", default=""),
            )
            or ""
        ).strip()
        ticket_store = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "ticketStore",
                "ticket_store",
                default=SyncUtil.payload_field_value(
                    raw_payload,
                    "storeInfo",
                    "store_info",
                    default=SyncUtil.payload_field_value(
                        raw_payload,
                        "storeId",
                        "store_id",
                        default=SyncUtil.payload_field_value(mapping_payload, "ticketStore", "ticket_store", default=""),
                    ),
                ),
            )
            or ""
        ).strip()
        ticket_assignee = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "ticketAssignee",
                "ticket_assignee",
                default=SyncUtil.payload_field_value(
                    raw_payload,
                    "currentAssigneeName",
                    "current_assignee_name",
                    default="",
                ),
            )
            or ""
        ).strip()
        current_assignee = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "currentAssigneeName",
                "current_assignee_name",
                default=SyncUtil.payload_field_value(
                    mapping_payload,
                    "currentAssigneeName",
                    "current_assignee_name",
                    default=ticket_assignee,
                ),
            )
            or ""
        ).strip()
        ticket_assignee_email = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "ticketAssigneeEmail",
                "ticket_assignee_email",
                default=SyncUtil.payload_field_value(
                    raw_payload,
                    "currentAssigneeEmail",
                    "current_assignee_email",
                    default=SyncUtil.payload_field_value(
                        raw_payload,
                        "assigneeEmail",
                        "assignee_email",
                        default=SyncUtil.payload_field_value(
                            mapping_payload,
                            "ticketAssigneeEmail",
                            "ticket_assignee_email",
                            default="",
                        ),
                    ),
                ),
            )
            or ""
        ).strip()
        current_assignee_email = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "currentAssigneeEmail",
                "current_assignee_email",
                default=SyncUtil.payload_field_value(
                    mapping_payload,
                    "currentAssigneeEmail",
                    "current_assignee_email",
                    default=ticket_assignee_email,
                ),
            )
            or ""
        ).strip()
        reporter_email = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "reporterEmail",
                "reporter_email",
                default=SyncUtil.payload_field_value(
                    mapping_payload,
                    "reporterEmail",
                    "reporter_email",
                    default="",
                ),
            )
            or ""
        ).strip()
        internal_owner = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "internalOwner",
                "internal_owner",
                default=SyncUtil.payload_field_value(
                    raw_payload,
                    "internalOwnerName",
                    "internal_owner_name",
                    default=SyncUtil.payload_field_value(
                        mapping_payload,
                        "internalOwner",
                        "internal_owner",
                        default=SyncUtil.payload_field_value(
                            mapping_payload,
                            "internalOwnerName",
                            "internal_owner_name",
                            default="",
                        ),
                    ),
                ),
            )
            or ""
        ).strip()
        internal_owner_email = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "internalOwnerEmail",
                "internal_owner_email",
                default=SyncUtil.payload_field_value(
                    mapping_payload,
                    "internalOwnerEmail",
                    "internal_owner_email",
                    default="",
                ),
            )
            or ""
        ).strip()
        ticket_pos = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "ticketPos",
                "ticket_pos",
                default=SyncUtil.payload_field_value(
                    raw_payload,
                    "posNo",
                    "pos_no",
                    default=SyncUtil.payload_field_value(
                        raw_payload,
                        "posId",
                        "pos_id",
                        default=SyncUtil.payload_field_value(mapping_payload, "ticketPos", "ticket_pos", default=""),
                    ),
                ),
            )
            or ""
        ).strip()
        ticket_sco = str(
            SyncUtil.payload_field_value(
                raw_payload,
                "ticketSco",
                "ticket_sco",
                default=SyncUtil.payload_field_value(
                    raw_payload,
                    "scoNo",
                    "sco_no",
                    default=SyncUtil.payload_field_value(
                        raw_payload,
                        "scoId",
                        "sco_id",
                        default=SyncUtil.payload_field_value(mapping_payload, "ticketSco", "ticket_sco", default=""),
                    ),
                ),
            )
            or ""
        ).strip()
        return {
            "ticketVender": ticket_vender,
            "ticketModle": ticket_modle,
            "ticketStatus": ticket_status,
            "ticketStore": ticket_store,
            "ticketAssignee": ticket_assignee,
            "ticketAssigneeEmail": ticket_assignee_email,
            "currentAssigneeName": current_assignee,
            "currentAssigneeEmail": current_assignee_email,
            "reporterEmail": reporter_email,
            "internalOwner": internal_owner,
            "internalOwnerEmail": internal_owner_email,
            "ticketPos": ticket_pos,
            "ticketSco": ticket_sco,
        }

    @classmethod
    def _has_incoming_project_value(
        cls,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any] | None,
    ) -> bool:
        """
        判断本次同步是否携带项目归属字段，用于决定更新场景是否允许覆盖旧项目。
        :param sync_object: 外部同步模型
        :param detected: 字段识别结果
        :return: 本次同步存在项目ID或项目文本时返回 True
        """
        external_fields = cls._extract_external_mapping_fields(sync_object)
        return any(
            str(value or "").strip()
            for value in (
                (detected or {}).get("projectId"),
                (detected or {}).get("projectName"),
                getattr(sync_object, "project_id", None),
                getattr(sync_object, "project_code", None),
                getattr(sync_object, "project_name", None),
                getattr(sync_object, "merchant_name", None),
                external_fields.get("ticketVender"),
            )
        )

    @classmethod
    def _has_incoming_module_value(
        cls,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any] | None,
    ) -> bool:
        """
        判断本次同步是否携带模块归属字段，用于决定更新场景是否允许覆盖旧模块。
        :param sync_object: 外部同步模型
        :param detected: 字段识别结果
        :return: 本次同步存在模块ID或模块文本时返回 True
        """
        external_fields = cls._extract_external_mapping_fields(sync_object)
        return any(
            str(value or "").strip()
            for value in (
                (detected or {}).get("moduleId"),
                (detected or {}).get("moduleName"),
                getattr(sync_object, "module_id", None),
                getattr(sync_object, "module_code", None),
                getattr(sync_object, "module_name", None),
                external_fields.get("ticketModle"),
            )
        )

    @classmethod
    def _match_mapping_exact(cls, field_value: str, mappings: Any) -> dict[str, Any] | None:
        """
        按完整关键字做精确映射，不进行模糊猜测。
        :param field_value: 外部字段值
        :param mappings: 映射配置列表
        :return: 命中的映射对象
        """
        target = str(field_value or "").strip().lower()
        if not target or not isinstance(mappings, list):
            return None
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            keywords = cls._mapping_keywords(mapping)
            if target in keywords:
                return mapping
        return None

    @classmethod
    def _match_mapping_contains(cls, field_value: str, mappings: Any) -> dict[str, Any] | None:
        """
        按关键字“包含关系”匹配映射配置（外部字段包含任意关键词即命中）。
        :param field_value: 外部字段值
        :param mappings: 映射配置列表
        :return: 命中的映射对象
        """
        target = str(field_value or "").strip().lower()
        if not target or not isinstance(mappings, list):
            return None
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            keywords = cls._mapping_keywords(mapping)
            if any(keyword and keyword in target for keyword in keywords):
                return mapping
        return None

    @classmethod
    def _resolve_project_by_ticket_vender(
        cls,
        db: Session,
        *,
        ticket_vender: str,
        project_mappings: list[dict[str, Any]],
    ) -> tuple[HrmProject | None, str]:
        """
        按 ticketVender 匹配所属项目与项目名称。
        :param db: 数据库会话
        :param ticket_vender: 外部商家文本
        :param project_mappings: 项目映射配置
        :return: (项目对象, 项目名称)
        """
        vendor_text = str(ticket_vender or "").strip()
        if not vendor_text:
            return None, ""
        matched_mapping = cls._match_mapping_contains(vendor_text, project_mappings)
        if isinstance(matched_mapping, dict):
            project_id = SyncUtil.safe_int(
                matched_mapping.get("projectId")
                or matched_mapping.get("project_id")
                or matched_mapping.get("id")
            )
            project_code = str(
                matched_mapping.get("projectCode")
                or matched_mapping.get("project_code")
                or ""
            ).strip()
            project_name = str(
                matched_mapping.get("projectName")
                or matched_mapping.get("project_name")
                or ""
            ).strip()
            query = db.query(HrmProject).filter(
                HrmProject.status == QtrDataStatusEnum.normal.value,
                HrmProject.del_flag == "0",
            )
            if project_id:
                project = query.filter(HrmProject.project_id == project_id).first()
                if project:
                    return project, str(project.project_name or "").strip()
            if project_code:
                project = query.filter(HrmProject.project_code == project_code).first()
                if project:
                    return project, str(project.project_name or "").strip()
            if project_name:
                project = query.filter(func.lower(HrmProject.project_name) == project_name.lower()).first()
                if project:
                    return project, str(project.project_name or "").strip()
                return None, project_name

        # 向后兼容：若商户编号本身可直接匹配项目商家映射表，则仍可命中项目。
        project_vendor_row = (
            db.query(TicketLogPullProjectVendorMap)
            .filter(TicketLogPullProjectVendorMap.vender_no == vendor_text)
            .order_by(TicketLogPullProjectVendorMap.modifid.desc(), TicketLogPullProjectVendorMap.id.desc())
            .first()
        )
        if not project_vendor_row:
            return None, ""
        project = (
            db.query(HrmProject)
            .filter(
                HrmProject.project_id == project_vendor_row.project_id,
                HrmProject.status == QtrDataStatusEnum.normal.value,
                HrmProject.del_flag == "0",
            )
            .first()
        )
        if project:
            return project, str(project.project_name or "").strip()
        return None, str(project_vendor_row.project_name or "").strip()

    @classmethod
    def _resolve_module_by_ticket_modle(
        cls,
        db: Session,
        *,
        ticket_modle: str,
        project_id: int | None,
        module_mappings: list[dict[str, Any]],
    ) -> HrmModule | None:
        """
        按 ticketModle 匹配所属模块。
        :param db: 数据库会话
        :param ticket_modle: 外部模块字段
        :param project_id: 已匹配项目ID
        :param module_mappings: 模块映射配置
        :return: 模块对象
        """
        module_text = str(ticket_modle or "").strip()
        if not module_text:
            return None
        matched_mapping = cls._match_mapping_contains(module_text, module_mappings)
        module_id = SyncUtil.safe_int((matched_mapping or {}).get("moduleId") or (matched_mapping or {}).get("module_id"))
        module_code = str(
            (matched_mapping or {}).get("moduleCode")
            or (matched_mapping or {}).get("module_code")
            or ""
        ).strip()
        module_name = str(
            (matched_mapping or {}).get("moduleName")
            or (matched_mapping or {}).get("module_name")
            or ""
        ).strip()
        query = db.query(HrmModule).filter(HrmModule.status == QtrDataStatusEnum.normal.value)
        if project_id:
            query = query.filter(HrmModule.project_id == project_id)
        if module_id:
            module = query.filter(HrmModule.module_id == module_id).first()
            if module:
                return module
        if module_code:
            module = query.filter(func.lower(HrmModule.module_code) == module_code.lower()).first()
            if module:
                return module
        if module_name:
            module = query.filter(func.lower(HrmModule.module_name) == module_name.lower()).first()
            if module:
                return module
        module = query.filter(func.lower(HrmModule.module_code) == module_text.lower()).first()
        if module:
            return module
        return query.filter(func.lower(HrmModule.module_name) == module_text.lower()).first()

    @classmethod
    def _resolve_status_by_external_value(
        cls,
        *,
        status_text: str,
        status_mappings: list[dict[str, Any]],
    ) -> str:
        """
        按显式外部状态字段匹配本地状态，不做模糊猜测。
        :param status_text: 外部状态值
        :param status_mappings: 状态映射配置
        :return: 本地状态编码或原始状态值
        """
        source_status = str(status_text or "").strip()
        if not source_status:
            return ""
        status_map = {
            "pending": TicketStatus.PENDING.value,
            "processing": TicketStatus.PROCESSING.value,
            "wait_user": TicketStatus.WAIT_USER.value,
            "wait_dev": TicketStatus.WAIT_DEV.value,
            "wait_release": TicketStatus.WAIT_RELEASE.value,
            "wait_verify": TicketStatus.WAIT_VERIFY.value,
            "resolved": TicketStatus.RESOLVED.value,
            "closed": TicketStatus.CLOSED.value,
            "rejected": TicketStatus.REJECTED.value,
            "non_problem": TicketStatus.NON_PROBLEM.value,
            "design_as_expected": TicketStatus.DESIGN_AS_EXPECTED.value,
            "user_misoperation": TicketStatus.USER_MISOPERATION.value,
            "duplicated": TicketStatus.DUPLICATED.value,
        }
        matched_mapping = cls._match_mapping_exact(source_status, status_mappings)
        status_candidate = source_status
        if isinstance(matched_mapping, dict):
            status_candidate = str(
                matched_mapping.get("status")
                or matched_mapping.get("ticketStatus")
                or matched_mapping.get("statusCode")
                or matched_mapping.get("value")
                or source_status
            ).strip()
        return status_map.get(status_candidate.lower(), status_candidate)

    @classmethod
    def _resolve_vendor_by_ticket_vender(
        cls,
        *,
        ticket_vender: str,
        vendor_mappings: list[dict[str, Any]],
    ) -> tuple[int | None, str]:
        """
        按 ticketVender 解析日志拉取商家信息。
        :param ticket_vender: 外部商家文本
        :param vendor_mappings: 商家映射配置
        :return: (vendor_id, vendor_name)
        """
        vendor_text = str(ticket_vender or "").strip()
        if not vendor_text:
            return None, ""
        matched_mapping = cls._match_mapping_contains(vendor_text, vendor_mappings)
        if isinstance(matched_mapping, dict):
            vendor_id = SyncUtil.safe_int(
                matched_mapping.get("vendorId")
                or matched_mapping.get("vendor_id")
                or matched_mapping.get("id")
            )
            vendor_name = str(matched_mapping.get("vendorName") or matched_mapping.get("vendor_name") or "").strip()
            if vendor_id:
                return vendor_id, vendor_name or vendor_text
        return None, vendor_text

    @classmethod
    def _resolve_vendor_by_project(cls, db: Session, *, project_id: int | None) -> int | None:
        """
        按项目映射配置回退解析商家ID。
        :param db: 数据库会话
        :param project_id: 项目ID
        :return: 商家ID，未命中返回 None
        """
        if not project_id:
            return None
        row = (
            db.query(TicketLogPullProjectVendorMap)
            .filter(TicketLogPullProjectVendorMap.project_id == project_id)
            .order_by(TicketLogPullProjectVendorMap.modifid.desc(), TicketLogPullProjectVendorMap.id.desc())
            .first()
        )
        if not row:
            return None
        return SyncUtil.safe_int(getattr(row, "vender_no", None))

    @classmethod
    def _resolve_store_by_external_value(
        cls,
        db: Session,
        *,
        vendor_id: int | None,
        ticket_store: str,
    ) -> tuple[str, str]:
        """
        按商家ID + 外部门店字段（sap_org_no）匹配门店配置。
        :param db: 数据库会话
        :param vendor_id: 已匹配商家ID
        :param ticket_store: 外部门店字段
        :return: (store_id, store_name)
        """
        store_text = str(ticket_store or "").strip()
        if not store_text:
            return "", ""
        if not vendor_id:
            return store_text, ""

        query = db.query(TicketLogPullStoreConfig).filter(TicketLogPullStoreConfig.sap_org_no == store_text)
        query = query.filter(TicketLogPullStoreConfig.vender_no == str(vendor_id))
        row = query.order_by(TicketLogPullStoreConfig.modifid.desc(), TicketLogPullStoreConfig.id.desc()).first()
        if not row:
            return store_text, ""
        resolved_store_id = str(row.org_no or row.sap_org_no or "").strip() or store_text
        return resolved_store_id, str(row.org_name or "").strip()

    @classmethod
    def _match_assignee_mapping_exact(cls, assignee_text: str, assignee_mappings: Any) -> dict[str, Any] | None:
        """
        按人员名称做完整匹配（不支持模糊包含）。
        :param assignee_text: 外部处理人文本
        :param assignee_mappings: 处理人映射配置
        :return: 命中的映射对象
        """
        target = str(assignee_text or "").strip().lower()
        if not target or not isinstance(assignee_mappings, list):
            return None
        for mapping in assignee_mappings:
            if not isinstance(mapping, dict):
                continue
            candidates = cls._mapping_keywords(mapping)
            candidates.extend(
                SyncUtil.normalize_keywords(
                    [
                        mapping.get("userName"),
                        mapping.get("user_name"),
                        mapping.get("name"),
                        mapping.get("email"),
                    ]
                )
            )
            if any(target == candidate for candidate in candidates if candidate):
                return mapping
        return None

    @classmethod
    def _resolve_assignee_by_external_value(
        cls,
        db: Session,
        *,
        assignee_text: str,
        assignee_mappings: list[dict[str, Any]],
    ) -> tuple[int | None, str]:
        """
        按显式处理人字段匹配本地用户，不做包含式猜测。
        :param db: 数据库会话
        :param assignee_text: 外部处理人字段
        :param assignee_mappings: 处理人映射配置
        :return: (处理人ID, 处理人名称)
        """
        from module_admin.entity.do.user_do import SysUser

        source_text = str(assignee_text or "").strip()
        matched_mapping = cls._match_assignee_mapping_exact(source_text, assignee_mappings)
        mapped_user_id = SyncUtil.safe_int(
            (matched_mapping or {}).get("userId")
            or (matched_mapping or {}).get("user_id")
            or (matched_mapping or {}).get("assigneeId")
        )
        mapped_email = str((matched_mapping or {}).get("email") or "").strip()
        mapped_user_name = str(
            (matched_mapping or {}).get("userName")
            or (matched_mapping or {}).get("user_name")
            or (matched_mapping or {}).get("name")
            or source_text
        ).strip()
        if mapped_user_id:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.user_id == mapped_user_id,
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name
        if mapped_email:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    func.lower(SysUser.email) == mapped_email.lower(),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name
        if mapped_user_name:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    (SysUser.user_name == mapped_user_name) | (SysUser.nick_name == mapped_user_name),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name
        if source_text:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    (
                        (SysUser.user_name == source_text)
                        | (SysUser.nick_name == source_text)
                        | (func.lower(SysUser.email) == source_text.lower())
                    ),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or source_text
        return None, mapped_user_name or source_text

    @classmethod
    def _resolve_sys_user_by_email(cls, db: Session, email: str):
        """
        根据邮箱匹配本地系统用户。
        :param db: 数据库会话
        :param email: 邮箱地址
        :return: 系统用户对象或 None
        """
        from module_admin.entity.do.user_do import SysUser

        normalized_email = str(email or "").strip().lower()
        if not normalized_email:
            return None
        return (
            db.query(SysUser)
            .filter(
                SysUser.status == "0",
                SysUser.del_flag == "0",
                func.lower(SysUser.email) == normalized_email,
            )
            .first()
        )

    @classmethod
    def _resolve_external_person_by_mapping_or_email(
        cls,
        db: Session,
        *,
        person_text: str,
        person_email: str,
        assignee_mappings: list[dict[str, Any]],
    ) -> tuple[int | None, str]:
        """
        外部推送人员先按显式映射表解析，再用多维表格邮箱匹配本地用户；失败时只保留名称。
        :param db: 数据库会话
        :param person_text: 外部人员名称
        :param person_email: 多维表格或入参补充邮箱
        :param assignee_mappings: 人员映射配置
        :return: (本地用户ID, 人员名称)
        """
        from module_admin.entity.do.user_do import SysUser

        source_text = str(person_text or "").strip()
        matched_mapping = cls._match_assignee_mapping_exact(source_text, assignee_mappings)
        mapped_user_id = SyncUtil.safe_int(
            (matched_mapping or {}).get("userId")
            or (matched_mapping or {}).get("user_id")
            or (matched_mapping or {}).get("assigneeId")
        )
        mapped_email = str((matched_mapping or {}).get("email") or "").strip()
        mapped_user_name = str(
            (matched_mapping or {}).get("userName")
            or (matched_mapping or {}).get("user_name")
            or (matched_mapping or {}).get("name")
            or source_text
        ).strip()

        if mapped_user_id:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.user_id == mapped_user_id,
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name

        lookup_email = mapped_email or str(person_email or "").strip()
        if lookup_email:
            user = cls._resolve_sys_user_by_email(db, lookup_email)
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name

        if matched_mapping and mapped_user_name:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    (SysUser.user_name == mapped_user_name) | (SysUser.nick_name == mapped_user_name),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name

        return None, mapped_user_name or source_text

    @classmethod
    def _resolve_remote_assignee_by_email_or_name(
        cls,
        db: Session,
        *,
        assignee_email: str,
        assignee_name: str,
    ) -> tuple[int | None, str]:
        """
        远端拉取人员只按邮箱或名称关联本地用户，禁止使用跨环境用户 ID。
        :param db: 数据库会话
        :param assignee_email: 远端处理人邮箱
        :param assignee_name: 远端处理人名称
        :return: (本地用户ID, 处理人名称)，未命中时只返回名称不返回ID
        """
        from module_admin.entity.do.user_do import SysUser

        normalized_email = str(assignee_email or "").strip().lower()
        normalized_name = str(assignee_name or "").strip()
        if normalized_email:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    func.lower(SysUser.email) == normalized_email,
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or normalized_name
        if normalized_name:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    (
                        (SysUser.user_name == normalized_name)
                        | (SysUser.nick_name == normalized_name)
                        | (func.lower(SysUser.email) == normalized_name.lower())
                    ),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or normalized_name
        return None, normalized_name or normalized_email

    @classmethod
    def _mapping_keywords(cls, mapping: dict[str, Any]) -> list[str]:
        keywords = SyncUtil.normalize_keywords(mapping.get("keywords") or mapping.get("aliases"))
        if mapping.get("matchText"):
            keywords.extend(SyncUtil.normalize_keywords([mapping.get("matchText")]))
        return [keyword for keyword in keywords if keyword]
