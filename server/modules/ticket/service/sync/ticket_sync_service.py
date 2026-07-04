from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketEvent, TicketMessage, TicketStatusHistory
from modules.ticket.entity.vo.ticket_vo import (
    TicketExternalSyncUpsertModel,
)
from modules.ticket.enums.ticket_enums import TicketEventType
from modules.ticket.service.ai.ticket_auto_classification_service import TicketAutoClassificationService
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.sync.ticket_external_bitable_email_service import TicketExternalBitableEmailService
from modules.ticket.service.sync.ticket_sync_automation_service import TicketSyncAutomationService
from modules.ticket.service.sync.ticket_sync_comment_service import TicketSyncCommentService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_delivery_service import TicketSyncDeliveryService
from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import (
    user_id as _user_id,
)
from modules.ticket.util.ticket_common_util import (
    user_name as _user_name,
)
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class TicketSyncService:
    """
    工单外部同步服务，统一处理外部推送、内网拉取和同步后自动化状态追踪。

    已提取的子服务（见对应文件，调用方应直接依赖对应子服务）：
    - TicketSyncConfigService (ticket_sync_config_service.py): 配置管理
    - SyncUtil (util/sync_util.py): 通用工具方法
    后续仅剩外部同步入库主编排仍在本服务内。
    """

    PUBLISH_STATUS_PROCESSING_AI = "processing_ai"

    @classmethod
    def _has_successful_ai_translation(cls, ticket: Ticket | None, source_description: str | None = None) -> bool:
        """
        判断工单是否已有成功的 AI 翻译结果。

        :param ticket: 工单对象
        :param source_description: 本次待翻译原文；传入后会校验是否与历史翻译源一致。
        :return: 是否已存在翻译结果
        """
        if not ticket or not isinstance(ticket.extra_data, dict):
            return False
        extra_data = ticket.extra_data
        translated_text = str(extra_data.get("ai_translation") or "").strip()
        if not translated_text:
            return False
        normalized_source = str(source_description or "").strip()
        if not normalized_source:
            return True
        source_hash = SyncUtil.text_sha256(normalized_source)
        stored_source_hash = str(extra_data.get("ai_translation_source_hash") or "").strip()
        if stored_source_hash:
            return stored_source_hash == source_hash
        origin_description = str(extra_data.get("origin_description") or "").strip()
        if origin_description:
            return SyncUtil.text_sha256(origin_description) == source_hash
        legacy_source_description = str(extra_data.get("ai_translation_source_description") or "").strip()
        if legacy_source_description:
            return SyncUtil.text_sha256(legacy_source_description) == source_hash
        return False

    @classmethod
    def _resolve_sync_title(
        cls,
        db: Session,
        *,
        sync_object: TicketExternalSyncUpsertModel,
        ticket_id: int | None,
        current_user: CurrentUserModel,
    ) -> tuple[str, dict[str, Any]]:
        """
        解析外部同步工单标题：优先原始标题，其次轻量AI总结，最后回退描述截断。
        :param db: 数据库会话
        :param sync_object: 外部同步模型
        :param ticket_id: 工单ID
        :param current_user: 当前用户
        :return: (最终标题, 标题元信息)
        """
        raw_title = str(sync_object.title or "").strip()
        if raw_title:
            return raw_title, {"mode": "raw", "title": raw_title}
        description = str(sync_object.description or "").strip()
        if not description:
            return sync_object.ticket_no, {"mode": "fallback", "fallback_reason": "description_empty"}
        ai_title, title_meta = TicketLightAiService.summarize_ticket_title(
            db,
            description=description,
            source_type="ticket",
            source_id=ticket_id,
            source_ref=sync_object.ticket_no,
            current_user_name=_user_name(current_user),
        )
        normalized_ai_title = str(ai_title or "").strip()
        if normalized_ai_title:
            return normalized_ai_title, {**title_meta, "mode": "ai"}
        fallback_title = description[:100]
        return fallback_title, {**title_meta, "mode": "fallback", "fallback_title": fallback_title}

    @classmethod
    def _should_skip_ai_analysis_for_update_with_title(
        cls,
        *,
        ticket: Ticket | None,
        incoming_title: str,
        meta: dict[str, Any] | None = None,
    ) -> bool:
        """
        判断是否因“更新且已带标题”跳过 AI 分析类任务（标题总结/分类/日志参数提取）。
        :param ticket: 当前工单对象
        :param incoming_title: 本次入参标题
        :param meta: 可选同步元数据，用于补充判断是否更新场景
        :return: 是否跳过
        """
        if not ticket:
            return False
        if not str(incoming_title or "").strip():
            return False
        revision = SyncUtil.safe_int((meta or {}).get("revision"))
        if revision is None:
            return True
        return revision > 1

    @classmethod
    def _apply_ai_extract_to_sync_object(
        cls,
        sync_object: TicketExternalSyncUpsertModel,
        extract_result: dict[str, Any] | None,
    ) -> tuple[TicketExternalSyncUpsertModel, dict[str, Any]]:
        """
        将统一提取结果回填到同步对象（当前仅回填日志拉取参数）。
        :param sync_object: 外部同步对象
        :param extract_result: 统一提取结果
        :return: (回填后的同步对象, 回填摘要)
        """
        result = extract_result if isinstance(extract_result, dict) else {}
        pos_no = SyncUtil.safe_int(result.get("posNo"))
        sco_no = SyncUtil.safe_int(result.get("scoNo"))
        log_date = TicketSyncPayloadService.normalize_auto_log_pull_date_text(result.get("logDate"))

        log_pull_payload = (
            dict(sync_object.log_pull_config or {})
            if isinstance(sync_object.log_pull_config, dict)
            else {}
        )
        changed = False
        if pos_no:
            if SyncUtil.safe_int(log_pull_payload.get("posNo")) != pos_no:
                log_pull_payload["posNo"] = pos_no
                changed = True
        elif sco_no:
            if SyncUtil.safe_int(log_pull_payload.get("scoNo")) != sco_no:
                log_pull_payload["scoNo"] = sco_no
                changed = True
        if log_date:
            previous_date = TicketSyncPayloadService.normalize_auto_log_pull_date_text(
                log_pull_payload.get("modifyTime") or log_pull_payload.get("logDate")
            )
            if previous_date != log_date:
                log_pull_payload["modifyTime"] = log_date
                changed = True

        if not changed:
            return sync_object, {"updated": False}
        updated_sync_object = sync_object.model_copy(update={"log_pull_config": log_pull_payload})
        return updated_sync_object, {
            "updated": True,
            "logPullConfig": {
                "posNo": SyncUtil.safe_int(log_pull_payload.get("posNo")),
                "scoNo": SyncUtil.safe_int(log_pull_payload.get("scoNo")),
                "modifyTime": TicketSyncPayloadService.normalize_auto_log_pull_date_text(
                    log_pull_payload.get("modifyTime")
                ),
            },
        }

    @classmethod
    def _attach_sync_ai_extract_meta(
        cls,
        extra_data: dict[str, Any],
        *,
        extract_result: dict[str, Any] | None,
        extract_meta: dict[str, Any] | None,
        applied_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        将统一提取执行信息写入 extra_data，便于排查和复盘。
        :param extra_data: 工单扩展字段
        :param extract_result: 提取结果
        :param extract_meta: 提取元信息
        :param applied_meta: 回填摘要
        :return: 更新后的扩展字段
        """
        payload = dict(extra_data or {})
        if not isinstance(extract_meta, dict):
            return payload
        payload["ai_sync_extract"] = {
            "executedAt": SyncUtil.now_iso(),
            "result": extract_result if isinstance(extract_result, dict) else {},
            "meta": extract_meta,
            "applied": applied_meta if isinstance(applied_meta, dict) else {},
        }
        return payload

    @classmethod
    def _translate_sync_description(
        cls,
        db: Session,
        *,
        title: str,
        description: str,
        ticket_id: int | None,
        ticket_no: str,
        current_user: CurrentUserModel,
        enabled: bool,
    ) -> tuple[str, dict[str, Any], str]:
        origin_description = str(description or "").strip()
        if not origin_description:
            return "", {"translated_text": "", "skipped": True}, ""
        if not enabled:
            return origin_description, {"translated_text": "", "skipped": True}, origin_description
        translated_description, translation_meta = TicketLightAiService.translate_ticket_description(
            db,
            title=title,
            content=origin_description,
            source_type="ticket",
            source_id=ticket_id,
            source_ref=ticket_no,
            current_user_name=_user_name(current_user),
        )
        if translation_meta.get("skipped") or not str(translation_meta.get("translated_text") or "").strip():
            return origin_description, {**translation_meta, "skipped": True}, origin_description
        return translated_description, translation_meta, origin_description

    @classmethod
    def _merge_legacy_ai_classification_prompt_content(
        cls,
        current_config: dict[str, Any],
        next_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        保存同步配置时保留旧版内联 AI 分类提示词正文。

        新版页面只保存 Provider/Prompt 编码，提示词正文统一由 SysAiPromptTemplate 管理。
        仅在前端未显式提交 promptContent 字段时才保留旧值，避免字段缺失导致的历史数据丢失。
        如果前端显式提交了 promptContent（包括空字符串），则以前端值为准。
        :param current_config: 当前已生效配置。
        :param next_config: 本次待保存配置。
        :return: 合并后的配置。
        """
        current_ai_config = (
            current_config.get("aiClassification")
            if isinstance(current_config.get("aiClassification"), dict)
            else {}
        )
        next_ai_config = (
            next_config.get("aiClassification")
            if isinstance(next_config.get("aiClassification"), dict)
            else {}
        )
        # 仅在前端未显式提交 promptContent 字段时才保留旧值
        if "promptContent" not in next_ai_config:
            legacy_prompt_content = str(current_ai_config.get("promptContent") or "").strip()
            if legacy_prompt_content:
                next_ai_config["promptContent"] = legacy_prompt_content
                next_config["aiClassification"] = next_ai_config
        return next_config

    @classmethod
    def _resolve_ai_classification_scene_for_sync_status(
        cls,
        config: dict[str, Any],
        *,
        sync_scene: str,
        previous_status: str,
        current_status: str,
    ) -> tuple[str, bool, bool, str]:
        """
        解析同步入库后应使用的 AI 分类场景。

        外部同步和远端入库也可能带来状态变更。若目标状态命中状态变更自动归类配置，则优先
        使用状态变更场景；否则继续按原入库场景执行。
        :param config: 同步自动化配置。
        :param sync_scene: 原始入库场景。
        :param previous_status: 入库前状态。
        :param current_status: 入库后状态。
        :return: (source_type, enabled_by_scene, force_reclassify, reason)。
        """
        ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
        old_status = str(previous_status or "").strip()
        new_status = str(current_status or "").strip()
        trigger_statuses = [
            str(item or "").strip()
            for item in (ai_config.get("statusChangeTriggerStatuses") or [])
            if str(item or "").strip()
        ]
        if (
            old_status
            and new_status
            and old_status != new_status
            and bool(ai_config.get("runOnStatusChange"))
            and new_status in trigger_statuses
        ):
            return (
                f"{sync_scene}_status_change_auto_category",
                True,
                bool(ai_config.get("statusChangeForceReclassify")),
                f"status_changed:{old_status}->{new_status}",
            )
        return (
            f"{sync_scene}_auto_category",
            TicketAutoClassificationService.should_run_ai_classification_for_scene(config, sync_scene),
            False,
            "sync_scene",
        )

    @classmethod
    def sync_external_ticket(
        cls,
        db: Session,
        sync_object: TicketExternalSyncUpsertModel,
        current_user: CurrentUserModel,
        sync_scene: str = "external_sync",
        defer_post_process: bool = False,
    ) -> CrudResponseModel:
        """
        外部工单同步入库并按配置执行后续动作。

        :param db: 数据库会话。
        :param sync_object: 外部同步入参。
        :param current_user: 当前登录用户。
        :param sync_scene: 同步触发场景，支持 external_sync/remote_pull。
        :param defer_post_process: 是否延后执行AI、自动化和群推送，开启后先快速入库返回。
        :return: 同步结果。
        """
        ticket = TicketDao.get_ticket_by_no(db, sync_object.ticket_no)
        config = TicketSyncConfigService.load_sync_config(db)
        automation = sync_object.automation
        if sync_scene == "external_sync":
            sync_object = TicketExternalBitableEmailService.enrich_person_emails(config, sync_object, ticket)
        raw_title = str(sync_object.title or "").strip()
        existing_title = str(ticket.title or "").strip() if ticket else ""
        skip_ai_analysis_due_to_update_title = cls._should_skip_ai_analysis_for_update_with_title(
            ticket=ticket,
            incoming_title=raw_title,
        )
        ai_extract_result: dict[str, Any] = {}
        ai_extract_meta: dict[str, Any] = {"skipped": True}
        ai_extract_apply_meta: dict[str, Any] = {"updated": False}
        title_meta: dict[str, Any] = {"mode": "raw", "title": raw_title}
        if defer_post_process:
            # 延后AI时先用稳定兜底标题入库，避免主链路被AI网络调用阻塞。
            resolved_title = raw_title or existing_title or str(sync_object.description or "").strip()[:100]
            if not resolved_title:
                resolved_title = sync_object.ticket_no
            if resolved_title != raw_title:
                sync_object = sync_object.model_copy(update={"title": resolved_title})
            if not raw_title and existing_title:
                title_meta = {"mode": "keep_existing", "title": existing_title}
            elif not raw_title:
                title_meta = {"mode": "fallback", "fallback_title": resolved_title}
        else:
            if skip_ai_analysis_due_to_update_title:
                logger.info(
                    f"外部工单同步跳过统一提取与标题AI：更新场景且已携带标题, "
                    f"ticket_no={sync_object.ticket_no}"
                )
            else:
                try:
                    ai_extract_result, ai_extract_meta = TicketLightAiService.extract_ticket_sync_fields(
                        db,
                        title=raw_title or existing_title,
                        description=str(sync_object.description or "").strip(),
                        raw_payload=sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {},
                        source_type=f"{sync_scene}_sync_extract",
                        source_id=getattr(ticket, "ticket_id", None),
                        source_ref=sync_object.ticket_no,
                        current_user_name=_user_name(current_user),
                    )
                    sync_object, ai_extract_apply_meta = cls._apply_ai_extract_to_sync_object(
                        sync_object,
                        ai_extract_result,
                    )
                except Exception as exc:
                    logger.warning(
                        f"外部工单同步统一提取执行失败，已继续后续流程: ticket_no={sync_object.ticket_no}, error={exc}"
                    )
                    ai_extract_result = {}
                    ai_extract_meta = {"skipped": True, "error": str(exc)}
                    ai_extract_apply_meta = {"updated": False}
            resolved_title = raw_title or existing_title
            if resolved_title:
                if not raw_title and existing_title:
                    title_meta = {"mode": "keep_existing", "title": existing_title}
            else:
                ai_extract_title = str((ai_extract_result or {}).get("title") or "").strip()
                if ai_extract_title:
                    resolved_title = ai_extract_title
                    title_meta = {"mode": "ai_extract", "title": ai_extract_title}
                else:
                    try:
                        resolved_title, title_meta = cls._resolve_sync_title(
                            db,
                            sync_object=sync_object,
                            ticket_id=getattr(ticket, "ticket_id", None),
                            current_user=current_user,
                        )
                    except Exception as exc:
                        logger.warning(
                            f"外部工单同步标题处理异常，已回退描述截断: "
                            f"ticket_no={sync_object.ticket_no}, error={exc}"
                        )
                        resolved_title = str(sync_object.description or "").strip()[:100]
                        if not resolved_title:
                            resolved_title = sync_object.ticket_no
                        title_meta = {"mode": "fallback", "fallback_title": resolved_title, "error": str(exc)}
            if resolved_title != raw_title:
                sync_object = sync_object.model_copy(update={"title": resolved_title})
        apply_external_mappings = sync_scene != "remote_pull"
        detected = TicketSyncAutomationService.detect_fields(
            db,
            sync_object,
            config,
            apply_external_mappings=apply_external_mappings,
        )
        should_translate = False
        translated_description = str(sync_object.description or "").strip()
        translation_meta: dict[str, Any] = {"translated_text": "", "skipped": True}
        origin_description = str(sync_object.description or "").strip()
        if not defer_post_process:
            translation_enabled = TicketLightAiService.is_translation_enabled(db)
            translation_already_succeeded = cls._has_successful_ai_translation(
                ticket,
                source_description=sync_object.description,
            )
            if sync_scene == "remote_pull":
                sync_translate_enabled = bool(
                    automation.auto_translate
                    if automation is not None
                    else (config.get("remoteSync") or {}).get("autoTranslateOnPull", True)
                )
            else:
                sync_translate_enabled = bool(
                    automation.auto_translate if automation is not None else config.get("autoTranslateOnSync", True)
                )
            should_translate = translation_enabled and sync_translate_enabled and not translation_already_succeeded
            logger.info(
                f"外部工单同步翻译决策: ticket_no={sync_object.ticket_no}, scene={sync_scene}, "
                f"global_switch={translation_enabled}, scene_switch={sync_translate_enabled}, "
                f"already_translated={translation_already_succeeded}, should_translate={should_translate}"
            )
            try:
                translated_description, translation_meta, origin_description = cls._translate_sync_description(
                    db,
                    title=sync_object.title or "",
                    description=sync_object.description,
                    ticket_id=getattr(ticket, "ticket_id", None),
                    ticket_no=sync_object.ticket_no,
                    current_user=current_user,
                    enabled=should_translate,
                )
            except Exception as exc:
                logger.warning(
                    "外部工单同步翻译异常，已回退原文: "
                    f"ticket_no={sync_object.ticket_no}, scene={sync_scene}, error={exc}"
                )
                translated_description = str(sync_object.description or "").strip()
                translation_meta = {"translated_text": "", "skipped": True, "error": str(exc)}
                origin_description = str(sync_object.description or "").strip()
            if should_translate:
                sync_object = sync_object.model_copy(update={"description": translated_description})
        previous_status = str(getattr(ticket, "status", "") or "").strip() if ticket else ""
        payload, meta, revision = TicketSyncPayloadService.build_upsert_payload(
            db,
            ticket,
            sync_object,
            detected,
            current_user,
            sync_scene=sync_scene,
        )
        if defer_post_process:
            meta["sourceStatusBefore"] = previous_status
            meta = TicketSyncGroupPushService.set_publish_state(
                meta,
                ready=False,
                status=cls.PUBLISH_STATUS_PROCESSING_AI,
                reason="工单已入库，等待后台后处理完成",
                ai_task_status="pending",
            )
            extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
            extra_data = TicketSyncPayloadService.attach_meta(extra_data, meta)
            payload["extra_data"] = extra_data
        if title_meta and title_meta.get("mode") != "raw":
            extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
            extra_data["title_summary"] = title_meta
            payload["extra_data"] = extra_data
        if should_translate and origin_description and str(translation_meta.get("translated_text") or "").strip():
            extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
            extra_data["origin_description"] = origin_description
            extra_data["ai_translation"] = translation_meta.get("translated_text") or translated_description
            extra_data["ai_translation_source_hash"] = SyncUtil.text_sha256(origin_description)
            if translation_meta.get("provider_code"):
                extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
            if translation_meta.get("prompt_code"):
                extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
            payload["extra_data"] = extra_data
        if not defer_post_process and isinstance(ai_extract_meta, dict):
            if not bool(ai_extract_meta.get("skipped")) or str(ai_extract_meta.get("error") or "").strip():
                extra_data = (
                    dict(payload.get("extra_data") or {})
                    if isinstance(payload.get("extra_data"), dict)
                    else {}
                )
                extra_data = cls._attach_sync_ai_extract_meta(
                    extra_data,
                    extract_result=ai_extract_result,
                    extract_meta=ai_extract_meta,
                    applied_meta=ai_extract_apply_meta,
                )
                payload["extra_data"] = extra_data
        now = datetime.now()
        try:
            created = ticket is None
            if created:
                ticket = Ticket(**payload)
                ticket = TicketDao.add_ticket(db, ticket)
                TicketDao.add_status_history(
                    db,
                    TicketStatusHistory(
                        ticket_id=ticket.ticket_id,
                        from_status=None,
                        to_status=ticket.status,
                        operator_id=_user_id(current_user),
                        operator_name=_user_name(current_user),
                        started_at=now,
                        comment="外部同步创建工单",
                    ),
                )
                TicketDao.add_message(
                    db,
                    TicketMessage(
                        ticket_id=ticket.ticket_id,
                        role="system",
                        message_type="sync_import",
                        content=f"外部同步创建工单\n\n{sync_object.title}\n\n{sync_object.description or ''}".strip(),
                        attachments={"source": meta.get("source"), "revision": revision},
                        reference_type="sync",
                        created_by_id=_user_id(current_user),
                        created_by_name=_user_name(current_user),
                        create_time=now,
                    ),
                )
            else:
                TicketDao.update_ticket(db, ticket.ticket_id, payload)
            TicketDao.add_event(
                db,
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=(
                        TicketEventType.TICKET_UPDATED.value
                        if not created
                        else TicketEventType.TICKET_CREATED.value
                    ),
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content="外部工单同步导入" if created else "外部工单同步更新",
                    event_data={
                        "syncRevision": revision,
                        "sourceSystem": meta.get("sourceSystem"),
                        "sourceRecordId": meta.get("sourceRecordId"),
                        "detected": detected,
                    },
                    create_time=now,
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        step_reason_summary = None
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            if sync_scene == "remote_pull":
                step_reason_summary = TicketSyncCommentService.sync_remote_payload_comments(
                    db,
                    ticket=ticket,
                    sync_object=sync_object,
                )
                if step_reason_summary.get("skipped"):
                    step_reason_summary = TicketSyncCommentService.sync_step_reason_comments(
                        db,
                        ticket=ticket,
                        sync_object=sync_object,
                    )
            else:
                step_reason_summary = TicketSyncCommentService.sync_step_reason_comments(
                    db,
                    ticket=ticket,
                    sync_object=sync_object,
                )
            if step_reason_summary and not step_reason_summary.get("skipped"):
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                f"外部工单同步排查过程入库失败: ticket_no={sync_object.ticket_no}, "
                f"scene={sync_scene}, error={exc}"
            )

        if defer_post_process:
            result = (
                TicketService.get_ticket_detail_services(db, ticket.ticket_id)
                or CamelCaseUtil.transform_result(ticket)
            )
            result["syncSummary"] = TicketSyncDeliveryService.extract_sync_summary(result.get("extraData"))
            result["syncDeferred"] = True
            if step_reason_summary:
                result["syncStepReason"] = step_reason_summary
            return CrudResponseModel(
                is_success=True,
                message="外部工单同步成功（AI与自动化已转后台处理）",
                result=result,
            )

        category_summary = None
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            source_type, enabled_by_scene, force_reclassify, classify_reason = (
                cls._resolve_ai_classification_scene_for_sync_status(
                    config,
                    sync_scene=sync_scene,
                    previous_status=previous_status,
                    current_status=str(ticket.status or "").strip(),
                )
            )
            if skip_ai_analysis_due_to_update_title and not classify_reason.startswith("status_changed:"):
                category_summary = {"skipped": True, "skipReason": "更新场景且已携带标题，跳过AI分类"}
                logger.info(
                    f"外部工单同步自动分类跳过: ticket_no={sync_object.ticket_no}, "
                    f"reason=更新场景且已携带标题，未命中状态变更分类"
                )
            else:
                logger.info(
                    f"外部工单同步自动分类场景: ticket_no={sync_object.ticket_no}, "
                    f"source_type={source_type}, enabled_by_scene={enabled_by_scene}, "
                    f"force_reclassify={force_reclassify}, reason={classify_reason}"
                )
                ticket, category_summary = TicketAutoClassificationService.run_auto_ticket_ai_classification(
                    db,
                    ticket=ticket,
                    title=str(sync_object.title or ticket.title or "").strip(),
                    description=str(sync_object.description or ticket.description or "").strip(),
                    current_user_name=_user_name(current_user),
                    source_type=source_type,
                    source_ref=sync_object.ticket_no,
                    force_reclassify=force_reclassify,
                    enabled_by_scene=enabled_by_scene,
                )
        except Exception as exc:
            logger.warning(f"外部工单同步自动分类执行失败: ticket_no={sync_object.ticket_no}, error={exc}")

        should_run_automation = bool(
            (
                automation
                and (
                    automation.auto_identify
                    or automation.auto_log_pull
                    or automation.auto_ai_analysis
                )
            )
            or config.get("autoRunOnSync")
        )
        automation_summary = None
        if should_run_automation:
            automation_summary = TicketSyncAutomationService.run_sync_automation(
                db,
                ticket.ticket_id,
                sync_object,
                detected,
                current_user,
            )

        group_push_summary = None
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            ticket, _, group_push_summary = TicketSyncGroupPushService.finalize_publish_state_after_post_process(
                db,
                ticket=ticket,
                sync_scene=sync_scene,
                update_by=_user_name(current_user),
            )
        except Exception as exc:
            logger.warning(
                f"工单同步发布状态收敛失败: ticket_no={sync_object.ticket_no}, "
                f"scene={sync_scene}, error={exc}"
            )

        result = (
            TicketService.get_ticket_detail_services(db, ticket.ticket_id)
            or CamelCaseUtil.transform_result(ticket)
        )
        result["syncSummary"] = TicketSyncDeliveryService.extract_sync_summary(result.get("extraData"))
        if automation_summary:
            result["syncAutomation"] = automation_summary
        if category_summary:
            result["syncCategory"] = category_summary
        if group_push_summary is not None:
            result["syncGroupPush"] = group_push_summary
        if step_reason_summary:
            result["syncStepReason"] = step_reason_summary
        return CrudResponseModel(
            is_success=True,
            message="外部工单同步成功",
            result=result,
        )

