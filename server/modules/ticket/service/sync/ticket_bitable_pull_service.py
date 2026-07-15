from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel, TicketSyncAutomationModel
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from modules.ticket.service.sync.ticket_sync_post_process_service import TicketSyncPostProcessService
from modules.ticket.service.sync.ticket_sync_service import TicketSyncService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_feishu_bitable_util import FeishuBitableUtil
from utils.log_util import logger


class TicketBitablePullService:
    """
    工单飞书多维表格主动拉取服务。

    该服务只负责多维表格字段预览、记录转换、快照去重与主动拉取调度；
    真正的工单入库和延后后处理继续调用 TicketSyncService 的同步主链路，避免复制外部同步业务逻辑。
    """

    @classmethod
    def build_system_current_user(cls) -> CurrentUserModel:
        """
        构造后台任务使用的系统用户上下文。

        :return: 包含空权限、空角色和 system 用户信息的当前用户模型。
        """
        return CurrentUserModel.model_validate(cls.build_system_current_user_payload())

    @classmethod
    def build_system_current_user_payload(cls) -> dict[str, Any]:
        """
        构造可跨 Celery 序列化的系统用户载荷。

        :return: 满足 CurrentUserModel 校验要求的用户字典。
        """
        return {
            "permissions": [],
            "roles": [],
            "user": {"userId": 0, "userName": "system", "nickName": "system"},
        }

    @classmethod
    def normalize_current_user_payload(cls, current_user_payload: dict[str, Any] | None) -> dict[str, Any]:
        """
        归一化延后后处理任务的当前用户载荷。

        :param current_user_payload: Celery 或本地后台任务传入的当前用户字典。
        :return: 补齐 permissions、roles 和 user 后的当前用户字典。
        """
        payload = dict(current_user_payload or {})
        payload.setdefault("permissions", [])
        payload.setdefault("roles", [])
        user_payload = payload.get("user")
        if isinstance(user_payload, dict):
            payload["user"] = {
                "userId": user_payload.get("userId", user_payload.get("user_id")),
                "userName": user_payload.get("userName", user_payload.get("user_name")),
                "nickName": user_payload.get("nickName", user_payload.get("nick_name")),
            }
        else:
            payload["user"] = cls.build_system_current_user_payload()["user"]
        return payload

    @classmethod
    def preview_bitable_pull_fields_services(
        cls,
        db: Session,
        *,
        bitable_pull_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        预览主动拉取配置对应多维表格中的字段名列表。

        :param db: 数据库会话。
        :param bitable_pull_override: 页面当前临时配置覆盖。
        :return: 字段名预览结果。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        pull_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "bitablePull",
            TicketSyncConfigService.default_bitable_pull_config(),
        )
        if isinstance(bitable_pull_override, dict):
            nested_override = (
                bitable_pull_override.get("bitablePull")
                if isinstance(bitable_pull_override.get("bitablePull"), dict)
                else bitable_pull_override
            )
            pull_config = TicketSyncConfigService.merge_non_empty_runtime_override(pull_config, nested_override)
        pull_config = TicketSyncConfigService.normalize_bitable_pull_config(
            pull_config,
            feishu_auth=config.get("feishuAuth") or TicketSyncConfigService.default_feishu_auth_config(),
            bitable_common=config.get("bitableCommon") or TicketSyncConfigService.default_bitable_common_config(),
        )
        preview_config = {
            **pull_config,
            "pageSize": 1,
            "filterFormula": "",
            "createdAfter": "",
        }
        fields_metadata: list[dict[str, Any]] = []
        try:
            fields_metadata = TicketSyncNotifyService.query_bitable_fields(preview_config)
        except Exception as exc:
            logger.warning(f"飞书多维表格字段元数据读取失败，回退样例记录推断字段: error={exc}")
        if fields_metadata:
            field_names = sorted(
                [
                    str(item.get("field_name") or item.get("name") or "").strip()
                    for item in fields_metadata
                    if str(item.get("field_name") or item.get("name") or "").strip()
                ]
            )
            return {
                "recordCount": 0,
                "fieldNames": field_names,
                "sampleRecordId": "",
                "source": "fields",
            }

        records = TicketSyncNotifyService.query_bitable_records(preview_config)
        first_record = records[0] if records else {}
        fields = first_record.get("fields") if isinstance(first_record.get("fields"), dict) else {}
        field_names = sorted([str(key).strip() for key in fields.keys() if str(key).strip()])
        return {
            "recordCount": len(records),
            "fieldNames": field_names,
            "sampleRecordId": str(first_record.get("record_id") or first_record.get("recordId") or "").strip(),
            "source": "sample_record",
        }

    @classmethod
    def run_bitable_pull_services(
        cls,
        db: Session,
        *,
        trigger_source: str,
        current_user: CurrentUserModel | None = None,
        bitable_pull_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        执行飞书多维表格主动拉取并复用外部同步逻辑入库。

        :param db: 数据库会话。
        :param trigger_source: 触发来源，支持 manual/scheduler。
        :param current_user: 当前用户，定时任务场景可为空。
        :param bitable_pull_override: 任务级覆盖配置。
        :return: 执行结果摘要。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        pull_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "bitablePull",
            TicketSyncConfigService.default_bitable_pull_config(),
        )

        if isinstance(bitable_pull_override, dict):
            nested_override = (
                bitable_pull_override.get("bitablePull")
                if isinstance(bitable_pull_override.get("bitablePull"), dict)
                else bitable_pull_override
            )
            pull_config = TicketSyncConfigService.merge_non_empty_runtime_override(pull_config, nested_override)
        pull_config = TicketSyncConfigService.normalize_bitable_pull_config(
            pull_config,
            feishu_auth=config.get("feishuAuth") or TicketSyncConfigService.default_feishu_auth_config(),
            bitable_common=config.get("bitableCommon") or TicketSyncConfigService.default_bitable_common_config(),
        )
        if not pull_config.get("enabled"):
            logger.info(f"飞书多维表格主动拉取已跳过: enabled=false, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "主动拉取未启用"}

        normalized_override = {}
        if isinstance(bitable_pull_override, dict):
            nested_override = (
                bitable_pull_override.get("bitablePull")
                if isinstance(bitable_pull_override.get("bitablePull"), dict)
                else bitable_pull_override
            )
            normalized_override = {
                str(key): value for key, value in dict(nested_override or {}).items() if value not in (None, "")
            }

        if normalized_override:
            logger.info(
                f"飞书多维表格主动拉取使用任务级覆盖: trigger={trigger_source}, "
                f"override_keys={list(normalized_override.keys())}"
            )

        required_missing: list[str] = [
            field_name
            for field_name in ("appId", "appSecret", "appToken", "tableId")
            if not str(pull_config.get(field_name) or "").strip()
        ]
        if not pull_config.get("fieldMappings"):
            required_missing.append("fieldMappings")
        if required_missing:
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": f"主动拉取配置不完整: {', '.join(required_missing)}",
                "configErrors": required_missing,
            }

        auto_append = SyncUtil.to_bool(pull_config.get("autoAppendTimeFilter"), True)
        # 与拆分前 TicketSyncService 保持一致：自动追加时间窗口时忽略配置里的显式时间，
        # 统一由本次执行动态生成最近 1 小时窗口，避免历史配置扩大主动拉取范围。
        raw_created_after = str(pull_config.get("createdAfter") or "").strip() if not auto_append else None
        raw_created_before = str(pull_config.get("createdBefore") or "").strip() if not auto_append else None

        created_after = (
            TicketSyncConfigService.resolve_bitable_pull_created_after(raw_created_after)
            if raw_created_after
            else None
        )
        created_before = (
            TicketSyncConfigService.resolve_bitable_pull_created_after(raw_created_before)
            if raw_created_before
            else None
        )

        if raw_created_after and not created_after:
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": "主动拉取开始时间格式错误",
                "configErrors": ["createdAfter"],
                "createdAfter": raw_created_after,
            }
        if raw_created_before and not created_before:
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": "主动拉取结束时间格式错误",
                "configErrors": ["createdBefore"],
                "createdBefore": raw_created_before,
            }

        if auto_append:
            # 现有行为：无显式时间时默认过滤过去 1 小时。
            if not created_after and not created_before:
                created_after = datetime.now() - timedelta(hours=1)
                pull_config["createdAfter"] = created_after.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # 精确模式：不自动追加，仅使用显式传入的时间参数。
            if not created_after and not created_before:
                created_after = None

        pull_filters: list[dict[str, Any]] = []
        if created_after or created_before:
            updated_at_field = str(pull_config.get("updatedAtField") or "").strip() or "更新时间"
            try:
                pull_filters = TicketSyncConfigService.build_bitable_pull_time_filters(
                    filter_formula=pull_config.get("filterFormula"),
                    created_after=created_after,
                    created_before=created_before,
                    updated_at_field=updated_at_field,
                    auto_append_time_filter=auto_append,
                )
            except ValueError as exc:
                return {
                    "triggerSource": trigger_source,
                    "skipped": True,
                    "skipReason": str(exc),
                    "configErrors": ["filterFormula"],
                    "createdAfter": created_after.strftime("%Y-%m-%d %H:%M:%S") if created_after else "",
                    "createdBefore": created_before.strftime("%Y-%m-%d %H:%M:%S") if created_before else "",
                }
            time_info_parts = []
            if created_after:
                time_info_parts.append(f"created_after={created_after.strftime('%Y-%m-%d %H:%M:%S')}")
            if created_before:
                time_info_parts.append(f"created_before={created_before.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(
                f"飞书多维表格主动拉取云端时间过滤: trigger={trigger_source}, "
                f"{', '.join(time_info_parts)}, auto_append={auto_append}, "
                f"updated_at_field={updated_at_field}"
            )
        else:
            try:
                pull_filters = TicketSyncConfigService.build_bitable_pull_time_filters(
                    filter_formula=pull_config.get("filterFormula"),
                    created_after=None,
                    created_before=None,
                    updated_at_field="",
                    auto_append_time_filter=auto_append,
                )
            except ValueError as exc:
                return {
                    "triggerSource": trigger_source,
                    "skipped": True,
                    "skipReason": str(exc),
                    "configErrors": ["filterFormula"],
                    "createdAfter": "",
                    "createdBefore": "",
                }
            logger.info(
                f"飞书多维表格主动拉取无时间过滤: trigger={trigger_source}, auto_append={auto_append}"
            )
        records = TicketSyncConfigService.iter_bitable_pull_records(pull_config, pull_filters)
        force_sync = SyncUtil.to_bool(pull_config.get("forceSync"), False)
        required_fields = TicketSyncConfigService.derive_required_fields_from_external_field_model(
            config.get("externalFieldModel")
        )
        summary = {
            "triggerSource": trigger_source,
            "skipped": False,
            "recordCount": 0,
            "queriedRecordCount": 0,
            "createdAfter": created_after.strftime("%Y-%m-%d %H:%M:%S") if created_after else "",
            "forceSync": force_sync,
            "syncedCount": 0,
            "skippedCount": 0,
            "failedCount": 0,
            "skipReasons": {},
            "failures": [],
        }
        fallback_user = current_user or cls.build_system_current_user()
        deferred_current_user_payload = (
            cls.build_system_current_user_payload()
            if current_user is None
            else cls.normalize_current_user_payload(current_user.model_dump())
        )
        automation_override = pull_config.get("automation") if isinstance(pull_config.get("automation"), dict) else {}

        for record in records:
            summary["recordCount"] += 1
            summary["queriedRecordCount"] += 1
            sync_object = cls.build_bitable_pull_sync_object(
                record=record,
                config=pull_config,
                field_mappings=pull_config.get("fieldMappings") or [],
                required_fields=required_fields,
            )
            record_id = str(record.get("record_id") or record.get("recordId") or "").strip()
            if not sync_object:
                summary["failedCount"] += 1
                summary["failures"].append({"recordId": record_id, "reason": "record_to_sync_object_failed"})
                continue
            sync_object = sync_object.model_copy(
                update={
                    "automation": TicketSyncAutomationModel.model_validate(automation_override),
                }
            )
            existing_ticket = TicketDao.get_ticket_by_no(db, sync_object.ticket_no)
            should_skip, skip_reason = (
                (False, "")
                if force_sync
                else cls.should_skip_bitable_pull_record(
                    existing_ticket=existing_ticket,
                    sync_object=sync_object,
                )
            )
            if should_skip:
                summary["skippedCount"] += 1
                summary["skipReasons"][skip_reason] = int(summary["skipReasons"].get(skip_reason) or 0) + 1
                continue
            if force_sync and existing_ticket:
                logger.info(
                    f"飞书多维表格主动拉取强制同步记录: ticket_no={sync_object.ticket_no}, "
                    f"record_id={record_id or '-'}"
                )
            try:
                result = TicketSyncService.sync_external_ticket(
                    db,
                    sync_object,
                    fallback_user,
                    "bitable_pull",
                    True,
                )
                if result.is_success:
                    summary["syncedCount"] += 1
                    deferred_dispatch = TicketSyncPostProcessService.dispatch_deferred_sync_post_process_task(
                        sync_object.model_dump(),
                        deferred_current_user_payload,
                        "bitable_pull",
                    )
                    if deferred_dispatch.get("mode") != TicketSyncPostProcessService.CELERY_DISPATCH_MODE:
                        TicketSyncPostProcessService.run_deferred_sync_post_process(
                            sync_object.model_dump(),
                            deferred_current_user_payload,
                            "bitable_pull",
                        )
                else:
                    summary["failedCount"] += 1
                    summary["failures"].append(
                        {"recordId": record_id, "ticketNo": sync_object.ticket_no, "reason": result.message}
                    )
            except Exception as exc:
                logger.exception(f"飞书多维表格主动拉取入库失败: record_id={record_id or '-'}, error={exc}")
                summary["failedCount"] += 1
                summary["failures"].append(
                    {"recordId": record_id, "ticketNo": sync_object.ticket_no, "reason": str(exc)}
                )
        return summary

    @classmethod
    def build_bitable_pull_sync_object(
        cls,
        *,
        record: dict[str, Any],
        config: dict[str, Any],
        field_mappings: list[dict[str, Any]],
        required_fields: list[str] | None = None,
    ) -> TicketExternalSyncUpsertModel | None:
        """
        将飞书多维表格记录转换为外部工单同步模型。

        :param record: 飞书多维表格记录。
        :param config: 主动拉取配置。
        :param field_mappings: 字段映射关系。
        :param required_fields: 外部同步必填字段列表，来源于外部字段模型。
        :return: 外部同步模型，缺少关键字段时返回 None。
        """
        fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
        record_id = str(record.get("record_id") or record.get("recordId") or "").strip()
        record_url = str(
            record.get("record_url")
            or record.get("recordUrl")
            or record.get("shared_url")
            or record.get("sharedUrl")
            or ""
        ).strip()
        payload = FeishuBitableUtil.build_pull_field_mapping_from_record(fields, field_mappings=field_mappings)
        if not payload:
            return None
        # 主动拉取不经过外部推送 controller 的兼容层，这里补齐同等字段语义，避免优先级和人员字段丢失。
        if payload.get("internalPriority") in (None, "", []) and payload.get("customerPriority") not in (None, "", []):
            payload["internalPriority"] = payload.get("customerPriority")
        if payload.get("customerPriority") in (None, "", []) and payload.get("internalPriority") not in (None, "", []):
            payload["customerPriority"] = payload.get("internalPriority")
        if payload.get("currentAssigneeName") in (None, "", []) and payload.get("ticketAssignee") not in (None, "", []):
            payload["currentAssigneeName"] = payload.get("ticketAssignee")
        if (
            payload.get("currentAssigneeEmail") in (None, "", [])
            and payload.get("ticketAssigneeEmail") not in (None, "", [])
        ):
            payload["currentAssigneeEmail"] = payload.get("ticketAssigneeEmail")
        if payload.get("ticketAssignee") in (None, "", []) and payload.get("currentAssigneeName") not in (None, "", []):
            payload["ticketAssignee"] = payload.get("currentAssigneeName")
        if (
            payload.get("ticketAssigneeEmail") in (None, "", [])
            and payload.get("currentAssigneeEmail") not in (None, "", [])
        ):
            payload["ticketAssigneeEmail"] = payload.get("currentAssigneeEmail")
        mapping_payload = dict(payload)
        top_level_alias_map = {
            "ticketVender": "projectName",
            "ticketModle": "moduleName",
            "internalOwner": "internalOwnerName",
            "internalOwnerEmail": "internalOwnerEmail",
            "reporterName": "reporterName",
            "reporterEmail": "reporterEmail",
            "currentAssigneeName": "currentAssigneeName",
            "currentAssigneeEmail": "currentAssigneeEmail",
            "ticketStatus": "status",
            "ticketStore": "ticketStore",
            "ticketPos": "ticketPos",
            "ticketSco": "ticketSco",
            "stepReason": "stepReason",
            "customerPriority": "customerPriority",
            "internalPriority": "internalPriority",
        }
        for source_key, target_key in top_level_alias_map.items():
            if source_key in payload and payload.get(source_key) not in (None, "", []):
                payload.setdefault(target_key, payload.get(source_key))
        field_mapping_snapshot = {
            FeishuBitableUtil.normalize_pull_target_field(item.get("targetField")): str(
                item.get("sourceField") or ""
            ).strip()
            for item in field_mappings
            if str(item.get("targetField") or "").strip() and str(item.get("sourceField") or "").strip()
        }
        payload["recordId"] = payload.get("recordId") or record_id
        normalized_required_fields = [
            str(item or "").strip()
            for item in required_fields or TicketSyncConfigService.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS
            if str(item or "").strip()
        ]
        missing_required_fields = [
            field_name
            for field_name in normalized_required_fields
            if payload.get(field_name) in (None, "", [])
        ]
        if missing_required_fields:
            logger.warning(
                f"飞书多维表格记录转换外部同步模型失败: record_id={record_id or '-'}, "
                f"missing_required_fields={missing_required_fields}"
            )
            return None
        if config.get("includeRecordUrl", True):
            payload["ticketUrl"] = payload.get("ticketUrl") or FeishuBitableUtil.build_record_url(
                config,
                record_id=record_id,
                record_url=record_url,
            )
        payload["source"] = {
            "system": str(config.get("sourceSystem") or "feishu_bitable_pull").strip() or "feishu_bitable_pull",
            "recordId": payload.get("recordId") or record_id,
            "recordUrl": payload.get("ticketUrl") or FeishuBitableUtil.build_record_url(
                config,
                record_id=record_id,
                record_url=record_url,
            ),
            "pushedAt": FeishuBitableUtil.normalize_record_datetime_text(
                fields.get(str(config.get("updatedAtField") or "").strip()) or record.get("created_time")
            )
            or None,
        }
        payload["raw_payload"] = {
            "recordId": record_id,
            "recordUrl": record_url or None,
            "fields": fields,
            "createdTime": record.get("created_time"),
            "lastModifiedTime": record.get("last_modified_time"),
        }
        extra_data = payload.get("extraData") if isinstance(payload.get("extraData"), dict) else {}
        extra_data = dict(extra_data or {})
        external_field_mapping = (
            dict(extra_data.get("external_field_mapping"))
            if isinstance(extra_data.get("external_field_mapping"), dict)
            else {}
        )
        external_field_mapping.update(mapping_payload)
        external_field_mapping["bitableRecordId"] = record_id
        if record_url:
            external_field_mapping["bitableRecordUrl"] = record_url
        extra_data["external_field_mapping"] = external_field_mapping
        bitable_pull_meta: dict[str, Any] = {
            "recordId": record_id,
            "snapshotHash": FeishuBitableUtil.build_pull_snapshot_hash(
                source_payload=payload,
                field_mapping_snapshot=field_mapping_snapshot,
            ),
            "stepReasonHash": SyncUtil.text_sha256(payload.get("stepReason")),
            "fieldMappings": field_mapping_snapshot,
            "sourceSystem": payload["source"]["system"],
            "pulledAt": SyncUtil.now_iso(),
        }
        send_group_override = config.get("sendGroupMessage") if isinstance(config, dict) else None
        if send_group_override is not None:
            bitable_pull_meta["sendGroupMessage"] = bool(send_group_override)
        extra_data["bitable_pull"] = bitable_pull_meta
        payload["extraData"] = extra_data
        try:
            return TicketExternalSyncUpsertModel.model_validate(payload)
        except Exception as exc:
            logger.warning(f"飞书多维表格记录转换外部同步模型失败: record_id={record_id or '-'}, error={exc}")
            return None

    @classmethod
    def should_skip_bitable_pull_record(
        cls,
        *,
        existing_ticket: Ticket | None,
        sync_object: TicketExternalSyncUpsertModel,
    ) -> tuple[bool, str]:
        """
        判断主动拉取记录是否因快照未变化而跳过入库。

        :param existing_ticket: 已存在工单。
        :param sync_object: 当前转换后的同步对象。
        :return: (是否跳过, 原因)。
        """
        if not existing_ticket or not isinstance(existing_ticket.extra_data, dict):
            return False, ""
        bitable_pull_meta = existing_ticket.extra_data.get("bitable_pull")
        if not isinstance(bitable_pull_meta, dict):
            return False, ""
        current_pull_meta = (
            sync_object.extra_data.get("bitable_pull") if isinstance(sync_object.extra_data, dict) else {}
        )
        existing_hash = str(bitable_pull_meta.get("snapshotHash") or "").strip()
        current_hash = str((current_pull_meta or {}).get("snapshotHash") or "").strip()
        existing_record_id = str(bitable_pull_meta.get("recordId") or "").strip()
        current_record_id = str((current_pull_meta or {}).get("recordId") or "").strip()
        if existing_hash and current_hash and existing_hash == current_hash and existing_record_id == current_record_id:
            return True, "snapshot_not_changed"
        return False, ""

