from __future__ import annotations

import base64
from typing import Any

from loguru import logger

from utils.api_key_util import ApiKeyUtil


class TicketAiObservabilityService:
    """
    工单 AI 分析可观测上报服务。

    负责把任务级 LLM 调用（prompt 输入、分析结果输出、Token 用量、耗时）按
    OTLP/HTTP(JSON) 协议上报到可观测平台（如水滴引擎 agents.dmall.com/observe）。
    本服务只负责解析 Provider 的可观测配置并生成 Agent 下发环境；任务级 span 的
    实际上报由 Agent 侧（client_new/services/ticket_ai_observability_service.py）执行：
    测试环境等服务端可能与可观测平台网络隔离，而 Agent 机器天然可达平台。

    平台映射规则（已实测验证，Agent 上报遵循同一约定）：
    - INPUT 列读取 span 属性 input.value
    - OUTPUT 列读取 span 属性 output.value
    - TOTAL TOKENS 读取 gen_ai.usage.input_tokens + gen_ai.usage.output_tokens
    - LLM 类型识别依赖 gen_ai.system / gen_ai.request.model
    - Sessions 页签按 span 属性 session.id 聚合
    """

    REQUEST_TIMEOUT_SECONDS = 5.0
    # 单个属性值的最大字符数，防止超长 prompt/结果拖垮上报和平台存储
    MAX_ATTRIBUTE_CHARS = 20000

    @classmethod
    def build_provider_config(cls, provider) -> dict[str, Any] | None:
        """
        从 Provider 数据库对象解析可观测上报配置。
        :param provider: AI Provider 数据库对象
        :return: 上报配置字典；未启用、配置不完整或密钥解密失败时返回 None
        """
        if not provider or not bool(getattr(provider, "observability_enabled", False)):
            return None
        endpoint = str(getattr(provider, "observability_endpoint", "") or "").strip()
        if not endpoint:
            return None
        provider_code = str(getattr(provider, "provider_code", "") or "")
        try:
            api_key = ApiKeyUtil.decrypt_api_key(
                str(getattr(provider, "observability_api_key_cipher_text", "") or "")
            )
        except Exception as exc:
            logger.warning(f"可观测密钥解密失败，跳过可观测上报: provider_code={provider_code}, error={exc}")
            return None
        auth_type = str(getattr(provider, "observability_auth_type", "") or "bearer").strip().lower()
        if auth_type == "basic":
            # Langfuse 兼容模式：库内保存 publicKey:secretKey 合并串，整体做 Basic 凭据
            auth_header = f"Basic {base64.b64encode(api_key.encode('utf-8')).decode('ascii')}"
        else:
            # 平台 Agent API Key 模式
            auth_header = f"Bearer {api_key}"
        service_name = str(getattr(provider, "observability_service_name", "") or "").strip()
        return {
            "endpoint": endpoint.rstrip("/"),
            "auth_header": auth_header,
            "service_name": service_name or "ticket-ai-analysis",
            "provider_code": provider_code,
            "platform_code": str(getattr(provider, "platform_code", "") or "custom"),
        }
