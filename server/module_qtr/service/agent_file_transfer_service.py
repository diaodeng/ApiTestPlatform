"""服务端到 Agent 的资源控制消息传输适配。"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from module_qtr.service.agent_service import (
    AgentResponseWebUI,
    HandleResponse,
    send_message,
)
from utils.log_util import logger

FILE_RESOURCE_REQUEST_TYPE = 7


@dataclass(frozen=True)
class AgentFileCommandResult:
    """Agent 资源命令的脱敏结果。"""

    success: bool
    data: dict[str, Any]
    error_code: str = ""
    error_message: str = ""
    status_code: int = 200


class AgentFileTransferService:
    """只负责通过统一 Agent Future 发送资源 begin/chunk/commit 控制消息。"""

    REQUEST_TIMEOUT_SECONDS = 60.0

    @classmethod
    def send_command(
        cls,
        agent_code: str,
        command: str,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> AgentFileCommandResult:
        """在线程池中同步等待统一 Agent 发送函数，禁止直接操作 WebSocket。"""
        return asyncio.run(
            cls.send_command_async(
                agent_code,
                command,
                payload,
                request_id=request_id,
                timeout_seconds=timeout_seconds,
            )
        )

    @classmethod
    async def send_command_async(
        cls,
        agent_code: str,
        command: str,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> AgentFileCommandResult:
        """发送一个不含普通业务响应正文的 Agent 资源控制命令。"""
        message = {**payload, "requestType": FILE_RESOURCE_REQUEST_TYPE, "command": command}
        effective_request_id = request_id or f"resource-transfer:{uuid.uuid4().hex}"
        response = await send_message(
            agent_code,
            message,
            request_id=effective_request_id,
            timeout_seconds=timeout_seconds or cls.REQUEST_TIMEOUT_SECONDS,
        )
        result = cls._parse_response(response)
        logger.info(
            f"Agent资源控制命令完成: agent_code={agent_code}, command={command}, "
            f"request_id={effective_request_id}, success={result.success}, error_code={result.error_code}"
        )
        return result

    @staticmethod
    def _parse_response(response: HandleResponse) -> AgentFileCommandResult:
        """将统一 Agent 响应收敛为资源传输需要的小结果。"""
        if not isinstance(response, HandleResponse):
            return AgentFileCommandResult(False, {}, "INVALID_AGENT_RESPONSE", "Agent 响应格式不合法", 500)
        if response.status_code != 200:
            return AgentFileCommandResult(
                False,
                {},
                f"AGENT_TRANSPORT_{response.status_code}",
                response.message or "Agent 传输失败",
                response.status_code,
            )
        body = response.response
        if isinstance(body, AgentResponseWebUI):
            data = body.data if isinstance(body.data, dict) else {}
            return AgentFileCommandResult(
                bool(body.success),
                data,
                body.error_code or ("AGENT_RESOURCE_REJECTED" if not body.success else ""),
                body.error_message or body.message or ("Agent 拒绝资源操作" if not body.success else ""),
                response.status_code,
            )
        if isinstance(body, dict):
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            return AgentFileCommandResult(
                bool(body.get("success", False)),
                data,
                str(body.get("error_code") or ""),
                str(body.get("error_message") or body.get("message") or ""),
                response.status_code,
            )
        return AgentFileCommandResult(
            False,
            {},
            "INVALID_AGENT_RESPONSE",
            "Agent 响应格式不合法",
            response.status_code,
        )
