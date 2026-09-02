from __future__ import annotations

import secrets
import time
from typing import Any

import httpx
from loguru import logger


class TicketAiObservabilityService:
    """
    工单 AI 分析可观测上报服务（Agent 侧）。

    任务级 LLM span 由执行 Agent 上报而不是服务端上报：测试环境等场景下，
    服务端与可观测平台可能网络隔离，而 Agent 机器本就直连平台（CLI 原生遥测
    也从 Agent 上报）。服务端通过 providerEnv 下发 OTLP 端点、鉴权头、
    service name、session 与 trace 上下文，本服务负责组装 span 并上报。

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
    SPAN_NAME = "ticket_ai_analysis"

    @classmethod
    def build_config_from_env(cls, provider_env_overrides: dict[str, str] | None) -> dict[str, str] | None:
        """
        从服务端下发的 providerEnv 解析可观测上报配置。
        :param provider_env_overrides: Provider 环境变量覆盖项（含 OTEL_*）
        :return: 上报配置字典；未下发端点或鉴权头时返回 None
        """
        overrides = provider_env_overrides or {}
        endpoint = str(overrides.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip().rstrip("/")
        if not endpoint:
            return None
        # OTEL_EXPORTER_OTLP_HEADERS 格式为 key=value[,key=value]；只取 Authorization 头
        auth_value = ""
        for pair in str(overrides.get("OTEL_EXPORTER_OTLP_HEADERS") or "").split(","):
            name, separator, value = pair.strip().partition("=")
            if separator and name.strip().lower() == "authorization":
                auth_value = value.strip()
                break
        if not auth_value:
            logger.debug("providerEnv 未下发可观测鉴权头，跳过任务span上报")
            return None
        config = {
            "endpoint": endpoint,
            "authorization": auth_value,
            "service_name": str(overrides.get("OTEL_SERVICE_NAME") or "ticket-ai-analysis").strip()
            or "ticket-ai-analysis",
            "session_id": str(overrides.get("OTEL_SESSION_ID") or "").strip(),
            "trace_id": str(overrides.get("OTEL_TRACE_ID") or "").strip(),
            "span_id": str(overrides.get("OTEL_SPAN_ID") or "").strip(),
        }
        return config

    @classmethod
    def report_task_span(
        cls,
        provider_env_overrides: dict[str, str] | None,
        *,
        task_id: int,
        ticket_id: int | None,
        model_name: str | None,
        system_name: str | None,
        prompt_text: str | None,
        result_text: str | None,
        token_usage: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        success: bool = True,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        上报任务级 LLM span（best-effort，失败只记日志，不影响分析任务）。
        :param provider_env_overrides: Provider 环境变量覆盖项（含 OTEL_*）
        :param task_id: AI 分析任务ID
        :param ticket_id: 工单ID
        :param model_name: 本次使用的模型名称
        :param system_name: AI 系统标识（provider 类型，如 codex/claude）
        :param prompt_text: 发送给 AI 的最终提示词文本
        :param result_text: AI 返回的分析结果文本
        :param token_usage: Token 用量（input_tokens/output_tokens/total_tokens）
        :param latency_ms: 任务执行耗时（毫秒）
        :param success: 任务是否成功
        :param error_code: 失败错误码
        :param error_message: 失败错误信息
        """
        config = cls.build_config_from_env(provider_env_overrides)
        if not config:
            return
        try:
            cls._do_report_task_span(
                config,
                task_id=task_id,
                ticket_id=ticket_id,
                model_name=model_name,
                system_name=system_name,
                prompt_text=prompt_text,
                result_text=result_text,
                token_usage=token_usage,
                latency_ms=latency_ms,
                success=success,
                error_code=error_code,
                error_message=error_message,
            )
        except Exception as exc:
            # 可观测上报绝不能影响分析任务主流程
            logger.warning(f"可观测任务span上报失败: task_id={task_id}, error={exc}")

    @classmethod
    def _do_report_task_span(
        cls,
        config: dict[str, str],
        *,
        task_id: int,
        ticket_id: int | None,
        model_name: str | None,
        system_name: str | None,
        prompt_text: str | None,
        result_text: str | None,
        token_usage: dict[str, Any] | None,
        latency_ms: float | None,
        success: bool,
        error_code: str | None,
        error_message: str | None,
    ) -> None:
        """
        执行 OTLP/HTTP(JSON) 上报。
        :param config: 可观测上报配置
        :param task_id: AI 分析任务ID
        :param ticket_id: 工单ID
        :param model_name: 模型名称
        :param system_name: AI 系统标识
        :param prompt_text: 提示词文本
        :param result_text: 结果文本
        :param token_usage: Token 用量
        :param latency_ms: 耗时毫秒
        :param success: 是否成功
        :param error_code: 错误码
        :param error_message: 错误信息
        """
        session_id = config.get("session_id") or f"ticket-ai-task-{task_id}"
        attributes: list[dict[str, Any]] = [
            cls._string_attribute("input.value", prompt_text or ""),
            cls._string_attribute("output.value", result_text or error_message or ""),
            cls._string_attribute("gen_ai.system", system_name or "unknown"),
        ]
        if model_name:
            attributes.append(cls._string_attribute("gen_ai.request.model", model_name))
        usage = token_usage or {}
        input_tokens = cls._to_int(usage.get("input_tokens"))
        output_tokens = cls._to_int(usage.get("output_tokens"))
        total_tokens = cls._to_int(usage.get("total_tokens"))
        if input_tokens is not None:
            attributes.append(cls._int_attribute("gen_ai.usage.input_tokens", input_tokens))
        if output_tokens is not None:
            attributes.append(cls._int_attribute("gen_ai.usage.output_tokens", output_tokens))
        if total_tokens is not None:
            attributes.append(cls._int_attribute("gen_ai.usage.total_tokens", total_tokens))
        attributes.append(cls._string_attribute("session.id", session_id))
        if ticket_id is not None:
            attributes.append(cls._int_attribute("ticket.id", ticket_id))
        attributes.append(cls._int_attribute("ticket_ai.task_id", task_id))
        if latency_ms is not None:
            attributes.append(cls._double_attribute("ticket_ai.latency_ms", latency_ms))
        if not success:
            attributes.append(cls._string_attribute("error.type", error_code or "AI_WORKER_EXECUTION_ERROR"))
            attributes.append(cls._string_attribute("error.message", error_message or ""))

        now_ns = time.time_ns()
        span: dict[str, Any] = {
            "traceId": config.get("trace_id") or secrets.token_hex(16),
            "spanId": config.get("span_id") or secrets.token_hex(8),
            "name": cls.SPAN_NAME,
            "kind": 1,
            "startTimeUnixNano": str(now_ns - 1_000_000),
            "endTimeUnixNano": str(now_ns),
            "attributes": attributes,
        }
        if not success:
            # OTLP SpanStatus：code 2 = ERROR
            span["status"] = {"code": 2, "message": (error_message or error_code or "analysis failed")[:512]}
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [cls._string_attribute("service.name", config.get("service_name") or "ticket-ai-analysis")]
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
        response = httpx.post(
            f"{config.get('endpoint')}/v1/traces",
            json=payload,
            headers={
                "Authorization": str(config.get("authorization")),
                "Content-Type": "application/json",
            },
            timeout=cls.REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            logger.warning(
                f"可观测任务span上报被拒绝: task_id={task_id}, status={response.status_code}, "
                f"body={response.text[:200]}"
            )
            return
        logger.info(
            f"可观测任务span上报成功: task_id={task_id}, session_id={session_id}, success={success}, "
            f"model={model_name or '<unknown>'}"
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

    @staticmethod
    def _to_int(value: Any) -> int | None:
        """
        安全转换为整数。
        :param value: 原始值
        :return: 整数；无法转换时返回 None
        """
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None