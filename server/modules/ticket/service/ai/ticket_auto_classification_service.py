from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketComment
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.util.sync_util import SyncUtil
from utils.log_util import logger


class TicketAutoClassificationService:
    """
    工单 AI 分类统计服务。

    该服务承接拆分前 `TicketSyncService._run_auto_ticket_ai_classification` 的行为，只依赖配置、DAO 和轻量 AI
    服务，供手工新增、状态流转、外部同步和批量重归类复用。
    """

    @classmethod
    def run_auto_ticket_ai_classification(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        title: str,
        description: str,
        current_user_name: str,
        source_type: str,
        source_ref: str,
        force_reclassify: bool = False,
        ai_prompt_code: str | None = None,
        enabled_by_scene: bool = True,
    ) -> tuple[Ticket, dict[str, Any]]:
        """
        执行工单 AI 分类统计并回填统计字段。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param title: 工单标题
        :param description: 工单描述
        :param current_user_name: 当前用户名
        :param source_type: 分类来源类型
        :param source_ref: 分类来源引用
        :param force_reclassify: 是否强制重新分类
        :param ai_prompt_code: 可选覆盖提示词编码
        :param enabled_by_scene: 当前场景是否启用
        :return: (最新工单对象, 分类摘要)
        """
        logger.info(
            f"工单AI分类统计流程开始: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"source_type={source_type}, source_ref={source_ref}, enabled_by_scene={enabled_by_scene}, "
            f"force_reclassify={bool(force_reclassify)}, ai_prompt_code={ai_prompt_code or '-'}"
        )
        if not enabled_by_scene and not force_reclassify:
            logger.info(
                f"工单AI分类统计跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=当前场景入参未启用且未强制重归类, source_type={source_type}"
            )
            return ticket, {"skipped": True, "skipReason": "当前场景未启用AI分类统计"}
        config = TicketSyncConfigService.load_sync_config(db)
        if not cls.should_run_ai_classification_for_scene(config, source_type) and not force_reclassify:
            logger.info(
                f"工单AI分类统计跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=同步配置未开启当前场景AI分类统计, source_type={source_type}"
            )
            return ticket, {"skipped": True, "skipReason": "当前场景未开启AI分类统计"}
        title_text = str(title or "").strip()
        description_text = str(description or "").strip()
        comment_context = cls.build_ticket_comment_context(db, ticket_id=ticket.ticket_id)
        logger.info(
            f"工单AI分类统计上下文: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"title_len={len(title_text)}, description_len={len(description_text)}, "
            f"comment_count={len(comment_context)}"
        )
        if not force_reclassify and cls.has_complete_ticket_classification_fields(ticket):
            if cls.has_successful_ai_classification(
                ticket,
                title=title_text,
                description=description_text,
                comments=comment_context,
            ):
                logger.info(
                    f"工单AI分类统计跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                    f"reason=核心分类字段完整且内容未变化, source_type={source_type}"
                )
                return ticket, {"skipped": True, "skipReason": "核心分类字段完整且内容未变化"}
            logger.info(
                f"工单AI分类统计继续执行: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=核心分类字段完整但内容已变化, source_type={source_type}"
            )
        elif not force_reclassify:
            logger.info(
                f"工单AI分类统计继续执行: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=存在核心分类字段缺失, source_type={source_type}"
            )
        ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
        stat_options = config.get("statClassification") if isinstance(config.get("statClassification"), dict) else {}
        if isinstance(stat_options.get("problemPatterns"), list):
            stat_options = dict(stat_options)
            stat_options["problemPatterns"] = [
                item
                for item in stat_options["problemPatterns"]
                if not isinstance(item, dict) or item.get("enabled") is not False
            ]
        logger.info(
            f"工单AI分类统计调用轻量AI: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"provider_code={str(ai_config.get('providerCode') or '').strip() or '-'}, "
            f"prompt_code={ai_prompt_code or str(ai_config.get('promptCode') or '').strip() or '-'}"
        )
        result_payload, meta = TicketLightAiService.classify_ticket_statistics(
            db,
            title=title_text,
            description=description_text,
            comments=comment_context,
            current_fields=cls.build_ticket_stat_current_fields(ticket),
            stat_options=stat_options,
            override_provider_code=str(ai_config.get("providerCode") or "").strip() or None,
            override_prompt_code=ai_prompt_code or str(ai_config.get("promptCode") or "").strip() or None,
            source_type=source_type,
            source_id=ticket.ticket_id,
            source_ref=source_ref,
            current_user_name=current_user_name,
        )
        if not result_payload:
            logger.info(
                f"工单AI分类统计无结果: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason={str(meta.get('error') or meta.get('skipReason') or 'AI未返回分类统计结果').strip()}"
            )
            return ticket, {
                "skipped": True,
                "skipReason": str(meta.get("error") or meta.get("skipReason") or "AI未返回分类统计结果").strip(),
                "meta": meta,
            }

        source_hash = cls.build_ai_classification_source_hash(
            title=title_text,
            description=description_text,
            comments=comment_context,
            root_cause=str(getattr(ticket, "root_cause", "") or "").strip(),
            solution=str(getattr(ticket, "solution", "") or "").strip(),
        )
        next_extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        next_extra_data["ai_classification"] = {
            "success": True,
            "sourceType": source_type,
            "sourceRef": source_ref,
            "sourceHash": source_hash,
            "commentCount": len(comment_context),
            "providerCode": meta.get("provider_code"),
            "promptCode": meta.get("prompt_code"),
            "classifiedAt": SyncUtil.now_iso(),
            "forceReclassify": bool(force_reclassify),
            "confidence": result_payload.get("confidence"),
            "reason": result_payload.get("reason"),
            "needRnd": result_payload.get("needRnd"),
            "needMonitor": result_payload.get("needMonitor"),
            "needKb": result_payload.get("needKb"),
            "rawPayload": result_payload.get("rawPayload"),
        }
        update_data: dict[str, Any] = {
            "extra_data": next_extra_data,
            "update_by": str(current_user_name or "").strip() or "system",
            "update_time": datetime.now(),
        }
        field_map = {
            "categoryName": "category_name",
            "issueTypeId": "issue_type_id",
            "issueTypeName": "issue_type_name",
            "moduleName": "module_name",
            "severity": "severity",
            "rootCauseType": "root_cause_type",
            "solutionType": "solution_type",
            "resolutionCode": "resolution_code",
            "resolutionName": "resolution_name",
            "problemPatternCode": "problem_pattern_code",
            "problemPatternName": "problem_pattern_name",
            "rootCause": "root_cause",
            "solution": "solution",
        }
        if str(getattr(ticket, "classification_source", "") or "").strip() == "external_mapping" and not force_reclassify:
            field_map.pop("issueTypeId")
            field_map.pop("issueTypeName")
        for result_key, db_field in field_map.items():
            if db_field.startswith("problem_pattern_") and getattr(ticket, "problem_pattern_verified", None) is True:
                continue
            value = result_payload.get(result_key)
            if value not in (None, ""):
                update_data[db_field] = value
        if "issue_type_id" in update_data:
            update_data["classification_source"] = "ai"
            update_data["classification_rule_id"] = ""
            update_data["classification_updated_at"] = datetime.now()
        if result_payload.get("isProblem") is not None:
            update_data["is_problem"] = bool(result_payload.get("isProblem"))
        if (
            result_payload.get("problemPatternConfidence") is not None
            and getattr(ticket, "problem_pattern_verified", None) is not True
        ):
            pattern_confidence = float(result_payload.get("problemPatternConfidence") or 0)
            update_data["problem_pattern_confidence"] = int(
                min(max(pattern_confidence * 100 if pattern_confidence <= 1 else pattern_confidence, 0), 100)
            )
        if result_payload.get("problemPatternCode") and getattr(ticket, "problem_pattern_verified", None) is not True:
            update_data["problem_pattern_source"] = "ai"
            if getattr(ticket, "problem_pattern_verified", None) is None:
                update_data["problem_pattern_verified"] = False

        TicketDao.update_ticket(db, ticket.ticket_id, update_data)
        db.commit()
        ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
        logger.info(
            f"工单AI分类统计回填完成: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"category={result_payload.get('categoryName') or '-'}, "
            f"issue_type={result_payload.get('issueTypeName') or '-'}, "
            f"is_problem={result_payload.get('isProblem')}, "
            f"root_cause_type={result_payload.get('rootCauseType') or '-'}, "
            f"solution_type={result_payload.get('solutionType') or '-'}, "
            f"problem_pattern={result_payload.get('problemPatternName') or '-'}"
        )
        return ticket, {
            "skipped": False,
            "categoryName": result_payload.get("categoryName"),
            "issueTypeName": result_payload.get("issueTypeName"),
            "isProblem": result_payload.get("isProblem"),
            "rootCauseType": result_payload.get("rootCauseType"),
            "solutionType": result_payload.get("solutionType"),
            "resolutionName": result_payload.get("resolutionName"),
            "problemPatternName": result_payload.get("problemPatternName"),
            "meta": meta,
        }

    @classmethod
    def build_ticket_stat_current_fields(cls, ticket: Ticket) -> dict[str, Any]:
        """
        构建 AI 分类统计需要的当前工单字段。
        :param ticket: 工单对象
        :return: 当前字段字典
        """
        return {
            "ticketNo": ticket.ticket_no,
            "categoryName": ticket.category_name,
            "issueTypeId": ticket.issue_type_id,
            "issueTypeName": ticket.issue_type_name,
            "moduleName": ticket.module_name,
            "status": ticket.status,
            "isProblem": ticket.is_problem,
            "rootCauseType": ticket.root_cause_type,
            "solutionType": ticket.solution_type,
            "resolutionCode": ticket.resolution_code,
            "resolutionName": ticket.resolution_name,
            "problemPatternCode": ticket.problem_pattern_code,
            "problemPatternName": ticket.problem_pattern_name,
            "problemPatternVerified": ticket.problem_pattern_verified,
            "severity": ticket.severity,
            "rootCause": ticket.root_cause,
            "solution": ticket.solution,
        }

    @classmethod
    def build_ticket_comment_context(cls, db: Session, *, ticket_id: int, limit: int = 30) -> list[str]:
        """
        构建 AI 分类统计使用的评论上下文。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param limit: 最多取最近评论数量
        :return: 按时间升序排列的评论文本
        """
        rows = (
            db.query(TicketComment)
            .filter(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.create_time.desc(), TicketComment.id.desc())
            .limit(max(int(limit or 30), 1))
            .all()
        )
        comment_lines: list[str] = []
        for comment in reversed(rows):
            content = str(getattr(comment, "content", "") or "").strip()
            if not content:
                continue
            created_at = getattr(comment, "create_time", None)
            created_text = created_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created_at, datetime) else ""
            user_text = str(getattr(comment, "user_name", "") or "").strip() or "未知人员"
            prefix_parts = [item for item in (created_text, user_text) if item]
            prefix = " ".join(prefix_parts)
            comment_lines.append(f"{prefix}：{content}" if prefix else content)
        return comment_lines

    @classmethod
    def build_ai_classification_source_hash(
        cls,
        *,
        title: str,
        description: str,
        comments: list[str] | None = None,
        root_cause: str | None = None,
        solution: str | None = None,
    ) -> str:
        """
        构建 AI 分类防重用来源摘要。
        :param title: 工单标题
        :param description: 工单描述
        :param comments: 工单评论上下文
        :param root_cause: 当前根因
        :param solution: 当前解决方案
        :return: 来源内容 SHA256
        """
        comment_text = "\n".join(str(item or "").strip() for item in comments or [] if str(item or "").strip())
        return SyncUtil.text_sha256(
            "\n\n".join(
                [
                    str(title or "").strip(),
                    str(description or "").strip(),
                    comment_text,
                    str(root_cause or "").strip(),
                    str(solution or "").strip(),
                ]
            )
        )

    @classmethod
    def has_successful_ai_classification(
        cls,
        ticket: Ticket,
        *,
        title: str,
        description: str,
        comments: list[str] | None = None,
    ) -> bool:
        """
        判断工单是否已经基于相同文本完成过 AI 分类统计。
        :param ticket: 工单对象
        :param title: 当前标题
        :param description: 当前描述
        :param comments: 当前评论上下文
        :return: 已成功分类且文本未变化时返回 True
        """
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        ai_meta = extra_data.get("ai_classification") if isinstance(extra_data.get("ai_classification"), dict) else {}
        source_hash = cls.build_ai_classification_source_hash(
            title=title,
            description=description,
            comments=comments,
            root_cause=str(getattr(ticket, "root_cause", "") or "").strip(),
            solution=str(getattr(ticket, "solution", "") or "").strip(),
        )
        return bool(ai_meta.get("success")) and str(ai_meta.get("sourceHash") or "") == source_hash

    @classmethod
    def has_complete_ticket_classification_fields(cls, ticket: Ticket) -> bool:
        """
        判断工单是否已经具备完整的核心分类统计结果。
        :param ticket: 工单对象
        :return: 核心分类字段均有值时返回 True
        """
        return all(
            [
                str(getattr(ticket, "category_name", "") or "").strip(),
                str(getattr(ticket, "issue_type_id", "") or "").strip(),
                str(getattr(ticket, "issue_type_name", "") or "").strip(),
                str(getattr(ticket, "root_cause_type", "") or "").strip(),
                str(getattr(ticket, "solution_type", "") or "").strip(),
                str(getattr(ticket, "resolution_code", "") or "").strip(),
                str(getattr(ticket, "resolution_name", "") or "").strip(),
                str(getattr(ticket, "problem_pattern_code", "") or "").strip(),
                str(getattr(ticket, "problem_pattern_name", "") or "").strip(),
                getattr(ticket, "is_problem", None) is not None,
            ]
        )

    @classmethod
    def should_run_ai_classification_for_scene(cls, config: dict[str, Any], scene: str) -> bool:
        """
        判断指定入库场景是否启用 AI 分类统计。
        :param config: 同步自动化配置
        :param scene: 场景 external_sync/remote_pull/manual_create/status_change/batch_reclassify
        :return: 是否启用
        """
        ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
        if not bool(ai_config.get("enabled")):
            return False
        normalized_scene = str(scene or "").strip()
        if (
            normalized_scene == "status_change"
            or normalized_scene.startswith("ticket_status_change")
            or "_status_change" in normalized_scene
        ):
            return bool(ai_config.get("runOnStatusChange"))
        if normalized_scene == "external_sync" or normalized_scene.startswith("external_sync"):
            return bool(ai_config.get("runOnExternalSync"))
        if normalized_scene == "remote_pull" or normalized_scene.startswith("remote_pull"):
            return bool(ai_config.get("runOnRemotePull"))
        if normalized_scene == "manual_create" or normalized_scene.startswith("ticket_manual_create"):
            return bool(ai_config.get("runOnManualCreate"))
        if normalized_scene == "bitable_pull" or normalized_scene.startswith("bitable_pull"):
            return bool(ai_config.get("runOnBitablePull"))
        if normalized_scene == "batch_reclassify" or normalized_scene.startswith("ticket_batch_reclassify"):
            return True
        return False
