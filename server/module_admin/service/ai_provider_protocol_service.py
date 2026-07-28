from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from utils.api_key_util import ApiKeyUtil


class AiProviderProtocolService:
    """
    AI Provider协议服务。

    按已声明的协议构造模型目录请求和文本生成请求，禁止调用方再根据平台名称猜测URL、
    请求头或响应结构。
    """

    DEFAULT_TIMEOUT_SEC = 30

    @classmethod
    def discover_models(cls, provider, api_key: str | None = None) -> list[dict[str, str]]:
        """
        调用Provider的模型目录接口并标准化为模型标识列表。
        :param provider: Provider对象或包含连接字段的草稿模型
        :param api_key: 可选明文密钥，草稿预览时优先使用
        :return: 标准化后的模型目录
        """
        protocol = cls._get_protocol(provider)
        if protocol in {"openai_chat_completions", "openai_responses"}:
            url = cls._build_openai_url(provider, "models")
            response = cls._request("GET", url, headers=cls._build_headers(provider, api_key))
            return cls._parse_openai_models(response.json())
        if protocol == "anthropic_messages":
            url = f"{cls._get_anthropic_base_url(provider)}/v1/models"
            response = cls._request("GET", url, headers=cls._build_headers(provider, api_key))
            return cls._parse_openai_models(response.json())
        if protocol == "ollama_chat":
            url = f"{cls._get_ollama_base_url(provider)}/api/tags"
            response = cls._request("GET", url, headers=cls._build_headers(provider, api_key))
            payload = response.json()
            return [
                {"model_id": str(item.get("name") or "").strip(), "display_name": str(item.get("name") or "").strip()}
                for item in payload.get("models", [])
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            ]
        raise ValueError(f"协议{protocol}不支持自动拉取模型目录")

    @classmethod
    def generate_text(
        cls,
        *,
        provider,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        timeout_sec: int | None = None,
    ) -> str:
        """
        使用Provider声明的协议生成文本。
        :param provider: 已保存Provider对象
        :param system_prompt: 系统提示词
        :param user_prompt: 用户提示词
        :param temperature: 生成温度
        :param timeout_sec: 超时时间秒数
        :return: 解析后的模型文本
        """
        protocol = cls._get_protocol(provider)
        model = str(getattr(provider, "default_model", "") or "").strip()
        if not model:
            raise ValueError("Provider默认模型不能为空")
        headers = cls._build_headers(provider)
        if protocol == "openai_chat_completions":
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": temperature,
            }
            response = cls._request(
                "POST",
                cls._build_openai_url(provider, "chat/completions"),
                headers=headers,
                json=payload,
                timeout_sec=timeout_sec,
            )
            return cls._extract_openai_text(response.json())
        if protocol == "openai_responses":
            payload = {
                "model": model,
                "input": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": temperature,
            }
            response = cls._request(
                "POST",
                cls._build_openai_url(provider, "responses"),
                headers=headers,
                json=payload,
                timeout_sec=timeout_sec,
            )
            return cls._extract_openai_text(response.json())
        if protocol == "azure_openai_chat":
            payload = {
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": temperature,
            }
            response = cls._request(
                "POST",
                cls._build_azure_url(provider),
                headers=headers,
                json=payload,
                timeout_sec=timeout_sec,
            )
            return cls._extract_openai_text(response.json())
        if protocol == "anthropic_messages":
            payload = {
                "model": model,
                "max_tokens": cls._get_connection_config(provider).get("maxTokens", 4096),
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": temperature,
            }
            response = cls._request(
                "POST",
                f"{cls._get_anthropic_base_url(provider)}/v1/messages",
                headers=headers,
                json=payload,
                timeout_sec=timeout_sec,
            )
            return cls._extract_anthropic_text(response.json())
        if protocol == "ollama_chat":
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "stream": False,
                "options": {"temperature": temperature},
            }
            response = cls._request(
                "POST",
                f"{cls._get_ollama_base_url(provider)}/api/chat",
                headers=headers,
                json=payload,
                timeout_sec=timeout_sec,
            )
            return str((response.json().get("message") or {}).get("content") or "").strip()
        raise ValueError(f"协议{protocol}暂不支持服务端直连文本生成")

    @classmethod
    def _request(
        cls,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout_sec: int | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        执行Provider HTTP请求并转换上游错误。
        :param method: HTTP方法
        :param url: 完整请求地址
        :param headers: 请求头
        :param timeout_sec: 超时时间秒数
        :param kwargs: HTTP客户端其他参数
        :return: 成功响应
        """
        with httpx.Client(timeout=timeout_sec or cls.DEFAULT_TIMEOUT_SEC, follow_redirects=False) as client:
            response = client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response

    @classmethod
    def _get_protocol(cls, provider) -> str:
        """读取并校验Provider协议编码。"""
        protocol = str(getattr(provider, "api_protocol", "") or "").strip()
        if not protocol:
            raise ValueError("Provider API协议不能为空")
        return protocol

    @classmethod
    def _get_base_url(cls, provider) -> str:
        """读取Provider基础地址并移除末尾斜杠。"""
        base_url = str(getattr(provider, "base_url", "") or "").strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Provider基础地址必须使用HTTP或HTTPS协议")
        return base_url

    @classmethod
    def _get_connection_config(cls, provider) -> dict[str, Any]:
        """读取Provider协议连接扩展配置。"""
        config = getattr(provider, "connection_config", None)
        return config if isinstance(config, dict) else {}

    @classmethod
    def _resolve_api_key(cls, provider, api_key: str | None = None) -> str:
        """优先使用草稿密钥，否则解密已保存Provider密钥。"""
        if str(api_key or "").strip():
            return str(api_key).strip()
        try:
            return ApiKeyUtil.decrypt_api_key(str(getattr(provider, "api_key_cipher_text", "") or ""))
        except Exception as exc:
            raise ValueError(f"Provider密钥解密失败: {exc}") from exc

    @classmethod
    def _build_headers(cls, provider, api_key: str | None = None) -> dict[str, str]:
        """按协议构造请求头。"""
        protocol = cls._get_protocol(provider)
        secret = cls._resolve_api_key(provider, api_key)
        headers = {"Content-Type": "application/json"}
        if protocol == "azure_openai_chat":
            headers["api-key"] = secret
        elif protocol == "anthropic_messages":
            headers["x-api-key"] = secret
            headers["anthropic-version"] = str(
                cls._get_connection_config(provider).get("anthropicVersion") or "2023-06-01"
            )
        elif secret:
            headers["Authorization"] = f"Bearer {secret}"
        return headers

    @classmethod
    def _build_openai_url(cls, provider, endpoint: str) -> str:
        """
        构造 OpenAI 兼容协议端点地址。
        :param provider: Provider对象
        :param endpoint: 相对接口路径
        :return: 完整接口地址
        """
        base_url = cls._get_openai_base_url(provider)
        return base_url if base_url.endswith(f"/{endpoint}") else f"{base_url}/{endpoint}"

    @classmethod
    def _get_openai_base_url(cls, provider) -> str:
        """
        获取 OpenAI 协议服务根地址，并去除误填的具体接口路径。
        :param provider: Provider对象
        :return: OpenAI API 根地址
        """
        base_url = cls._get_base_url(provider)
        for endpoint in ("/chat/completions", "/responses", "/models"):
            if base_url.endswith(endpoint):
                return base_url[: -len(endpoint)]
        return base_url

    @classmethod
    def _get_anthropic_base_url(cls, provider) -> str:
        """
        获取 Anthropic 服务根地址，并去除误填的版本或消息接口路径。
        :param provider: Provider对象
        :return: Anthropic API 根地址
        """
        base_url = cls._get_base_url(provider)
        for endpoint in ("/v1/messages", "/v1/models", "/v1"):
            if base_url.endswith(endpoint):
                return base_url[: -len(endpoint)]
        return base_url

    @classmethod
    def _get_ollama_base_url(cls, provider) -> str:
        """
        获取 Ollama 服务根地址，并去除误填的具体接口路径。
        :param provider: Provider对象
        :return: Ollama 服务根地址
        """
        base_url = cls._get_base_url(provider)
        for endpoint in ("/api/chat", "/api/tags"):
            if base_url.endswith(endpoint):
                return base_url[: -len(endpoint)]
        return base_url

    @classmethod
    def _build_azure_url(cls, provider) -> str:
        """
        构造 Azure OpenAI Chat Completions 地址。
        :param provider: Provider对象
        :return: Azure OpenAI 完整请求地址
        """
        config = cls._get_connection_config(provider)
        deployment = str(config.get("deployment") or getattr(provider, "default_model", "") or "").strip()
        api_version = str(config.get("apiVersion") or "").strip()
        if not deployment or not api_version:
            raise ValueError("Azure OpenAI必须配置deployment和apiVersion")
        query = urlencode({"api-version": api_version})
        return f"{cls._get_azure_base_url(provider)}/openai/deployments/{deployment}/chat/completions?{query}"

    @classmethod
    def _get_azure_base_url(cls, provider) -> str:
        """
        获取 Azure OpenAI 服务根地址，并去除误填的 Azure 接口路径。
        :param provider: Provider对象
        :return: Azure OpenAI 服务根地址
        """
        base_url = cls._get_base_url(provider)
        endpoint_start = base_url.find("/openai/deployments/")
        if endpoint_start >= 0:
            return base_url[:endpoint_start]
        return base_url[: -len("/openai")] if base_url.endswith("/openai") else base_url

    @classmethod
    def _parse_openai_models(cls, payload: Any) -> list[dict[str, str]]:
        """解析OpenAI风格或Anthropic风格的模型目录响应。"""
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        models = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or item.get("name") or "").strip()
            if model_id:
                models.append({"model_id": model_id, "display_name": str(item.get("display_name") or model_id).strip()})
        return models

    @classmethod
    def _extract_openai_text(cls, payload: Any) -> str:
        """解析OpenAI Chat或Responses协议的文本结果。"""
        if not isinstance(payload, dict):
            return ""
        if str(payload.get("output_text") or "").strip():
            return str(payload["output_text"]).strip()
        choices = payload.get("choices") or []
        if choices and isinstance(choices[0], dict):
            content = ((choices[0].get("message") or {}).get("content"))
            if isinstance(content, str):
                return content.strip()
        output = payload.get("output") or []
        texts = [
            str(content["text"]).strip()
            for item in output
            for content in ((item.get("content") or []) if isinstance(item, dict) else [])
            if isinstance(content, dict) and str(content.get("text") or "").strip()
        ]
        return "\n".join(texts).strip()

    @classmethod
    def _extract_anthropic_text(cls, payload: Any) -> str:
        """解析Anthropic Messages协议的文本结果。"""
        if not isinstance(payload, dict):
            return ""
        return "\n".join(
            str(item.get("text") or "").strip()
            for item in payload.get("content", [])
            if isinstance(item, dict) and str(item.get("type") or "") == "text" and str(item.get("text") or "").strip()
        ).strip()
