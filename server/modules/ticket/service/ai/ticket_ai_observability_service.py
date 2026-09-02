from __future__ import annotations

import base64
import secrets
import time
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from utils.api_key_util import ApiKeyUtil


class TicketAiObservabilityService:
    """
    工单 AI 分析可观测上报服务。

    负责把任务级 LLM 调用（prompt 输入、分析结果输出、Token 用量、耗时）按
    OTLP/HTTP(JSON) 协议上报到可观测平台（如水滴引擎 agents.dmall.com/observe）。
    上报是旁路 best-effort 能力：任何失败只记录日志，绝不影响 AI 分析任务本身。

    平台映射规则（已实测验证）：
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

    @classmethod
    def report_task_span(
        cls,
        config: dict[str, Any] | None,
        *,
        task_id: int,
        ticket_id: int | None,
        model_name: str | None,
        prompt_text: str | None,
        result_text: str | None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: float | None = None,
        success: bool = True,
        error_code: str | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        """
        上报一个任务级 LLM span（best-effort，失败只记日志）。
        :param config: 可观测上报配置，None 表示未启用直接跳过
        :param task_id: AI 分析任务ID
        :param ticket_id: 工单ID
        :param model_name: 本次使用的模型名称
        :param prompt_text: 发送给 AI 的提示词文本
        :param result_text: AI 返回的分析结果文本
        :param input_tokens: 输入 Token 用量
        :param output_tokens: 输出 Token 用量
        :param total_tokens: 总 Token 用量
        :param latency_ms: 任务执行耗时（毫秒）
        :param success: 任务是否成功
        :param error_code: 失败错误码
        :param error_message: 失败错误信息
        :param started_at: 任务开始时间
        :param trace_id: 任务级traceId（32位hex），与CLI原生遥测共用同一trace
        :param span_id: 任务级spanId（16位hex）
        """
        if not config:
            return
        try:
            cls._do_report_task_span(
                config,
                task_id=task_id,
                ticket_id=ticket_id,
                model_name=model_name,
                prompt_text=prompt_text,
                result_text=result_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                success=success,
                error_code=error_code,
                error_message=error_message,
                started_at=started_at,
                trace_id=trace_id,
                span_id=span_id,
            )
        except Exception as exc:
            # 可观测上报绝不能影响分析任务主流程
            logger.warning(
                f"可观测任务span上报失败: task_id={task_id}, provider_code={config.get('provider_code')}, error={exc}"
            )

    @classmethod
    def _do_report_task_span(
        cls,
        config: dict[str, Any],
        *,
        task_id: int,
        ticket_id: int | None,
        model_name: str | None,
        prompt_text: str | None,
        result_text: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        latency_ms: float | None,
        success: bool,
        error_code: str | None,
        error_message: str | None,
        started_at: datetime | None,
        trace_id: str | None,
        span_id: str | None,
    ) -> None:
        """
        执行 OTLP/HTTP(JSON) 上报。
        :param config: 可观测上报配置
        :param task_id: AI 分析任务ID
        :param ticket_id: 工单ID
        :param model_name: 模型名称
        :param prompt_text: 提示词文本
        :param result_text: 结果文本
        :param input_tokens: 输入 Token 用量
        :param output_tokens: 输出 Token 用量
        :param total_tokens: 总 Token 用量
        :param latency_ms: 耗时毫秒
        :param success: 是否成功
        :param error_code: 错误码
        :param error_message: 错误信息
        :param started_at: 开始时间
        """
        session_id = f"ticket-ai-task-{task_id}"
        attributes: list[dict[str, Any]] = [
            cls._string_attribute("input.value", prompt_text or ""),
            cls._string_attribute("output.value", result_text or error_message or ""),
            # gen_ai.* 语义属性驱动平台的 LLM 识别、Token 聚合和成本计算
            cls._string_attribute("gen_ai.system", str(config.get("platform_code") or "custom")),
        ]
        if model_name:
            attributes.append(cls._string_attribute("gen_ai.request.model", model_name))
        if input_tokens is not None:
            attributes.append(cls._int_attribute("gen_ai.usage.input_tokens", input_tokens))
        if output_tokens is not None:
            attributes.append(cls._int_attribute("gen_ai.usage.output_tokens", output_tokens))
        if total_tokens is not None:
            attributes.append(cls._int_attribute("gen_ai.usage.total_tokens", total_tokens))
        # session.id 驱动 Sessions 页签按任务聚合，同时用于与 CLI 原生遥测关联
        attributes.append(cls._string_attribute("session.id", session_id))
        if ticket_id is not None:
            attributes.append(cls._int_attribute("ticket.id", ticket_id))
        attributes.append(cls._int_attribute("ticket_ai.task_id", task_id))
        if latency_ms is not None:
            attributes.append(cls._double_attribute("ticket_ai.latency_ms", latency_ms))
        if not success:
            attributes.append(cls._string_attribute("error.type", error_code or "AI_ANALYSIS_EXECUTION_ERROR"))
            attributes.append(cls._string_attribute("error.message", error_message or ""))

        now_ns = time.time_ns()
        start_ns = int(started_at.timestamp() * 1_000_000_000) if started_at else now_ns - 1_000_000
        # trace_id/span_id 由调用方传入时与 CLI 原生遥测共用同一 trace（TRACEPARENT 挂接）
        span: dict[str, Any] = {
            "traceId": trace_id or cls._random_hex(32),
            "spanId": span_id or cls._random_hex(16),
            "name": "ticket_ai_analysis",
            "kind": 1,
            "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(max(now_ns, start_ns + 1)),
            "attributes": attributes,
        }
        if not success:
            # OTLP SpanStatus：code 2 = ERROR
            span["status"] = {"code": 2, "message": (error_message or error_code or "analysis failed")[:512]}
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [cls._string_attribute("service.name", str(config.get("service_name")))]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "ticket_ai_analysis", "version": "1.0"},
                            "spans": [span],
                        }
                    ],
                }
            ]
        }
        url = f"{config.get('endpoint')}/v1/traces"
        response = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": str(config.get("auth_header")),
                "Content-Type": "application/json",
            },
            timeout=cls.REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            logger.warning(
                f"可观测任务span上报被拒绝: task_id={task_id}, url={url}, "
                f"status={response.status_code}, body={response.text[:200]}"
            )
            return
        logger.info(
            f"可观测任务span上报成功: task_id={task_id}, session_id={session_id}, "
            f"success={success}, model={model_name or '<unknown>'}"
        )

    @classmethod
    def _string_attribute(cls, key: str, value: str) -> dict[str, Any]:
        """
        构造字符串属性，超长时截断。
        :param key: 属性名
        :param value: 属性值
        :return: OTLP属性结构
        """
        return {"key": key, "value": {"stringValue": (value or "")[: cls.MAX_ATTRIBUTE_CHARS]}}

    @classmethod
    def _int_attribute(cls, key: str, value: int) -> dict[str, Any]:
        """
        构造整数属性。
        :param key: 属性名
        :param value: 属性值
        :return: OTLP属性结构
        """
        return {"key": key, "value": {"intValue": int(value)}}

    @classmethod
    def _double_attribute(cls, key: str, value: float) -> dict[str, Any]:
        """
        构造浮点属性。
        :param key: 属性名
        :param value: 属性值
        :return: OTLP属性结构
        """
        return {"key": key, "value": {"doubleValue": float(value)}}

    @classmethod
    def _random_hex(cls, length: int) -> str:
        """
        生成随机十六进制字符串（用于 traceId/spanId）。
        :param length: 长度
        :return: 十六进制字符串
        """
        return secrets.token_hex(length // 2)