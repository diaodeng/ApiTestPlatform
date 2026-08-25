"""
指定工单手动执行同步自动化服务。

该服务将手动入口限制在既有 ``bitable_pull`` 场景内，复用已配置的 AI 字段提取、
自动识别、日志拉取、AI 分析、向量化与通知能力，不改变定时主动拉取任务的行为。
"""
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import (
    TicketExternalSyncUpsertModel,
    TicketManualAutomationRunModel,
)
from modules.ticket.service.sync.ticket_bitable_pull_service import TicketBitablePullService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_post_process_service import TicketSyncPostProcessService
from modules.ticket.service.sync.ticket_sync_service import TicketSyncService
from utils.log_util import logger


class TicketManualAutomationService:
    """
    指定工单号手动重放多维表格主动拉取后的自动化服务。
    """

    BITABLE_SYNC_SCENE = "bitable_pull"
    DATABASE_SOURCE_SYSTEM = "manual_database_replay"
    MANUAL_BITABLE_PAGE_SIZE = 50

    @classmethod
    def run_services(
        cls,
        db: Session,
        query_object: TicketManualAutomationRunModel,
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        """
        按数据来源执行指定工单的自动化流程。

        :param db: 数据库会话。
        :param query_object: 已校验的工单号和数据来源。
        :param current_user: 当前操作用户。
        :return: 执行摘要，不返回数据库大整数主键。
        """
        logger.info(
            f"开始手动工单自动化: ticket_no={query_object.ticket_no}, source={query_object.source}"
        )
        if query_object.source == "database":
            return cls.run_database_replay(db, query_object.ticket_no, current_user)
        return cls.run_bitable_replay(db, query_object.ticket_no, current_user)

    @classmethod
    def run_bitable_replay(
        cls,
        db: Session,
        ticket_no: str,
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        """
        只按工单号查询飞书多维表格，入库后立即执行既有后处理自动化。

        本方法刻意忽略主动拉取开关、常规过滤条件和时间窗口，避免手动补跑被定时任务配置拦截。

        :param db: 数据库会话。
        :param ticket_no: 精确工单号。
        :param current_user: 当前操作用户。
        :return: 执行结果摘要。
        """
        config, pull_config = cls.build_manual_bitable_config(db)
        ticket_no_field = cls.resolve_ticket_no_field(pull_config)
        filter_formula = cls.build_ticket_no_filter(ticket_no_field, ticket_no)
        pull_config["filterFormula"] = filter_formula
        pull_config["pageSize"] = min(
            max(int(pull_config.get("pageSize") or cls.MANUAL_BITABLE_PAGE_SIZE), 1),
            cls.MANUAL_BITABLE_PAGE_SIZE,
        )
        # 手动模式不复用常规主动拉取的时间窗口，确保历史指定工单也能补跑。
        pull_config["createdAfter"] = ""
        pull_config["createdBefore"] = ""
        pull_config["autoAppendTimeFilter"] = False

        required_fields = TicketSyncConfigService.derive_required_fields_from_external_field_model(
            config.get("externalFieldModel")
        )
        matches: list[TicketExternalSyncUpsertModel] = []
        queried_record_count = 0
        for record in TicketSyncConfigService.iter_bitable_pull_records(pull_config, [filter_formula]):
            queried_record_count += 1
            sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
                record=record,
                config=pull_config,
                field_mappings=pull_config["fieldMappings"],
                required_fields=required_fields,
            )
            if not sync_object or sync_object.ticket_no != ticket_no:
                continue
            matches.append(sync_object)
            if len(matches) > 1:
                break

        if not matches:
            raise ValueError(f"多维表格中未找到工单号为 {ticket_no} 的有效记录")
        if len(matches) > 1:
            raise ValueError(f"多维表格中找到多条工单号为 {ticket_no} 的记录，请先处理重复数据")

        sync_object = matches[0]
        sync_result = TicketSyncService.sync_external_ticket(
            db,
            sync_object,
            current_user,
            cls.BITABLE_SYNC_SCENE,
            True,
        )
        if not sync_result.is_success:
            raise ValueError(str(sync_result.message or "工单同步失败"))

        TicketSyncPostProcessService.execute_deferred_sync_post_process(
            db,
            sync_object,
            current_user,
            cls.BITABLE_SYNC_SCENE,
        )
        logger.info(
            f"手动多维表格工单自动化完成: ticket_no={ticket_no}, "
            f"record_id={sync_object.source.record_id or '-'}, queried_records={queried_record_count}"
        )
        return {
            "ticketNo": ticket_no,
            "source": "bitable",
            "recordId": sync_object.source.record_id or "",
            "queriedRecordCount": queried_record_count,
            "synced": True,
            "postProcessExecuted": True,
        }

    @classmethod
    def run_database_replay(
        cls,
        db: Session,
        ticket_no: str,
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        """
        基于本地 ORM 工单快照重放后处理自动化，不再覆盖外部同步字段。

        :param db: 数据库会话。
        :param ticket_no: 精确工单号。
        :param current_user: 当前操作用户。
        :return: 执行结果摘要。
        """
        ticket = TicketDao.get_ticket_by_no(db, ticket_no)
        if not ticket:
            raise ValueError(f"数据库中未找到工单号为 {ticket_no} 的工单")

        sync_object = cls.build_database_replay_sync_object(ticket)
        TicketSyncPostProcessService.execute_deferred_sync_post_process(
            db,
            sync_object,
            current_user,
            cls.BITABLE_SYNC_SCENE,
        )
        logger.info(f"手动数据库工单自动化完成: ticket_no={ticket_no}")
        return {
            "ticketNo": ticket_no,
            "source": "database",
            "synced": False,
            "postProcessExecuted": True,
        }

    @classmethod
    def build_manual_bitable_config(cls, db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        构建手动飞书查询配置并校验最小连接条件。

        :param db: 数据库会话。
        :return: 完整同步配置和已归一化的飞书主动拉取配置。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        pull_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "bitablePull",
            TicketSyncConfigService.default_bitable_pull_config(),
            keep_filter_formula=False,
        )
        pull_config = TicketSyncConfigService.normalize_bitable_pull_config(
            pull_config,
            feishu_auth=config.get("feishuAuth") or TicketSyncConfigService.default_feishu_auth_config(),
            bitable_common=config.get("bitableCommon") or TicketSyncConfigService.default_bitable_common_config(),
        )
        required_missing = [
            field_name
            for field_name in ("appId", "appSecret", "appToken", "tableId")
            if not str(pull_config.get(field_name) or "").strip()
        ]
        if not pull_config.get("fieldMappings"):
            required_missing.append("fieldMappings")
        if required_missing:
            raise ValueError(f"多维表格手动查询配置不完整: {', '.join(required_missing)}")
        return config, pull_config

    @classmethod
    def resolve_ticket_no_field(cls, pull_config: dict[str, Any]) -> str:
        """
        解析飞书工单号字段，优先使用显式字段名，再回退字段映射。

        :param pull_config: 已归一化主动拉取配置。
        :return: 飞书多维表格中的工单号字段名。
        """
        ticket_no_field = str(pull_config.get("ticketNoField") or "").strip()
        if ticket_no_field and ticket_no_field != "ticketNo":
            return ticket_no_field
        for item in pull_config.get("fieldMappings") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("targetField") or "").strip() != "ticketNo":
                continue
            source_field = str(item.get("sourceField") or "").strip()
            if source_field:
                return source_field
        raise ValueError("未配置多维表格工单号字段，请填写工单号字段或配置 ticketNo 字段映射")

    @classmethod
    def build_ticket_no_filter(cls, ticket_no_field: str, ticket_no: str) -> dict[str, Any]:
        """
        构建仅用于手动补跑的飞书 records/search 工单号过滤条件。

        :param ticket_no_field: 多维表格工单号字段名。
        :param ticket_no: 要查询的工单号。
        :return: 飞书 filter 对象。
        """
        return {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": ticket_no_field,
                    "operator": "contains",
                    "value": [ticket_no],
                }
            ],
        }

    @classmethod
    def build_database_replay_sync_object(cls, ticket: Ticket) -> TicketExternalSyncUpsertModel:
        """
        从 ORM 工单实体构造后处理所需同步模型。

        这里只读取 ORM 实体作为领域数据来源；模型仅用于复用既有后处理，绝不调用同步入库以覆盖本地字段。

        :param ticket: 已存在的工单 ORM 实体。
        :return: 满足后处理契约的外部同步模型。
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        bitable_pull = extra_data.get("bitable_pull") if isinstance(extra_data.get("bitable_pull"), dict) else {}
        replay_at = datetime.now().isoformat(timespec="seconds")
        extra_data["manual_automation_replay"] = {
            "source": "database",
            "triggeredAt": replay_at,
            "reason": "manual_ticket_automation_replay",
        }
        source_record_id = str(bitable_pull.get("recordId") or "").strip() or None
        source_record_url = str(ticket.ticket_url or "").strip() or None
        raw_payload = {
            "ticketNo": ticket.ticket_no,
            "title": ticket.title,
            "description": ticket.description,
            "projectName": ticket.merchant_name,
            "moduleName": ticket.module_name,
            "status": ticket.status,
        }
        return TicketExternalSyncUpsertModel.model_validate(
            {
                "ticket_no": ticket.ticket_no,
                "ticket_url": ticket.ticket_url,
                "title": ticket.title,
                "description": ticket.description,
                "project_id": ticket.project_id,
                "merchant_name": ticket.merchant_name,
                "module_id": ticket.module_id,
                "module_code": ticket.module_code,
                "module_name": ticket.module_name,
                "category_id": ticket.category_id,
                "category_name": ticket.category_name,
                "issue_type_id": ticket.issue_type_id,
                "issue_type_name": ticket.issue_type_name,
                "status": ticket.status,
                "customer_priority": ticket.customer_priority,
                "internal_priority": ticket.internal_priority,
                "severity": ticket.severity,
                "reporter_id": ticket.reporter_id,
                "reporter_name": ticket.reporter_name,
                "current_assignee_id": ticket.current_assignee_id,
                "current_assignee_name": ticket.current_assignee_name,
                "internal_owner_id": ticket.internal_owner_id,
                "internal_owner_name": ticket.internal_owner_name,
                "is_problem": ticket.is_problem,
                "root_cause_type": ticket.root_cause_type,
                "solution_type": ticket.solution_type,
                "resolution_code": ticket.resolution_code,
                "resolution_name": ticket.resolution_name,
                "submit_time": ticket.submit_time,
                "extra_data": extra_data,
                "source": {
                    "system": cls.DATABASE_SOURCE_SYSTEM,
                    "recordId": source_record_id,
                    "recordUrl": source_record_url,
                    "pushedAt": ticket.update_time,
                },
                "raw_payload": raw_payload,
            }
        )
