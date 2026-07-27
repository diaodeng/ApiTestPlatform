"""
工单批量重归类服务。

负责手动批量重跑工单分类统计和未归类统计，不参与外部同步入库主事务。
"""
import re
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import TicketBatchReclassifyRequestModel
from modules.ticket.service.ai.ticket_auto_classification_service import TicketAutoClassificationService
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import user_name as _user_name
from utils.log_util import logger


class TicketBatchReclassificationService:
    """批量重归类与未归类统计服务。"""

    @classmethod
    def run_auto_ticket_category_classification(
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
        classification_strategy: str = "ai",
        regex_rules: list[dict[str, Any]] | None = None,
        ai_prompt_code: str | None = None,
        pre_classified_category: str | None = None,
        pre_classified_meta: dict[str, Any] | None = None,
        prefer_no_ai_fallback: bool = False,
    ) -> tuple[Ticket, dict[str, Any]]:
        """
        执行单张工单自动分类并在成功时回填分类字段。
        :param db: 数据库会话。
        :param ticket: 待分类工单对象。
        :param title: 工单标题。
        :param description: 工单描述。
        :param current_user_name: 当前操作人名称。
        :param source_type: 分类来源类型。
        :param source_ref: 分类来源引用。
        :param force_reclassify: 是否强制覆盖已有分类。
        :param classification_strategy: 分类策略，支持 ai/regex。
        :param regex_rules: 正则分类规则。
        :param ai_prompt_code: AI 提示词编码。
        :param pre_classified_category: 已预提取的分类。
        :param pre_classified_meta: 已预提取的分类元信息。
        :param prefer_no_ai_fallback: 无预提取结果时是否禁止二次 AI。
        :return: (最新工单对象, 分类执行摘要)。
        """
        existing_category = str(getattr(ticket, "category_name", "") or "").strip()
        logger.info(
            f"工单自动分类开始: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"source_type={source_type}, source_ref={source_ref}, strategy={classification_strategy}, "
            f"force_reclassify={bool(force_reclassify)}, existing_category={existing_category or '-'}, "
            f"title_len={len(str(title or '').strip())}, description_len={len(str(description or '').strip())}"
        )
        if existing_category and not force_reclassify:
            logger.info(
                f"工单自动分类跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=工单已归类且未开启强制重归类, category={existing_category}"
            )
            return ticket, {
                "skipped": True,
                "skipReason": "工单已归类，跳过自动分类",
                "categoryName": existing_category,
            }

        normalized_category = str(pre_classified_category or "").strip()
        category_meta = dict(pre_classified_meta or {})
        normalized_strategy = str(classification_strategy or "ai").strip().lower()
        if normalized_strategy not in {"ai", "regex"}:
            normalized_strategy = "ai"
        if normalized_strategy == "regex" and not normalized_category:
            logger.info(
                f"工单自动分类开始正则匹配: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"rule_count={len(regex_rules or [])}, title_len={len(str(title or '').strip())}, "
                f"description_len={len(str(description or '').strip())}"
            )
            normalized_category, regex_meta = cls.classify_ticket_category_by_regex(
                title=title,
                description=description,
                regex_rules=regex_rules,
            )
            category_meta = {**category_meta, **regex_meta}
        if not normalized_category:
            if prefer_no_ai_fallback:
                logger.info(
                    f"工单自动分类跳过二次AI: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                    f"reason=统一提取未返回分类且配置禁止二次AI调用"
                )
                return ticket, {
                    "skipped": True,
                    "skipReason": "统一提取未返回分类，已按配置跳过二次分类AI调用",
                    "categoryName": existing_category,
                    "meta": category_meta,
                }
            config = TicketSyncConfigService.load_sync_config(db)
            ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
            stat_options = (
                config.get("statClassification") if isinstance(config.get("statClassification"), dict) else {}
            )
            logger.info(
                f"工单AI分类统计调用轻量AI: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"source_type={source_type}, source_ref={source_ref}, strategy={normalized_strategy}, "
                f"provider_code={category_meta.get('provider_code') or '-'}, "
                f"prompt_code={category_meta.get('prompt_code') or '-'}"
            )
            result_payload, category_meta = TicketLightAiService.classify_ticket_statistics(
                db,
                title=title,
                description=description,
                comments=TicketAutoClassificationService.build_ticket_comment_context(db, ticket_id=ticket.ticket_id),
                current_fields=TicketAutoClassificationService.build_ticket_stat_current_fields(ticket),
                stat_options=stat_options,
                override_provider_code=str(ai_config.get("providerCode") or "").strip() or None,
                override_prompt_code=ai_prompt_code or str(ai_config.get("promptCode") or "").strip() or None,
                source_type=source_type,
                source_id=ticket.ticket_id,
                source_ref=source_ref,
                current_user_name=current_user_name,
            )
            normalized_category = str(
                result_payload.get("categoryName") or result_payload.get("issueTypeName") or ""
            ).strip()
        if not normalized_category:
            logger.info(
                f"工单自动分类未返回结果: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason={str(category_meta.get('error') or '未返回可识别分类').strip()}"
            )
            return ticket, {
                "skipped": True,
                "skipReason": str(category_meta.get("error") or "未返回可识别分类").strip(),
                "categoryName": existing_category,
                "meta": category_meta,
            }

        next_extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        next_extra_data["auto_category_classify"] = {
            "categoryName": normalized_category,
            "providerCode": category_meta.get("provider_code"),
            "promptCode": category_meta.get("prompt_code"),
            "rawCategory": category_meta.get("raw_category"),
            "strategy": category_meta.get("strategy") or normalized_strategy,
            "matchedPattern": category_meta.get("matchedPattern"),
            "classifiedAt": SyncUtil.now_iso(),
            "forceReclassify": bool(force_reclassify),
        }
        if normalized_category == existing_category and ticket.extra_data == next_extra_data:
            return ticket, {"skipped": True, "skipReason": "分类结果未变化", "categoryName": normalized_category}

        update_by = str(current_user_name or "").strip() or "system"
        try:
            TicketDao.update_ticket(
                db,
                ticket.ticket_id,
                {
                    "category_name": normalized_category,
                    "extra_data": next_extra_data,
                    "update_by": update_by,
                    "update_time": datetime.now(),
                },
            )
            db.commit()
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            logger.info(
                f"工单自动分类完成: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"category={normalized_category}, strategy={category_meta.get('strategy') or normalized_strategy}, "
                f"force_reclassify={bool(force_reclassify)}"
            )
            return ticket, {
                "skipped": False,
                "categoryName": normalized_category,
                "meta": category_meta,
            }
        except Exception:
            db.rollback()
            raise

    @classmethod
    def classify_ticket_category_by_regex(
        cls,
        *,
        title: str,
        description: str,
        regex_rules: list[dict[str, Any]] | None,
    ) -> tuple[str, dict[str, Any]]:
        """
        使用正则规则匹配工单分类。
        :param title: 工单标题。
        :param description: 工单描述。
        :param regex_rules: 正则规则列表，每条规则包含 pattern/category/flags。
        :return: (分类名称, 匹配元信息)。
        """
        text = "\n".join([str(title or "").strip(), str(description or "").strip()])
        for rule in regex_rules or []:
            pattern = str((rule or {}).get("pattern") or "").strip()
            category = str((rule or {}).get("category") or (rule or {}).get("categoryName") or "").strip()
            flags_text = str((rule or {}).get("flags") or "").strip().lower()
            if not pattern or not category:
                continue
            flags = re.IGNORECASE if "i" in flags_text or not flags_text else 0
            try:
                matched = re.search(pattern, text, flags=flags)
            except re.error as exc:
                logger.warning(f"工单正则归类规则无效: pattern={pattern}, error={exc}")
                continue
            if not matched:
                continue
            matched_text = str(matched.group(0) or "").strip()
            logger.info(f"工单正则归类命中: category={category}, pattern={pattern}, matched={matched_text}")
            return category, {
                "strategy": "regex",
                "matchedPattern": pattern,
                "matchedText": matched_text,
                "raw_category": category,
            }
        return "", {"strategy": "regex", "skipReason": "未命中正则归类规则"}

    @classmethod
    def batch_reclassify_ticket_categories_services(
        cls,
        db: Session,
        request: TicketBatchReclassifyRequestModel,
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        """
        批量执行工单自动分类。
        :param db: 数据库会话。
        :param request: 批量重归类请求模型。
        :param current_user: 当前登录用户。
        :return: 执行结果摘要。
        """
        current_user_name = _user_name(current_user) or "system"
        strategy = str(getattr(request, "strategy", "ai") or "ai").strip().lower()
        if strategy not in {"ai", "regex"}:
            strategy = "ai"
        ai_prompt_code = str(getattr(request, "ai_prompt_code", "") or "").strip() or None
        regex_rules = getattr(request, "regex_rules", None)
        only_uncategorized = bool(getattr(request, "only_uncategorized", False))
        all_tickets = bool(getattr(request, "all_tickets", False))
        logger.info(
            f"工单批量重归类开始: user={current_user_name}, strategy={strategy}, "
            f"only_uncategorized={only_uncategorized}, all_tickets={all_tickets}, "
            f"force_reclassify={bool(getattr(request, 'force_reclassify', False))}, "
            f"page_num={int(getattr(request, 'page_num', 1) or 1)}, "
            f"page_size={int(getattr(request, 'page_size', 100) or 100)}, "
            f"ticket_nos_count={len(getattr(request, 'ticket_nos', None) or [])}, "
            f"regex_rules_count={len(regex_rules or [])}, "
            f"ai_prompt_code={ai_prompt_code or '-'}"
        )

        base_query = db.query(Ticket).filter(Ticket.del_flag == "0")
        if only_uncategorized:
            base_query = base_query.filter(
                Ticket.is_problem.is_(None),
                or_(Ticket.category_name.is_(None), Ticket.category_name == ""),
                or_(Ticket.issue_type_name.is_(None), Ticket.issue_type_name == ""),
            )
        base_query = base_query.order_by(Ticket.update_time.desc(), Ticket.ticket_id.desc())

        if getattr(request, "ticket_nos", None):
            query = base_query.filter(Ticket.ticket_no.in_(request.ticket_nos))
            total = query.count()
            tickets = query.all()
        else:
            total = base_query.count()
            if all_tickets:
                tickets = base_query.all()
            else:
                page_num = max(int(getattr(request, "page_num", 1) or 1), 1)
                page_size = min(max(int(getattr(request, "page_size", 100) or 100), 1), 500)
                tickets = base_query.offset((page_num - 1) * page_size).limit(page_size).all()
        logger.info(
            f"工单批量重归类筛选完成: total={total}, selected={len(tickets)}, strategy={strategy}, "
            f"only_uncategorized={only_uncategorized}, all_tickets={all_tickets}"
        )

        summary = {
            "total": total,
            "selectedCount": len(tickets),
            "successCount": 0,
            "skippedCount": 0,
            "failedCount": 0,
            "strategy": strategy,
            "onlyUncategorized": only_uncategorized,
            "allTickets": all_tickets,
            "details": [],
        }
        if strategy == "regex" and not regex_rules:
            logger.info(
                f"工单批量重归类跳过: strategy=regex 但未配置正则规则, selected={len(tickets)}, "
                f"only_uncategorized={only_uncategorized}, all_tickets={all_tickets}"
            )
            summary["skippedCount"] = len(tickets)
            summary["details"] = [
                {
                    "ticketId": ticket.ticket_id,
                    "ticketNo": ticket.ticket_no,
                    "skipped": True,
                    "skipReason": "未配置正则归类规则",
                }
                for ticket in tickets
            ]
            return summary

        for ticket in tickets:
            try:
                logger.info(
                    f"工单批量重归类处理开始: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                    f"title_len={len(str(ticket.title or '').strip())}, "
                    f"description_len={len(str(ticket.description or '').strip())}, "
                    f"strategy={strategy}, force_reclassify={bool(getattr(request, 'force_reclassify', False))}"
                )
                if strategy == "regex":
                    _, category_result = cls.run_auto_ticket_category_classification(
                        db,
                        ticket=ticket,
                        title=str(ticket.title or "").strip(),
                        description=str(ticket.description or "").strip(),
                        current_user_name=current_user_name,
                        source_type="ticket_batch_reclassify",
                        source_ref=str(ticket.ticket_no or ticket.ticket_id),
                        force_reclassify=bool(getattr(request, "force_reclassify", False)),
                        classification_strategy=strategy,
                        regex_rules=regex_rules,
                        ai_prompt_code=ai_prompt_code,
                    )
                else:
                    _, category_result = TicketAutoClassificationService.run_auto_ticket_ai_classification(
                        db,
                        ticket=ticket,
                        title=str(ticket.title or "").strip(),
                        description=str(ticket.description or "").strip(),
                        current_user_name=current_user_name,
                        source_type="ticket_batch_reclassify",
                        source_ref=str(ticket.ticket_no or ticket.ticket_id),
                        force_reclassify=bool(getattr(request, "force_reclassify", False)),
                        ai_prompt_code=ai_prompt_code,
                        enabled_by_scene=True,
                    )
                detail = {
                    "ticketId": ticket.ticket_id,
                    "ticketNo": ticket.ticket_no,
                    **category_result,
                }
                summary["details"].append(detail)
                if category_result.get("skipped"):
                    logger.info(
                        f"工单批量重归类跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                        f"reason={detail.get('skipReason') or category_result.get('skipReason') or '未说明'}"
                    )
                    summary["skippedCount"] += 1
                else:
                    logger.info(
                        f"工单批量重归类成功: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                        f"category={category_result.get('categoryName') or '-'}, "
                        f"issue_type={category_result.get('issueTypeName') or '-'}, "
                        f"is_problem={category_result.get('isProblem')}"
                    )
                    summary["successCount"] += 1
            except Exception as exc:
                logger.warning(
                    f"批量工单自动分类失败: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, error={exc}"
                )
                summary["failedCount"] += 1
                summary["details"].append(
                    {
                        "ticketId": ticket.ticket_id,
                        "ticketNo": ticket.ticket_no,
                        "skipped": False,
                        "failed": True,
                        "error": str(exc),
                    }
                )
        logger.info(
            f"工单批量重归类结束: total={summary['total']}, selected={summary['selectedCount']}, "
            f"success={summary['successCount']}, skipped={summary['skippedCount']}, failed={summary['failedCount']}"
        )
        return summary

    @classmethod
    def get_uncategorized_ticket_statistics_services(cls, db: Session) -> dict[str, Any]:
        """
        统计当前工单中未归类数量。
        :param db: 数据库会话。
        :return: 未归类统计结果。
        """
        logger.info("工单未归类统计开始: 仅执行统计查询，不触发自动归类")
        total_count = db.query(Ticket).filter(Ticket.del_flag == "0").count()
        uncategorized_count = (
            db.query(Ticket)
            .filter(
                Ticket.del_flag == "0",
                Ticket.is_problem.is_(None),
                or_(
                    Ticket.category_name.is_(None),
                    Ticket.category_name == "",
                ),
                or_(
                    Ticket.issue_type_name.is_(None),
                    Ticket.issue_type_name == "",
                ),
            )
            .count()
        )
        categorized_count = max(total_count - uncategorized_count, 0)
        uncategorized_ratio = round((uncategorized_count / total_count) * 100, 2) if total_count else 0
        logger.info(
            f"工单未归类统计完成: total_count={total_count}, categorized_count={categorized_count}, "
            f"uncategorized_count={uncategorized_count}, uncategorized_ratio={uncategorized_ratio}"
        )
        return {
            "totalCount": total_count,
            "categorizedCount": categorized_count,
            "uncategorizedCount": uncategorized_count,
            "uncategorizedRatio": uncategorized_ratio,
        }
