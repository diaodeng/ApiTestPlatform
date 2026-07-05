import json
import unittest
from unittest.mock import patch

import requests

from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService


class TicketEmbeddingServiceTests(unittest.TestCase):
    """验证工单向量服务与 Qdrant 的边界处理。"""

    def _response(self, status_code: int, body: dict | str) -> requests.Response:
        """构造 requests 响应用于模拟 Qdrant HTTP 返回。"""
        response = requests.Response()
        response.status_code = status_code
        response._content = (
            json.dumps(body, ensure_ascii=False).encode("utf-8") if isinstance(body, dict) else body.encode("utf-8")
        )
        response.headers["Content-Type"] = "application/json"
        return response

    def test_existing_qdrant_collection_dimension_mismatch_fails_early(self):
        """已存在 collection 的维度与当前向量不一致时，应在写入前给出明确错误。"""
        config = {
            "embedding": {"dimension": 1536},
            "qdrant": {"url": "http://qdrant.local", "collection": "ticket_similarity", "createCollection": True},
        }
        detail_response = self._response(
            200,
            {"result": {"config": {"params": {"vectors": {"size": 128, "distance": "Cosine"}}}}},
        )

        with patch("modules.ticket.service.ai.ticket_embedding_service.requests.get", return_value=detail_response):
            with self.assertRaisesRegex(ValueError, "collectionDimension=128, vectorDimension=1536"):
                TicketEmbeddingService._ensure_qdrant_collection(config, expected_dimension=1536)

    def test_qdrant_dimension_mismatch_recreates_collection_when_enabled_for_write(self):
        """写入链路开启维度不一致覆盖时，应先删除旧 collection 再按当前维度重建。"""
        config = {
            "embedding": {"dimension": 1536},
            "qdrant": {
                "url": "http://qdrant.local",
                "collection": "ticket_similarity",
                "createCollection": True,
                "recreateCollectionOnDimensionMismatch": True,
            },
        }
        detail_response = self._response(
            200,
            {"result": {"config": {"params": {"vectors": {"size": 128, "distance": "Cosine"}}}}},
        )
        delete_response = self._response(200, {"result": True})
        create_response = self._response(200, {"result": True})

        with (
            patch("modules.ticket.service.ai.ticket_embedding_service.requests.get", return_value=detail_response),
            patch(
                "modules.ticket.service.ai.ticket_embedding_service.requests.delete", return_value=delete_response
            ) as delete_mock,
            patch(
                "modules.ticket.service.ai.ticket_embedding_service.requests.put", return_value=create_response
            ) as put_mock,
        ):
            TicketEmbeddingService._ensure_qdrant_collection(
                config, expected_dimension=1536, allow_recreate=True
            )

        delete_mock.assert_called_once()
        self.assertEqual(put_mock.call_args.kwargs["json"]["vectors"]["size"], 1536)

    def test_qdrant_dimension_mismatch_does_not_recreate_for_search(self):
        """查询链路即使配置了覆盖，也不应因为维度不一致删除 collection。"""
        config = {
            "embedding": {"dimension": 1536},
            "qdrant": {
                "url": "http://qdrant.local",
                "collection": "ticket_similarity",
                "createCollection": True,
                "recreateCollectionOnDimensionMismatch": True,
            },
        }
        detail_response = self._response(
            200,
            {"result": {"config": {"params": {"vectors": {"size": 128, "distance": "Cosine"}}}}},
        )

        with (
            patch("modules.ticket.service.ai.ticket_embedding_service.requests.get", return_value=detail_response),
            patch("modules.ticket.service.ai.ticket_embedding_service.requests.delete") as delete_mock,
        ):
            with self.assertRaisesRegex(ValueError, "collectionDimension=128, vectorDimension=1536"):
                TicketEmbeddingService._ensure_qdrant_collection(
                    config, expected_dimension=1536, allow_recreate=False
                )

        delete_mock.assert_not_called()

    def test_create_qdrant_collection_uses_actual_vector_dimension(self):
        """collection 不存在时，应优先使用本次实际向量维度创建 collection。"""
        config = {
            "embedding": {"dimension": 128},
            "qdrant": {"url": "http://qdrant.local", "collection": "ticket_similarity", "createCollection": True},
        }
        detail_response = self._response(404, {"status": {"error": "Not found"}})
        create_response = self._response(200, {"result": True})

        with (
            patch("modules.ticket.service.ai.ticket_embedding_service.requests.get", return_value=detail_response),
            patch(
                "modules.ticket.service.ai.ticket_embedding_service.requests.put", return_value=create_response
            ) as put_mock,
        ):
            TicketEmbeddingService._ensure_qdrant_collection(config, expected_dimension=768)

        self.assertEqual(put_mock.call_args.kwargs["json"]["vectors"]["size"], 768)

    def test_qdrant_http_error_keeps_response_body(self):
        """Qdrant 返回 4xx/5xx 时，异常信息应包含服务端响应体用于定位根因。"""
        response = self._response(400, {"status": {"error": "Vector dimension error"}})

        with self.assertRaisesRegex(requests.HTTPError, "Vector dimension error"):
            TicketEmbeddingService._raise_for_qdrant_status(response, "写入工单向量")


if __name__ == "__main__":
    unittest.main()
