import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from config.database import SessionLocal
from context.request_context import trace_context
from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.do.config_do import SysConfig
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import EmbeddingRecord, Ticket, TicketRca
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class TicketEmbeddingService:
    """
    工单相似度检索服务，支持本地哈希向量兜底和可配置的 Qdrant 外部向量库。
    """

    CONFIG_KEY = "ticket.similarity.config"
    MODEL = "local-hash"
    VERSION = "v1"
    DIMENSION = 128
    PROVIDER_LOCAL_HASH = "local_hash"
    PROVIDER_QDRANT = "qdrant"
    DEFAULT_CONFIG: dict[str, Any] = {
        "enabled": True,
        "provider": PROVIDER_LOCAL_HASH,
        "fallbackProvider": PROVIDER_LOCAL_HASH,
        "topK": 20,
        "threshold": 0.05,
        "keywordWeight": 0.15,
        "vectorWeight": 0.85,
        "fields": [
            "ticketNo",
            "title",
            "description",
            "aiSummary",
            "rootCause",
            "solution",
            "rca",
            "moduleName",
            "categoryName",
            "tags",
        ],
        "embedding": {
            "provider": PROVIDER_LOCAL_HASH,
            "model": MODEL,
            "version": VERSION,
            "dimension": DIMENSION,
            "endpoint": "",
            "apiKey": "",
            "timeoutSeconds": 15,
        },
        "qdrant": {
            "url": "http://127.0.0.1:6333",
            "apiKey": "",
            "collection": "ticket_similarity",
            "distance": "Cosine",
            "timeoutSeconds": 15,
            "createCollection": True,
            "recreateCollectionOnDimensionMismatch": False,
        },
        "sceneTriggers": {
            "externalSync": True,
            "remotePull": True,
            "manualCreate": True,
            "manualUpdate": True,
            "import": True,
            "closeKnowledge": True,
        },
    }

    @classmethod
    def get_similarity_config(cls, query_db: Session) -> dict[str, Any]:
        """
        读取工单相似度配置，缺失或格式错误时返回默认配置。
        :param query_db: 数据库会话
        :return: 相似度配置字典
        """
        config = json.loads(json.dumps(cls.DEFAULT_CONFIG, ensure_ascii=False))
        config_info = ConfigDao.get_config_detail_by_key(query_db, cls.CONFIG_KEY)
        raw_value = getattr(config_info, "config_value", None)
        if raw_value:
            try:
                parsed = json.loads(raw_value)
                if isinstance(parsed, dict):
                    config = cls._deep_merge(config, parsed)
            except Exception as exc:
                logger.warning(f"工单相似度配置解析失败，使用默认配置: key={cls.CONFIG_KEY}, error={exc}")
        config["provider"] = cls._normalize_provider(config.get("provider"))
        config["fallbackProvider"] = cls._normalize_provider(config.get("fallbackProvider"))
        config["topK"] = cls._safe_int(config.get("topK"), 20, 1, 100)
        config["threshold"] = cls._safe_float(config.get("threshold"), 0.05, -1.0, 1.0)
        config["keywordWeight"] = cls._safe_float(config.get("keywordWeight"), 0.15, 0.0, 1.0)
        config["vectorWeight"] = cls._safe_float(config.get("vectorWeight"), 0.85, 0.0, 1.0)
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        embedding_config["provider"] = cls._normalize_embedding_provider(embedding_config.get("provider"))
        embedding_config["dimension"] = cls._safe_int(embedding_config.get("dimension"), cls.DIMENSION, 1, 16384)
        config["embedding"] = embedding_config
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else {}
        qdrant_config["timeoutSeconds"] = cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120)
        qdrant_config["createCollection"] = bool(qdrant_config.get("createCollection", True))
        qdrant_config["recreateCollectionOnDimensionMismatch"] = bool(
            qdrant_config.get("recreateCollectionOnDimensionMismatch", False)
        )
        config["qdrant"] = qdrant_config
        scene_triggers = config.get("sceneTriggers") if isinstance(config.get("sceneTriggers"), dict) else {}
        config["sceneTriggers"] = {
            key: bool(scene_triggers.get(key, default_value))
            for key, default_value in cls.DEFAULT_CONFIG["sceneTriggers"].items()
        }
        return config

    @classmethod
    def ensure_default_config(cls, query_db: Session) -> dict[str, Any]:
        """
        确保系统中存在相似度默认配置，便于后续通过参数管理页面修改。
        :param query_db: 数据库会话
        :return: 当前配置
        """
        config_info = ConfigDao.get_config_detail_by_key(query_db, cls.CONFIG_KEY)
        if not config_info:
            query_db.add(
                SysConfig(
                    config_name="工单相似度检索配置",
                    config_key=cls.CONFIG_KEY,
                    config_value=json.dumps(cls.DEFAULT_CONFIG, ensure_ascii=False, indent=2),
                    config_type="Y",
                    create_by="system",
                    update_by="system",
                    remark="配置相似工单检索 Provider、Embedding 和 Qdrant 连接信息",
                )
            )
            query_db.flush()
            query_db.commit()
        return cls.get_similarity_config(query_db)

    @classmethod
    def save_similarity_config(
        cls,
        query_db: Session,
        config: dict[str, Any],
        current_user_name: str = "",
    ) -> dict[str, Any]:
        """
        保存工单相似度配置。
        :param query_db: 数据库会话
        :param config: 前端提交的相似度配置
        :param current_user_name: 当前用户名
        :return: 保存后的规范化配置
        """
        try:
            normalized = cls._normalize_config_for_save(config)
            config_text = json.dumps(normalized, ensure_ascii=False, indent=2)
            config_info = ConfigDao.get_config_detail_by_key(query_db, cls.CONFIG_KEY)
            now = datetime.now()
            if config_info:
                config_info.config_name = "工单相似度检索配置"
                config_info.config_value = config_text
                config_info.config_type = "Y"
                config_info.update_by = current_user_name or "system"
                config_info.update_time = now
                config_info.remark = "配置相似工单检索 Provider、Embedding、Qdrant 和自动触发场景"
            else:
                query_db.add(
                    SysConfig(
                        config_name="工单相似度检索配置",
                        config_key=cls.CONFIG_KEY,
                        config_value=config_text,
                        config_type="Y",
                        create_by=current_user_name or "system",
                        create_time=now,
                        update_by=current_user_name or "system",
                        update_time=now,
                        remark="配置相似工单检索 Provider、Embedding、Qdrant 和自动触发场景",
                    )
                )
            query_db.commit()
            return cls.get_similarity_config(query_db)
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def should_vectorize_for_scene(cls, config: dict[str, Any], scene: str) -> bool:
        """
        判断指定业务场景是否需要自动刷新工单向量。
        :param config: 相似度配置
        :param scene: 场景编码
        :return: 需要刷新返回 True
        """
        if not config.get("enabled", True):
            return False
        scene_key = str(scene or "").strip()
        scene_triggers = config.get("sceneTriggers") if isinstance(config.get("sceneTriggers"), dict) else {}
        return bool(scene_triggers.get(scene_key, False))

    @classmethod
    def vectorize_ticket_for_scene(
        cls,
        query_db: Session,
        ticket: Ticket,
        scene: str,
        *,
        rca: TicketRca | None = None,
        config: dict[str, Any] | None = None,
    ) -> bool:
        """
        按场景配置刷新单个工单向量。
        :param query_db: 数据库会话
        :param ticket: 工单对象
        :param scene: 场景编码
        :param rca: 可选 RCA 对象
        :param config: 相似度配置
        :return: 实际执行返回 True，未命中场景开关返回 False
        """
        active_config = config or cls.get_similarity_config(query_db)
        if not cls.should_vectorize_for_scene(active_config, scene):
            return False
        cls.vectorize_ticket(query_db, ticket, rca=rca, config=active_config)
        return True

    @classmethod
    def vectorize_tickets_for_scene(
        cls,
        query_db: Session,
        tickets: list[Ticket],
        scene: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> int:
        """
        按场景配置批量刷新工单向量。
        :param query_db: 数据库会话
        :param tickets: 工单对象列表
        :param scene: 场景编码
        :param config: 相似度配置
        :return: 实际刷新数量
        """
        active_config = config or cls.get_similarity_config(query_db)
        if not cls.should_vectorize_for_scene(active_config, scene):
            return 0
        return cls.vectorize_tickets(query_db, tickets, config=active_config)

    @classmethod
    def build_ticket_text(
        cls,
        ticket: Ticket,
        rca: TicketRca | None = None,
        config: dict[str, Any] | None = None,
    ) -> str:
        """
        拼接工单可检索文本，优先覆盖标题、描述、AI 摘要和 RCA 结构化信息。
        :param ticket: 工单对象
        :param rca: 可选 RCA 对象
        :param config: 相似度配置
        :return: 用于向量化和自然语言搜索的文本
        """
        fields = set((config or {}).get("fields") or cls.DEFAULT_CONFIG["fields"])
        ai_payload = ticket.ai_analysis if isinstance(ticket.ai_analysis, dict) else {}
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        parts: list[Any] = []
        field_map = {
            "ticketNo": ticket.ticket_no,
            "title": ticket.title,
            "description": ticket.description,
            "originDescription": extra_data.get("origin_description"),
            "aiSummary": ai_payload.get("analysis_summary") or ai_payload.get("summary"),
            "rootCause": ticket.root_cause or ai_payload.get("root_cause"),
            "solution": ticket.solution or ai_payload.get("fix_suggestion"),
            "moduleName": ticket.module_name,
            "categoryName": ticket.category_name,
            "issueTypeName": getattr(ticket, "issue_type_name", None),
            "status": ticket.status,
            "assignee": ticket.current_assignee_name,
        }
        for key, value in field_map.items():
            if key in fields:
                parts.append(value)
        if "tags" in fields and ticket.tags:
            parts.append(" ".join(ticket.tags) if isinstance(ticket.tags, list) else str(ticket.tags))
        if "rca" in fields and rca:
            parts.extend(
                [
                    rca.symptom,
                    rca.impact_scope,
                    rca.reproduce_steps,
                    rca.investigation_process,
                    rca.root_cause_detail,
                    rca.fix_solution,
                    rca.verify_method,
                    rca.prevention_solution,
                ]
            )
        return "\n".join(str(item) for item in parts if item)

    @classmethod
    def embed_text(
        cls, text: str, config: dict[str, Any] | None = None, allow_local_fallback: bool = True
    ) -> list[float]:
        """
        将文本转换为向量；默认使用本地哈希向量，可按配置调用兼容 OpenAI 的 Embedding 接口。
        :param text: 原始文本
        :param config: 相似度配置
        :param allow_local_fallback: 外部 Embedding 失败时是否允许回退本地哈希向量
        :return: 归一化向量
        """
        embedding_config = (config or {}).get("embedding") if isinstance((config or {}).get("embedding"), dict) else {}
        provider = cls._normalize_embedding_provider(embedding_config.get("provider"))
        if provider == "openai_compatible":
            try:
                return cls._embed_text_openai_compatible(text, embedding_config)
            except Exception as exc:
                if not allow_local_fallback:
                    raise ValueError(
                        f"外部Embedding生成失败，已阻止回退本地哈希写入Qdrant: provider={provider}, error={exc}"
                    ) from exc
                logger.warning(f"外部Embedding生成失败，回退本地哈希向量: provider={provider}, error={exc}")
        dimension = cls._safe_int(embedding_config.get("dimension"), cls.DIMENSION, 1, 16384)
        return cls._embed_text_local_hash(text, dimension)

    @classmethod
    def vectorize_ticket(
        cls,
        query_db: Session,
        ticket: Ticket,
        *,
        rca: TicketRca | None = None,
        config: dict[str, Any] | None = None,
        sync_qdrant: bool | None = None,
    ) -> EmbeddingRecord:
        """
        为单个工单生成或更新向量记录，并按配置同步外部向量库。
        :param query_db: 数据库会话
        :param ticket: 工单对象
        :param rca: 可选 RCA 对象
        :param config: 相似度配置
        :param sync_qdrant: 是否同步写入 Qdrant，None 表示由配置决定
        :return: 向量记录
        """
        active_config = config or cls.get_similarity_config(query_db)
        text = cls.build_ticket_text(ticket, rca=rca, config=active_config)
        should_sync_qdrant = (
            sync_qdrant
            if sync_qdrant is not None
            else active_config.get("provider") == cls.PROVIDER_QDRANT
            or active_config.get("fallbackProvider") == cls.PROVIDER_QDRANT
        )
        vector = cls.embed_text(text, active_config, allow_local_fallback=not should_sync_qdrant)
        embedding_config = active_config.get("embedding") if isinstance(active_config.get("embedding"), dict) else {}
        model = str(embedding_config.get("model") or cls.MODEL)
        version = str(embedding_config.get("version") or cls.VERSION)
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        record = EmbeddingRecord(
            object_type="ticket",
            object_id=ticket.ticket_id,
            embedding_model=model,
            embedding_version=version,
            embedding_dimension=len(vector),
            embedding=vector,
            content_hash=content_hash,
            create_time=datetime.now(),
        )
        saved_record = TicketDao.upsert_embedding_record(query_db, record)
        if should_sync_qdrant:
            cls._upsert_qdrant_ticket(active_config, ticket, vector, text, model, version)
        return saved_record

    @classmethod
    def vectorize_tickets(
        cls,
        query_db: Session,
        tickets: list[Ticket],
        *,
        config: dict[str, Any] | None = None,
        sync_qdrant: bool | None = None,
    ) -> int:
        """
        批量生成工单向量。
        :param query_db: 数据库会话
        :param tickets: 工单对象列表
        :param config: 相似度配置
        :param sync_qdrant: 是否同步写入 Qdrant
        :return: 成功写入向量数量
        """
        active_config = config or cls.get_similarity_config(query_db)
        rca_map = TicketDao.list_rca_by_ticket_ids(query_db, [ticket.ticket_id for ticket in tickets])
        count = 0
        for ticket in tickets:
            cls.vectorize_ticket(
                query_db,
                ticket,
                rca=rca_map.get(ticket.ticket_id),
                config=active_config,
                sync_qdrant=sync_qdrant,
            )
            count += 1
        return count

    @classmethod
    def resolve_ticket_ids_for_rebuild(
        cls, query_db: Session, ticket_nos: list[str] | None, ticket_ids: list[int] | None = None
    ) -> tuple[list[int] | None, list[str]]:
        """
        解析手动重建范围，优先使用业务工单号 ticketNo 映射系统工单ID。
        :param query_db: 数据库会话
        :param ticket_nos: 指定重建的工单号列表
        :param ticket_ids: 兼容旧入口传入的系统工单ID列表
        :return: 解析后的系统工单ID列表和未命中的工单号列表
        """
        normalized_nos: list[str] = []
        for ticket_no in ticket_nos or []:
            normalized_no = str(ticket_no or "").strip()
            if normalized_no and normalized_no not in normalized_nos:
                normalized_nos.append(normalized_no)
        if normalized_nos:
            tickets = TicketDao.list_tickets_by_nos(query_db, normalized_nos)
            ticket_id_list = [int(ticket.ticket_id) for ticket in tickets if ticket.ticket_id]
            found_nos = {str(ticket.ticket_no or "").strip() for ticket in tickets}
            missing_nos = [ticket_no for ticket_no in normalized_nos if ticket_no not in found_nos]
            return ticket_id_list or [], missing_nos
        return ticket_ids, []

    @classmethod
    def rebuild_ticket_embeddings(
        cls,
        query_db: Session,
        *,
        ticket_ids: list[int] | None = None,
        page_size: int = 100,
        provider: str | None = None,
        include_qdrant: bool | None = None,
    ) -> dict[str, Any]:
        """
        批量重建历史工单向量，文本范围包含标题、描述、AI 摘要和 RCA。
        :param query_db: 数据库会话
        :param ticket_ids: 可选指定工单ID列表
        :param page_size: 每批处理数量
        :param provider: 指定 Provider，传空则读取配置
        :param include_qdrant: 是否同步 Qdrant，传空则由配置决定
        :return: 重建结果摘要
        """
        active_config = cls.ensure_default_config(query_db)
        if provider:
            active_config["provider"] = cls._normalize_provider(provider)
        safe_page_size = min(max(int(page_size or 100), 1), 500)
        total = TicketDao.count_tickets_for_embedding(query_db, ticket_ids)
        processed = 0
        failed = 0
        failed_items: list[dict[str, Any]] = []
        offset = 0
        while processed + failed < total:
            current_offset = offset if not ticket_ids else processed + failed
            batch = TicketDao.list_tickets_for_embedding(
                query_db,
                offset=current_offset,
                limit=safe_page_size,
                ticket_ids=ticket_ids,
            )
            if not batch:
                break
            rca_map = TicketDao.list_rca_by_ticket_ids(query_db, [ticket.ticket_id for ticket in batch])
            for ticket in batch:
                try:
                    cls.vectorize_ticket(
                        query_db,
                        ticket,
                        rca=rca_map.get(ticket.ticket_id),
                        config=active_config,
                        sync_qdrant=include_qdrant,
                    )
                    processed += 1
                except Exception as exc:
                    failed += 1
                    failed_items.append({"ticketId": ticket.ticket_id, "ticketNo": ticket.ticket_no, "error": str(exc)})
                    logger.warning(
                        f"工单向量重建失败: ticket_id={ticket.ticket_id}, "
                        f"ticket_no={ticket.ticket_no}, error={exc}"
                    )
            query_db.commit()
            offset += safe_page_size
        qdrant_synced = (
            bool(include_qdrant)
            if include_qdrant is not None
            else active_config.get("provider") == cls.PROVIDER_QDRANT
        )
        return {
            "total": total,
            "processed": processed,
            "failed": failed,
            "failedItems": failed_items[:20],
            "provider": active_config.get("provider"),
            "qdrantSynced": qdrant_synced,
        }

    @classmethod
    def search_tickets(cls, query_db: Session, keyword: str, limit: int = 20) -> list[dict]:
        """
        使用自然语言进行相似工单检索，优先配置 Provider，失败时回退本地哈希。
        :param query_db: 数据库会话
        :param keyword: 搜索文本
        :param limit: 返回数量
        :return: 带 score 的工单列表
        """
        safe_limit = min(max(limit or 20, 1), 100)
        config = cls.get_similarity_config(query_db)
        if not config.get("enabled", True):
            return []
        provider = cls._normalize_provider(config.get("provider"))
        try:
            if provider == cls.PROVIDER_QDRANT:
                scored = cls._search_qdrant(query_db, keyword, safe_limit, config)
            else:
                scored = cls._search_local_hash(query_db, keyword, safe_limit, config)
        except Exception as exc:
            logger.warning(f"工单相似度Provider检索失败，回退本地哈希: provider={provider}, error={exc}")
            scored = cls._search_local_hash(query_db, keyword, safe_limit, config)
        scored = cls._merge_keyword_scores(query_db, keyword, safe_limit, scored, config)
        return cls._build_ticket_search_result(query_db, scored, safe_limit, config)

    @classmethod
    def _search_local_hash(
        cls,
        query_db: Session,
        keyword: str,
        limit: int,
        config: dict[str, Any],
    ) -> dict[int, float]:
        """
        使用本地 JSON 向量记录计算余弦相似度。
        :param query_db: 数据库会话
        :param keyword: 搜索文本
        :param limit: 返回数量
        :param config: 相似度配置
        :return: 工单ID到分数的映射
        """
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        model = str(embedding_config.get("model") or cls.MODEL)
        version = str(embedding_config.get("version") or cls.VERSION)
        query_vector = cls.embed_text(keyword, config)
        scored: dict[int, float] = {}
        for record in TicketDao.list_ticket_embedding_records(query_db, model, version):
            if not isinstance(record.embedding, list):
                continue
            score = cls._cosine(query_vector, record.embedding)
            if score > config.get("threshold", 0.05):
                scored[record.object_id] = max(scored.get(record.object_id, 0.0), score)
        return dict(sorted(scored.items(), key=lambda item: item[1], reverse=True)[:limit])

    @classmethod
    def _search_qdrant(
        cls,
        query_db: Session,
        keyword: str,
        limit: int,
        config: dict[str, Any],
    ) -> dict[int, float]:
        """
        调用 Qdrant 查询相似工单。
        :param query_db: 数据库会话
        :param keyword: 搜索文本
        :param limit: 返回数量
        :param config: 相似度配置
        :return: 工单ID到分数的映射
        """
        query_vector = cls.embed_text(keyword, config)
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else {}
        cls._ensure_qdrant_collection(config, expected_dimension=len(query_vector), allow_recreate=False)
        url = cls._qdrant_url(qdrant_config, f"/collections/{qdrant_config.get('collection')}/points/search")
        payload = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "score_threshold": config.get("threshold", 0.05),
        }
        response = requests.post(
            url,
            headers=cls._qdrant_headers(qdrant_config),
            json=payload,
            timeout=cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120),
        )
        cls._raise_for_qdrant_status(response, "查询相似工单")
        rows = response.json().get("result") or []
        scored: dict[int, float] = {}
        for row in rows:
            payload_data = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            ticket_id = cls._safe_int(payload_data.get("ticketId") or row.get("id"), 0, 0, 9223372036854775807)
            if ticket_id > 0:
                scored[ticket_id] = max(scored.get(ticket_id, 0.0), float(row.get("score") or 0.0))
        return scored

    @classmethod
    def _merge_keyword_scores(
        cls,
        query_db: Session,
        keyword: str,
        limit: int,
        scored: dict[int, float],
        config: dict[str, Any],
    ) -> dict[int, float]:
        """
        合并关键词命中分数，关键词只做弱加分，不再直接置为 100%。
        :param query_db: 数据库会话
        :param keyword: 搜索文本
        :param limit: 返回数量
        :param scored: 已有向量分数
        :param config: 相似度配置
        :return: 合并后的分数映射
        """
        keyword_weight = cls._safe_float(config.get("keywordWeight"), 0.15, 0.0, 1.0)
        vector_weight = cls._safe_float(config.get("vectorWeight"), 0.85, 0.0, 1.0)
        for index, ticket in enumerate(TicketDao.search_tickets_by_keyword(query_db, keyword, limit)):
            keyword_score = keyword_weight * (1 - (index / max(limit, 1)) * 0.5)
            vector_score = max(scored.get(ticket.ticket_id, 0.0), 0.0) * vector_weight
            scored[ticket.ticket_id] = max(scored.get(ticket.ticket_id, 0.0), min(vector_score + keyword_score, 1.0))
        return scored

    @classmethod
    def _build_ticket_search_result(
        cls,
        query_db: Session,
        scored: dict[int, float],
        limit: int,
        config: dict[str, Any],
    ) -> list[dict]:
        """
        根据分数映射装配工单搜索结果。
        :param query_db: 数据库会话
        :param scored: 工单ID到分数的映射
        :param limit: 返回数量
        :param config: 相似度配置
        :return: 搜索结果列表
        """
        threshold = cls._safe_float(config.get("threshold"), 0.05, -1.0, 1.0)
        top_ids = [
            ticket_id
            for ticket_id, _score in sorted(scored.items(), key=lambda item: item[1], reverse=True)
            if _score >= threshold
        ][:limit]
        ticket_map = {ticket.ticket_id: ticket for ticket in TicketDao.get_tickets_by_ids(query_db, top_ids)}
        result = []
        for ticket_id in top_ids:
            ticket = ticket_map.get(ticket_id)
            if not ticket:
                continue
            item = CamelCaseUtil.transform_result(ticket)
            item["score"] = round(scored[ticket_id], 4)
            result.append(item)
        return result

    @classmethod
    def _upsert_qdrant_ticket(
        cls,
        config: dict[str, Any],
        ticket: Ticket,
        vector: list[float],
        text: str,
        model: str,
        version: str,
    ) -> None:
        """
        将单个工单向量写入 Qdrant。
        :param config: 相似度配置
        :param ticket: 工单对象
        :param vector: 向量
        :param text: 入库文本
        :param model: Embedding 模型
        :param version: Embedding 版本
        :return: 无
        """
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else {}
        cls._ensure_qdrant_collection(config, expected_dimension=len(vector), allow_recreate=True)
        url = cls._qdrant_url(qdrant_config, f"/collections/{qdrant_config.get('collection')}/points")
        payload = {
            "points": [
                {
                    "id": int(ticket.ticket_id),
                    "vector": vector,
                    "payload": {
                        "objectType": "ticket",
                        "ticketId": int(ticket.ticket_id),
                        "ticketNo": ticket.ticket_no,
                        "title": ticket.title,
                        "moduleName": ticket.module_name,
                        "categoryName": ticket.category_name,
                        "model": model,
                        "version": version,
                        "contentHash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "updateTime": datetime.now().isoformat(),
                    },
                }
            ]
        }
        response = requests.put(
            url,
            headers=cls._qdrant_headers(qdrant_config),
            json=payload,
            timeout=cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120),
        )
        cls._raise_for_qdrant_status(response, f"写入工单向量: ticket_id={ticket.ticket_id}")

    @classmethod
    def _ensure_qdrant_collection(
        cls, config: dict[str, Any], expected_dimension: int | None = None, allow_recreate: bool = False
    ) -> None:
        """
        确保 Qdrant collection 存在，配置关闭自动创建时只做存在性校验。
        :param config: 相似度配置
        :param expected_dimension: 本次要写入或查询的实际向量维度
        :param allow_recreate: 当前调用链是否允许维度不一致时重建 collection
        :return: 无
        """
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else {}
        collection = str(qdrant_config.get("collection") or "").strip()
        if not collection:
            raise ValueError("Qdrant collection 未配置")
        headers = cls._qdrant_headers(qdrant_config)
        timeout = cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120)
        detail_url = cls._qdrant_url(qdrant_config, f"/collections/{collection}")
        detail_response = requests.get(detail_url, headers=headers, timeout=timeout)
        if detail_response.status_code == 200:
            collection_dimension = cls._extract_qdrant_vector_size(detail_response.json())
            if expected_dimension and collection_dimension and collection_dimension != expected_dimension:
                if allow_recreate and qdrant_config.get("recreateCollectionOnDimensionMismatch", False):
                    logger.warning(
                        f"Qdrant collection 维度不一致，按配置删除并重建: collection={collection}, "
                        f"collectionDimension={collection_dimension}, vectorDimension={expected_dimension}"
                    )
                    cls._recreate_qdrant_collection(
                        detail_url=detail_url,
                        headers=headers,
                        timeout=timeout,
                        collection=collection,
                        vector_size=expected_dimension,
                        distance=qdrant_config.get("distance") or "Cosine",
                    )
                    return
                raise ValueError(
                    f"Qdrant collection 向量维度不一致: collection={collection}, "
                    f"collectionDimension={collection_dimension}, vectorDimension={expected_dimension}。"
                    f"请确认 Embedding 配置 dimension/model 与既有 collection 一致，"
                    f"或使用新 collection 后重新重建向量。"
                )
            return
        if detail_response.status_code != 404 or not qdrant_config.get("createCollection", True):
            cls._raise_for_qdrant_status(detail_response, f"读取 collection: collection={collection}")
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        configured_dimension = embedding_config.get("dimension") if isinstance(embedding_config, dict) else None
        vector_size = cls._safe_int(expected_dimension or configured_dimension, cls.DIMENSION, 1, 16384)
        create_payload = {"vectors": {"size": vector_size, "distance": qdrant_config.get("distance") or "Cosine"}}
        create_response = requests.put(detail_url, headers=headers, json=create_payload, timeout=timeout)
        cls._raise_for_qdrant_status(create_response, f"创建 collection: collection={collection}")

    @classmethod
    def _recreate_qdrant_collection(
        cls,
        *,
        detail_url: str,
        headers: dict[str, str],
        timeout: int,
        collection: str,
        vector_size: int,
        distance: str,
    ) -> None:
        """
        删除并按当前向量维度重建 Qdrant collection，仅用于手动允许的写入链路。
        :param detail_url: collection 详情地址
        :param headers: Qdrant 请求头
        :param timeout: 请求超时时间
        :param collection: collection 名称
        :param vector_size: 新 collection 向量维度
        :param distance: 向量距离算法
        :return: 无
        """
        delete_response = requests.delete(detail_url, headers=headers, timeout=timeout)
        if delete_response.status_code != 404:
            cls._raise_for_qdrant_status(delete_response, f"删除 collection: collection={collection}")
        create_payload = {"vectors": {"size": vector_size, "distance": distance}}
        create_response = requests.put(detail_url, headers=headers, json=create_payload, timeout=timeout)
        if create_response.status_code == 409:
            detail_response = requests.get(detail_url, headers=headers, timeout=timeout)
            cls._raise_for_qdrant_status(detail_response, f"确认 collection: collection={collection}")
            collection_dimension = cls._extract_qdrant_vector_size(detail_response.json())
            if collection_dimension == vector_size:
                return
        cls._raise_for_qdrant_status(create_response, f"重建 collection: collection={collection}")

    @classmethod
    def _extract_qdrant_vector_size(cls, collection_detail: dict[str, Any]) -> int | None:
        """
        从 Qdrant collection 详情中解析默认向量维度，无法识别命名向量时返回空。
        :param collection_detail: Qdrant collection 详情响应
        :return: 默认向量维度
        """
        result = collection_detail.get("result") if isinstance(collection_detail, dict) else {}
        config = result.get("config") if isinstance(result, dict) else {}
        params = config.get("params") if isinstance(config, dict) else {}
        vectors = params.get("vectors") if isinstance(params, dict) else {}
        if isinstance(vectors, dict) and "size" in vectors:
            return cls._safe_int(vectors.get("size"), 0, 0, 16384) or None
        return None

    @classmethod
    def _raise_for_qdrant_status(cls, response: requests.Response, action: str) -> None:
        """
        检查 Qdrant HTTP 响应，失败时带上响应体，便于从日志判断具体原因。
        :param response: requests 响应对象
        :param action: 当前 Qdrant 操作描述
        :return: 无
        """
        if response.status_code < 400:
            return
        detail = response.text[:1000] if response.text else ""
        raise requests.HTTPError(
            f"Qdrant请求失败: action={action}, status={response.status_code}, detail={detail}",
            response=response,
        )

    @classmethod
    def _embed_text_openai_compatible(cls, text: str, embedding_config: dict[str, Any]) -> list[float]:
        """
        调用兼容 OpenAI /v1/embeddings 的接口生成向量。
        :param text: 原始文本
        :param embedding_config: Embedding 配置
        :return: 向量
        """
        endpoint = str(embedding_config.get("endpoint") or "").strip()
        if not endpoint:
            raise ValueError("Embedding endpoint 未配置")
        headers = {"Content-Type": "application/json"}
        api_key = str(embedding_config.get("apiKey") or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        dimension = cls._safe_int(embedding_config.get("dimension"), 0, 0, 16384)
        payload: dict[str, Any] = {"model": embedding_config.get("model"), "input": text}
        if dimension > 0:
            payload["dimensions"] = dimension
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=cls._safe_int(embedding_config.get("timeoutSeconds"), 15, 1, 120),
        )
        response.raise_for_status()
        data = response.json()
        vector = ((data.get("data") or [{}])[0] or {}).get("embedding")
        if not isinstance(vector, list):
            raise ValueError("Embedding 接口未返回 data[0].embedding")
        result = [float(item) for item in vector]
        if dimension > 0 and len(result) != dimension:
            raise ValueError(f"Embedding接口返回维度与配置不一致: expected={dimension}, actual={len(result)}")
        return result

    @classmethod
    def _embed_text_local_hash(cls, text: str, dimension: int | None = None) -> list[float]:
        """
        将文本转换为固定维度的本地哈希向量。
        :param text: 原始文本
        :param dimension: 向量维度
        :return: 归一化向量
        """
        safe_dimension = dimension or cls.DIMENSION
        vector = [0.0] * safe_dimension
        for token in cls._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % safe_dimension
            sign = 1 if digest[4] % 2 == 0 else -1
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 6) for value in vector]

    @classmethod
    def _tokens(cls, text: str) -> list[str]:
        """
        将中英文混合文本切分为哈希向量 token。
        :param text: 原始文本
        :return: token 列表
        """
        normalized = (text or "").lower()
        words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
        cjk = [word for word in words if re.fullmatch(r"[\u4e00-\u9fff]", word)]
        cjk_bigrams = [f"{cjk[index]}{cjk[index + 1]}" for index in range(len(cjk) - 1)]
        return words + cjk_bigrams

    @classmethod
    def _cosine(cls, left: list[float], right: list[float]) -> float:
        """
        计算两个向量的余弦相似度。
        :param left: 左侧向量
        :param right: 右侧向量
        :return: 相似度
        """
        if len(left) != len(right):
            return 0.0
        return sum(left[index] * float(right[index]) for index in range(len(left)))

    @classmethod
    def _qdrant_url(cls, qdrant_config: dict[str, Any], path: str) -> str:
        """
        拼接 Qdrant API 地址。
        :param qdrant_config: Qdrant 配置
        :param path: API 路径
        :return: 完整 URL
        """
        base_url = str(qdrant_config.get("url") or "").rstrip("/")
        if not base_url:
            raise ValueError("Qdrant url 未配置")
        return f"{base_url}{path}"

    @classmethod
    def _qdrant_headers(cls, qdrant_config: dict[str, Any]) -> dict[str, str]:
        """
        构造 Qdrant 请求头。
        :param qdrant_config: Qdrant 配置
        :return: 请求头
        """
        headers = {"Content-Type": "application/json"}
        api_key = str(qdrant_config.get("apiKey") or "").strip()
        if api_key:
            headers["api-key"] = api_key
        return headers

    @classmethod
    def _normalize_provider(cls, value: Any) -> str:
        """
        归一化相似度 Provider。
        :param value: 原始 Provider
        :return: Provider 编码
        """
        provider = str(value or cls.PROVIDER_LOCAL_HASH).strip().lower().replace("-", "_")
        return provider if provider in {cls.PROVIDER_LOCAL_HASH, cls.PROVIDER_QDRANT} else cls.PROVIDER_LOCAL_HASH

    @classmethod
    def _normalize_embedding_provider(cls, value: Any) -> str:
        """
        归一化 Embedding Provider。
        :param value: 原始 Provider
        :return: Provider 编码
        """
        provider = str(value or cls.PROVIDER_LOCAL_HASH).strip().lower().replace("-", "_")
        return provider if provider in {cls.PROVIDER_LOCAL_HASH, "openai_compatible"} else cls.PROVIDER_LOCAL_HASH

    @classmethod
    def _deep_merge(cls, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """
        深度合并配置字典。
        :param base: 默认配置
        :param override: 覆盖配置
        :return: 合并后的配置
        """
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = cls._deep_merge(dict(base[key]), value)
            else:
                base[key] = value
        return base

    @classmethod
    def _normalize_config_for_save(cls, config: dict[str, Any]) -> dict[str, Any]:
        """
        规范化前端提交的相似度配置。
        :param config: 原始配置
        :return: 规范化配置
        """
        source = config if isinstance(config, dict) else {}
        normalized = json.loads(json.dumps(cls.DEFAULT_CONFIG, ensure_ascii=False))
        normalized = cls._deep_merge(normalized, source)
        normalized["enabled"] = bool(normalized.get("enabled", True))
        normalized["provider"] = cls._normalize_provider(normalized.get("provider"))
        normalized["fallbackProvider"] = cls._normalize_provider(normalized.get("fallbackProvider"))
        normalized["topK"] = cls._safe_int(normalized.get("topK"), 20, 1, 100)
        normalized["threshold"] = cls._safe_float(normalized.get("threshold"), 0.05, -1.0, 1.0)
        normalized["keywordWeight"] = cls._safe_float(normalized.get("keywordWeight"), 0.15, 0.0, 1.0)
        normalized["vectorWeight"] = cls._safe_float(normalized.get("vectorWeight"), 0.85, 0.0, 1.0)
        normalized["fields"] = [
            str(item or "").strip()
            for item in normalized.get("fields", [])
            if str(item or "").strip()
        ] or list(cls.DEFAULT_CONFIG["fields"])
        embedding_config = normalized.get("embedding") if isinstance(normalized.get("embedding"), dict) else {}
        embedding_config["provider"] = cls._normalize_embedding_provider(embedding_config.get("provider"))
        embedding_config["model"] = str(embedding_config.get("model") or cls.MODEL).strip()
        embedding_config["version"] = str(embedding_config.get("version") or cls.VERSION).strip()
        embedding_config["dimension"] = cls._safe_int(embedding_config.get("dimension"), cls.DIMENSION, 1, 16384)
        embedding_config["endpoint"] = str(embedding_config.get("endpoint") or "").strip()
        embedding_config["apiKey"] = str(embedding_config.get("apiKey") or "").strip()
        embedding_config["timeoutSeconds"] = cls._safe_int(embedding_config.get("timeoutSeconds"), 15, 1, 120)
        normalized["embedding"] = embedding_config
        qdrant_config = normalized.get("qdrant") if isinstance(normalized.get("qdrant"), dict) else {}
        qdrant_config["url"] = str(qdrant_config.get("url") or "").strip() or cls.DEFAULT_CONFIG["qdrant"]["url"]
        qdrant_config["apiKey"] = str(qdrant_config.get("apiKey") or "").strip()
        qdrant_config["collection"] = (
            str(qdrant_config.get("collection") or "").strip() or cls.DEFAULT_CONFIG["qdrant"]["collection"]
        )
        qdrant_config["distance"] = str(qdrant_config.get("distance") or "Cosine").strip() or "Cosine"
        qdrant_config["timeoutSeconds"] = cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120)
        qdrant_config["createCollection"] = bool(qdrant_config.get("createCollection", True))
        qdrant_config["recreateCollectionOnDimensionMismatch"] = bool(
            qdrant_config.get("recreateCollectionOnDimensionMismatch", False)
        )
        normalized["qdrant"] = qdrant_config
        scene_triggers = normalized.get("sceneTriggers") if isinstance(normalized.get("sceneTriggers"), dict) else {}
        normalized["sceneTriggers"] = {
            key: bool(scene_triggers.get(key, default_value))
            for key, default_value in cls.DEFAULT_CONFIG["sceneTriggers"].items()
        }
        return normalized

    @classmethod
    def _safe_int(cls, value: Any, default: int, min_value: int, max_value: int) -> int:
        """
        安全解析整数并限制范围。
        :param value: 原始值
        :param default: 默认值
        :param min_value: 最小值
        :param max_value: 最大值
        :return: 整数值
        """
        try:
            parsed = int(value)
        except Exception:
            parsed = default
        return min(max(parsed, min_value), max_value)

    @classmethod
    def _safe_float(cls, value: Any, default: float, min_value: float, max_value: float) -> float:
        """
        安全解析浮点数并限制范围。
        :param value: 原始值
        :param default: 默认值
        :param min_value: 最小值
        :param max_value: 最大值
        :return: 浮点值
        """
        try:
            parsed = float(value)
        except Exception:
            parsed = default
        return min(max(parsed, min_value), max_value)

    @classmethod
    def rebuild_with_independent_session(
        cls,
        payload,
        trace_id: str | None = None,
    ) -> None:
        """
        在后台任务中使用独立数据库会话重建工单向量，避免复用请求会话。
        :param payload: 工单向量重建请求参数
        :param trace_id: 日志追踪ID，用于串联提交请求与后台重建过程
        :return: 无
        """
        if trace_id:
            with trace_context(trace_id):
                cls.rebuild_with_independent_session(payload)
            return

        with SessionLocal() as db:
            ticket_ids, missing_ticket_nos = cls.resolve_ticket_ids_for_rebuild(
                db, getattr(payload, "ticket_nos", None), getattr(payload, "ticket_ids", None)
            )
            result = cls.rebuild_ticket_embeddings(
                db,
                ticket_ids=ticket_ids,
                page_size=payload.page_size,
                provider=payload.provider,
                include_qdrant=payload.include_qdrant,
            )
            result["missingTicketNos"] = missing_ticket_nos[:100]
            logger.info(f"工单向量后台重建完成: result={result}")

    @classmethod
    def rebuild_result_with_independent_session(cls, payload) -> dict:
        """
        在线程池中使用独立数据库会话重建工单向量并返回结果。
        :param payload: 工单向量重建请求参数
        :return: 重建结果摘要
        """
        with SessionLocal() as db:
            ticket_ids, missing_ticket_nos = cls.resolve_ticket_ids_for_rebuild(
                db, getattr(payload, "ticket_nos", None), getattr(payload, "ticket_ids", None)
            )
            result = cls.rebuild_ticket_embeddings(
                db,
                ticket_ids=ticket_ids,
                page_size=payload.page_size,
                provider=payload.provider,
                include_qdrant=payload.include_qdrant,
            )
            result["missingTicketNos"] = missing_ticket_nos[:100]
            return result
