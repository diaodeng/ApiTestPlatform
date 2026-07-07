"""
工单外部同步延后后处理服务。

负责外部同步入库后的异步任务投递、Celery/本地后台运行入口，以及 AI 提取、
翻译、自动分类、自动化、向量刷新和发布状态收敛。
"""
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from config.database import SessionLocal
from context.request_context import get_current_trace_id, trace_context
from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.ai.ticket_auto_classification_service import TicketAutoClassificationService
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.sync.ticket_sync_automation_service import TicketSyncAutomationService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import user_name as _user_name
from utils.log_util import logger


class TicketSyncPostProcessService:
    """外部同步延后后处理任务编排。"""

    CELERY_DISPATCH_MODE = "celery"
    BACKGROUND_DISPATCH_MODE = "background"

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
    def dispatch_deferred_sync_post_process_task(
        cls,
        sync_payload: dict[str, Any],
        current_user_payload: dict[str, Any],
        sync_scene: str = "external_sync",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """
        分发外部工单延后后处理任务。
        :param sync_payload: 外部同步入参字典。
        :param current_user_payload: 当前用户字典。
        :param sync_scene: 同步触发场景。
        :param trace_id: 日志追踪ID，用于串联入库请求与延后后处理。
        :return: 分发结果摘要。
        """
        ticket_no = str(sync_payload.get("ticketNo") or sync_payload.get("ticket_no") or "").strip()
        resolved_trace_id = str(trace_id or "").strip() or get_current_trace_id(default="")
        if not cls.is_celery_worker_available():
            return {
                "mode": cls.BACKGROUND_DISPATCH_MODE,
                "celeryAvailable": False,
                "reason": "celery_worker_unavailable",
                "ticketNo": ticket_no or None,
            }
        try:
            from config.celery_app import celery_app
            from module_task.celery_contract import CELERY_TICKET_SYNC_DEFERRED_POST_PROCESS_TASK

            async_result = celery_app.send_task(
                CELERY_TICKET_SYNC_DEFERRED_POST_PROCESS_TASK,
                args=[sync_payload, current_user_payload, sync_scene, resolved_trace_id],
            )
            task_id = str(getattr(async_result, "id", "") or "").strip()
            logger.info(
                f"外部工单延后后处理已投递Celery: ticket_no={ticket_no or '-'}, "
                f"sync_scene={sync_scene}, celery_task_id={task_id or '-'}"
            )
            return {
                "mode": cls.CELERY_DISPATCH_MODE,
                "celeryAvailable": True,
                "taskName": CELERY_TICKET_SYNC_DEFERRED_POST_PROCESS_TASK,
                "taskId": task_id or None,
                "ticketNo": ticket_no or None,
            }
        except Exception as exc:
            logger.warning(
                f"外部工单延后后处理投递Celery失败，降级本地后台任务: "
                f"ticket_no={ticket_no or '-'}, sync_scene={sync_scene}, error={exc}"
            )
            return {
                "mode": cls.BACKGROUND_DISPATCH_MODE,
                "celeryAvailable": False,
                "reason": f"celery_dispatch_failed:{exc}",
                "ticketNo": ticket_no or None,
            }

    @classmethod
    def is_celery_worker_available(cls) -> bool:
        """
        判断 Celery Worker 当前是否可用（基于 inspect.ping）。
        :return: Worker 可用返回 True，否则返回 False。
        """
        try:
            from config.celery_app import celery_app

            inspector = celery_app.control.inspect(timeout=1.0)
            ping_result = inspector.ping() if inspector else {}
            return bool(ping_result)
        except Exception as exc:
            logger.warning(f"检测Celery可用性失败，降级本地后台任务: error={exc}")
            return False

    @classmethod
    def run_deferred_sync_post_process(
        cls,
        sync_payload: dict[str, Any],
        current_user_payload: dict[str, Any],
        sync_scene: str = "external_sync",
        trace_id: str | None = None,
    ) -> None:
        """
        执行外部工单同步的延后后处理任务（AI、自动化、群推送）。
        :param sync_payload: 外部同步入参字典。
        :param current_user_payload: 当前用户字典。
        :param sync_scene: 同步触发场景。
        :param trace_id: 日志追踪ID，用于本地后台任务日志串联。
        :return: 无。
        """
        if trace_id:
            with trace_context(trace_id):
                cls.run_deferred_sync_post_process(sync_payload, current_user_payload, sync_scene)
            return

        query_db = SessionLocal()
        try:
            sync_object = TicketExternalSyncUpsertModel.model_validate(sync_payload)
            current_user = CurrentUserModel.model_validate(cls.normalize_current_user_payload(current_user_payload))
            cls.execute_deferred_sync_post_process(query_db, sync_object, current_user, sync_scene)
        except Exception as exc:
            logger.warning(
                f"外部工单同步延后后处理异常: "
                f"ticket_no={sync_payload.get('ticketNo') or sync_payload.get('ticket_no')}, error={exc}"
            )
        finally:
            query_db.close()

    @classmethod
    def execute_deferred_sync_post_process(
        cls,
        db: Session,
        sync_object: TicketExternalSyncUpsertModel,
        current_user: CurrentUserModel,
        sync_scene: str,
    ) -> None:
        """
        处理外部同步入库后的重任务，避免阻塞主入库链路。
        :param db: 数据库会话。
        :param sync_object: 外部同步入参。
        :param current_user: 当前用户。
        :param sync_scene: 同步触发场景。
        :return: 无。
        """
        ticket = TicketDao.get_ticket_by_no(db, sync_object.ticket_no)
        if not ticket:
            logger.warning(f"外部工单同步延后后处理跳过: 未找到工单 ticket_no={sync_object.ticket_no}")
            return
        config = TicketSyncConfigService.load_sync_config(db)
        automation = sync_object.automation
        update_data: dict[str, Any] = {}
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        existing_title = str(ticket.title or "").strip()
        incoming_title = str(sync_object.title or "").strip()
        meta = TicketSyncPayloadService.build_meta(extra_data)
        skip_ai_analysis_due_to_update_title = cls.should_skip_ai_analysis_for_update_with_title(
            ticket=ticket,
            incoming_title=incoming_title,
            meta=meta,
        )
        ai_extract_result: dict[str, Any] = {}
        ai_extract_meta: dict[str, Any] = {"skipped": True}
        ai_extract_apply_meta: dict[str, Any] = {"updated": False}

        if skip_ai_analysis_due_to_update_title:
            logger.info(
                f"外部工单同步延后处理跳过统一提取与分类AI：更新场景且已携带标题, "
                f"ticket_no={sync_object.ticket_no}"
            )
        else:
            try:
                ai_extract_result, ai_extract_meta = TicketLightAiService.extract_ticket_sync_fields(
                    db,
                    title=incoming_title or existing_title,
                    description=str(sync_object.description or "").strip(),
                    raw_payload=sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {},
                    source_type=f"{sync_scene}_sync_extract",
                    source_id=ticket.ticket_id,
                    source_ref=sync_object.ticket_no,
                    current_user_name=_user_name(current_user),
                    sync_scene=sync_scene,
                )
                sync_object, ai_extract_apply_meta = cls.apply_ai_extract_to_sync_object(
                    sync_object,
                    ai_extract_result,
                )
                ai_extract_title = str((ai_extract_result or {}).get("title") or "").strip()
                if not incoming_title and not existing_title and ai_extract_title:
                    update_data["title"] = ai_extract_title
                    extra_data["title_summary"] = {"mode": "ai_extract", "title": ai_extract_title}
            except Exception as exc:
                logger.warning(f"外部工单同步延后统一提取失败: ticket_no={sync_object.ticket_no}, error={exc}")
                ai_extract_result = {}
                ai_extract_meta = {"skipped": True, "error": str(exc)}
                ai_extract_apply_meta = {"updated": False}

        try:
            if not incoming_title and not existing_title and "title" not in update_data:
                resolved_title, title_meta = cls.resolve_sync_title(
                    db,
                    sync_object=sync_object,
                    ticket_id=ticket.ticket_id,
                    current_user=current_user,
                )
                if resolved_title and resolved_title != str(ticket.title or "").strip():
                    update_data["title"] = resolved_title
                if title_meta and title_meta.get("mode") != "raw":
                    extra_data["title_summary"] = title_meta
        except Exception as exc:
            logger.warning(f"外部工单同步延后标题处理失败: ticket_no={sync_object.ticket_no}, error={exc}")

        try:
            translation_enabled = TicketLightAiService.is_translation_enabled(db)
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
            translation_already_succeeded = cls.has_successful_ai_translation(
                ticket,
                source_description=sync_object.description,
            )
            should_translate = translation_enabled and sync_translate_enabled and not translation_already_succeeded
            if translation_already_succeeded:
                logger.info(f"外部工单同步延后翻译跳过：已有历史翻译结果, ticket_no={sync_object.ticket_no}")
            translated_description, translation_meta, origin_description = cls.translate_sync_description(
                db,
                title=str(update_data.get("title") or ticket.title or ""),
                description=sync_object.description,
                ticket_id=ticket.ticket_id,
                ticket_no=sync_object.ticket_no,
                current_user=current_user,
                enabled=should_translate,
            )
            if (
                should_translate
                and translated_description
                and translated_description != str(ticket.description or "").strip()
            ):
                update_data["description"] = translated_description
            if should_translate and origin_description and str(translation_meta.get("translated_text") or "").strip():
                extra_data["origin_description"] = origin_description
                extra_data["ai_translation"] = translation_meta.get("translated_text") or translated_description
                extra_data["ai_translation_source_hash"] = SyncUtil.text_sha256(origin_description)
                if translation_meta.get("provider_code"):
                    extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
                if translation_meta.get("prompt_code"):
                    extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
        except Exception as exc:
            logger.warning(f"外部工单同步延后翻译处理失败: ticket_no={sync_object.ticket_no}, error={exc}")

        if isinstance(ai_extract_meta, dict):
            if not bool(ai_extract_meta.get("skipped")) or str(ai_extract_meta.get("error") or "").strip():
                extra_data = cls.attach_sync_ai_extract_meta(
                    extra_data,
                    extract_result=ai_extract_result,
                    extract_meta=ai_extract_meta,
                    applied_meta=ai_extract_apply_meta,
                )

        if update_data or extra_data != (ticket.extra_data or {}):
            update_data["extra_data"] = extra_data
            update_data["update_by"] = _user_name(current_user)
            update_data["update_time"] = datetime.now()
            try:
                TicketDao.update_ticket(db, ticket.ticket_id, update_data)
                db.commit()
                ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            except Exception as exc:
                db.rollback()
                logger.warning(f"外部工单同步延后更新工单失败: ticket_no={sync_object.ticket_no}, error={exc}")

        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            meta = TicketSyncPayloadService.build_meta(ticket.extra_data if isinstance(ticket.extra_data, dict) else {})
            previous_status = str(meta.get("sourceStatusBefore") or "").strip()
            source_type, enabled_by_scene, force_reclassify, classify_reason = (
                cls.resolve_ai_classification_scene_for_sync_status(
                    config,
                    sync_scene=sync_scene,
                    previous_status=previous_status,
                    current_status=str(ticket.status or "").strip(),
                )
            )
            if skip_ai_analysis_due_to_update_title and not classify_reason.startswith("status_changed:"):
                logger.info(
                    f"外部工单同步延后自动分类跳过: ticket_no={sync_object.ticket_no}, "
                    f"reason=更新场景且已携带标题，未命中状态变更分类"
                )
            else:
                logger.info(
                    f"外部工单同步延后自动分类场景: ticket_no={sync_object.ticket_no}, "
                    f"source_type={source_type}, enabled_by_scene={enabled_by_scene}, "
                    f"force_reclassify={force_reclassify}, reason={classify_reason}"
                )
                TicketAutoClassificationService.run_auto_ticket_ai_classification(
                    db,
                    ticket=ticket,
                    title=str(update_data.get("title") or ticket.title or "").strip(),
                    description=str(
                        update_data.get("description")
                        or sync_object.description
                        or ticket.description
                        or ""
                    ).strip(),
                    current_user_name=_user_name(current_user),
                    source_type=source_type,
                    source_ref=sync_object.ticket_no,
                    force_reclassify=force_reclassify,
                    enabled_by_scene=enabled_by_scene,
                )
        except Exception as exc:
            logger.warning(f"外部工单同步延后自动分类失败: ticket_no={sync_object.ticket_no}, error={exc}")

        apply_external_mappings = sync_scene != "remote_pull"
        detected = TicketSyncAutomationService.detect_fields(
            db,
            sync_object,
            config,
            apply_external_mappings=apply_external_mappings,
        )

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
        if should_run_automation:
            try:
                TicketSyncAutomationService.run_sync_automation(
                    db,
                    ticket.ticket_id,
                    sync_object,
                    detected,
                    current_user,
                )
            except Exception as exc:
                logger.warning(f"外部工单同步延后自动化失败: ticket_no={sync_object.ticket_no}, error={exc}")
        ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
        try:
            vector_scene_map = {
                "remote_pull": "remotePull",
                "bitable_pull": "bitablePull",
                "external_sync": "externalSync",
            }
            vector_scene = vector_scene_map.get(sync_scene, "externalSync")
            TicketEmbeddingService.vectorize_ticket_for_scene(db, ticket, vector_scene)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                f"外部工单同步延后向量刷新失败: ticket_no={sync_object.ticket_no}, "
                f"scene={sync_scene}, error={exc}"
            )
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
        try:
            TicketSyncGroupPushService.finalize_publish_state_after_post_process(
                db,
                ticket=ticket,
                sync_scene=sync_scene,
                update_by=_user_name(current_user),
            )
        except Exception as exc:
            logger.warning(
                f"外部工单同步延后发布状态收敛失败: ticket_no={sync_object.ticket_no}, "
                f"scene={sync_scene}, error={exc}"
            )

    @classmethod
    def resolve_sync_title(
        cls,
        db: Session,
        *,
        sync_object: TicketExternalSyncUpsertModel,
        ticket_id: int | None,
        current_user: CurrentUserModel,
    ) -> tuple[str, dict[str, Any]]:
        """
        解析外部同步工单标题：优先原始标题，其次轻量AI总结，最后回退描述截断。
        :param db: 数据库会话。
        :param sync_object: 外部同步模型。
        :param ticket_id: 工单ID。
        :param current_user: 当前用户。
        :return: (最终标题, 标题元信息)。
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
    def should_skip_ai_analysis_for_update_with_title(
        cls,
        *,
        ticket: Ticket | None,
        incoming_title: str,
        meta: dict[str, Any] | None = None,
    ) -> bool:
        """
        判断是否因“更新且已带标题”跳过 AI 分析类任务。
        :param ticket: 当前工单对象。
        :param incoming_title: 本次入参标题。
        :param meta: 可选同步元数据，用于补充判断是否更新场景。
        :return: 是否跳过。
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
    def apply_ai_extract_to_sync_object(
        cls,
        sync_object: TicketExternalSyncUpsertModel,
        extract_result: dict[str, Any] | None,
    ) -> tuple[TicketExternalSyncUpsertModel, dict[str, Any]]:
        """
        将统一提取结果回填到同步对象。
        :param sync_object: 外部同步对象。
        :param extract_result: 统一提取结果。
        :return: (回填后的同步对象, 回填摘要)。
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
    def attach_sync_ai_extract_meta(
        cls,
        extra_data: dict[str, Any],
        *,
        extract_result: dict[str, Any] | None,
        extract_meta: dict[str, Any] | None,
        applied_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        将统一提取执行信息写入 extra_data。
        :param extra_data: 工单扩展字段。
        :param extract_result: 提取结果。
        :param extract_meta: 提取元信息。
        :param applied_meta: 回填摘要。
        :return: 更新后的扩展字段。
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
    def translate_sync_description(
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
        """
        按配置翻译外部同步描述。
        :param db: 数据库会话。
        :param title: 工单标题。
        :param description: 原始描述。
        :param ticket_id: 工单ID。
        :param ticket_no: 工单号。
        :param current_user: 当前用户。
        :param enabled: 是否允许翻译。
        :return: (落库描述, 翻译元信息, 原文描述)。
        """
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
    def has_successful_ai_translation(cls, ticket: Ticket | None, source_description: str | None = None) -> bool:
        """
        判断工单是否已有成功的 AI 翻译结果。
        :param ticket: 工单对象。
        :param source_description: 本次待翻译原文。
        :return: 是否已存在翻译结果。
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
    def resolve_ai_classification_scene_for_sync_status(
        cls,
        config: dict[str, Any],
        *,
        sync_scene: str,
        previous_status: str,
        current_status: str,
    ) -> tuple[str, bool, bool, str]:
        """
        解析同步入库后应使用的 AI 分类场景。
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
