from typing import Any

import requests
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel, TicketSyncAutomationModel
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_service import TicketSyncService
from modules.ticket.util.sync_util import SyncUtil
from utils.log_util import logger


class TicketRemoteSyncService:
    """
    工单远端拉取同步服务。

    负责从公网工单系统拉取待交付数据、判断本地是否需要覆盖、复用外部同步入库链路并回写远端 ack。
    """

    META_KEY = "external_sync"

    @classmethod
    def build_external_sync_meta(cls, extra_data: dict[str, Any] | None) -> dict[str, Any]:
        """
        读取工单外部同步元数据。

        :param extra_data: 工单扩展字段。
        :return: 外部同步元数据；不存在时返回空字典。
        """
        source = extra_data if isinstance(extra_data, dict) else {}
        meta = source.get(cls.META_KEY) if isinstance(source.get(cls.META_KEY), dict) else {}
        return dict(meta)

    @classmethod
    def should_apply_remote_sync_item(
        cls,
        *,
        local_ticket: Ticket | None,
        remote_sync_revision: int,
        remote_pushed_at: Any,
    ) -> tuple[bool, str]:
        """
        判断远端工单是否需要覆盖本地数据（仅远端较新时更新）。

        :param local_ticket: 本地工单。
        :param remote_sync_revision: 远端同步修订号。
        :param remote_pushed_at: 远端最新更新时间。
        :return: (是否需要同步, 原因)。
        """
        if not local_ticket:
            return True, "local_missing"
        extra_data = local_ticket.extra_data if isinstance(local_ticket.extra_data, dict) else {}
        local_meta = cls.build_external_sync_meta(extra_data)
        local_source_revision = SyncUtil.safe_int(local_meta.get("sourceRevision"))
        if remote_sync_revision > 0 and local_source_revision is not None:
            if remote_sync_revision <= local_source_revision:
                return (
                    False,
                    f"remote_revision_not_newer(remote={remote_sync_revision}, local={local_source_revision})",
                )
            return True, "remote_revision_newer"
        if remote_sync_revision > 0 and local_source_revision is None:
            return True, "remote_revision_available_without_local_revision"

        local_source = local_meta.get("source") if isinstance(local_meta.get("source"), dict) else {}
        local_pushed_at = (
            local_source.get("pushedAt")
            or local_meta.get("lastImportedAt")
        )
        parsed_remote_time = SyncUtil.parse_datetime_value(remote_pushed_at)
        parsed_local_time = SyncUtil.parse_datetime_value(local_pushed_at)
        if parsed_remote_time and parsed_local_time and parsed_remote_time <= parsed_local_time:
            return (
                False,
                (
                    f"remote_time_not_newer(remote={parsed_remote_time.isoformat()}, "
                    f"local={parsed_local_time.isoformat()})"
                ),
            )
        return True, "remote_time_newer_or_unknown"

    @classmethod
    def build_request_headers(cls, remote_sync: dict[str, Any]) -> dict[str, str]:
        """
        构建远端工单同步请求头。

        :param remote_sync: 远端同步配置。
        :return: 请求头字典。
        """
        headers = dict(remote_sync.get("headers") or {})
        normalized = {str(key).strip().lower(): str(value or "").strip() for key, value in headers.items()}
        result = {"Content-Type": "application/json", "Accept": "application/json"}
        if normalized.get("cookie"):
            result["Cookie"] = normalized["cookie"]
        if normalized.get("authorization"):
            result["Authorization"] = normalized["authorization"]
        if normalized.get("origin"):
            result["Origin"] = normalized["origin"]
        return result

    @classmethod
    def build_upsert_model(
        cls,
        item: dict[str, Any],
        *,
        remote_sync: dict[str, Any],
    ) -> TicketExternalSyncUpsertModel | None:
        """
        将远端拉取的工单数据转换为外部同步入库模型。

        :param item: 远端返回的工单字典。
        :param remote_sync: 远端同步配置。
        :return: 可用于外部同步入库的模型，失败时返回 None。
        """
        ticket_no = str(item.get("ticketNo") or item.get("ticket_no") or "").strip()
        description = str(item.get("description") or "").strip()
        title = str(item.get("title") or "").strip()
        if not ticket_no or not description:
            return None
        sync_summary = item.get("syncSummary") if isinstance(item.get("syncSummary"), dict) else {}
        remote_sync_revision = int(
            item.get("syncRevision")
            or sync_summary.get("revision")
            or item.get("revision")
            or 0
        )
        external_create_time = (
            item.get("externalCreateTime")
            or item.get("external_create_time")
            or sync_summary.get("externalCreateTime")
            or item.get("createTime")
            or item.get("create_time")
        )
        remote_ticket_url = str(
            item.get("ticketUrl")
            or item.get("ticket_url")
            or item.get("url")
            or item.get("detailUrl")
            or item.get("detail_url")
            or sync_summary.get("ticketUrl")
            or sync_summary.get("sourceRecordUrl")
            or ""
        ).strip() or None

        source_payload = {
            "system": str(remote_sync.get("sourceSystem") or "public").strip() or "public",
            "recordId": str(item.get("ticketId") or item.get("ticket_id") or ticket_no).strip() or ticket_no,
            "recordUrl": remote_ticket_url,
            "pushedAt": (
                item.get("updateTime")
                or item.get("update_time")
                or item.get("createTime")
                or item.get("create_time")
            ),
        }
        sync_extra_data = item.get("extraData") if isinstance(item.get("extraData"), dict) else {}
        if not sync_extra_data and isinstance(item.get("extra_data"), dict):
            sync_extra_data = item.get("extra_data")
        sync_extra_data = dict(sync_extra_data or {})
        sync_extra_data["_remote_sync_revision"] = remote_sync_revision
        remote_comments = item.get("comments") if isinstance(item.get("comments"), list) else []
        if remote_comments:
            sync_extra_data["_remote_sync_comments"] = remote_comments
        external_field_mapping = (
            sync_extra_data.get("external_field_mapping")
            if isinstance(sync_extra_data.get("external_field_mapping"), dict)
            else {}
        )
        ticket_status = str(
            item.get("ticketStatus")
            or item.get("ticket_status")
            or item.get("status")
            or external_field_mapping.get("ticketStatus")
            or ""
        ).strip()
        module_name = str(
            item.get("moduleName")
            or item.get("module_name")
            or item.get("ticketModle")
            or item.get("ticketModel")
            or item.get("ticket_model")
            or external_field_mapping.get("ticketModle")
            or external_field_mapping.get("ticketModel")
            or ""
        ).strip()
        log_pull_hints = (
            sync_extra_data.get("log_pull_hints")
            if isinstance(sync_extra_data.get("log_pull_hints"), dict)
            else {}
        )
        log_pull_config = {
            "vendorId": log_pull_hints.get("vendorId") or log_pull_hints.get("vendor_id"),
            "storeId": log_pull_hints.get("storeId") or log_pull_hints.get("store_id"),
            "storeName": log_pull_hints.get("storeName") or log_pull_hints.get("store_name"),
            "posNo": log_pull_hints.get("posNo") or log_pull_hints.get("pos_no"),
            "scoNo": log_pull_hints.get("scoNo") or log_pull_hints.get("sco_no"),
            "modifyTime": log_pull_hints.get("modifyTime") or log_pull_hints.get("modify_time"),
        }
        log_pull_config = {key: value for key, value in log_pull_config.items() if value not in (None, "", [])}
        internal_owner_name = str(
            item.get("internalOwner")
            or item.get("internal_owner")
            or item.get("internalOwnerName")
            or item.get("internal_owner_name")
            or external_field_mapping.get("internalOwner")
            or external_field_mapping.get("internalOwnerName")
            or ""
        ).strip()
        internal_owner_email = str(
            item.get("internalOwnerEmail")
            or item.get("internal_owner_email")
            or external_field_mapping.get("internalOwnerEmail")
            or ""
        ).strip()
        step_reason = str(
            item.get("stepReason")
            or item.get("step_reason")
            or sync_extra_data.get("step_reason")
            or external_field_mapping.get("stepReason")
            or ""
        ).strip()
        sync_payload = {
            "source": source_payload,
            "syncConsumer": str(remote_sync.get("consumer") or "").strip() or None,
            "rawPayload": item,
            "ticketNo": ticket_no,
            "ticketUrl": remote_ticket_url,
            "title": title,
            "description": description,
            "createTime": external_create_time or source_payload.get("pushedAt"),
            "projectId": None,
            "projectName": item.get("projectName") or item.get("project_name") or item.get("merchantName") or "",
            "projectCode": item.get("projectCode") or item.get("project_code") or "",
            "merchantName": item.get("merchantName") or item.get("projectName") or item.get("project_name") or "",
            "moduleId": None,
            "moduleName": module_name,
            "moduleCode": item.get("moduleCode") or item.get("module_code") or "",
            "versionKey": item.get("versionKey") or item.get("version_key") or "",
            "status": ticket_status,
            "issueTypeId": item.get("issueTypeId") or item.get("issue_type_id") or "",
            "issueTypeName": item.get("issueTypeName") or item.get("issue_type_name") or "",
            "isProblem": item.get("isProblem") if item.get("isProblem") is not None else item.get("is_problem"),
            "rootCauseType": item.get("rootCauseType") or item.get("root_cause_type") or "",
            "solutionType": item.get("solutionType") or item.get("solution_type") or "",
            "resolutionCode": item.get("resolutionCode") or item.get("resolution_code") or "",
            "resolutionName": item.get("resolutionName") or item.get("resolution_name") or "",
            "customerPriority": item.get("customerPriority") or item.get("customer_priority") or "P3",
            "internalPriority": item.get("internalPriority") or item.get("internal_priority") or "P3",
            "severity": item.get("severity") or "",
            "reporterId": item.get("reporterId") or item.get("reporter_id"),
            "reporterName": item.get("reporterName") or item.get("reporter_name") or "",
            "currentAssigneeId": None,
            "currentAssigneeName": item.get("currentAssigneeName") or item.get("current_assignee_name") or "",
            "internalOwnerId": item.get("internalOwnerId") or item.get("internal_owner_id"),
            "internalOwnerName": internal_owner_name,
            "internalOwnerEmail": internal_owner_email,
            "rootCause": item.get("rootCause") or item.get("root_cause") or "",
            "solution": item.get("solution") or "",
            "tags": item.get("tags"),
            "extraData": sync_extra_data,
            "stepReason": step_reason,
            "logPullConfig": log_pull_config or None,
            "createBy": item.get("createBy") or item.get("create_by") or "",
            "updateBy": item.get("updateBy") or item.get("update_by") or "",
        }
        try:
            return TicketExternalSyncUpsertModel.model_validate(sync_payload)
        except Exception as exc:
            logger.warning(f"转换远端工单同步模型失败，ticket_no={ticket_no}, error={exc}")
            return None

    @classmethod
    def sync_remote_pending_tickets(
        cls,
        db: Session,
        current_user: CurrentUserModel | None = None,
        remote_sync_override: dict[str, Any] | None = None,
        external_sync_handler=None,
    ) -> dict[str, Any]:
        """
        从远端公网环境拉取未同步工单，入库后回写远端交付状态。

        :param db: 数据库会话。
        :param current_user: 当前用户，定时任务场景可为空。
        :param remote_sync_override: 可选远端同步覆盖配置。
        :param external_sync_handler: 外部同步入库处理函数，默认复用 TicketSyncService.sync_external_ticket。
        :return: 同步汇总结果。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        remote_sync = dict(config.get("remoteSync") or TicketSyncConfigService.default_remote_sync_config())
        if remote_sync_override:
            override_remote_sync = (
                remote_sync_override.get("remoteSync")
                if isinstance(remote_sync_override, dict)
                else None
            )
            if isinstance(override_remote_sync, dict):
                remote_sync.update(override_remote_sync)
            elif isinstance(remote_sync_override, dict):
                remote_sync.update(remote_sync_override)
        remote_sync["pullUrl"] = str(remote_sync.get("pullUrl") or "").strip()
        remote_sync["ackUrl"] = str(remote_sync.get("ackUrl") or "").strip()
        remote_sync["consumer"] = str(remote_sync.get("consumer") or "").strip()
        remote_sync["sourceSystem"] = str(remote_sync.get("sourceSystem") or "public").strip() or "public"
        remote_sync["limit"] = min(max(int(remote_sync.get("limit") or config.get("defaultPullLimit") or 50), 1), 200)
        remote_sync["includeClosed"] = bool(remote_sync.get("includeClosed", True))
        remote_sync["autoTranslateOnPull"] = bool(remote_sync.get("autoTranslateOnPull", True))
        remote_sync["timeoutSec"] = max(int(remote_sync.get("timeoutSec") or 30), 10)
        remote_sync["headers"] = {
            **TicketSyncConfigService.default_remote_sync_config()["headers"],
            **(remote_sync.get("headers") if isinstance(remote_sync.get("headers"), dict) else {}),
        }

        if not remote_sync.get("enabled"):
            logger.info(
                f"远端工单拉取已跳过：配置未启用 | consumer={remote_sync['consumer'] or '-'} "
                f"source_system={remote_sync['sourceSystem']}"
            )
            return {
                "consumer": remote_sync["consumer"],
                "batchId": "",
                "pulledCount": 0,
                "syncedCount": 0,
                "failedCount": 0,
                "ackedCount": 0,
                "skipped": True,
                "skipReason": "远端同步未启用",
            }

        if not remote_sync.get("pullUrl"):
            raise ValueError("远端工单拉取地址未配置，请检查 ticket.sync.automation.remoteSync.pullUrl")
        if not remote_sync.get("ackUrl"):
            raise ValueError("远端工单回写地址未配置，请检查 ticket.sync.automation.remoteSync.ackUrl")
        if not remote_sync.get("consumer"):
            raise ValueError("远端工单同步消费者未配置，请检查 ticket.sync.automation.remoteSync.consumer")

        logger.info(
            f"开始拉取远端工单同步数据 | pull_url={remote_sync['pullUrl']} ack_url={remote_sync['ackUrl']} "
            f"consumer={remote_sync['consumer']} limit={remote_sync['limit']} "
            f"include_closed={remote_sync['includeClosed']}"
        )
        response = requests.get(
            remote_sync["pullUrl"],
            params={
                "consumer": remote_sync["consumer"],
                "limit": remote_sync["limit"],
                "includeClosed": remote_sync["includeClosed"],
            },
            timeout=(10, remote_sync["timeoutSec"]),
            headers=cls.build_request_headers(remote_sync),
        )
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("code") or 0) != 200:
            raise RuntimeError(f"远端工单拉取失败: {payload.get('msg') or payload}")

        data = payload.get("data")
        if isinstance(data, dict):
            items = data.get("items") if isinstance(data.get("items"), list) else []
            batch_id = str(data.get("batchId") or "")
        elif isinstance(data, list):
            items = data
            batch_id = ""
        else:
            items = []
            batch_id = ""

        summary = {
            "consumer": remote_sync["consumer"],
            "batchId": batch_id,
            "pulledCount": len(items),
            "syncedCount": 0,
            "failedCount": 0,
            "ackedCount": 0,
            "skippedCount": 0,
        }
        ack_items: list[dict[str, Any]] = []
        sync_handler = external_sync_handler or TicketSyncService.sync_external_ticket

        for item in items:
            if not isinstance(item, dict):
                continue
            remote_ticket_id = int(item.get("ticketId") or item.get("ticket_id") or 0)
            sync_revision = int(
                item.get("syncRevision")
                or (item.get("syncSummary") or {}).get("revision")
                or item.get("revision")
                or 0
            )
            upsert_model = cls.build_upsert_model(item, remote_sync=remote_sync)
            if not upsert_model:
                summary["failedCount"] += 1
                if remote_ticket_id:
                    ack_items.append(
                        {
                            "ticketId": remote_ticket_id,
                            "syncRevision": sync_revision,
                            "deliveryStatus": "failed",
                            "message": "远端工单数据缺少 ticketNo 或 description",
                        }
                    )
                continue

            upsert_model = upsert_model.model_copy(
                update={
                    "automation": TicketSyncAutomationModel(
                        auto_identify=False,
                        auto_log_pull=False,
                        auto_ai_analysis=False,
                        auto_translate=bool(remote_sync.get("autoTranslateOnPull", True)),
                    )
                }
            )
            local_ticket = TicketDao.get_ticket_by_no(db, upsert_model.ticket_no)
            should_apply_remote, apply_reason = cls.should_apply_remote_sync_item(
                local_ticket=local_ticket,
                remote_sync_revision=sync_revision,
                remote_pushed_at=upsert_model.source.pushed_at,
            )
            if not should_apply_remote:
                summary["skippedCount"] += 1
                summary["syncedCount"] += 1
                if remote_ticket_id:
                    ack_items.append(
                        {
                            "ticketId": remote_ticket_id,
                            "syncRevision": sync_revision,
                            "deliveryStatus": "delivered",
                            "message": "本地数据已是最新，跳过覆盖更新",
                            "detail": {
                                "skipReason": apply_reason,
                                "localTicketId": getattr(local_ticket, "ticket_id", None),
                            },
                        }
                    )
                continue

            try:
                sync_result = sync_handler(
                    db,
                    upsert_model,
                    current_user,
                    sync_scene="remote_pull",
                )
                if sync_result.is_success:
                    summary["syncedCount"] += 1
                    local_ticket_id = None
                    if isinstance(sync_result.result, dict):
                        local_ticket_id = sync_result.result.get("ticketId") or sync_result.result.get("ticket_id")
                    ack_items.append(
                        {
                            "ticketId": remote_ticket_id,
                            "syncRevision": sync_revision,
                            "deliveryStatus": "delivered",
                            "message": sync_result.message,
                            "detail": {"localTicketId": local_ticket_id},
                        }
                    )
                else:
                    summary["failedCount"] += 1
                    if remote_ticket_id:
                        ack_items.append(
                            {
                                "ticketId": remote_ticket_id,
                                "syncRevision": sync_revision,
                                "deliveryStatus": "failed",
                                "message": sync_result.message,
                            }
                        )
            except Exception as exc:
                summary["failedCount"] += 1
                logger.exception(f"远端工单同步入库失败，ticketId={remote_ticket_id}, error={exc}")
                if remote_ticket_id:
                    ack_items.append(
                        {
                            "ticketId": remote_ticket_id,
                            "syncRevision": sync_revision,
                            "deliveryStatus": "failed",
                            "message": str(exc),
                            "detail": {"error": str(exc)},
                        }
                    )

        if ack_items:
            ack_response = requests.post(
                remote_sync["ackUrl"],
                json={"consumer": remote_sync["consumer"], "items": ack_items},
                timeout=(10, remote_sync["timeoutSec"]),
                headers=cls.build_request_headers(remote_sync),
            )
            ack_response.raise_for_status()
            ack_payload = ack_response.json()
            if int(ack_payload.get("code") or 0) != 200:
                raise RuntimeError(f"远端工单回写失败: {ack_payload.get('msg') or ack_payload}")
            summary["ackedCount"] = len(ack_items)

        return summary
