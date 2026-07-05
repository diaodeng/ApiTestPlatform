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

    def test_openai_compatible_embedding_sends_configured_dimensions(self):
        """调用 OpenAI 兼容 Embedding 时，应按配置传递 dimensions 并校验返回维度。"""
        response = self._response(200, {"data": [{"embedding": [0.1, 0.2, 0.3]}]})
        config = {
            "endpoint": "http://embedding.local/v1/embeddings",
            "model": "mock-embedding",
            "dimension": 3,
            "timeoutSeconds": 15,
        }

        with patch("modules.ticket.service.ai.ticket_embedding_service.requests.post", return_value=response) as post:
            vector = TicketEmbeddingService._embed_text_openai_compatible("测试文本", config)

        self.assertEqual(vector, [0.1, 0.2, 0.3])
        self.assertEqual(post.call_args.kwargs["json"]["dimensions"], 3)

    def test_openai_compatible_embedding_dimension_mismatch_fails(self):
        """外部 Embedding 返回维度与配置不一致时，应直接失败而不是继续写入 Qdrant。"""
        response = self._response(200, {"data": [{"embedding": [0.1, 0.2]}]})
        config = {
            "endpoint": "http://embedding.local/v1/embeddings",
            "model": "mock-embedding",
            "dimension": 3,
            "timeoutSeconds": 15,
        }

        with patch("modules.ticket.service.ai.ticket_embedding_service.requests.post", return_value=response):
            with self.assertRaisesRegex(ValueError, "expected=3, actual=2"):
                TicketEmbeddingService._embed_text_openai_compatible("测试文本", config)

    def test_qdrant_sync_disables_local_hash_fallback_when_embedding_fails(self):
        """同步 Qdrant 时外部 Embedding 失败，应阻止回退本地哈希，避免错误维度写入。"""
        config = {
            "embedding": {
                "provider": "openai_compatible",
                "endpoint": "http://embedding.local/v1/embeddings",
                "model": "mock-embedding",
                "dimension": 1024,
                "timeoutSeconds": 15,
            }
        }

        with patch.object(TicketEmbeddingService, "_embed_text_openai_compatible", side_effect=RuntimeError("521")):
            with self.assertRaisesRegex(ValueError, "已阻止回退本地哈希写入Qdrant"):
                TicketEmbeddingService.embed_text("测试文本", config, allow_local_fallback=False)

    def test_qdrant_recreate_ignores_concurrent_create_conflict_when_dimension_matches(self):
        """并发重建 collection 时，若 409 后确认维度已正确，应视为成功。"""
        delete_response = self._response(200, {"result": True})
        conflict_response = self._response(409, {"status": {"error": "already exists"}})
        detail_response = self._response(
            200,
            {"result": {"config": {"params": {"vectors": {"size": 1536, "distance": "Cosine"}}}}},
        )

        with (
            patch("modules.ticket.service.ai.ticket_embedding_service.requests.delete", return_value=delete_response),
            patch("modules.ticket.service.ai.ticket_embedding_service.requests.put", return_value=conflict_response),
            patch("modules.ticket.service.ai.ticket_embedding_service.requests.get", return_value=detail_response),
        ):
            TicketEmbeddingService._recreate_qdrant_collection(
                detail_url="http://qdrant.local/collections/ticket_similarity",
                headers={},
                timeout=15,
                collection="ticket_similarity",
                vector_size=1536,
                distance="Cosine",
            )

    def test_qdrant_http_error_keeps_response_body(self):
        """Qdrant 返回 4xx/5xx 时，异常信息应包含服务端响应体用于定位根因。"""
        response = self._response(400, {"status": {"error": "Vector dimension error"}})

        with self.assertRaisesRegex(requests.HTTPError, "Vector dimension error"):
            TicketEmbeddingService._raise_for_qdrant_status(response, "写入工单向量")


if __name__ == "__main__":
    unittest.main()
