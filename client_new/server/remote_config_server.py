from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from model.config import AgentConfigModel, PosConfigModel
from server.config import AgentConfig, PosConfig, PosToolConfig
from utils.http_defaults import DEFAULT_HTTP_TIMEOUT
from utils.pos_network import update_network_host


ModelT = TypeVar("ModelT", bound=BaseModel)


class RemoteConfigServer:
    REQUEST_TIMEOUT = DEFAULT_HTTP_TIMEOUT

    @classmethod
    def fetch_remote_config(cls, config_url: str) -> dict[str, Any]:
        normalized_url = cls._normalize_http_url(config_url)
        with httpx.Client(verify=False, timeout=cls.REQUEST_TIMEOUT, follow_redirects=True) as client:
            response = client.get(normalized_url)

        if response.status_code != 200:
            raise ValueError(f"拉取配置失败，HTTP 状态码: {response.status_code}")

        try:
            payload = response.json()
        except Exception as exc:
            raise ValueError("拉取配置失败，服务端返回不是有效 JSON") from exc

        config_payload: Any = payload
        config_key = ""
        updated_at = ""

        if isinstance(payload, dict) and "code" in payload:
            if payload.get("code") != 200:
                raise ValueError(payload.get("msg") or "拉取配置失败")
            data = payload.get("data")
            if isinstance(data, dict) and "config" in data:
                config_payload = data.get("config")
                config_key = str(data.get("configKey") or "")
                updated_at = str(data.get("updatedAt") or "")
            else:
                config_payload = data

        if not isinstance(config_payload, dict):
            raise ValueError("服务端返回的配置不是 JSON 对象")

        return {
            "config": config_payload,
            "config_key": config_key,
            "updated_at": updated_at,
            "sync_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": normalized_url,
        }

    @classmethod
    def sync_pos_config(cls, config_url: str) -> dict[str, Any]:
        local_config = PosConfig.read_pos_config()
        remote_result = cls.fetch_remote_config(config_url)
        merged = cls.merge_model(PosConfigModel, local_config, remote_result["config"])
        merged.config_sync_url = (local_config.config_sync_url or config_url or "").strip()
        merged.config_sync_initialized = True
        merged.config_sync_last_sync_at = str(remote_result.get("sync_at") or "")
        PosConfig.save_pos_config(merged)
        PosToolConfig.clear_local_pos_tool_config()
        update_network_host(merged)
        remote_result["merged_config"] = merged
        return remote_result

    @classmethod
    def sync_agent_config(cls, config_url: str) -> dict[str, Any]:
        local_config = AgentConfig.read_config()
        remote_result = cls.fetch_remote_config(config_url)
        merged = cls.merge_model(AgentConfigModel, local_config, remote_result["config"])
        merged.config_sync_url = (local_config.config_sync_url or config_url or "").strip()
        merged.config_sync_initialized = True
        merged.config_sync_last_sync_at = str(remote_result.get("sync_at") or "")
        AgentConfig.save_config(merged)
        remote_result["merged_config"] = merged
        return remote_result

    @classmethod
    def merge_model(cls, model_cls: type[ModelT], local_model: ModelT, remote_payload: dict[str, Any]) -> ModelT:
        local_data = local_model.model_dump(mode="python")
        merged = cls._merge_partial_dict(local_data, remote_payload)
        return model_cls.model_validate(merged)

    @classmethod
    def _merge_partial_dict(cls, local_data: dict[str, Any], remote_payload: dict[str, Any]) -> dict[str, Any]:
        merged = copy.deepcopy(local_data)
        for key, remote_value in (remote_payload or {}).items():
            if remote_value is None:
                continue

            current_value = merged.get(key)
            if isinstance(current_value, dict) and isinstance(remote_value, dict):
                merged[key] = cls._merge_partial_dict(current_value, remote_value)
            else:
                merged[key] = copy.deepcopy(remote_value)
        return merged

    @staticmethod
    def _normalize_http_url(config_url: str) -> str:
        normalized_url = (config_url or "").strip()
        if not normalized_url:
            raise ValueError("请先填写配置拉取地址")

        parsed = urlsplit(normalized_url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ValueError("配置拉取地址必须是完整的 HTTP/HTTPS 地址")
        return normalized_url
