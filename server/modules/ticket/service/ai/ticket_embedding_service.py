import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from config.database import SessionLocal
from context.request_context import trace_context
from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.do.config_do import SysConfig
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import EmbeddingRecord, Ticket, TicketRca
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class ExternalEmbeddingUnavailableError(RuntimeError):
    """
    外部 Embedding 不可用异常，用于批量重建时熔断后续外部接口请求。
    """


class TicketEmbeddingService:
    """
    工单相似度检索服务，按配置严格使用本地哈希、外部 Embedding 或 Qdrant。
    """

    CONFIG_KEY = "ticket.similarity.config"
    MODEL = "local-hash"
    VERSION = "v1"
    DIMENSION = 128
    PROVIDER_LOCAL_HASH = "local_hash"
    PROVIDER_EMBEDDING = "embedding"
    PROVIDER_QDRANT = "qdrant"
    DEFAULT_CONFIG: dict[str, Any] = {
        "enabled": True,
        "provider": PROVIDER_LOCAL_HASH,
        # 历史字段，仅用于兼容旧配置 JSON；严格模式下不再读取降级 Provider。
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
            "requestParams": {},
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
            "bitablePull": True,
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
        raw_scene_triggers: dict[str, Any] = {}
        if raw_value:
            try:
                parsed = json.loads(raw_value)
                if isinstance(parsed, dict):
                    raw_scene_triggers = (
                        parsed.get("sceneTriggers") if isinstance(parsed.get("sceneTriggers"), dict) else {}
                    )
                    config = cls._deep_merge(config, parsed)
            except Exception as exc:
                logger.warning(f"工单相似度配置解析失败，使用默认配置: key={cls.CONFIG_KEY}, error={exc}")
        config["provider"] = cls._normalize_provider(config.get("provider"))
        config["topK"] = cls._safe_int(config.get("topK"), 20, 1, 100)
        config["threshold"] = cls._safe_float(config.get("threshold"), 0.05, -1.0, 1.0)
        config["keywordWeight"] = cls._safe_float(config.get("keywordWeight"), 0.15, 0.0, 1.0)
        config["vectorWeight"] = cls._safe_float(config.get("vectorWeight"), 0.85, 0.0, 1.0)
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        embedding_config["provider"] = cls._normalize_embedding_provider(embedding_config.get("provider"))
        embedding_config["dimension"] = cls._safe_int(embedding_config.get("dimension"), cls.DIMENSION, 1, 16384)
        request_params = embedding_config.get("requestParams")
        embedding_config["requestParams"] = dict(request_params) if isinstance(request_params, dict) else {}
        config["embedding"] = embedding_config
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else {}
        qdrant_config["timeoutSeconds"] = cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120)
        qdrant_config["createCollection"] = bool(qdrant_config.get("createCollection", True))
        qdrant_config["recreateCollectionOnDimensionMismatch"] = bool(
            qdrant_config.get("recreateCollectionOnDimensionMismatch", False)
        )
        config["qdrant"] = qdrant_config
        scene_triggers = config.get("sceneTriggers") if isinstance(config.get("sceneTriggers"), dict) else {}
        bitable_pull_default = cls.DEFAULT_CONFIG["sceneTriggers"]["bitablePull"]
        if "bitablePull" not in raw_scene_triggers and "externalSync" in raw_scene_triggers:
            bitable_pull_default = bool(raw_scene_triggers.get("externalSync"))
        config["sceneTriggers"] = {
            key: (
                bool(bitable_pull_default)
                if key == "bitablePull" and "bitablePull" not in raw_scene_triggers
                else bool(scene_triggers.get(key, default_value))
            )
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
            cls._validate_similarity_config(normalized)
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
    def _validate_similarity_config(cls, config: dict[str, Any]) -> None:
        """
        校验相似工单配置的 Provider 组合和已存在 Qdrant collection 维度。
        :param config: 已规范化的相似工单配置
        :return: 无
        """
        provider = cls._normalize_provider(config.get("provider"))
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        embedding_provider = cls._normalize_embedding_provider(embedding_config.get("provider"))
        if provider == cls.PROVIDER_LOCAL_HASH:
            return
        if embedding_provider != "openai_compatible":
            raise ValueError(f"检索 Provider={provider} 时，Embedding Provider 必须配置为 openai_compatible")
        if provider == cls.PROVIDER_QDRANT:
            cls._validate_qdrant_collection_dimension(config)

    @classmethod
    def _validate_qdrant_collection_dimension(cls, config: dict[str, Any]) -> None:
        """
        保存 Qdrant 配置时，如果目标 collection 已存在则提前校验维度是否一致。
        :param config: 已规范化的相似工单配置
        :return: 无
        """
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else {}
        collection = str(qdrant_config.get("collection") or "").strip()
        if not collection:
            raise ValueError("Qdrant collection 未配置")
        detail_url = cls._qdrant_url(qdrant_config, f"/collections/{collection}")
        timeout = cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120)
        response = httpx.get(detail_url, headers=cls._qdrant_headers(qdrant_config), timeout=timeout)
        if response.status_code == 404:
            logger.info(f"Qdrant配置保存校验跳过: collection={collection}, reason=collection不存在")
            return
        cls._raise_for_qdrant_status(response, f"保存配置校验 collection: collection={collection}")
        collection_dimension = cls._extract_qdrant_vector_size(response.json())
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        configured_dimension = cls._safe_int(embedding_config.get("dimension"), cls.DIMENSION, 1, 16384)
        logger.info(
            f"Qdrant配置保存校验: collection={collection}, collectionDimension={collection_dimension}, "
            f"configuredDimension={configured_dimension}"
        )
        if collection_dimension and collection_dimension != configured_dimension:
            raise ValueError(
                f"Qdrant collection 向量维度不一致: collection={collection}, "
                f"collectionDimension={collection_dimension}, configuredDimension={configured_dimension}。"
                f"请调整 Embedding 维度或更换 Collection 后再保存。"
            )

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
            logger.info(
                f"跳过工单场景向量刷新: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"scene={scene}, reason=相似工单配置未启用或场景开关关闭"
            )
            return False
        cls.vectorize_ticket(query_db, ticket, rca=rca, config=active_config)
        logger.info(
            f"工单场景向量刷新完成: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, scene={scene}"
        )
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
            logger.info(
                f"跳过工单批量场景向量刷新: scene={scene}, count={len(tickets)}, "
                f"reason=相似工单配置未启用或场景开关关闭"
            )
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
        cls, text: str, config: dict[str, Any] | None = None
    ) -> list[float]:
        """
        将文本转换为向量；配置本地哈希就只用本地哈希，配置外部接口就只调用外部接口。
        :param text: 原始文本
        :param config: 相似度配置
        :return: 归一化向量
        """
        embedding_config = (config or {}).get("embedding") if isinstance((config or {}).get("embedding"), dict) else {}
        provider = cls._normalize_embedding_provider(embedding_config.get("provider"))
        if provider == "openai_compatible":
            try:
                return cls._embed_text_openai_compatible(text, embedding_config)
            except Exception as exc:
                raise ExternalEmbeddingUnavailableError(
                    f"外部Embedding生成失败，严格模式不回退本地哈希: provider={provider}, error={exc}"
                ) from exc
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
        force_rebuild: bool = False,
    ) -> EmbeddingRecord:
        """
        为单个工单生成或更新向量记录，并按配置同步外部向量库。
        :param query_db: 数据库会话
        :param ticket: 工单对象
        :param rca: 可选 RCA 对象
        :param config: 相似度配置
        :param sync_qdrant: 是否同步写入 Qdrant，None 表示由配置决定
        :param force_rebuild: 是否强制重新生成向量，默认按内容哈希幂等跳过
        :return: 向量记录
        """
        active_config = config or cls.get_similarity_config(query_db)
        vector_provider = cls._normalize_provider(active_config.get("provider"))
        vector_config = cls._config_for_vector_provider(active_config, vector_provider)
        text = cls.build_ticket_text(ticket, rca=rca, config=active_config)
        embedding_config = vector_config.get("embedding") if isinstance(vector_config.get("embedding"), dict) else {}
        model = str(embedding_config.get("model") or cls.MODEL)
        version = str(embedding_config.get("version") or cls.VERSION)
        configured_dimension = cls._safe_int(embedding_config.get("dimension"), cls.DIMENSION, 1, 16384)
        content_hash = cls._embedding_content_hash(text, active_config)
        should_sync_qdrant = vector_provider == cls.PROVIDER_QDRANT
        if sync_qdrant is not None and bool(sync_qdrant) != should_sync_qdrant:
            logger.info(
                f"忽略手动Qdrant同步覆盖: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"provider={vector_provider}, requestedSyncQdrant={sync_qdrant}, "
                f"effectiveSyncQdrant={should_sync_qdrant}"
            )
        logger.info(
            f"工单向量生成开始: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"provider={vector_provider}, embeddingProvider={embedding_config.get('provider')}, "
            f"model={embedding_config.get('model')}, "
            f"configuredDimension={embedding_config.get('dimension')}, shouldSyncQdrant={should_sync_qdrant}, "
            f"textChars={len(text)}"
        )
        existing_record = TicketDao.get_embedding_record(query_db, "ticket", ticket.ticket_id, model, version)
        if cls._can_reuse_embedding_record(existing_record, content_hash, configured_dimension, force_rebuild):
            logger.info(
                f"跳过外部Embedding请求: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=内容哈希、模型版本和维度未变化, contentHash={content_hash[:12]}, "
                f"vectorDimension={existing_record.embedding_dimension}"
            )
            existing_record._embedding_reused = True
            existing_record._qdrant_synced_from_cache = False
            if should_sync_qdrant:
                cls._upsert_qdrant_ticket(
                    active_config,
                    ticket,
                    existing_record.embedding,
                    text,
                    model,
                    version,
                    content_hash,
                    reused=True,
                )
                existing_record._qdrant_synced_from_cache = True
            return existing_record
        if existing_record and force_rebuild:
            logger.info(
                f"强制重建向量: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=forceRebuild=true"
            )
        elif existing_record:
            logger.info(
                f"需要重新生成向量: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"oldHash={str(existing_record.content_hash or '')[:12]}, newHash={content_hash[:12]}, "
                f"oldDimension={existing_record.embedding_dimension}, configuredDimension={configured_dimension}"
            )
        vector = cls.embed_text(text, vector_config)
        logger.info(
            f"工单向量生成完成: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"vectorDimension={len(vector)}, contentHash={content_hash[:12]}"
        )
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
            cls._upsert_qdrant_ticket(active_config, ticket, vector, text, model, version, content_hash)
        else:
            logger.info(
                f"跳过Qdrant写入: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=当前配置未要求同步Qdrant"
            )
        saved_record._embedding_reused = False
        saved_record._qdrant_synced_from_cache = False
        return saved_record

    @classmethod
    def vectorize_tickets(
        cls,
        query_db: Session,
        tickets: list[Ticket],
        *,
        config: dict[str, Any] | None = None,
        sync_qdrant: bool | None = None,
        force_rebuild: bool = False,
    ) -> int:
        """
        批量生成工单向量。
        :param query_db: 数据库会话
        :param tickets: 工单对象列表
        :param config: 相似度配置
        :param sync_qdrant: 是否同步写入 Qdrant
        :param force_rebuild: 是否强制重新生成向量
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
                force_rebuild=force_rebuild,
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
        force_rebuild: bool = False,
    ) -> dict[str, Any]:
        """
        批量重建历史工单向量，文本范围包含标题、描述、AI 摘要和 RCA。
        :param query_db: 数据库会话
        :param ticket_ids: 可选指定工单ID列表
        :param page_size: 每批处理数量
        :param provider: 指定 Provider，传空则读取配置
        :param include_qdrant: 是否同步 Qdrant，传空则由配置决定
        :param force_rebuild: 是否强制重新生成向量
        :return: 重建结果摘要
        """
        active_config = cls.ensure_default_config(query_db)
        if provider:
            active_config["provider"] = cls._normalize_provider(provider)
        safe_page_size = min(max(int(page_size or 100), 1), 500)
        total = TicketDao.count_tickets_for_embedding(query_db, ticket_ids)
        embedding_config = active_config.get("embedding") if isinstance(active_config.get("embedding"), dict) else {}
        qdrant_config = active_config.get("qdrant") if isinstance(active_config.get("qdrant"), dict) else {}
        qdrant_synced = active_config.get("provider") == cls.PROVIDER_QDRANT
        if include_qdrant is not None and bool(include_qdrant) != qdrant_synced:
            logger.info(
                f"忽略手动Qdrant同步覆盖: provider={active_config.get('provider')}, "
                f"requestedIncludeQdrant={include_qdrant}, effectiveQdrantSynced={qdrant_synced}"
            )
        logger.info(
            f"工单向量重建开始: total={total}, specifiedTicketIds={bool(ticket_ids)}, "
            f"pageSize={safe_page_size}, provider={active_config.get('provider')}, "
            f"embeddingProvider={embedding_config.get('provider')}, model={embedding_config.get('model')}, "
            f"configuredDimension={embedding_config.get('dimension')}, includeQdrant={include_qdrant}, "
            f"qdrantSynced={qdrant_synced}, qdrantCollection={qdrant_config.get('collection')}, "
            f"recreateOnDimensionMismatch={qdrant_config.get('recreateCollectionOnDimensionMismatch')}, "
            f"forceRebuild={force_rebuild}"
        )
        processed = 0
        failed = 0
        failed_items: list[dict[str, Any]] = []
        skipped = 0
        idempotent_skipped = 0
        qdrant_synced_from_cache = 0
        abort_reason: str | None = None
        offset = 0
        while processed + failed < total and not abort_reason:
            current_offset = offset if not ticket_ids else processed + failed
            batch = TicketDao.list_tickets_for_embedding(
                query_db,
                offset=current_offset,
                limit=safe_page_size,
                ticket_ids=ticket_ids,
            )
            if not batch:
                break
            logger.info(
                f"工单向量重建批次开始: offset={current_offset}, batchSize={len(batch)}, "
                f"processed={processed}, failed={failed}"
            )
            rca_map = TicketDao.list_rca_by_ticket_ids(query_db, [ticket.ticket_id for ticket in batch])
            for ticket in batch:
                try:
                    record = cls.vectorize_ticket(
                        query_db,
                        ticket,
                        rca=rca_map.get(ticket.ticket_id),
                        config=active_config,
                        sync_qdrant=include_qdrant,
                        force_rebuild=force_rebuild,
                    )
                    if getattr(record, "_embedding_reused", False):
                        idempotent_skipped += 1
                        if getattr(record, "_qdrant_synced_from_cache", False):
                            qdrant_synced_from_cache += 1
                    processed += 1
                except ExternalEmbeddingUnavailableError as exc:
                    failed += 1
                    abort_reason = str(exc)
                    failed_items.append({"ticketId": ticket.ticket_id, "ticketNo": ticket.ticket_no, "error": str(exc)})
                    logger.error(
                        f"外部Embedding异常，停止本次重建后续外部请求: ticket_id={ticket.ticket_id}, "
                        f"ticket_no={ticket.ticket_no}, processed={processed}, failed={failed}, error={exc}"
                    )
                    break
                except Exception as exc:
                    failed += 1
                    failed_items.append({"ticketId": ticket.ticket_id, "ticketNo": ticket.ticket_no, "error": str(exc)})
                    logger.warning(
                        f"工单向量重建失败: ticket_id={ticket.ticket_id}, "
                        f"ticket_no={ticket.ticket_no}, error={exc}"
                    )
            query_db.commit()
            logger.info(
                f"工单向量重建批次结束: offset={current_offset}, processed={processed}, failed={failed}, "
                f"abort={bool(abort_reason)}"
            )
            offset += safe_page_size
        if abort_reason:
            skipped = max(total - processed - failed, 0)
            logger.warning(
                f"工单向量重建提前停止: processed={processed}, failed={failed}, skipped={skipped}, "
                f"reason={abort_reason}"
            )
        logger.info(
            f"工单向量重建结束: total={total}, processed={processed}, failed={failed}, skipped={skipped}, "
            f"provider={active_config.get('provider')}, qdrantSynced={qdrant_synced}"
        )
        return {
            "total": total,
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
            "idempotentSkipped": idempotent_skipped,
            "qdrantSyncedFromCache": qdrant_synced_from_cache,
            "abortReason": abort_reason,
            "failedItems": failed_items[:20],
            "provider": active_config.get("provider"),
            "qdrantSynced": qdrant_synced,
        }

    @classmethod
    def _embedding_content_hash(cls, text: str, config: dict[str, Any]) -> str:
        """
        根据向量化字段配置和最终文本计算内容哈希，字段范围变化也会触发重新生成。
        :param text: 实际参与向量化的文本
        :param config: 相似度配置
        :return: 内容哈希
        """
        fields = config.get("fields") if isinstance(config.get("fields"), list) else cls.DEFAULT_CONFIG["fields"]
        payload = {"fields": [str(item) for item in fields], "text": text}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @classmethod
    def _config_for_vector_provider(cls, config: dict[str, Any], provider: str) -> dict[str, Any]:
        """
        根据顶层检索 Provider 生成向量化配置，避免外部 Embedding 与本地 hash 互相兜底。
        :param config: 当前相似度配置
        :param provider: 顶层检索 Provider
        :return: 用于生成向量的配置
        """
        resolved = json.loads(json.dumps(config, ensure_ascii=False))
        embedding_config = resolved.get("embedding") if isinstance(resolved.get("embedding"), dict) else {}
        if provider == cls.PROVIDER_LOCAL_HASH:
            embedding_config["provider"] = cls.PROVIDER_LOCAL_HASH
            embedding_config["model"] = cls.MODEL
            embedding_config["version"] = cls.VERSION
            embedding_config["dimension"] = cls._safe_int(embedding_config.get("dimension"), cls.DIMENSION, 1, 16384)
        elif cls._normalize_embedding_provider(embedding_config.get("provider")) != "openai_compatible":
            raise ValueError(f"检索 Provider={provider} 时，embedding.provider 必须配置为 openai_compatible")
        resolved["embedding"] = embedding_config
        return resolved

    @classmethod
    def _can_reuse_embedding_record(
        cls,
        record: EmbeddingRecord | None,
        content_hash: str,
        configured_dimension: int,
        force_rebuild: bool,
    ) -> bool:
        """
        判断已有向量是否可复用，避免重复调用外部 Embedding。
        :param record: 已有向量记录
        :param content_hash: 当前向量化内容哈希
        :param configured_dimension: 当前配置维度
        :param force_rebuild: 是否强制重建
        :return: 可以复用返回 True
        """
        if force_rebuild or not record:
            return False
        return (
            str(record.content_hash or "") == content_hash
            and int(record.embedding_dimension or 0) == configured_dimension
            and isinstance(record.embedding, list)
            and len(record.embedding) == configured_dimension
        )

    @classmethod
    def search_tickets(cls, query_db: Session, keyword: str, limit: int = 20) -> list[dict]:
        """
        使用自然语言进行相似工单检索，严格按配置 Provider 查询，不做降级或关键词混合。
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
        logger.info(f"工单相似度检索开始: provider={provider}, keywordChars={len(keyword or '')}, limit={safe_limit}")
        if provider == cls.PROVIDER_QDRANT:
            scored = cls._search_qdrant(query_db, keyword, safe_limit, config)
        elif provider == cls.PROVIDER_EMBEDDING:
            scored = cls._search_embedding(query_db, keyword, safe_limit, config)
        else:
            scored = cls._search_local_hash(query_db, keyword, safe_limit, config)
        return cls._build_ticket_search_result(query_db, scored, safe_limit, config)

    @classmethod
    def get_ticket_embedding_context(
        cls,
        query_db: Session,
        ticket: Ticket,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        读取当前工单可复用的向量上下文，不触发外部 Embedding。
        :param query_db: 数据库会话
        :param ticket: 当前工单
        :param config: 相似度配置
        :return: 状态、消息、向量记录和向量身份信息
        """
        active_config = config or cls.get_similarity_config(query_db)
        if not active_config.get("enabled", True):
            return {"status": "disabled", "message": "相似工单检索未启用"}
        provider = cls._normalize_provider(active_config.get("provider"))
        vector_config = cls._config_for_vector_provider(active_config, provider)
        embedding_config = vector_config.get("embedding") if isinstance(vector_config.get("embedding"), dict) else {}
        model = str(embedding_config.get("model") or cls.MODEL)
        version = str(embedding_config.get("version") or cls.VERSION)
        dimension = cls._safe_int(embedding_config.get("dimension"), cls.DIMENSION, 1, 16384)
        rca_map = TicketDao.list_rca_by_ticket_ids(query_db, [ticket.ticket_id])
        text = cls.build_ticket_text(ticket, rca=rca_map.get(ticket.ticket_id), config=active_config)
        content_hash = cls._embedding_content_hash(text, active_config)
        record = TicketDao.get_embedding_record(query_db, "ticket", ticket.ticket_id, model, version)
        if not record or not isinstance(record.embedding, list):
            return {
                "status": "missing",
                "message": "当前工单向量未生成，等待自动刷新或手动重建后可查看相似工单。",
                "provider": provider,
                "model": model,
                "version": version,
                "dimension": dimension,
                "contentHash": content_hash,
            }
        if (
            str(record.content_hash or "") != content_hash
            or int(record.embedding_dimension or 0) != dimension
            or len(record.embedding) != dimension
        ):
            return {
                "status": "stale",
                "message": "当前工单向量已过期，等待自动刷新或手动重建后可查看相似工单。",
                "provider": provider,
                "model": model,
                "version": version,
                "dimension": dimension,
                "contentHash": content_hash,
                "record": record,
            }
        return {
            "status": "ready",
            "message": "",
            "provider": provider,
            "model": model,
            "version": version,
            "dimension": dimension,
            "contentHash": content_hash,
            "record": record,
            "vector": record.embedding,
            "config": active_config,
        }

    @classmethod
    def search_tickets_by_vector(
        cls,
        query_db: Session,
        query_vector: list[float],
        limit: int,
        config: dict[str, Any],
        exclude_ticket_id: int | None = None,
    ) -> list[dict]:
        """
        使用已保存向量查询相似工单，不触发外部 Embedding。
        :param query_db: 数据库会话
        :param query_vector: 当前工单已保存向量
        :param limit: 返回数量
        :param config: 相似度配置
        :param exclude_ticket_id: 排除当前工单ID
        :return: 带 score 的工单列表
        """
        provider = cls._normalize_provider(config.get("provider"))
        safe_limit = min(max(limit or 5, 1), 100)
        if provider == cls.PROVIDER_QDRANT:
            scored = cls.search_qdrant_by_vector(query_vector, safe_limit + 1, config)
        else:
            scored = cls.search_embedding_records_by_vector(query_db, query_vector, safe_limit + 1, config, provider)
        if exclude_ticket_id:
            scored.pop(int(exclude_ticket_id), None)
        return cls._build_ticket_search_result(query_db, scored, safe_limit, config)

    @classmethod
    def search_embedding_records_by_vector(
        cls,
        query_db: Session,
        query_vector: list[float],
        limit: int,
        config: dict[str, Any],
        provider: str,
    ) -> dict[int, float]:
        """
        使用数据库中保存的向量记录计算相似度。
        :param query_db: 数据库会话
        :param query_vector: 查询向量
        :param limit: 返回数量
        :param config: 相似度配置
        :param provider: local_hash 或 embedding
        :return: 工单ID到分数的映射
        """
        vector_config = cls._config_for_vector_provider(config, provider)
        embedding_config = vector_config.get("embedding") if isinstance(vector_config.get("embedding"), dict) else {}
        model = str(embedding_config.get("model") or cls.MODEL)
        version = str(embedding_config.get("version") or cls.VERSION)
        scored: dict[int, float] = {}
        for record in TicketDao.list_ticket_embedding_records(query_db, model, version):
            if not isinstance(record.embedding, list):
                continue
            score = cls._cosine(query_vector, record.embedding)
            if score > config.get("threshold", 0.05):
                scored[record.object_id] = max(scored.get(record.object_id, 0.0), score)
        return dict(sorted(scored.items(), key=lambda item: item[1], reverse=True)[:limit])

    @classmethod
    def search_qdrant_by_vector(
        cls,
        query_vector: list[float],
        limit: int,
        config: dict[str, Any],
    ) -> dict[int, float]:
        """
        使用已保存向量查询 Qdrant，不调用外部 Embedding。
        :param query_vector: 查询向量
        :param limit: 返回数量
        :param config: 相似度配置
        :return: 工单ID到分数的映射
        """
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else {}
        cls._ensure_qdrant_collection(config, expected_dimension=len(query_vector), allow_recreate=False)
        url = cls._qdrant_url(qdrant_config, f"/collections/{qdrant_config.get('collection')}/points/search")
        payload = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "score_threshold": config.get("threshold", 0.05),
        }
        response = httpx.post(
            url,
            headers=cls._qdrant_headers(qdrant_config),
            json=payload,
            timeout=cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120),
        )
        cls._raise_for_qdrant_status(response, "使用缓存向量查询相似工单")
        rows = response.json().get("result") or []
        scored: dict[int, float] = {}
        for row in rows:
            payload_data = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            ticket_id = cls._safe_int(payload_data.get("ticketId") or row.get("id"), 0, 0, 9223372036854775807)
            if ticket_id > 0:
                scored[ticket_id] = max(scored.get(ticket_id, 0.0), float(row.get("score") or 0.0))
        return scored

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
        local_config = cls._config_for_vector_provider(config, cls.PROVIDER_LOCAL_HASH)
        query_vector = cls.embed_text(keyword, local_config)
        model = cls.MODEL
        version = cls.VERSION
        scored: dict[int, float] = {}
        for record in TicketDao.list_ticket_embedding_records(query_db, model, version):
            if not isinstance(record.embedding, list):
                continue
            score = cls._cosine(query_vector, record.embedding)
            if score > config.get("threshold", 0.05):
                scored[record.object_id] = max(scored.get(record.object_id, 0.0), score)
        return dict(sorted(scored.items(), key=lambda item: item[1], reverse=True)[:limit])

    @classmethod
    def _search_embedding(
        cls,
        query_db: Session,
        keyword: str,
        limit: int,
        config: dict[str, Any],
    ) -> dict[int, float]:
        """
        使用本地数据库中保存的外部 Embedding 向量计算余弦相似度。
        :param query_db: 数据库会话
        :param keyword: 搜索文本
        :param limit: 返回数量
        :param config: 相似度配置
        :return: 工单ID到分数的映射
        """
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        if cls._normalize_embedding_provider(embedding_config.get("provider")) != "openai_compatible":
            raise ValueError("检索 Provider=embedding 时，embedding.provider 必须配置为 openai_compatible")
        model = str(embedding_config.get("model") or cls.MODEL)
        version = str(embedding_config.get("version") or cls.VERSION)
        vector_config = cls._config_for_vector_provider(config, cls.PROVIDER_EMBEDDING)
        query_vector = cls.embed_text(keyword, vector_config)
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
        response = httpx.post(
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
        content_hash: str,
        reused: bool = False,
    ) -> None:
        """
        将单个工单向量写入 Qdrant。
        :param config: 相似度配置
        :param ticket: 工单对象
        :param vector: 向量
        :param text: 入库文本
        :param model: Embedding 模型
        :param version: Embedding 版本
        :param content_hash: 与本地向量记录一致的内容哈希
        :param reused: 是否复用已有向量写入 Qdrant
        :return: 无
        """
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else {}
        logger.info(
            f"Qdrant写入开始: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"collection={qdrant_config.get('collection')}, vectorDimension={len(vector)}, "
            f"model={model}, version={version}, reused={reused}"
        )
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
                        "contentHash": content_hash,
                        "updateTime": datetime.now().isoformat(),
                    },
                }
            ]
        }
        response = httpx.put(
            url,
            headers=cls._qdrant_headers(qdrant_config),
            json=payload,
            timeout=cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120),
        )
        cls._raise_for_qdrant_status(response, f"写入工单向量: ticket_id={ticket.ticket_id}")
        logger.info(
            f"Qdrant写入完成: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"collection={qdrant_config.get('collection')}, vectorDimension={len(vector)}, reused={reused}"
        )

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
        detail_response = httpx.get(detail_url, headers=headers, timeout=timeout)
        if detail_response.status_code == 200:
            collection_dimension = cls._extract_qdrant_vector_size(detail_response.json())
            logger.info(
                f"Qdrant collection检查: collection={collection}, status=exists, "
                f"collectionDimension={collection_dimension}, expectedDimension={expected_dimension}, "
                f"allowRecreate={allow_recreate}"
            )
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
            logger.warning(
                f"Qdrant collection检查失败且不创建: collection={collection}, "
                f"status={detail_response.status_code}, createCollection={qdrant_config.get('createCollection', True)}"
            )
            cls._raise_for_qdrant_status(detail_response, f"读取 collection: collection={collection}")
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        configured_dimension = embedding_config.get("dimension") if isinstance(embedding_config, dict) else None
        vector_size = cls._safe_int(expected_dimension or configured_dimension, cls.DIMENSION, 1, 16384)
        logger.info(
            f"Qdrant collection不存在，准备创建: collection={collection}, vectorSize={vector_size}, "
            f"distance={qdrant_config.get('distance') or 'Cosine'}"
        )
        create_payload = {"vectors": {"size": vector_size, "distance": qdrant_config.get("distance") or "Cosine"}}
        create_response = httpx.put(detail_url, headers=headers, json=create_payload, timeout=timeout)
        cls._raise_for_qdrant_status(create_response, f"创建 collection: collection={collection}")
        logger.info(f"Qdrant collection创建完成: collection={collection}, vectorSize={vector_size}")

    @classmethod
    def list_qdrant_collections(cls, config: dict[str, Any]) -> dict[str, Any]:
        """
        查询 Qdrant collection 列表并解析默认向量维度，供配置页面提示维度匹配情况。
        :param config: 相似度配置或仅包含 qdrant 的配置
        :return: collection 列表、当前配置维度和服务地址
        """
        qdrant_config = config.get("qdrant") if isinstance(config.get("qdrant"), dict) else config
        embedding_config = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
        url = cls._qdrant_url(qdrant_config, "/collections")
        headers = cls._qdrant_headers(qdrant_config)
        timeout = cls._safe_int(qdrant_config.get("timeoutSeconds"), 15, 1, 120)
        response = httpx.get(url, headers=headers, timeout=timeout)
        cls._raise_for_qdrant_status(response, "查询 collection 列表")
        rows = ((response.json().get("result") or {}).get("collections") or [])
        collections: list[dict[str, Any]] = []
        for row in rows:
            collection_name = str((row or {}).get("name") or "").strip()
            if not collection_name:
                continue
            collections.append(cls._get_qdrant_collection_summary(qdrant_config, collection_name, headers, timeout))
        configured_dimension = cls._safe_int(embedding_config.get("dimension"), 0, 0, 16384)
        return {
            "collections": collections,
            "configuredDimension": configured_dimension or None,
            "url": str(qdrant_config.get("url") or "").strip(),
        }

    @classmethod
    def _get_qdrant_collection_summary(
        cls,
        qdrant_config: dict[str, Any],
        collection_name: str,
        headers: dict[str, str],
        timeout: int,
    ) -> dict[str, Any]:
        """
        查询单个 Qdrant collection 摘要信息。
        :param qdrant_config: Qdrant 配置
        :param collection_name: collection 名称
        :param headers: 请求头
        :param timeout: 超时时间
        :return: collection 摘要
        """
        detail_url = cls._qdrant_url(qdrant_config, f"/collections/{collection_name}")
        detail_response = httpx.get(detail_url, headers=headers, timeout=timeout)
        cls._raise_for_qdrant_status(detail_response, f"读取 collection: collection={collection_name}")
        detail = detail_response.json()
        vector_info = cls._extract_qdrant_vector_info(detail)
        status = ((detail.get("result") or {}).get("status") if isinstance(detail, dict) else "") or ""
        return {
            "name": collection_name,
            "dimension": vector_info.get("size"),
            "distance": vector_info.get("distance"),
            "status": status,
            "namedVectors": vector_info.get("namedVectors", False),
        }

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
        delete_response = httpx.delete(detail_url, headers=headers, timeout=timeout)
        if delete_response.status_code != 404:
            cls._raise_for_qdrant_status(delete_response, f"删除 collection: collection={collection}")
        else:
            logger.info(f"Qdrant collection删除跳过: collection={collection}, reason=collection不存在")
        create_payload = {"vectors": {"size": vector_size, "distance": distance}}
        create_response = httpx.put(detail_url, headers=headers, json=create_payload, timeout=timeout)
        if create_response.status_code == 409:
            detail_response = httpx.get(detail_url, headers=headers, timeout=timeout)
            cls._raise_for_qdrant_status(detail_response, f"确认 collection: collection={collection}")
            collection_dimension = cls._extract_qdrant_vector_size(detail_response.json())
            if collection_dimension == vector_size:
                logger.info(
                    f"Qdrant collection并发重建已完成: collection={collection}, vectorSize={vector_size}, "
                    f"reason=创建返回409但维度已匹配"
                )
                return
        cls._raise_for_qdrant_status(create_response, f"重建 collection: collection={collection}")
        logger.info(f"Qdrant collection重建完成: collection={collection}, vectorSize={vector_size}")

    @classmethod
    def _extract_qdrant_vector_size(cls, collection_detail: dict[str, Any]) -> int | None:
        """
        从 Qdrant collection 详情中解析默认向量维度，无法识别命名向量时返回空。
        :param collection_detail: Qdrant collection 详情响应
        :return: 默认向量维度
        """
        return cls._extract_qdrant_vector_info(collection_detail).get("size")

    @classmethod
    def _extract_qdrant_vector_info(cls, collection_detail: dict[str, Any]) -> dict[str, Any]:
        """
        从 Qdrant collection 详情中解析向量维度、距离算法和是否命名向量。
        :param collection_detail: collection 详情响应
        :return: 向量信息
        """
        result = collection_detail.get("result") if isinstance(collection_detail, dict) else {}
        config = result.get("config") if isinstance(result, dict) else {}
        params = config.get("params") if isinstance(config, dict) else {}
        vectors = params.get("vectors") if isinstance(params, dict) else {}
        if isinstance(vectors, dict) and "size" in vectors:
            return {
                "size": cls._safe_int(vectors.get("size"), 0, 0, 16384) or None,
                "distance": vectors.get("distance"),
                "namedVectors": False,
            }
        if isinstance(vectors, dict) and vectors:
            first_name = next(iter(vectors.keys()))
            first_vector = vectors.get(first_name) if isinstance(vectors.get(first_name), dict) else {}
            return {
                "size": cls._safe_int(first_vector.get("size"), 0, 0, 16384) or None,
                "distance": first_vector.get("distance"),
                "namedVectors": True,
            }
        return {"size": None, "distance": None, "namedVectors": False}

    @classmethod
    def build_config_with_qdrant_override(
        cls,
        query_db: Session,
        qdrant_override: dict[str, Any] | None = None,
        embedding_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        基于已保存配置叠加页面未保存的 Qdrant/Embedding 配置，用于即时预览 collection。
        :param query_db: 数据库会话
        :param qdrant_override: 页面当前 Qdrant 表单
        :param embedding_override: 页面当前 Embedding 表单
        :return: 合并后的配置
        """
        config = cls.get_similarity_config(query_db)
        if isinstance(qdrant_override, dict):
            config["qdrant"] = cls._deep_merge(config.get("qdrant") or {}, qdrant_override)
        if isinstance(embedding_override, dict):
            config["embedding"] = cls._deep_merge(config.get("embedding") or {}, embedding_override)
        return cls._normalize_config_for_save(config)

    @classmethod
    def _raise_for_qdrant_status(cls, response: httpx.Response, action: str) -> None:
        """
        检查 Qdrant HTTP 响应，失败时带上响应体，便于从日志判断具体原因。
        :param response: requests 响应对象
        :param action: 当前 Qdrant 操作描述
        :return: 无
        """
        if response.status_code < 400:
            return
        detail = response.text[:1000] if response.text else ""
        raise httpx.HTTPStatusError(
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
        payload: dict[str, Any] = {"model": embedding_config.get("model"), "input": text}
        request_params = embedding_config.get("requestParams")
        if isinstance(request_params, dict):
            payload.update(request_params)
        dimension = cls._safe_int(embedding_config.get("dimension"), 0, 0, 16384)
        logger.info(
            f"外部Embedding请求开始: provider=openai_compatible, model={embedding_config.get('model')}, "
            f"configuredDimension={dimension}, requestParamKeys={list(payload.keys())}, "
            f"textChars={len(text)}, endpoint={endpoint.split('?')[0]}"
        )
        response = httpx.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=cls._safe_int(embedding_config.get("timeoutSeconds"), 15, 1, 120),
        )
        if response.status_code != 200:
            logger.error(
                f"请求embeddings接口异常: endpoint={endpoint.split('?')[0]}, "
                f"headerKeys={list(headers.keys())}, response={response.text}"
            )
        response.raise_for_status()
        data = response.json()
        vector = ((data.get("data") or [{}])[0] or {}).get("embedding")
        if not isinstance(vector, list):
            raise ValueError("Embedding 接口未返回 data[0].embedding")
        result = [float(item) for item in vector]
        logger.info(
            f"外部Embedding请求完成: provider=openai_compatible, model={embedding_config.get('model')}, "
            f"configuredDimension={dimension}, returnedDimension={len(result)}"
        )
        if dimension > 0 and len(result) != dimension:
            logger.error(
                f"Embedding接口返回维度与配置不一致，流程中断: model={embedding_config.get('model')}, "
                f"expected={dimension}, actual={len(result)}, endpoint={endpoint.split('?')[0]}"
            )
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
        supported = {cls.PROVIDER_LOCAL_HASH, cls.PROVIDER_EMBEDDING, cls.PROVIDER_QDRANT}
        return provider if provider in supported else cls.PROVIDER_LOCAL_HASH

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
        normalized["fallbackProvider"] = cls.PROVIDER_LOCAL_HASH
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
        request_params = embedding_config.get("requestParams")
        embedding_config["requestParams"] = dict(request_params) if isinstance(request_params, dict) else {}
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
        source_scene_triggers = source.get("sceneTriggers") if isinstance(source.get("sceneTriggers"), dict) else {}
        scene_triggers = normalized.get("sceneTriggers") if isinstance(normalized.get("sceneTriggers"), dict) else {}
        bitable_pull_default = cls.DEFAULT_CONFIG["sceneTriggers"]["bitablePull"]
        if "bitablePull" not in source_scene_triggers and "externalSync" in source_scene_triggers:
            bitable_pull_default = bool(source_scene_triggers.get("externalSync"))
        normalized["sceneTriggers"] = {
            key: (
                bool(bitable_pull_default)
                if key == "bitablePull" and "bitablePull" not in source_scene_triggers
                else bool(scene_triggers.get(key, default_value))
            )
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
                force_rebuild=payload.force_rebuild,
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
                force_rebuild=payload.force_rebuild,
            )
            result["missingTicketNos"] = missing_ticket_nos[:100]
            return result
