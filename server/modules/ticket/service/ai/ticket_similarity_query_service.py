from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService


class TicketSimilarityQueryService:
    """
    工单相似查询服务，负责优先复用已保存向量查询相似工单。
    """

    @classmethod
    def search_similar_tickets_by_ticket(
        cls,
        query_db: Session,
        ticket_id: int,
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        优先使用当前工单已保存向量查询相似工单；向量缺失或过期时刷新向量后再查询。
        :param query_db: 数据库会话
        :param ticket_id: 当前工单ID
        :param limit: 返回数量
        :return: 相似工单列表、向量状态和提示信息
        """
        ticket = TicketDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return {
                "similarTickets": [],
                "similarEmbeddingStatus": "missing",
                "similarEmbeddingMessage": "工单不存在，无法查询相似工单。",
            }
        similar_tickets = []
        similar_status = "disabled"
        similar_message = ""
        try:
            config = TicketEmbeddingService.get_similarity_config(query_db)
            embedding_context = TicketEmbeddingService.get_ticket_embedding_context(query_db, ticket, config)
            similar_status = embedding_context.get("status") or "disabled"
            similar_message = embedding_context.get("message") or ""
            if similar_status in {"missing", "stale"}:
                # 详情页要尽量给出可用相似工单；缓存不可用时按当前配置同步生成查询向量。
                rca_map = TicketDao.list_rca_by_ticket_ids(query_db, [ticket.ticket_id])
                refreshed_record = TicketEmbeddingService.vectorize_ticket(
                    query_db,
                    ticket,
                    rca=rca_map.get(ticket.ticket_id),
                    config=config,
                )
                query_db.commit()
                embedding_context = {
                    "status": "ready",
                    "message": "当前工单向量已刷新后完成相似工单查询。",
                    "vector": refreshed_record.embedding,
                }
                similar_status = "ready"
                similar_message = embedding_context["message"]
            if similar_status == "ready":
                similar_tickets = TicketEmbeddingService.search_tickets_by_vector(
                    query_db,
                    embedding_context.get("vector") or [],
                    limit,
                    config,
                    exclude_ticket_id=ticket_id,
                )
        except Exception as exc:
            query_db.rollback()
            similar_status = "error"
            similar_message = f"相似工单查询失败：{exc}"
        return {
            "similarTickets": similar_tickets[:limit],
            "similarEmbeddingStatus": similar_status,
            "similarEmbeddingMessage": similar_message,
        }
