from __future__ import annotations

from collections.abc import Iterable


class AiProviderCapabilityService:
    """
    AI Provider 能力契约服务。

    统一维护平台、协议、业务用途和执行器之间的合法组合，供 Provider 配置、候选过滤
    与工单任务执行前校验复用。
    """

    PLATFORM_OPTIONS = (
        {"value": "openai", "label": "OpenAI"},
        {"value": "openai_compatible", "label": "OpenAI 兼容网关"},
        {"value": "azure_openai", "label": "Azure OpenAI"},
        {"value": "anthropic", "label": "Anthropic"},
        {"value": "ollama", "label": "Ollama"},
        {"value": "custom", "label": "自定义平台"},
    )
    PROTOCOL_OPTIONS = (
        {"value": "openai_chat_completions", "label": "OpenAI Chat Completions"},
        {"value": "openai_responses", "label": "OpenAI Responses"},
        {"value": "azure_openai_chat", "label": "Azure OpenAI Chat"},
        {"value": "anthropic_messages", "label": "Anthropic Messages"},
        {"value": "ollama_chat", "label": "Ollama Chat"},
        {"value": "custom", "label": "自定义协议"},
    )
    USAGE_OPTIONS = (
        {"value": "ticket_light_text", "label": "工单轻量AI"},
        {"value": "ticket_analysis_worker", "label": "工单AI分析"},
        {"value": "ticket_embedding", "label": "工单向量化"},
        {"value": "provider_model_discovery", "label": "模型目录发现"},
    )
    EXECUTOR_OPTIONS = (
        {"value": "direct_http", "label": "服务端直连"},
        {"value": "codex", "label": "Codex Worker"},
        {"value": "claude_code", "label": "Claude Code Worker"},
    )
    DIRECT_HTTP_PROTOCOLS = {
        "openai_chat_completions",
        "openai_responses",
        "azure_openai_chat",
        "anthropic_messages",
        "ollama_chat",
    }
    MODEL_DISCOVERY_PROTOCOLS = {
        "openai_chat_completions",
        "openai_responses",
        "anthropic_messages",
        "ollama_chat",
    }

    @classmethod
    def normalize_values(cls, values: Iterable[str] | None) -> list[str]:
        """
        归一化多选字符串，清除空值与重复项并保持用户填写顺序。
        :param values: 原始多选值
        :return: 去重后的标准值列表
        """
        normalized: list[str] = []
        for item in values or []:
            value = str(item or "").strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    @classmethod
    def validate_provider_contract(
        cls,
        *,
        platform_code: str,
        api_protocol: str,
        supported_usages: Iterable[str] | None,
        supported_executors: Iterable[str] | None,
    ) -> tuple[list[str], list[str]]:
        """
        校验Provider能力契约并返回归一化后的用途和执行器列表。
        :param platform_code: 平台编码
        :param api_protocol: API协议编码
        :param supported_usages: 支持的业务用途
        :param supported_executors: 支持的执行器
        :return: (标准用途列表, 标准执行器列表)
        """
        platform_values = {item["value"] for item in cls.PLATFORM_OPTIONS}
        protocol_values = {item["value"] for item in cls.PROTOCOL_OPTIONS}
        usage_values = {item["value"] for item in cls.USAGE_OPTIONS}
        executor_values = {item["value"] for item in cls.EXECUTOR_OPTIONS}
        if platform_code not in platform_values:
            raise ValueError(f"不支持的平台编码：{platform_code}")
        if api_protocol not in protocol_values:
            raise ValueError(f"不支持的API协议：{api_protocol}")
        usages = cls.normalize_values(supported_usages)
        executors = cls.normalize_values(supported_executors)
        if not usages:
            raise ValueError("至少选择一个Provider用途")
        if not executors:
            raise ValueError("至少选择一个Provider执行器")
        invalid_usages = [item for item in usages if item not in usage_values]
        invalid_executors = [item for item in executors if item not in executor_values]
        if invalid_usages:
            raise ValueError(f"存在不支持的Provider用途：{','.join(invalid_usages)}")
        if invalid_executors:
            raise ValueError(f"存在不支持的Provider执行器：{','.join(invalid_executors)}")
        if "ticket_light_text" in usages and (
            "direct_http" not in executors or api_protocol not in cls.DIRECT_HTTP_PROTOCOLS
        ):
            raise ValueError("工单轻量AI必须配置服务端直连执行器和已支持的直连协议")
        if "provider_model_discovery" in usages and api_protocol not in cls.MODEL_DISCOVERY_PROTOCOLS:
            raise ValueError("当前协议不支持自动拉取模型目录，请移除模型目录发现用途")
        return usages, executors

    @classmethod
    def is_provider_eligible(cls, provider, usage: str | None = None, executor: str | None = None) -> bool:
        """
        判断一个已启用Provider是否满足指定业务用途和执行器。
        :param provider: Provider数据库对象
        :param usage: 业务用途，为空时不按用途过滤
        :param executor: 执行器，为空时不按执行器过滤
        :return: 是否满足候选条件
        """
        if not provider or not bool(getattr(provider, "enabled", False)):
            return False
        usages = cls.normalize_values(getattr(provider, "supported_usages", None))
        executors = cls.normalize_values(getattr(provider, "supported_executors", None))
        return (not usage or usage in usages) and (not executor or executor in executors)

    @classmethod
    def require_provider_eligibility(cls, provider, *, usage: str, executor: str) -> None:
        """
        强制校验任务选中的Provider是否具备指定用途和执行器能力。
        :param provider: Provider数据库对象
        :param usage: 当前业务用途
        :param executor: 当前执行器
        :return: 无返回，不满足时抛出业务异常
        """
        if not provider:
            raise ValueError("未找到AI Provider配置")
        if not bool(getattr(provider, "enabled", False)):
            raise ValueError("所选AI Provider已禁用")
        if not cls.is_provider_eligible(provider, usage, executor):
            raise ValueError(f"AI Provider不兼容当前场景：usage={usage}, executor={executor}")
