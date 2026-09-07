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
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.core.ticket_version_service import TicketVersionService
from modules.ticket.service.sync.ticket_automation_scope_service import TicketAutomationScopeService
from modules.ticket.service.sync.ticket_external_bitable_email_service import TicketExternalBitableEmailService
from modules.ticket.service.sync.ticket_external_classification_mapping_service import (
    TicketExternalClassificationMappingService,
)
from modules.ticket.service.sync.ticket_sync_ai_field_service import TicketSyncAiFieldService
from modules.ticket.service.sync.ticket_sync_automation_service import TicketSyncAutomationService
from modules.ticket.service.sync.ticket_sync_comment_service import TicketSyncCommentService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_delivery_service import TicketSyncDeliveryService
from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.service.sync.ticket_sync_post_process_service import TicketSyncPostProcessService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import (
    user_id as _user_id,
)
from modules.ticket.util.ticket_common_util import (
    user_name as _user_name,
)
from modules.ticket.util.ticket_store_resolution_util import TicketStoreResolutionUtil
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class TicketSyncService:
    """
    工单外部同步服务，统一处理外部推送、内网拉取和同步后自动化状态追踪。

    已提取的子服务（见对应文件，调用方应直接依赖对应子服务）：
    - TicketSyncConfigService (ticket_sync_config_service.py): 配置管理
    - TicketSyncPostProcessService (ticket_sync_post_process_service.py): 翻译/标题/分类场景解析等
      可复用业务判定，本服务内不再保留重复实现
    - SyncUtil (util/sync_util.py): 通用工具方法
    后续仅剩外部同步入库主编排仍在本服务内。
    """

    PUBLISH_STATUS_PROCESSING_AI = "processing_ai"

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
        if sync_scene in ("external_sync", "bitable_pull"):
            sync_object = TicketExternalBitableEmailService.enrich_person_emails(config, sync_object, ticket)
        apply_external_mappings = sync_scene != "remote_pull"
        detected = TicketSyncAutomationService.detect_fields(
            db,
            sync_object,
            config,
            apply_external_mappings=apply_external_mappings,
        )
        scope_decision = TicketAutomationScopeService.evaluate_detected_module(config, detected)
        scope_allowed = scope_decision.eligible
        sync_extra_data = TicketAutomationScopeService.attach_audit_data(
            sync_object.extra_data,
            scope_decision,
        )

        # 模块映射审计写入 extra_data
        module_result = (detected or {}).get("moduleMappingResult") if isinstance(detected, dict) else None
        if module_result is not None:
            if not isinstance(sync_extra_data, dict):
                sync_extra_data = {}
            sync_extra_data["module_mapping"] = {
                "mappingMatched": module_result.mapping_matched,
                "mappedModuleId": module_result.mapped_module_id,
                "mappedModuleCode": module_result.mapped_module_code,
                "mappedModuleName": module_result.mapped_module_name,
                "resolvedModuleId": module_result.resolved_module_id,
                "resolvedModuleCode": module_result.resolved_module_code,
                "resolvedModuleName": module_result.resolved_module_name,
                "matchedBy": module_result.matched_by,
                "matchedAt": SyncUtil.now_iso(),
            }

        sync_object = sync_object.model_copy(update={"extra_data": sync_extra_data})
        logger.info(
            f"外部工单同步自动化范围判定: ticket_no={sync_object.ticket_no}, scene={sync_scene}, "
            f"eligible={scope_allowed}, module_id={scope_decision.module_id}, "
            f"module_name={scope_decision.module_name!r}, matched_by={scope_decision.matched_by}, "
            f"matched_value={scope_decision.matched_value!r}, reason={scope_decision.reason}"
        )
        raw_title = str(sync_object.title or "").strip()
        existing_title = str(ticket.title or "").strip() if ticket else ""
        cached_extract_state = {}
        if ticket and isinstance(ticket.extra_data, dict):
            cached_extract_state = (
                ticket.extra_data.get("ai_sync_extract")
                if isinstance(ticket.extra_data.get("ai_sync_extract"), dict)
                else {}
            )
        ai_extract_result: dict[str, Any] = {}
        ai_extract_meta: dict[str, Any] = {"skipped": True}
        ai_extract_apply_meta: dict[str, Any] = {"updated": False}
        title_meta: dict[str, Any] = {"mode": "raw", "title": raw_title}
        # AI统一提取：三场景（外部推送/远端拉取/多维表格拉取）均执行，由场景独立开关控制
        if not scope_allowed:
            logger.info(
                f"外部工单同步跳过统一提取与标题AI: ticket_no={sync_object.ticket_no}, "
                f"reason={scope_decision.reason}"
            )
        elif defer_post_process:
            logger.info(
                f"外部工单同步延后处理：主入库阶段跳过统一提取，交由后台按指纹执行, "
                f"ticket_no={sync_object.ticket_no}, scene={sync_scene}"
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
                    sync_scene=sync_scene,
                    cached_extract_state=cached_extract_state,
                    source_fields={
                        "projectName": sync_object.project_name or sync_object.merchant_name,
                        "moduleName": sync_object.module_name,
                        "sourceStoreCode": TicketStoreResolutionUtil.resolve_source_store_code(
                            raw_payload=sync_object.raw_payload,
                            extra_data=sync_object.extra_data,
                            log_pull_config=sync_object.log_pull_config,
                        ),
                    },
                )
                sync_object, ai_extract_apply_meta = TicketSyncAiFieldService.apply_extract_to_sync_object(
                    sync_object,
                    ai_extract_result,
                )
                # AI 回填后重新识别，确保自动化使用本次提取后的统一字段。
                detected = TicketSyncAutomationService.detect_fields(
                    db,
                    sync_object,
                    config,
                    apply_external_mappings=apply_external_mappings,
                )
            except Exception as exc:
                logger.warning(
                    f"外部工单同步统一提取执行失败，已继续后续流程: ticket_no={sync_object.ticket_no}, error={exc}"
                )
                ai_extract_result = {}
                ai_extract_meta = {"skipped": True, "error": str(exc)}
                ai_extract_apply_meta = {"updated": False}

        # 标题处理：defer_post_process场景用兜底标题快速入库，其他场景可用AI提取标题
        if defer_post_process:
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
            resolved_title = raw_title or existing_title
            if resolved_title:
                if not raw_title and existing_title:
                    title_meta = {"mode": "keep_existing", "title": existing_title}
            else:
                ai_extract_title = str((ai_extract_result or {}).get("title") or "").strip()
                if ai_extract_title:
                    resolved_title = ai_extract_title
                    title_meta = {"mode": "ai_extract", "title": ai_extract_title}
                elif not scope_allowed:
                    resolved_title = str(sync_object.description or "").strip()[:100] or sync_object.ticket_no
                    title_meta = {"mode": "fallback", "fallback_title": resolved_title, "reason": scope_decision.reason}
                else:
                    try:
                        resolved_title, title_meta = TicketSyncPostProcessService.resolve_sync_title(
                            db,
                            sync_object=sync_object,
                            ticket_id=getattr(ticket, "ticket_id", None),
                            current_user=current_user,
                        )
                    except Exception as exc:
                        logger.warning(
                            f"外部工单同步标题处理异常，已回退描述截断: ticket_no={sync_object.ticket_no}, error={exc}"
                        )
                        resolved_title = str(sync_object.description or "").strip()[:100]
                        if not resolved_title:
                            resolved_title = sync_object.ticket_no
                        title_meta = {"mode": "fallback", "fallback_title": resolved_title, "error": str(exc)}
            if resolved_title != raw_title:
                sync_object = sync_object.model_copy(update={"title": resolved_title})
        external_classification_match = None
        if str(getattr(ticket, "classification_source", "") or "").strip() != "manual":
            external_classification_match = TicketExternalClassificationMappingService.match(config, sync_object)
            if external_classification_match:
                extra_data = dict(sync_object.extra_data or {}) if isinstance(sync_object.extra_data, dict) else {}
                extra_data["external_classification"] = {
                    "ruleId": external_classification_match.rule_id,
                    "sourceField": external_classification_match.source_field,
                    "sourceValue": external_classification_match.source_value,
                    "operator": external_classification_match.operator,
                    "matchedAt": SyncUtil.now_iso(),
                }
                sync_object = sync_object.model_copy(update={
                    "issue_type_id": external_classification_match.issue_type_id,
                    "issue_type_name": external_classification_match.issue_type_name,
                    "extra_data": extra_data,
                })
                logger.info(
                    f"外部字段工单类型映射命中: ticket_no={sync_object.ticket_no}, "
                    f"rule_id={external_classification_match.rule_id}, "
                    f"issue_type={external_classification_match.issue_type_id}"
                )
        should_translate = False
        translated_description = str(sync_object.description or "").strip()
        translation_meta: dict[str, Any] = {"translated_text": "", "skipped": True}
        origin_description = str(sync_object.description or "").strip()
        if not defer_post_process:
            translation_enabled = TicketLightAiService.is_translation_enabled(db)
            translate_config = config.get("translateConfig") if isinstance(config.get("translateConfig"), dict) else {}
            translate_config_enabled = bool(translate_config.get("enabled", False))
            sync_translate_enabled = (
                bool(automation.auto_translate)
                if automation is not None
                else TicketSyncPostProcessService.resolve_translate_enabled_by_scene(
                    sync_scene, translate_config, translate_config_enabled
                )
            )
            translation_already_succeeded = TicketSyncPostProcessService.has_successful_ai_translation(
                ticket,
                source_description=sync_object.description,
            )
            should_translate = (
                scope_allowed and translation_enabled and sync_translate_enabled and not translation_already_succeeded
            )
            logger.info(
                f"外部工单同步翻译决策: ticket_no={sync_object.ticket_no}, scene={sync_scene}, "
                f"global_switch={translation_enabled}, scene_switch={sync_translate_enabled}, "
                f"scope_allowed={scope_allowed}, already_translated={translation_already_succeeded}, "
                f"should_translate={should_translate}"
            )
            try:
                translated_description, translation_meta, origin_description = (
                    TicketSyncPostProcessService.translate_sync_description(
                        db,
                        title=sync_object.title or "",
                        description=sync_object.description,
                        ticket_id=getattr(ticket, "ticket_id", None),
                        ticket_no=sync_object.ticket_no,
                        current_user=current_user,
                        enabled=should_translate,
                    )
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
        if external_classification_match:
            payload["classification_source"] = "external_mapping"
            payload["classification_rule_id"] = external_classification_match.rule_id
            payload["classification_updated_at"] = datetime.now()
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
            extra_data["ai_translation"] = str(translation_meta.get("translated_text") or "").strip()
            extra_data["ai_translation_source_hash"] = SyncUtil.text_sha256(origin_description)
            if translation_meta.get("provider_code"):
                extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
            if translation_meta.get("prompt_code"):
                extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
            payload["extra_data"] = extra_data
        if not defer_post_process and isinstance(ai_extract_meta, dict):
            if not bool(ai_extract_meta.get("skipped")) or str(ai_extract_meta.get("error") or "").strip():
                extra_data = (
                    dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
                )
                extra_data = TicketSyncPostProcessService.attach_sync_ai_extract_meta(
                    extra_data,
                    extract_result=ai_extract_result,
                    extract_meta=ai_extract_meta,
                    applied_meta=ai_extract_apply_meta,
                )
                payload["extra_data"] = extra_data
        now = datetime.now()
        try:
            detected_version_key = str(payload.pop("_detected_affected_version_key", "") or "").strip()
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
                ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            TicketVersionService.validate_ticket_version_ids(db, ticket)
            if not ticket.affected_version_id and detected_version_key:
                TicketVersionService.assign_detected_ticket_version(
                    db,
                    ticket,
                    version_type="affected",
                    version_key=detected_version_key,
                    source=sync_scene,
                )
            TicketDao.add_event(
                db,
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=(
                        TicketEventType.TICKET_UPDATED.value if not created else TicketEventType.TICKET_CREATED.value
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
                f"外部工单同步排查过程入库失败: ticket_no={sync_object.ticket_no}, scene={sync_scene}, error={exc}"
            )

        if defer_post_process:
            result = TicketService.get_ticket_detail_services(db, ticket.ticket_id) or CamelCaseUtil.transform_result(
                ticket
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
                TicketSyncPostProcessService.resolve_ai_classification_scene_for_sync_status(
                    config,
                    sync_scene=sync_scene,
                    previous_status=previous_status,
                    current_status=str(ticket.status or "").strip(),
                )
            )
            if not scope_allowed:
                category_summary = {"skipped": True, "skipReason": scope_decision.reason}
                logger.info(
                    f"外部工单同步自动分类跳过: ticket_no={sync_object.ticket_no}, "
                    f"reason={scope_decision.reason}"
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
            (automation and (automation.auto_identify or automation.auto_log_pull or automation.auto_ai_analysis))
            or TicketSyncPostProcessService.should_run_automation_by_config(config, sync_scene)
        )
        automation_summary = None
        if should_run_automation and scope_allowed:
            automation_summary = TicketSyncAutomationService.run_sync_automation(
                db,
                ticket.ticket_id,
                sync_object,
                detected,
                current_user,
                sync_scene=sync_scene,
            )
        elif should_run_automation:
            automation_summary = {"skipped": True, "skipReason": scope_decision.reason}
            logger.info(
                f"外部工单同步自动化跳过: ticket_no={sync_object.ticket_no}, reason={scope_decision.reason}"
            )

        # 非延后路径（当前仅远端拉取）内联执行向量刷新，保证 sceneTriggers.remotePull 等场景
        # 开关在同步入库链路生效；延后路径（external_sync/bitable_pull/manual_create）由
        # TicketSyncPostProcessService.execute_deferred_sync_post_process 统一刷新，不在此重复执行。
        if not defer_post_process and scope_allowed:
            try:
                vector_scene_map = {
                    "remote_pull": "remotePull",
                    "bitable_pull": "bitablePull",
                    "external_sync": "externalSync",
                    "manual_create": "manualCreate",
                }
                vector_scene = vector_scene_map.get(sync_scene, "externalSync")
                TicketEmbeddingService.vectorize_ticket_for_scene(db, ticket, vector_scene)
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning(
                    f"外部工单同步向量刷新失败: ticket_no={sync_object.ticket_no}, "
                    f"scene={sync_scene}, error={exc}"
                )
                ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket

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
                f"工单同步发布状态收敛失败: ticket_no={sync_object.ticket_no}, scene={sync_scene}, error={exc}"
            )

        result = TicketService.get_ticket_detail_services(db, ticket.ticket_id) or CamelCaseUtil.transform_result(
            ticket
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
