import json
import unittest
from unittest.mock import patch

import requests

from modules.ticket.entity.vo.ticket_vo import TicketEmbeddingRebuildRequestModel
from modules.ticket.service.ai.ticket_embedding_service import ExternalEmbeddingUnavailableError, TicketEmbeddingService


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

    def test_openai_compatible_embedding_fails_without_local_hash_fallback(self):
        """严格模式下外部 Embedding 失败应直接报错，不回退本地哈希。"""
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
            with self.assertRaisesRegex(ExternalEmbeddingUnavailableError, "严格模式不回退本地哈希"):
                TicketEmbeddingService.embed_text("测试文本", config)

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

    def test_embedding_content_hash_changes_when_fields_change(self):
        """向量化字段配置变化时，内容哈希应变化并触发重新生成。"""
        text = "同一段工单文本"
        left_hash = TicketEmbeddingService._embedding_content_hash(text, {"fields": ["title", "description"]})
        right_hash = TicketEmbeddingService._embedding_content_hash(text, {"fields": ["title", "rca"]})

        self.assertNotEqual(left_hash, right_hash)

    def test_can_reuse_embedding_record_requires_hash_dimension_and_vector(self):
        """幂等复用必须同时满足内容哈希、配置维度和已存向量长度。"""
        record = type(
            "MockRecord",
            (),
            {"content_hash": "hash-a", "embedding_dimension": 3, "embedding": [0.1, 0.2, 0.3]},
        )()

        self.assertTrue(TicketEmbeddingService._can_reuse_embedding_record(record, "hash-a", 3, False))
        self.assertFalse(TicketEmbeddingService._can_reuse_embedding_record(record, "hash-b", 3, False))
        self.assertFalse(TicketEmbeddingService._can_reuse_embedding_record(record, "hash-a", 2, False))
        self.assertFalse(TicketEmbeddingService._can_reuse_embedding_record(record, "hash-a", 3, True))

    def test_rebuild_request_normalizes_force_rebuild(self):
        """重建请求默认不强制，显式传入时按布尔值归一。"""
        default_payload = TicketEmbeddingRebuildRequestModel()
        force_payload = TicketEmbeddingRebuildRequestModel(forceRebuild=True)

        self.assertFalse(default_payload.force_rebuild)
        self.assertTrue(force_payload.force_rebuild)

    def test_normalize_provider_supports_embedding(self):
        """检索 Provider 支持本地 hash、数据库 Embedding 和 Qdrant 三种严格模式。"""
        self.assertEqual(TicketEmbeddingService._normalize_provider("embedding"), "embedding")
        self.assertEqual(TicketEmbeddingService._normalize_provider("qdrant"), "qdrant")
        self.assertEqual(TicketEmbeddingService._normalize_provider("local-hash"), "local_hash")

    def test_list_qdrant_collections_returns_dimensions(self):
        """配置页查询 Qdrant collections 时应带出 collection 维度。"""
        list_response = self._response(200, {"result": {"collections": [{"name": "ticket_similarity"}]}})
        detail_response = self._response(
            200,
            {
                "result": {
                    "status": "green",
                    "config": {"params": {"vectors": {"size": 1024, "distance": "Cosine"}}},
                }
            },
        )
        config = {
            "embedding": {"dimension": 1024},
            "qdrant": {"url": "http://qdrant.local", "collection": "ticket_similarity"},
        }

        with patch(
            "modules.ticket.service.ai.ticket_embedding_service.requests.get",
            side_effect=[list_response, detail_response],
        ):
            result = TicketEmbeddingService.list_qdrant_collections(config)

        self.assertEqual(result["collections"][0]["name"], "ticket_similarity")
        self.assertEqual(result["collections"][0]["dimension"], 1024)

    def test_qdrant_http_error_keeps_response_body(self):
        """Qdrant 返回 4xx/5xx 时，异常信息应包含服务端响应体用于定位根因。"""
        response = self._response(400, {"status": {"error": "Vector dimension error"}})

        with self.assertRaisesRegex(requests.HTTPError, "Vector dimension error"):
            TicketEmbeddingService._raise_for_qdrant_status(response, "写入工单向量")

    def test_validate_qdrant_config_rejects_existing_collection_dimension_mismatch(self):
        """保存 Qdrant 配置时，已存在 collection 维度不一致应直接拒绝。"""
        config = TicketEmbeddingService._normalize_config_for_save(
            {
                "provider": "qdrant",
                "embedding": {
                    "provider": "openai_compatible",
                    "endpoint": "http://embedding.local/v1/embeddings",
                    "model": "mock-embedding",
                    "dimension": 1024,
                },
                "qdrant": {"url": "http://qdrant.local", "collection": "ticket_similarity"},
            }
        )
        detail_response = self._response(
            200,
            {"result": {"config": {"params": {"vectors": {"size": 2560, "distance": "Cosine"}}}}},
        )

        with patch("modules.ticket.service.ai.ticket_embedding_service.requests.get", return_value=detail_response):
            with self.assertRaisesRegex(ValueError, "collectionDimension=2560, configuredDimension=1024"):
                TicketEmbeddingService._validate_similarity_config(config)

    def test_validate_qdrant_config_allows_missing_collection(self):
        """保存 Qdrant 配置时，collection 不存在可保存，后续写入链路再按配置自动创建。"""
        config = TicketEmbeddingService._normalize_config_for_save(
            {
                "provider": "qdrant",
                "embedding": {
                    "provider": "openai_compatible",
                    "endpoint": "http://embedding.local/v1/embeddings",
                    "model": "mock-embedding",
                    "dimension": 1024,
                },
                "qdrant": {"url": "http://qdrant.local", "collection": "ticket_similarity"},
            }
        )
        detail_response = self._response(404, {"status": {"error": "Not found"}})

        with patch("modules.ticket.service.ai.ticket_embedding_service.requests.get", return_value=detail_response):
            TicketEmbeddingService._validate_similarity_config(config)


if __name__ == "__main__":
    unittest.main()
