import hashlib
import math
import re
from datetime import datetime

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import EmbeddingRecord, Ticket
from utils.common_util import CamelCaseUtil


class TicketEmbeddingService:
    """
    工单向量化服务，当前使用本地哈希向量，后续可替换为真实 Embedding 模型。
    """

    MODEL = "local-hash"
    VERSION = "v1"
    DIMENSION = 128

    @classmethod
    def build_ticket_text(cls, ticket: Ticket) -> str:
        """
        拼接工单可检索文本。
        :param ticket: 工单对象
        :return: 用于向量化和自然语言搜索的文本
        """
        parts = [
            ticket.ticket_no,
            ticket.title,
            ticket.description,
            ticket.merchant_name,
            ticket.module_name,
            ticket.category_name,
            ticket.status,
            ticket.current_assignee_name,
            ticket.root_cause,
            ticket.solution,
        ]
        if ticket.tags:
            parts.append(" ".join(ticket.tags) if isinstance(ticket.tags, list) else str(ticket.tags))
        return " ".join(str(item) for item in parts if item)

    @classmethod
    def embed_text(cls, text: str) -> list[float]:
        """
        将文本转换为固定维度的本地哈希向量。
        :param text: 原始文本
        :return: 归一化向量
        """
        vector = [0.0] * cls.DIMENSION
        for token in cls._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % cls.DIMENSION
            sign = 1 if digest[4] % 2 == 0 else -1
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 6) for value in vector]

    @classmethod
    def vectorize_ticket(cls, query_db: Session, ticket: Ticket) -> EmbeddingRecord:
        """
        为单个工单生成或更新向量记录。
        :param query_db: 数据库会话
        :param ticket: 工单对象
        :return: 向量记录
        """
        text = cls.build_ticket_text(ticket)
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        record = EmbeddingRecord(
            object_type="ticket",
            object_id=ticket.ticket_id,
            embedding_model=cls.MODEL,
            embedding_version=cls.VERSION,
            embedding_dimension=cls.DIMENSION,
            embedding=cls.embed_text(text),
            content_hash=content_hash,
            create_time=datetime.now(),
        )
        return TicketDao.upsert_embedding_record(query_db, record)

    @classmethod
    def vectorize_tickets(cls, query_db: Session, tickets: list[Ticket]) -> int:
        """
        批量生成工单向量。
        :param query_db: 数据库会话
        :param tickets: 工单对象列表
        :return: 成功写入向量数量
        """
        count = 0
        for ticket in tickets:
            cls.vectorize_ticket(query_db, ticket)
            count += 1
        return count

    @classmethod
    def search_tickets(cls, query_db: Session, keyword: str, limit: int = 20) -> list[dict]:
        """
        使用自然语言进行工单检索，优先向量相似度并合并关键字命中。
        :param query_db: 数据库会话
        :param keyword: 搜索文本
        :param limit: 返回数量
        :return: 带 score 的工单列表
        """
        safe_limit = min(max(limit or 20, 1), 100)
        query_vector = cls.embed_text(keyword)
        scored: dict[int, float] = {}
        for record in TicketDao.list_ticket_embedding_records(query_db, cls.MODEL, cls.VERSION):
            if not isinstance(record.embedding, list):
                continue
            score = cls._cosine(query_vector, record.embedding)
            if score > 0:
                scored[record.object_id] = max(scored.get(record.object_id, 0.0), score)

        for ticket in TicketDao.search_tickets_by_keyword(query_db, keyword, safe_limit):
            scored[ticket.ticket_id] = max(scored.get(ticket.ticket_id, 0.0), 1.0)

        top_ids = [
            ticket_id
            for ticket_id, _score in sorted(scored.items(), key=lambda item: item[1], reverse=True)[:safe_limit]
        ]
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
