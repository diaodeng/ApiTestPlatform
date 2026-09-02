from __future__ import annotations

import asyncio
import bz2
import gzip
import hashlib
import json
import lzma
import os
import re
import shutil
import subprocess
import tarfile
import zipfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import py7zr
from dotenv import dotenv_values
from loguru import logger
import httpx

from server.config import AgentConfig
from services.ticket_ai_codex_config_service import TicketAiCodexConfigService
from utils.common import get_client_root_dir

EventSender = Callable[[dict[str, Any]], Awaitable[None]]


class TicketAiAnalysisService:
    """
    client_new 侧工单 AI 分析执行服务，支持多种 AI Provider（Codex、Claude Code 等）。
    """

    DEFAULT_TIMEOUT_SEC = 3600
    DEFAULT_WORKER_COMMAND = "codex exec"
    DEFAULT_WORKER_SANDBOX = "workspace-write"
    DEFAULT_LOG_DIGEST_MAX_CHARS = 300000
    DEFAULT_LOG_DIGEST_MAX_MATCHES_PER_FILE = 80

    # --- Provider 运行时配置映射 ---
    # 每种 provider_type 对应一组 CLI 行为，新增 AI 工具时只需在此追加条目。
    PROVIDER_WORKER_MAP: dict[str, dict[str, Any]] = {
        "codex": {
            "command": "codex exec",
            "sandbox": "workspace-write",
            "code_arg_flag": "-C",            # 代码目录参数
            "output_mode": "file",             # 结果从文件读取
            "output_schema_flag": "--output-schema",
            "output_file_flag": "--output-last-message",
            # stdout 输出 JSONL 事件流，其中 turn.completed 事件携带 Token 用量；
            # 结果本体仍从 --output-last-message 文件读取，不受事件流影响。
            "json_output_flag": "--json",
            "resume_flag": "--resume",
            "model_flag": "-m",
            "skip_git_check_flag": "--skip-git-repo-check",
        },
        "claude": {
            "command": "claude -p",
            "sandbox": None,                   # Claude Code 无沙箱参数
            "code_arg_flag": "--add-dir",      # 代码目录参数
            "output_mode": "stdout",            # 结果从 stdout 解析
            "output_schema_flag": "--json-schema",  # 结构化输出 schema（传 JSON 字符串，非文件）
            "output_file_flag": None,           # 不支持输出到文件
            "resume_flag": "--resume",
            "model_flag": "--model",
            "skip_git_check_flag": None,
            "output_format_flag": "--output-format",  # 非交互输出的格式参数
            "output_format": "json",                   # 输出为单行 JSON，便于解析 structured_output
            "permission_mode_flag": "--permission-mode",
            "permission_mode": "plan",                 # 只分析不改代码的只读权限模式
            "allowed_tools_flag": "--allowedTools",
            "allowed_tools": "Read,Grep,Glob,Bash(rg *)",
            "stdin_placeholder": "-",                  # prompt 从 stdin 读取的占位符
        },
    }
    DEFAULT_LOG_DIGEST_CONTEXT_LINES = 3
    DEFAULT_LOG_DIGEST_MAX_LINE_CHARS = 1200
    TIMESTAMP_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")

    @staticmethod
    def _json_safe_value(value: Any) -> Any:
        """
        将值转换为可 JSON 序列化内容。
        :param value: 原始值
        :return: 可序列化值
        """
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: TicketAiAnalysisService._json_safe_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [TicketAiAnalysisService._json_safe_value(item) for item in value]
        if isinstance(value, tuple):
            return [TicketAiAnalysisService._json_safe_value(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    @classmethod
    def _dumps(cls, value: Any, *, indent: int | None = 2) -> str:
        """
        序列化 JSON。
        :param value: 原始值
        :param indent: 缩进
        :return: JSON 文本
        """
        return json.dumps(cls._json_safe_value(value), ensure_ascii=False, indent=indent)

    @classmethod
    def _load_codex_env(cls, codex_home: Path) -> dict[str, str]:
        """
        读取 Codex 配置目录中的 .env，并回退到当前进程环境变量。
        :param codex_home: Codex home 目录
        :return: 环境变量字典
        """
        env_values: dict[str, str] = {}
        env_file = codex_home / ".env"
        if env_file.exists():
            try:
                parsed = dotenv_values(env_file)
                for key, value in parsed.items():
                    if key and value is not None:
                        env_values[str(key)] = str(value)
            except Exception as exc:
                logger.warning(f"读取 Codex .env 失败: {exc}")
        for key, value in os.environ.items():
            env_values.setdefault(key, value)
        return env_values

    @staticmethod
    def _apply_env_overrides(env_values: dict[str, str], overrides: dict[str, Any] | None) -> dict[str, str]:
        """
        将请求下发的环境变量覆盖到 Worker 运行环境。
        :param env_values: 原始环境变量
        :param overrides: 覆盖项
        :return: 合并后的环境变量
        """
        merged_env = dict(env_values)
        if not isinstance(overrides, dict):
            return merged_env
        for key, value in overrides.items():
            if key in (None, "") or value in (None, ""):
                continue
            merged_env[str(key)] = str(value)
        return merged_env

    @staticmethod
    def _resolve_worker_api_key(
        provider_type: str,
        ai_home: Path | None,
        env_values: dict[str, str],
    ) -> tuple[str, str]:
        """
        解析 Worker 实际用于鉴权的 API Key，但不记录明文。
        Codex 的 model_providers 配置可能通过 experimental_bearer_token 覆盖
        auth.json，必须按 CLI 的实际优先级读取；其他 Provider 使用其约定的环境变量。
        :param provider_type: 当前 Provider 类型
        :param ai_home: 任务级配置目录
        :param env_values: 已合并的 Worker 环境变量
        :return: (API Key, 脱敏诊断中的来源标识)
        """
        if provider_type == "codex" and ai_home:
            config_file = ai_home / "config.toml"
            if config_file.exists():
                try:
                    config_text = config_file.read_text(encoding="utf-8")
                    bearer_match = re.search(
                        r'^\s*experimental_bearer_token\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s#]+))',
                        config_text,
                        flags=re.MULTILINE,
                    )
                    if bearer_match:
                        bearer_token = next(
                            (group for group in bearer_match.groups() if group is not None),
                            "",
                        ).strip()
                        if bearer_token:
                            return bearer_token, "config.toml.experimental_bearer_token"
                except OSError as exc:
                    logger.warning(f"读取任务级 Codex config.toml 鉴权配置失败，将回退 auth.json: {exc}")
            auth_file = ai_home / "auth.json"
            if auth_file.exists():
                try:
                    auth_data = json.loads(auth_file.read_text(encoding="utf-8"))
                    auth_key = str((auth_data or {}).get("OPENAI_API_KEY") or "").strip()
                    if auth_key:
                        return auth_key, "auth.json.OPENAI_API_KEY"
                except (OSError, json.JSONDecodeError, TypeError, AttributeError) as exc:
                    logger.warning(f"读取任务级 Codex auth.json 失败，将回退环境变量: {exc}")
            return str(env_values.get("OPENAI_API_KEY") or "").strip(), "OPENAI_API_KEY"
        if provider_type == "claude":
            return (
                str(env_values.get("ANTHROPIC_API_KEY") or env_values.get("OPENAI_API_KEY") or "").strip(),
                "ANTHROPIC_API_KEY/OPENAI_API_KEY",
            )
        return str(env_values.get("OPENAI_API_KEY") or "").strip(), "OPENAI_API_KEY"

    @staticmethod
    def _resolve_worker_base_url(
        provider_type: str,
        ai_home: Path | None,
        env_values: dict[str, str],
    ) -> str:
        """
        解析 Worker 实际请求的基础地址。
        Codex 优先使用任务级 config.toml 中的 base_url，与 CLI 的配置优先级保持一致；
        文件未配置或读取失败时才回退到环境变量。
        :param provider_type: 当前 Provider 类型
        :param ai_home: 任务级配置目录
        :param env_values: 已合并的 Worker 环境变量
        :return: 去除末尾斜杠后的基础地址，未配置时返回空字符串
        """
        if provider_type == "codex" and ai_home:
            config_file = ai_home / "config.toml"
            if config_file.exists():
                try:
                    config_text = config_file.read_text(encoding="utf-8")
                    match = re.search(r'^[ \t]*base_url\s*=\s*(["\'])(.*?)\1', config_text, flags=re.MULTILINE)
                    if match:
                        return match.group(2).strip().rstrip("/")
                except OSError as exc:
                    logger.warning(f"读取任务级 Codex config.toml 失败，将回退环境变量: {exc}")
        env_key = "ANTHROPIC_BASE_URL" if provider_type == "claude" else "OPENAI_BASE_URL"
        return str(env_values.get(env_key) or "").strip().rstrip("/")

    @staticmethod
    def _build_api_key_fingerprint(api_key: str) -> dict[str, Any]:
        """
        构造不包含明文 API Key 的鉴权指纹，用于关联问题日志。
        :param api_key: 原始 API Key
        :return: 是否存在、长度与 SHA-256 前 16 位组成的脱敏信息
        """
        normalized_key = str(api_key or "").strip()
        return {
            "api_key_present": bool(normalized_key),
            "api_key_length": len(normalized_key),
            "api_key_sha256_16": hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()[:16]
            if normalized_key
            else "",
        }

    @classmethod
    def _build_worker_auth_diagnostic(
        cls,
        *,
        provider_type: str,
        provider_code: str,
        worker_model: str,
        ai_home: Path | None,
        env_values: dict[str, str],
    ) -> tuple[dict[str, Any], str]:
        """
        生成 Worker 鉴权故障诊断上下文，不暴露任何密钥明文。
        :param provider_type: 当前 Provider 类型
        :param provider_code: 当前 Provider 编码
        :param worker_model: 实际下发的模型名
        :param ai_home: 任务级配置目录
        :param env_values: 已合并的 Worker 环境变量
        :return: (诊断信息, 实际用于探测的 API Key)
        """
        api_key, api_key_source = cls._resolve_worker_api_key(provider_type, ai_home, env_values)
        diagnostic = {
            "provider_type": provider_type,
            "provider_code": provider_code or "<none>",
            "worker_model": worker_model or "<default>",
            "base_url": cls._resolve_worker_base_url(provider_type, ai_home, env_values) or "<none>",
            "api_key_source": api_key_source,
            **cls._build_api_key_fingerprint(api_key),
        }
        return diagnostic, api_key

    @staticmethod
    def _is_unauthorized_worker_failure(raw_stdout: str, raw_stderr: str) -> bool:
        """
        判断 Worker 输出是否包含需要进行鉴权探测的 401 错误。
        :param raw_stdout: Worker 标准输出
        :param raw_stderr: Worker 标准错误
        :return: 是否命中 401、Unauthorized 或 Invalid token 特征
        """
        output_text = f"{raw_stderr}\n{raw_stdout}".lower()
        return bool(
            re.search(
                r"\b401\b|\bunauthorized\b|\binvalid\s+token\b",
                output_text,
            )
        )

    @staticmethod
    async def _probe_codex_authentication(base_url: str, api_key: str) -> dict[str, Any]:
        """
        使用 GET /models 对 Codex 兼容 Provider 执行轻量鉴权探测，不调用模型推理。
        :param base_url: Provider OpenAI 兼容基础地址
        :param api_key: 实际请求使用的 API Key，仅用于请求头，不记录日志
        :return: 探测状态、请求 ID 或跳过/异常原因组成的脱敏结果
        """
        normalized_base_url = str(base_url or "").strip().rstrip("/")
        normalized_api_key = str(api_key or "").strip()
        if not normalized_base_url:
            return {"auth_probe": "skipped", "auth_probe_reason": "base_url_missing"}
        if not normalized_api_key:
            return {"auth_probe": "skipped", "auth_probe_reason": "api_key_missing"}
        if not normalized_base_url.lower().startswith(("http://", "https://")):
            return {"auth_probe": "skipped", "auth_probe_reason": "base_url_invalid"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.get(
                    f"{normalized_base_url}/models",
                    headers={"Authorization": f"Bearer {normalized_api_key}"},
                )
            return {
                "auth_probe": "completed",
                "auth_probe_http_status": response.status_code,
                "auth_probe_request_id": response.headers.get("x-request-id")
                or response.headers.get("request-id")
                or "",
            }
        except httpx.HTTPError as exc:
            return {
                "auth_probe": "failed",
                "auth_probe_error": f"{type(exc).__name__}: {str(exc)[:300]}",
            }

    @staticmethod
    def _inject_worker_model(command: list[str], model_name: str | None) -> list[str]:
        """
        将 Provider 选择的模型注入 Worker 命令参数。
        :param command: 原始 Worker 命令
        :param model_name: 模型名称
        :return: 注入后的 Worker 命令
        """
        normalized_model = str(model_name or "").strip()
        if not normalized_model:
            return list(command)
        command_parts = [str(part) for part in command]
        if "-m" in command_parts or "--model" in command_parts:
            return command_parts
        return [*command_parts, "-m", normalized_model]

    @classmethod
    def _prepare_codex_home(
        cls,
        workspace_dir: Path,
        provider_env_overrides: dict[str, str] | None = None,
    ) -> Path:
        """
        准备独立的 Codex home 目录。
        :param workspace_dir: 当前任务工作区
        :param provider_env_overrides: Provider 环境变量覆盖项
        :return: Codex home 目录
        """
        source_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
        codex_home = workspace_dir / ".codex_home"
        overrides = provider_env_overrides or {}
        has_provider_keys = bool(overrides.get("OPENAI_BASE_URL") or overrides.get("OPENAI_API_KEY"))
        TicketAiCodexConfigService.copy_task_home_files(source_home, codex_home)
        cls._trust_codex_workspace(codex_home, workspace_dir)
        if has_provider_keys:
            cls._patch_codex_config_for_provider(codex_home, overrides)
        return codex_home

    @staticmethod
    def _trust_codex_workspace(codex_home: Path, workspace_dir: Path) -> None:
        """
        将当前任务工作区加入任务级 Codex 配置的可信项目列表。

        只信任任务工作区，不信任用户目录、磁盘根目录或代码仓库父目录；代码仓库的
        可写范围由命令行的 ``--add-dir`` 单独控制。任务级配置位于工作区内，重试时
        会保留，因此同一任务不会反复触发项目授权提示。
        :param codex_home: 任务级 Codex 配置目录
        :param workspace_dir: 当前任务工作区
        :return: 无
        """
        workspace_path = workspace_dir.resolve()
        if not workspace_path.is_absolute() or workspace_path == Path(workspace_path.anchor):
            raise ValueError(f"拒绝将不安全路径加入 Codex trusted: {workspace_path}")
        if "'" in str(workspace_path):
            raise ValueError(f"Codex 工作区路径包含不支持的单引号: {workspace_path}")

        config_file = codex_home / "config.toml"
        config_text = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
        project_header = f"[projects.'{workspace_path}']"
        section_pattern = re.compile(
            rf"(?ms)^{re.escape(project_header)}\s*$.*?(?=^\[|\Z)"
        )
        trusted_section = f"{project_header}\ntrust_level = \"trusted\"\n"
        if section_pattern.search(config_text):
            # Windows 路径包含反斜杠，不能直接作为 re.sub 的 replacement，
            # 否则重试更新已有 trusted 段落时会把 ``\x`` 解析成非法转义。
            new_config = section_pattern.sub(lambda _: trusted_section, config_text, count=1)
        else:
            separator = "\n" if config_text and not config_text.endswith("\n") else ""
            new_config = f"{config_text}{separator}\n{trusted_section}"
        if new_config != config_text:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(new_config, encoding="utf-8")
            logger.info(f"已将当前 AI 任务工作区加入 Codex trusted: {workspace_path}")

    @staticmethod
    def _patch_codex_config_for_provider(codex_home: Path, overrides: dict[str, str]) -> None:
        """
        修改副本 config.toml 和 .env，使 Provider 下发的 base_url 和 api_key 生效。
        Codex CLI 读 config.toml 中 model_providers 的 base_url 和
        experimental_bearer_token 优先级高于环境变量/auth.json，因此需要直接修改副本文件。
        :param codex_home: Codex home 目录
        :param overrides: Provider 环境变量覆盖项
        :return: 无
        """
        base_url = str(overrides.get("OPENAI_BASE_URL") or "").strip()
        api_key = str(overrides.get("OPENAI_API_KEY") or "").strip()
        # 修改 config.toml 中的 base_url
        if base_url:
            config_file = codex_home / "config.toml"
            if config_file.exists():
                try:
                    config_text = config_file.read_text(encoding="utf-8")
                    # base_url 通常位于 [model_providers.<name>] 节中，前面带缩进，
                    # 旧正则只匹配行首无缩进配置，导致下发 Provider 地址没有覆盖实际模型 Provider。
                    new_config = re.sub(
                        r'^([ \t]*base_url\s*=\s*)(["\'])(.*?)(\2)',
                        lambda match: f'{match.group(1)}{match.group(2)}{base_url}{match.group(4)}',
                        config_text,
                        flags=re.MULTILINE,
                    )
                    if new_config != config_text:
                        config_file.write_text(new_config, encoding="utf-8")
                        logger.info(f"已修改 Codex config.toml base_url: {base_url}")
                except Exception as exc:
                    logger.warning(f"修改 Codex config.toml 失败: {exc}")
        # 修改当前 model provider 的 experimental_bearer_token，避免复制用户本地配置中的旧代理令牌。
        if api_key:
            config_file = codex_home / "config.toml"
            try:
                if config_file.exists():
                    config_text = config_file.read_text(encoding="utf-8")
                    provider_match = re.search(
                        r'^\s*model_provider\s*=\s*["\']([^"\']+)["\']',
                        config_text,
                        flags=re.MULTILINE,
                    )
                    provider_name = provider_match.group(1) if provider_match else ""
                    section_pattern = (
                        rf'(?ms)(^\[model_providers\.{re.escape(provider_name)}\]\s*$.*?)(?=^\[|\Z)'
                        if provider_name
                        else ""
                    )
                    section_match = re.search(section_pattern, config_text) if section_pattern else None
                    if section_match:
                        provider_section = section_match.group(1)
                        token_pattern = (
                            r'(?m)^(\s*experimental_bearer_token\s*=\s*)'
                            r'("[^"]*"|\'[^\']*\'|[^\s#]+)'
                        )
                        token_value = json.dumps(api_key, ensure_ascii=False)
                        patched_section, replaced_count = re.subn(
                            token_pattern,
                            lambda match: f"{match.group(1)}{token_value}",
                            provider_section,
                            count=1,
                        )
                        if replaced_count == 0:
                            patched_section = provider_section.rstrip() + (
                                f"\nexperimental_bearer_token = {token_value}\n"
                            )
                        if patched_section != provider_section:
                            config_file.write_text(
                                config_text[: section_match.start(1)]
                                + patched_section
                                + config_text[section_match.end(1) :],
                                encoding="utf-8",
                            )
                            logger.info("已修改 Codex config.toml experimental_bearer_token")
            except Exception as exc:
                logger.warning(f"修改 Codex config.toml experimental_bearer_token 失败: {exc}")
        # 修改 .env 中的 OPENAI_API_KEY 和 OPENAI_BASE_URL
        if base_url or api_key:
            env_file = codex_home / ".env"
            try:
                lines: list[str] = []
                if env_file.exists():
                    lines = env_file.read_text(encoding="utf-8").splitlines()
                updated_keys: set[str] = set()
                new_lines: list[str] = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("OPENAI_API_KEY=") and api_key:
                        new_lines.append(f"OPENAI_API_KEY={api_key}")
                        updated_keys.add("OPENAI_API_KEY")
                    elif stripped.startswith("OPENAI_BASE_URL=") and base_url:
                        new_lines.append(f"OPENAI_BASE_URL={base_url}")
                        updated_keys.add("OPENAI_BASE_URL")
                    else:
                        new_lines.append(line)
                if "OPENAI_API_KEY" not in updated_keys and api_key:
                    new_lines.append(f"OPENAI_API_KEY={api_key}")
                if "OPENAI_BASE_URL" not in updated_keys and base_url:
                    new_lines.append(f"OPENAI_BASE_URL={base_url}")
                env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                logger.info(f"已修改 Codex .env: api_key={'***' if api_key else ''}, base_url={base_url}")
            except Exception as exc:
                logger.warning(f"修改 Codex .env 失败: {exc}")
        # 同步修改 auth.json 中的 OPENAI_API_KEY，兼容 Codex 的认证回退路径。
        if api_key:
            auth_file = codex_home / "auth.json"
            try:
                auth_data: dict[str, Any] = {}
                if auth_file.exists():
                    auth_data = json.loads(auth_file.read_text(encoding="utf-8"))
                    if not isinstance(auth_data, dict):
                        auth_data = {}
                auth_data["OPENAI_API_KEY"] = api_key
                auth_file.write_text(json.dumps(auth_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                logger.info("已修改 Codex auth.json 中的 OPENAI_API_KEY")
            except Exception as exc:
                logger.warning(f"修改 Codex auth.json 失败: {exc}")

    @classmethod
    def _resolve_provider_type(cls, context_payload: dict[str, Any] | None) -> str:
        """
        从上下文解析当前请求的 Provider 类型。
        优先读取 selectedExecutor（服务端下发的执行器编码），
        兼容历史 selectedAiProviderType 字段，均回退为 "codex"。
        :param context_payload: 上下文快照
        :return: provider_type 字符串，默认 "codex"
        """
        executor = str((context_payload or {}).get("selectedExecutor") or "").strip().lower()
        # 服务端执行器编码 claude_code 映射到本地运行时类型 claude
        if executor == "claude_code":
            executor = "claude"
        if executor in cls.PROVIDER_WORKER_MAP:
            return executor
        raw = str((context_payload or {}).get("selectedAiProviderType") or "").strip().lower()
        return raw if raw in cls.PROVIDER_WORKER_MAP else "codex"

    @classmethod
    def _get_provider_worker_config(cls, provider_type: str) -> dict[str, Any]:
        """
        获取指定 Provider 的 Worker 运行时配置。
        :param provider_type: Provider 类型
        :return: Worker 配置字典
        """
        return cls.PROVIDER_WORKER_MAP.get(provider_type, cls.PROVIDER_WORKER_MAP["codex"])

    @classmethod
    def _resolve_worker_command_parts(cls, command_parts: list[str]) -> list[str]:
        """
        解析 Worker 命令为可直接执行的进程参数，并避免误用 Codex 桌面应用。
        :param command_parts: 原始命令参数
        :return: 可执行的命令参数
        """
        parts = [str(part).strip() for part in command_parts if str(part).strip()]
        if not parts:
            parts = ["codex", "exec"]
        executable = parts[0]
        if Path(executable).suffix and cls._is_codex_cli_executable(executable):
            return parts
        config = AgentConfig.read_config()
        configured_cli = str(getattr(config, "ticket_ai_codex_cli_path", "") or "").strip()
        resolved_executable = cls._resolve_codex_cli_executable(executable, configured_cli)
        if not resolved_executable:
            raise FileNotFoundError(
                "未找到可执行的 Codex CLI。"
                "请安装 Codex CLI，或在 Agent 配置 ticket_ai_codex_cli_path 中填写 CLI 路径"
            )
        if resolved_executable.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", resolved_executable, *parts[1:]]
        return [resolved_executable, *parts[1:]]

    @staticmethod
    def _is_codex_desktop_app_path(executable: str | Path | None) -> bool:
        """
        判断可执行文件是否来自 OpenAI Codex 安装目录。
        :param executable: 可执行文件路径
        :return: 是否为 OpenAI Codex 安装目录路径
        """
        if not executable:
            return False
        normalized = str(executable).replace("/", "\\").lower()
        return "\\appdata\\local\\programs\\openai\\codex\\" in normalized

    @staticmethod
    def _is_codex_cli_executable(executable: str | Path | None) -> bool:
        """
        通过 --version 判断可执行文件是否为可用的 Codex CLI。
        :param executable: 可执行文件路径
        :return: 是否为可执行 Codex CLI
        """
        if not executable:
            return False
        try:
            popen_kwargs: dict[str, Any] = TicketAiAnalysisService._build_hidden_subprocess_kwargs()
            if str(executable).lower().endswith((".cmd", ".bat")):
                command = ["cmd", "/c", str(executable), "--version"]
            else:
                command = [str(executable), "--version"]
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=10,
                **popen_kwargs,
            )
            version_text = f"{result.stdout}\n{result.stderr}".strip().lower()
            return result.returncode == 0 and "codex-cli" in version_text
        except Exception:
            return False

    @classmethod
    def _resolve_codex_cli_executable(cls, executable: str, configured_cli: str | None = None) -> str | None:
        """
        解析 Codex CLI 可执行文件，优先使用本地配置和 Node/npm CLI，并用 --version 校验 CLI 身份。
        :param executable: 命令名或配置的可执行文件
        :param configured_cli: Agent 本地显式配置的 Codex CLI 路径
        :return: Codex CLI 可执行文件路径
        """
        candidates: list[str | None] = [
            configured_cli,
            str(Path(r"C:\nvm4w\nodejs\codex.cmd")),
            str(Path(r"C:\nvm4w\nodejs\codex.exe")),
            str(Path(r"C:\nvm4w\nodejs\codex")),
            str(Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd"),
            str(Path.home() / "AppData" / "Roaming" / "npm" / "codex.exe"),
            str(Path.home() / "AppData" / "Roaming" / "npm" / "codex"),
            shutil.which(executable),
        ]
        if Path(executable).suffix:
            candidates.insert(0, executable)
        for candidate in candidates:
            if not candidate:
                continue
            candidate_path = Path(candidate)
            if candidate_path.exists() and cls._is_codex_cli_executable(candidate_path):
                return str(candidate_path)
        return None

    @classmethod
    def _resolve_claude_cli_executable(cls) -> str | None:
        """
        解析 Claude Code CLI 可执行文件。
        :return: claude 可执行文件路径，未找到返回 None
        """
        config = AgentConfig.read_config()
        configured_cli = str(getattr(config, "ticket_ai_claude_cli_path", "") or "").strip()
        candidates: list[str | None] = [
            configured_cli,
            shutil.which("claude"),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            candidate_path = Path(candidate)
            if candidate_path.exists():
                return str(candidate_path)
        return None

    @classmethod
    def _resolve_provider_executable(cls, provider_type: str, command_parts: list[str]) -> list[str]:
        """
        按 provider_type 解析可执行文件并返回完整的命令行参数。
        :param provider_type: Provider 类型
        :param command_parts: 原始命令参数列表
        :return: 可执行命令参数列表
        """
        if provider_type == "codex":
            return cls._resolve_worker_command_parts(command_parts)
        if provider_type == "claude":
            parts = [str(p).strip() for p in command_parts if str(p).strip()]
            if not parts:
                parts = ["claude", "-p"]
            executable = parts[0]
            if Path(executable).suffix:
                # 已有完整路径，直接使用
                pass
            else:
                resolved = cls._resolve_claude_cli_executable()
                if not resolved:
                    raise FileNotFoundError(
                        "未找到可执行的 Claude Code CLI。"
                        "请安装 Claude Code，或在 Agent 配置 ticket_ai_claude_cli_path 中填写 CLI 路径"
                    )
                if resolved.lower().endswith((".cmd", ".bat")):
                    return ["cmd", "/c", resolved, *parts[1:]]
                parts[0] = resolved
            return parts
        # 兜底走 codex 逻辑
        return cls._resolve_worker_command_parts(command_parts)

    @classmethod
    def _prepare_ai_home(
        cls,
        workspace_dir: Path,
        provider_type: str,
        provider_env_overrides: dict[str, str] | None = None,
    ) -> Path | None:
        """
        为指定 Provider 准备独立的配置目录。
        - codex: 复制 CODEX_HOME 到 .ai_home/
        - claude: 无需额外配置（Claude Code 自动管理 .claude/），仅写 .env
        :param workspace_dir: 任务工作区
        :param provider_type: Provider 类型
        :param provider_env_overrides: 环境变量覆盖项
        :return: 配置目录路径（claude 时返回 None）
        """
        if provider_type == "claude":
            cls._prepare_claude_env(workspace_dir, provider_env_overrides)
            return None
        return cls._prepare_codex_home(workspace_dir, provider_env_overrides)

    @classmethod
    def _prepare_claude_env(
        cls,
        workspace_dir: Path,
        provider_env_overrides: dict[str, str] | None = None,
    ) -> None:
        """
        为 Claude Code 准备环境：在 workspace_dir 下写入 .env 文件。
        Claude Code 在 cwd（即 workspace_dir）下自动管理 .claude/ 会话目录。
        :param workspace_dir: 任务工作区
        :param provider_env_overrides: 环境变量覆盖项
        """
        overrides = provider_env_overrides or {}
        env_lines: list[str] = []
        api_key = str(overrides.get("ANTHROPIC_API_KEY") or overrides.get("OPENAI_API_KEY") or "").strip()
        base_url = str(overrides.get("ANTHROPIC_BASE_URL") or overrides.get("OPENAI_BASE_URL") or "").strip()
        if api_key:
            env_lines.append(f"ANTHROPIC_API_KEY={api_key}")
        if base_url:
            env_lines.append(f"ANTHROPIC_BASE_URL={base_url}")
        if env_lines:
            env_file = workspace_dir / ".env"
            try:
                existing_lines: list[str] = []
                if env_file.exists():
                    existing_lines = env_file.read_text(encoding="utf-8").splitlines()
                # 同一工作区重试或切换 Provider 时必须覆盖旧值，不能只追加缺失键。
                # 否则 Claude Code 会继续读取上一次任务的 API 地址和密钥。
                override_map = {
                    line.split("=", 1)[0]: line
                    for line in env_lines
                    if "=" in line
                }
                updated_lines: list[str] = []
                written_keys: set[str] = set()
                for existing_line in existing_lines:
                    key = existing_line.split("=", 1)[0] if "=" in existing_line else ""
                    if key in override_map:
                        updated_lines.append(override_map[key])
                        written_keys.add(key)
                    else:
                        updated_lines.append(existing_line)
                updated_lines.extend(
                    line for key, line in override_map.items() if key not in written_keys
                )
                env_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
                logger.info(f"已为 Claude Code 写入 .env: api_key={'***' if api_key else ''}")
            except Exception as exc:
                logger.warning(f"写入 Claude Code .env 失败: {exc}")

    @classmethod
    def _load_worker_env(
        cls,
        ai_home: Path | None,
        provider_type: str,
    ) -> dict[str, str]:
        """
        加载 Worker 执行环境变量。
        :param ai_home: 配置目录（codex），claude 时为 None
        :param provider_type: Provider 类型
        :return: 环境变量字典
        """
        if provider_type == "claude":
            # Claude Code: 直接使用进程环境变量
            return dict(os.environ)
        # Codex: 读取隔离配置目录
        env_values = cls._load_codex_env(ai_home) if ai_home else {}
        if ai_home:
            env_values["CODEX_HOME"] = str(ai_home)
        return env_values

    @classmethod
    def _build_worker_command(
        cls,
        *,
        provider_type: str,
        worker_config: dict[str, Any],
        repo_path: Path,
        workspace_dir: Path | None = None,
        schema_file: Path | None,
        result_file: Path | None,
        selected_worker_model: str | None,
    ) -> list[str]:
        """
        按 Provider 类型构建完整的 Worker 命令行。
        :param provider_type: Provider 类型
        :param worker_config: Worker 运行时配置
        :param repo_path: 代码仓库路径
        :param workspace_dir: 当前任务工作区路径
        :param schema_file: JSON Schema 文件路径
        :param result_file: 结果输出文件路径
        :param selected_worker_model: 选择的模型名称
        :return: 命令行参数列表
        """
        command_parts = [str(p).strip() for p in str(worker_config["command"]).split() if str(p).strip()]
        command = cls._resolve_provider_executable(provider_type, command_parts)

        # 代码目录参数
        code_flag = worker_config.get("code_arg_flag")
        if code_flag:
            if provider_type == "codex" and workspace_dir:
                # Codex 的主项目是任务工作区；指定的 worktree 作为额外可写目录提供。
                command.extend([str(code_flag), str(workspace_dir), "--add-dir", str(repo_path)])
            else:
                command.extend([str(code_flag), str(repo_path)])

        # --approve-for-me 本身会使用 workspace-write，不能再同时传 --sandbox。
        # 这样既避免 CLI 参数冲突，也不会使用 dangerously-bypass 全盘绕过沙箱。
        if provider_type == "codex" and "--approve-for-me" not in command:
            command.append("--approve-for-me")

        # 未启用自动审批时才传显式沙箱参数；当前 Codex 后台执行默认启用自动审批。
        sandbox = worker_config.get("sandbox")
        if sandbox and "--approve-for-me" not in command:
            command.extend(["-s", str(sandbox)])

        # git 检查跳过（仅 codex）
        skip_flag = worker_config.get("skip_git_check_flag")
        if skip_flag:
            command.append(str(skip_flag))

        # 输出 schema（codex 传文件路径，claude 传 JSON 字符串）
        schema_flag = worker_config.get("output_schema_flag")
        if schema_flag and schema_file:
            if provider_type == "claude" and schema_file.exists():
                schema_text = schema_file.read_text(encoding="utf-8").strip()
                # 压缩为单行 JSON，避免多行文本通过 cmd /c 传递时被 shell 截断
                minified = json.dumps(json.loads(schema_text), ensure_ascii=False)
                command.extend([str(schema_flag), minified])
            else:
                command.extend([str(schema_flag), str(schema_file)])

        # 输出结果文件（仅 codex）
        output_flag = worker_config.get("output_file_flag")
        if output_flag and result_file:
            command.extend([str(output_flag), str(result_file)])

        # JSONL 事件流输出（仅 codex）：stdout 会输出事件流，
        # turn.completed 事件携带每次回合的 Token 用量，用于统计累计消耗。
        json_output_flag = worker_config.get("json_output_flag")
        if json_output_flag:
            command.append(str(json_output_flag))

        # 输出格式（仅 claude：--output-format json）
        output_format_flag = worker_config.get("output_format_flag")
        output_format = worker_config.get("output_format")
        if output_format_flag and output_format:
            command.extend([str(output_format_flag), str(output_format)])

        # 权限模式（仅 claude）
        permission_flag = worker_config.get("permission_mode_flag")
        permission_mode = worker_config.get("permission_mode")
        if permission_flag and permission_mode:
            command.extend([str(permission_flag), str(permission_mode)])

        # 工具白名单（仅 claude）
        allowed_tools_flag = worker_config.get("allowed_tools_flag")
        allowed_tools = worker_config.get("allowed_tools")
        if allowed_tools_flag and allowed_tools:
            command.extend([str(allowed_tools_flag), str(allowed_tools)])

        # 模型参数
        if selected_worker_model:
            model_flag = worker_config.get("model_flag")
            if model_flag and model_flag not in command:
                command.extend([str(model_flag), str(selected_worker_model)])

        # stdin 占位符（claude 使用 "-" 从 stdin 读取 prompt）
        stdin_placeholder = worker_config.get("stdin_placeholder")
        if stdin_placeholder and stdin_placeholder not in command:
            command.append(str(stdin_placeholder))

        return command

    @classmethod
    def _resolve_worker_result_text(
        cls,
        *,
        provider_type: str,
        worker_config: dict[str, Any],
        result_file: Path | None,
        raw_stdout: str,
        raw_stderr: str,
    ) -> str:
        """
        按 Provider 输出模式解析出待解析的原始结果文本。
        :param provider_type: Provider 类型
        :param worker_config: Worker 运行时配置
        :param result_file: Codex 结果文件
        :param raw_stdout: Worker 标准输出
        :param raw_stderr: Worker 标准错误
        :return: 原始结果文本，可能为空字符串
        """
        result_text = ""
        if worker_config.get("output_mode") == "file" and result_file and result_file.exists():
            result_text = result_file.read_text(encoding="utf-8")
        elif raw_stdout.strip():
            result_text = raw_stdout.strip()
        elif raw_stderr.strip():
            result_text = raw_stderr.strip()
        return result_text

    @classmethod
    def _parse_worker_output(
        cls,
        *,
        provider_type: str,
        worker_config: dict[str, Any],
        result_file: Path | None,
        raw_stdout: str,
        raw_stderr: str,
        schema_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        按 Provider 类型解析 Worker 输出结果。
        :param provider_type: Provider 类型
        :param worker_config: Worker 运行时配置
        :param result_file: Codex 结果文件
        :param raw_stdout: Worker 标准输出
        :param raw_stderr: Worker 标准错误
        :param schema_payload: 本次任务要求的 JSON Schema
        :return: 解析后的结果字典，解析失败返回 None
        """
        result_text = cls._resolve_worker_result_text(
            provider_type=provider_type,
            worker_config=worker_config,
            result_file=result_file,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
        )

        if not result_text.strip():
            return None

        # Claude Code 使用 --output-format json 时，stdout 是单行 JSON，
        # 其中 structured_output 是已解析好的 dict，result 是模型最终文本。
        def accept_candidate(candidate: Any) -> dict[str, Any] | None:
            if not isinstance(candidate, dict):
                return None
            if schema_payload and not cls._validate_json_schema(candidate, schema_payload):
                return None
            return candidate

        if provider_type == "claude":
            claude_payload = cls._extract_json_from_text(result_text)
            if isinstance(claude_payload, dict):
                structured = claude_payload.get("structured_output")
                if isinstance(structured, dict):
                    accepted = accept_candidate(structured)
                    if accepted is not None:
                        return accepted
                raw_result = claude_payload.get("result")
                if isinstance(raw_result, str):
                    parsed = cls._extract_json_from_text(raw_result)
                    accepted = accept_candidate(parsed)
                    if accepted is not None:
                        return accepted
                if claude_payload.get("is_error"):
                    return None
                accepted = accept_candidate(claude_payload)
                if accepted is not None:
                    return accepted

        # 尝试直接解析 JSON
        try:
            accepted = accept_candidate(json.loads(result_text))
            if accepted is not None:
                return accepted
        except Exception:
            pass

        # Codex 结果文件和 Claude 最终文本都可能带 markdown JSON 围栏，统一尝试提取。
        extracted_result = accept_candidate(cls._extract_json_from_text(result_text))
        if extracted_result is not None:
            return extracted_result

        # 尝试取最后一行 JSON
        try:
            return accept_candidate(json.loads(raw_stdout.strip().splitlines()[-1]))
        except Exception:
            return None

    @classmethod
    def _validate_json_schema(cls, payload: Any, schema: dict[str, Any]) -> bool:
        """
        校验 Worker 结果是否满足当前任务下发的 JSON Schema。
        当前工单分析 schema 使用 object、array、string、number、integer、null 和 required，
        这里仅实现这些无副作用的基础规则，避免 Agent 客户端增加额外运行时依赖。
        :param payload: 待校验结果
        :param schema: JSON Schema
        :return: 是否通过校验
        """
        return not cls._collect_json_schema_violations(payload, schema)

    @classmethod
    def _collect_json_schema_violations(cls, payload: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
        """
        收集 Worker 结果相对任务下发 JSON Schema 的违规路径，用于失败诊断上报。
        判定规则与 _validate_json_schema 完全一致，但以
        `字段路径: 期望类型/实际类型` 形式返回，便于随 ai_analysis_error 事件
        直接写入服务端日志、任务记录和前端失败提示。
        :param payload: 待校验结果
        :param schema: JSON Schema
        :param path: 当前校验的 JSON 路径
        :return: 违规描述列表，空列表表示通过校验
        """
        expected_type = schema.get("type")

        def _type_name(value: Any) -> str:
            if value is None:
                return "null"
            if isinstance(value, bool):
                return "boolean"
            if isinstance(value, (int, float)):
                return "number"
            if isinstance(value, str):
                return "string"
            if isinstance(value, list):
                return "array"
            if isinstance(value, dict):
                return "object"
            return type(value).__name__

        if isinstance(expected_type, list):
            # 联合类型：任一分支通过即通过，全部分支失败才报告违规。
            branch_violations = [
                cls._collect_json_schema_violations(payload, {**schema, "type": item}, path)
                for item in expected_type
            ]
            if all(branch_violations):
                expected_desc = "/".join(expected_type)
                return [f"{path}: 期望 {expected_desc}，实际 {_type_name(payload)}"]
            return []
        if expected_type == "object":
            if not isinstance(payload, dict):
                return [f"{path}: 期望 object，实际 {_type_name(payload)}"]
            violations: list[str] = []
            required = schema.get("required") or []
            properties = schema.get("properties") or {}
            for field in required:
                if field not in payload:
                    violations.append(f"{path}.{field}: required 字段缺失")
            if schema.get("additionalProperties") is False:
                for key in payload:
                    if key not in properties:
                        violations.append(f"{path}.{key}: additionalProperties 不允许的额外字段")
            for key, child_schema in properties.items():
                if key in payload:
                    violations.extend(cls._collect_json_schema_violations(payload[key], child_schema, f"{path}.{key}"))
            return violations
        if expected_type == "array":
            if not isinstance(payload, list):
                return [f"{path}: 期望 array，实际 {_type_name(payload)}"]
            violations = []
            items_schema = schema.get("items") or {}
            for index, item in enumerate(payload):
                violations.extend(cls._collect_json_schema_violations(item, items_schema, f"{path}[{index}]"))
            return violations
        if expected_type == "string":
            if not isinstance(payload, str):
                return [f"{path}: 期望 string，实际 {_type_name(payload)}"]
            return []
        if expected_type == "number":
            if not (isinstance(payload, (int, float)) and not isinstance(payload, bool)):
                return [f"{path}: 期望 number，实际 {_type_name(payload)}"]
            return []
        if expected_type == "integer":
            if not (isinstance(payload, int) and not isinstance(payload, bool)):
                return [f"{path}: 期望 integer，实际 {_type_name(payload)}"]
            return []
        if expected_type == "null":
            if payload is not None:
                return [f"{path}: 期望 null，实际 {_type_name(payload)}"]
            return []
        if expected_type == "boolean":
            if not isinstance(payload, bool):
                return [f"{path}: 期望 boolean，实际 {_type_name(payload)}"]
            return []
        return []

    @classmethod
    def _find_token_usage_payload(cls, candidate: Any) -> dict[str, Any] | None:
        """
        递归查找结果结构中的 Token 用量对象。
        :param candidate: 待查找对象
        :return: Token 用量字典
        """
        if isinstance(candidate, dict):
            direct_keys = {
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "input_tokens",
                "output_tokens",
                "inputTokens",
                "outputTokens",
                "totalTokens",
            }
            if any(key in candidate for key in direct_keys):
                return candidate
            for key in ("usage", "token_usage", "tokenUsage"):
                payload = candidate.get(key)
                if isinstance(payload, dict):
                    return payload
            for value in candidate.values():
                payload = cls._find_token_usage_payload(value)
                if payload is not None:
                    return payload
            return None
        if isinstance(candidate, (list, tuple)):
            for item in candidate:
                payload = cls._find_token_usage_payload(item)
                if payload is not None:
                    return payload
        return None

    @classmethod
    def _extract_token_usage_payload(cls, *candidates: Any) -> dict[str, Any] | None:
        """
        从多个候选对象中提取 Token 用量。
        :param candidates: 候选对象列表
        :return: Token 用量字典
        """
        for candidate in candidates:
            payload = cls._find_token_usage_payload(candidate)
            if payload is not None:
                return payload
        return None

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        """
        将 Token 计数字段安全转换为整数。
        :param value: 原始值
        :return: 整数值，无法转换时返回 None
        """
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        try:
            text_value = str(value).strip().replace(",", "")
        except Exception:
            return None
        if not text_value:
            return None
        try:
            return int(text_value)
        except Exception:
            try:
                return int(float(text_value))
            except Exception:
                return None

    @classmethod
    def _recover_token_usage_from_workspace(
        cls,
        workspace_dir: Path | None,
        *,
        provider_type: str,
    ) -> dict[str, Any] | None:
        """
        从工作区已落盘的文件中恢复 Token 用量（用于超时/异常等拿不到进程输出的分支）。
        :param workspace_dir: 任务工作区，可能尚未创建
        :param provider_type: Provider 类型
        :return: Token 用量字典，无法恢复时返回 None
        """
        if not workspace_dir:
            return None
        try:
            return cls._parse_failure_token_usage(
                provider_type=provider_type,
                raw_stdout=(workspace_dir / "worker.stdout.txt").read_text(encoding="utf-8")
                if (workspace_dir / "worker.stdout.txt").exists()
                else None,
                raw_stderr=(workspace_dir / "worker.stderr.txt").read_text(encoding="utf-8")
                if (workspace_dir / "worker.stderr.txt").exists()
                else None,
                result_file=workspace_dir / "result.json",
            )
        except Exception as exc:
            logger.warning(f"从工作区恢复 Token 用量失败: {exc}")
            return None

    @classmethod
    def _parse_failure_token_usage(
        cls,
        *,
        provider_type: str,
        raw_stdout: str | None,
        raw_stderr: str | None,
        result_file: Path | None = None,
    ) -> dict[str, Any] | None:
        """
        从失败/超时执行路径中尽力提取已消耗的 Token 用量。

        Worker 失败、结果无效或超时时，模型调用可能已经发生并产生真实消耗：
        Codex 事件流中已完成的 turn、Claude modelUsage、结果文件内嵌 usage 都可能存在。
        失败不影响已产生 token 的真实性，失败路径同样解析，供服务端如实入审计。
        :param provider_type: Provider 类型（codex/claude）
        :param raw_stdout: Worker 标准输出
        :param raw_stderr: Worker 标准错误
        :param result_file: 结果文件路径（可能残留部分结果）
        :return: 已消耗的 Token 用量字典，无法提取时返回 None
        """
        token_usage_payload: dict[str, Any] | None = None
        if provider_type == "codex":
            token_usage_payload = cls._parse_codex_jsonl_token_usage(raw_stdout)
        elif provider_type == "claude":
            token_usage_payload = cls._parse_claude_token_usage(raw_stdout, accept_error_result=True)
        if token_usage_payload is None:
            # 回退通用候选提取：结果文件内容、stdout/stderr 中可能内嵌 usage。
            file_payload = cls._read_json_file(result_file) if result_file else None
            token_usage_payload = cls._extract_token_usage_payload(
                file_payload,
                cls._extract_json_from_text(raw_stdout) if (raw_stdout or "").strip() else None,
                cls._extract_json_from_text(raw_stderr) if (raw_stderr or "").strip() else None,
            )
        if token_usage_payload is not None:
            logger.info(f"失败路径提取到已消耗 Token 用量: {token_usage_payload}")
        return token_usage_payload

    @classmethod
    def _parse_codex_jsonl_token_usage(cls, raw_stdout: str | None) -> dict[str, Any] | None:
        """
        从 Codex --json 的 JSONL 事件流中解析并累加 Token 用量。

        Codex 以 --json 运行时，stdout 每行输出一个 JSON 事件，回合结束事件
        turn.completed 携带 usage 字段（input_tokens / cached_input_tokens /
        output_tokens 等）。一次执行可能包含多个 turn（如 resume、多阶段执行），
        这里逐行累加所有事件的用量，得到整个过程的总消耗，而不是只取最后一次。

        注意：必须限定为多行事件流结构（type + usage 双特征）才解析，
        避免 Claude 单行 JSON 输出（顶层 usage 语义为最后一次 API 调用）被误判。
        :param raw_stdout: Worker 标准输出（JSONL 事件流文本）
        :return: 累加后的 Token 用量字典，无有效事件时返回 None
        """
        if not raw_stdout or not raw_stdout.strip():
            return None
        total_input = 0
        total_output = 0
        total_cached = 0
        total_all = 0
        found = False
        for line in raw_stdout.splitlines():
            line_text = line.strip()
            if not line_text:
                continue
            try:
                event = json.loads(line_text)
            except Exception:
                # 事件流中混入非 JSON 行时跳过，不中断整体解析。
                continue
            if not isinstance(event, dict):
                continue
            usage = event.get("usage")
            # 仅识别 codex 事件流形态：回合结束事件（turn.completed，兼容后续版本
            # 可能的 thread.completed 等变体）中的 usage 为该轮增量累计。
            # Claude 输出 type 固定为 result 且无 turn/thread 事件，不会进入此分支。
            event_type = event.get("type")
            if not isinstance(usage, dict) or not isinstance(event_type, str):
                continue
            if event_type not in ("turn.completed", "thread.completed"):
                continue
            input_count = cls._to_optional_int(usage.get("input_tokens")) or 0
            output_count = cls._to_optional_int(usage.get("output_tokens")) or 0
            cached_count = cls._to_optional_int(usage.get("cached_input_tokens")) or 0
            found = True
            total_input += input_count
            total_output += output_count
            total_cached += cached_count
            # input_tokens 为包含缓存命中的总输入；若某版本仅输出不含缓存的口径，
            # cached_input_tokens 大于 input 时按两者之和兜底，避免总量小于分量。
            turn_total = input_count + output_count
            if cached_count > input_count:
                turn_total = cached_count + output_count
            total_all += turn_total
        if not found:
            return None
        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cached_input_tokens": total_cached if total_cached else None,
            "total_tokens": total_all,
        }

    @classmethod
    def _parse_claude_token_usage(
        cls,
        raw_stdout: str | None,
        accept_error_result: bool = False,
    ) -> dict[str, Any] | None:
        """
        从 Claude Code --output-format json 的单行 JSON 输出中解析 Token 用量。

        Claude 顶层 usage 是主模型最后一次 API 调用的值（非整个任务累计）；
        modelUsage 按模型给出本次执行的累计用量（inputTokens / outputTokens /
        cacheReadInputTokens / cacheCreationInputTokens），这里按模型累加得到总量。
        :param raw_stdout: Worker 标准输出（单行 JSON）
        :param accept_error_result: 是否接受 is_error=True 的失败结果报文；
            失败提取路径传 True，模型调用可能已发生且消耗真实
        :return: 累加后的 Token 用量字典，无有效数据时返回 None
        """
        if not raw_stdout or not raw_stdout.strip():
            return None
        try:
            payload = json.loads(raw_stdout.strip().splitlines()[-1])
        except Exception:
            return None
        # 仅识别 Claude result 报文：type=result 且顶层有 result/num_turns 等特征；
        # Codex 事件流最后一行是 turn.completed，不会被误解析。
        if not isinstance(payload, dict) or payload.get("type") != "result":
            return None
        if not accept_error_result and payload.get("is_error"):
            # 成功路径拒绝错误报文（历史语义，避免误读半截输出）；
            # 失败提取（accept_error_result=True）接受：调用可能已发生且消耗真实。
            return None
        model_usage = payload.get("modelUsage")
        total_input = 0
        total_output = 0
        total_cached = 0
        found = False
        if isinstance(model_usage, dict) and model_usage:
            # modelUsage 覆盖任务中实际使用的全部模型（含轻量分类等辅助模型），
            # 逐模型累加得到整个任务的消耗。
            for model_stat in model_usage.values():
                if not isinstance(model_stat, dict):
                    continue
                input_count = cls._to_optional_int(model_stat.get("inputTokens")) or 0
                output_count = cls._to_optional_int(model_stat.get("outputTokens")) or 0
                cached_count = (
                    cls._to_optional_int(model_stat.get("cacheReadInputTokens")) or 0
                ) + (cls._to_optional_int(model_stat.get("cacheCreationInputTokens")) or 0)
                if not input_count and not output_count and not cached_count:
                    continue
                found = True
                total_input += input_count
                total_output += output_count
                total_cached += cached_count
        if not found:
            # 旧版本无 modelUsage 时回退顶层 usage：虽只是主模型最后一次调用的近似值，
            # 也好于完全无数据；total 按 input + output 计算，避免缓存重复计入。
            usage = payload.get("usage")
            if not isinstance(usage, dict):
                return None
            input_count = cls._to_optional_int(usage.get("input_tokens")) or 0
            output_count = cls._to_optional_int(usage.get("output_tokens")) or 0
            if not input_count and not output_count:
                return None
            return {
                "input_tokens": input_count,
                "output_tokens": output_count,
                "cached_input_tokens": None,
                "total_tokens": input_count + output_count,
            }
        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cached_input_tokens": total_cached if total_cached else None,
            "total_tokens": total_input + total_output,
        }

    @staticmethod
    def _repair_unescaped_quotes(text: str) -> str | None:
        """
        尝试修复 JSON 字符串值内部未转义的英文双引号。

        部分模型（如 deepseek-v4-flash）即使通过 --output-schema 约束，
        仍可能在字符串值中输出未转义双引号（例如：停留在"恢复中"（Pending）状态），
        导致 JSON 本身非法。这里做一次结构化扫描：
        - 在字符串内部遇到未转义引号时，按"引号后紧跟 , } ] : 或文本结束"判断
          它是否为键/值的真实结束符；不是则补反斜杠转义为值内部字符。
        - 修复结果必须能通过 json.loads 且为 dict，否则放弃修复返回 None，
          保持与修复前一致的行为（解析失败）。
        :param text: 原始文本（应已剥离 Markdown 代码块围栏）
        :return: 修复后的 JSON 文本；无法修复时返回 None
        """
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        candidate = text[start : end + 1]

        in_string = False
        repaired_chars: list[str] = []
        index = 0
        length = len(candidate)
        while index < length:
            ch = candidate[index]
            if not in_string:
                # 字符串外：引号视为字符串开始，其余字符原样保留
                if ch == '"':
                    in_string = True
                repaired_chars.append(ch)
                index += 1
                continue
            if ch == "\\" and index + 1 < length:
                # 已转义序列原样保留（如 \" \\ \n）
                repaired_chars.append(candidate[index : index + 2])
                index += 2
                continue
            if ch == '"':
                # 字符串内的引号：后紧跟结构符（, } ] :)或文本结束时视为真实结束符，
                # 否则视为值内部未转义引号，转义后继续
                after = candidate[index + 1 :].lstrip()
                if after.startswith((",", "}", "]", ":")) or after == "":
                    in_string = False
                    repaired_chars.append(ch)
                else:
                    repaired_chars.append('\\"')
                index += 1
                continue
            repaired_chars.append(ch)
            index += 1

        repaired = "".join(repaired_chars)
        try:
            payload = json.loads(repaired)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return repaired

    @classmethod
    def _extract_json_from_text(cls, text: str) -> dict[str, Any] | None:
        """
        从 Claude Code 输出文本中提取 JSON 结果块。
        Claude Code 的 stdout 可能在 markdown 代码块中包含 JSON。
        :param text: 原始输出文本
        :return: 解析后的字典
        """
        # 尝试匹配 ```json ... ``` 代码块
        import re as _re
        json_block_match = _re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', text)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except Exception:
                pass
        # 尝试匹配纯 JSON 对象（从第一个 { 到最后一个 }）
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass
        # 常规解析失败后，兜底修复字符串值内部未转义的双引号
        # （例如 deepseek-v4-flash 输出：停留在"恢复中"（Pending）状态）。
        for source in (
            json_block_match.group(1) if json_block_match else None,
            text[start:end + 1] if start >= 0 and end > start else None,
        ):
            if not source:
                continue
            repaired = cls._repair_unescaped_quotes(source)
            if repaired is not None:
                try:
                    payload = json.loads(repaired)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    return payload
        return None

    @classmethod
    def _copy_session_for_resume(
        cls,
        workspace_dir: Path,
        provider_type: str,
        resume_from_workspace: str | None,
    ) -> tuple[bool, str | list[str]]:
        """
        Resume 时将上一次任务的会话数据复制到当前工作区。
        - codex: 复制 .ai_home/ 目录
        - claude: 复制 .claude/ 目录
        :param workspace_dir: 当前任务工作区
        :param provider_type: Provider 类型
        :param resume_from_workspace: 上次任务的 workspace 路径
        :return: (是否成功复制, resume 命令行参数列表)
        """
        if not resume_from_workspace:
            return False, []
        source_ws = Path(resume_from_workspace)
        if not source_ws.exists():
            logger.warning(f"Resume 源工作区不存在: {resume_from_workspace}")
            return False, []

        worker_config = cls._get_provider_worker_config(provider_type)
        resume_flag = worker_config.get("resume_flag")
        if not resume_flag:
            return False, []

        try:
            if provider_type == "claude":
                # 复制 .claude/ 目录到当前 workspace
                src_claude = source_ws / ".claude"
                dst_claude = workspace_dir / ".claude"
                if src_claude.exists() and not dst_claude.exists():
                    shutil.copytree(src_claude, dst_claude)
                    logger.info(f"已复制 Claude 会话: {src_claude} → {dst_claude}")
                return True, [str(resume_flag)]
            else:
                # codex: 复制 .ai_home/ 目录
                src_home = source_ws / ".ai_home"
                dst_home = workspace_dir / ".ai_home"
                if src_home.exists() and not dst_home.exists():
                    shutil.copytree(src_home, dst_home)
                    logger.info(f"已复制 Codex 会话: {src_home} → {dst_home}")
                return True, [str(resume_flag)]
        except Exception as exc:
            logger.warning(f"复制 Resume 会话失败: provider={provider_type}, error={exc}")
            return False, []

    @staticmethod
    def _build_hidden_subprocess_kwargs() -> dict[str, Any]:
        """
        构建 Windows 下隐藏子进程控制台窗口的参数。
        :return: subprocess.run 可用的额外参数
        """
        if os.name != "nt":
            return {}
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            "startupinfo": startupinfo,
        }

    @staticmethod
    def _sanitize_path_segment(value: str, fallback: str = "repo") -> str:
        """
        将文本转换为可作为目录名的安全片段。
        :param value: 原始文本。
        :param fallback: 文本为空时的默认片段。
        :return: 安全目录名片段。
        """
        normalized = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value or "").strip())
        normalized = normalized.strip("._-")
        return normalized[:120] or fallback

    @staticmethod
    def _normalize_branch_name(branch_name: str | None) -> str:
        """
        归一化分支名，兼容 refs/heads 与 origin 前缀。
        :param branch_name: 原始分支名。
        :return: 本地分支名。
        """
        normalized = str(branch_name or "").strip().replace("\\", "/")
        for prefix in ("refs/heads/", "remotes/origin/", "origin/"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        return normalized.strip("/")

    @classmethod
    def _run_git_command(
        cls,
        args: list[str],
        *,
        cwd: Path | None = None,
        timeout_sec: int = 120,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        执行 git 命令，并在失败时返回面向 Agent 的明确错误。
        :param args: git 子命令参数。
        :param cwd: 执行目录。
        :param timeout_sec: 超时时间。
        :param check: 是否校验退出码。
        :return: git 执行结果。
        """
        command = ["git", *args]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                cwd=str(cwd) if cwd else None,
                timeout=max(timeout_sec, 10),
                **cls._build_hidden_subprocess_kwargs(),
            )
        except FileNotFoundError as exc:
            raise RuntimeError("未找到 git 命令，请先安装 Git 并确认 git 已加入 PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"执行 git 命令超时: {' '.join(command)}") from exc
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"执行 git 命令失败: {' '.join(command)}; {detail}")
        return result

    @classmethod
    def _get_repo_current_branch(cls, repo_path: Path) -> str:
        """
        读取本地仓库当前分支。
        :param repo_path: 本地仓库或 worktree 目录。
        :return: 当前分支名。
        """
        result = cls._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
        branch_name = result.stdout.strip()
        if not branch_name or branch_name == "HEAD":
            raise RuntimeError(f"本地仓库处于 detached HEAD，无法校验分支: {repo_path}")
        return branch_name

    @classmethod
    def _ensure_repo_branch_matches(cls, repo_path: Path, expected_branch: str) -> str:
        """
        校验本地仓库分支必须与工单映射分支一致。
        :param repo_path: 本地仓库或 worktree 目录。
        :param expected_branch: 工单映射要求的分支。
        :return: 当前分支名。
        """
        expected = cls._normalize_branch_name(expected_branch)
        if not expected:
            raise RuntimeError("仓库映射 branchName 为空，无法校验 AI 分析代码分支")
        if not repo_path.exists():
            raise FileNotFoundError(f"本地仓库路径不存在: {repo_path}")
        current = cls._get_repo_current_branch(repo_path)
        if cls._normalize_branch_name(current) != expected:
            raise RuntimeError(
                "本地仓库分支与工单映射不一致，已停止 AI 分析。"
                f"期望分支: {expected}; 当前分支: {current}; localRepoPath: {repo_path}"
            )
        return current

    @classmethod
    def _find_registered_worktree_by_branch(cls, repo_path: Path, expected_branch: str) -> Path | None:
        """
        从当前 Git 仓库已登记的 worktree 中查找指定分支目录。
        :param repo_path: Git 仓库、bare 仓库或任意 worktree 目录。
        :param expected_branch: 需要复用的分支名。
        :return: 已登记且分支匹配的 worktree 路径，不存在时返回 None。
        """
        expected = cls._normalize_branch_name(expected_branch)
        if not expected or not repo_path.exists():
            return None

        result = cls._run_git_command(["worktree", "list", "--porcelain"], cwd=repo_path, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            logger.warning(f"读取 Git worktree 列表失败，跳过已登记目录复用: repo_path={repo_path}, detail={detail}")
            return None

        current_path: Path | None = None
        current_branch = ""
        for raw_line in (result.stdout or "").splitlines():
            line = raw_line.strip()
            if not line:
                if current_path and cls._normalize_branch_name(current_branch) == expected and current_path.exists():
                    cls._ensure_repo_branch_matches(current_path, expected)
                    return current_path
                current_path = None
                current_branch = ""
                continue
            if line.startswith("worktree "):
                current_path = Path(line[len("worktree "):].strip())
                current_branch = ""
            elif line.startswith("branch "):
                current_branch = line[len("branch "):].strip()

        if current_path and cls._normalize_branch_name(current_branch) == expected and current_path.exists():
            cls._ensure_repo_branch_matches(current_path, expected)
            return current_path
        return None

    @classmethod
    def _repo_cache_dir(cls, workspace_root: Path, repo_url: str) -> Path:
        """
        根据远端仓库地址生成 bare 仓库缓存目录。
        :param workspace_root: AI 工作区根目录。
        :param repo_url: 远端仓库地址。
        :return: bare 仓库缓存目录。
        """
        safe_repo = cls._sanitize_path_segment(repo_url.replace(":", "_").replace("/", "_"), "repo")
        return workspace_root / "_repo_cache" / f"{safe_repo}.git"

    @classmethod
    def _worktree_path(cls, workspace_root: Path, repo_url: str, branch_name: str) -> Path:
        """
        根据远端仓库地址和分支生成固定 worktree 目录。
        :param workspace_root: AI 工作区根目录。
        :param repo_url: 远端仓库地址。
        :param branch_name: 分支名称。
        :return: worktree 目录。
        """
        safe_repo = cls._sanitize_path_segment(repo_url.replace(":", "_").replace("/", "_"), "repo")
        safe_branch = cls._sanitize_path_segment(cls._normalize_branch_name(branch_name).replace("/", "_"), "branch")
        return workspace_root / "repo_worktrees" / safe_repo / safe_branch

    @classmethod
    def _local_worktree_path(cls, workspace_root: Path, source_repo_path: Path, branch_name: str) -> Path:
        """
        根据本地仓库路径和分支生成固定 worktree 目录。
        :param workspace_root: AI 工作区根目录。
        :param source_repo_path: 仓库映射配置的本地仓库目录。
        :param branch_name: 分支名称。
        :return: 本地仓库派生的 worktree 目录。
        """
        safe_repo = cls._sanitize_path_segment(str(source_repo_path.resolve()).replace(":", "_").replace("\\", "_"), "repo")
        safe_branch = cls._sanitize_path_segment(cls._normalize_branch_name(branch_name).replace("/", "_"), "branch")
        return workspace_root / "repo_worktrees" / "local" / safe_repo / safe_branch

    @classmethod
    def _ensure_local_worktree_repo(
        cls,
        *,
        workspace_root: Path,
        source_repo_path: Path,
        branch_name: str,
    ) -> Path:
        """
        基于仓库映射中的本地仓库创建分支固定 worktree，复用原仓库 Git 配置和凭据。
        :param workspace_root: AI 工作区根目录。
        :param source_repo_path: 仓库映射配置的本地仓库目录。
        :param branch_name: 分支名称。
        :return: 可用于 Codex 分析的 worktree 目录。
        """
        expected_branch = cls._normalize_branch_name(branch_name)
        if not expected_branch:
            raise RuntimeError("仓库映射 branchName 为空，无法基于本地仓库创建 worktree")
        if not source_repo_path.exists():
            raise FileNotFoundError(f"本地仓库路径不存在: {source_repo_path}")

        worktree_path = cls._local_worktree_path(workspace_root, source_repo_path, expected_branch)
        if worktree_path.exists():
            cls._ensure_repo_branch_matches(worktree_path, expected_branch)
            return worktree_path

        registered_worktree = cls._find_registered_worktree_by_branch(source_repo_path, expected_branch)
        if registered_worktree:
            logger.info(
                f"复用 Git 已登记的本地派生 worktree: "
                f"source_repo_path={source_repo_path}, branch={expected_branch}, path={registered_worktree}"
            )
            return registered_worktree

        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"基于映射本地仓库创建 AI 分析固定 worktree: "
            f"source_repo_path={source_repo_path}, branch={expected_branch}, path={worktree_path}"
        )
        local_branch_check = cls._run_git_command(
            ["show-ref", "--verify", f"refs/heads/{expected_branch}"],
            cwd=source_repo_path,
            check=False,
        )
        if local_branch_check.returncode == 0:
            cls._run_git_command(
                ["worktree", "add", str(worktree_path), expected_branch],
                cwd=source_repo_path,
                timeout_sec=900,
            )
        else:
            fetch_result = cls._run_git_command(
                ["fetch", "origin", expected_branch],
                cwd=source_repo_path,
                timeout_sec=600,
                check=False,
            )
            if fetch_result.returncode != 0:
                detail = (fetch_result.stderr or fetch_result.stdout or "").strip()
                raise RuntimeError(
                    f"基于本地仓库创建 worktree 前拉取远端分支失败: "
                    f"branch={expected_branch}, source_repo_path={source_repo_path}, detail={detail}"
                )
            cls._run_git_command(
                ["worktree", "add", "-b", expected_branch, str(worktree_path), f"origin/{expected_branch}"],
                cwd=source_repo_path,
                timeout_sec=900,
            )
        cls._ensure_repo_branch_matches(worktree_path, expected_branch)
        return worktree_path

    @classmethod
    def _ensure_worktree_repo(
        cls,
        *,
        workspace_root: Path,
        repo_url: str,
        branch_name: str,
    ) -> Path:
        """
        准备分支固定 worktree；已有目录只校验分支，不自动 checkout。
        :param workspace_root: AI 工作区根目录。
        :param repo_url: 远端仓库地址。
        :param branch_name: 分支名称。
        :return: 可用于 Codex 分析的 worktree 目录。
        """
        expected_branch = cls._normalize_branch_name(branch_name)
        if not repo_url:
            raise RuntimeError("仓库映射 localRepoPath 为空，且 repoUrl 为空，无法自动创建 worktree")
        if not expected_branch:
            raise RuntimeError("仓库映射 localRepoPath 为空，且 branchName 为空，无法自动创建 worktree")

        worktree_path = cls._worktree_path(workspace_root, repo_url, expected_branch)
        if worktree_path.exists():
            cls._ensure_repo_branch_matches(worktree_path, expected_branch)
            return worktree_path

        cache_dir = cls._repo_cache_dir(workspace_root, repo_url)
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        if not cache_dir.exists():
            logger.info(f"AI 分析 worktree 缺失，开始克隆 bare 仓库: repo_url={repo_url}, cache_dir={cache_dir}")
            cls._run_git_command(["clone", "--bare", repo_url, str(cache_dir)], timeout_sec=1800)
        else:
            logger.info(f"AI 分析 worktree 缺失，刷新 bare 仓库引用: cache_dir={cache_dir}, branch={expected_branch}")
            cls._run_git_command(["fetch", "origin", expected_branch], cwd=cache_dir, timeout_sec=600, check=False)

        registered_worktree = cls._find_registered_worktree_by_branch(cache_dir, expected_branch)
        if registered_worktree:
            logger.info(
                f"复用 Git 已登记的远端仓库 worktree: "
                f"repo_url={repo_url}, branch={expected_branch}, path={registered_worktree}"
            )
            return registered_worktree

        local_branch_check = cls._run_git_command(
            ["show-ref", "--verify", f"refs/heads/{expected_branch}"],
            cwd=cache_dir,
            check=False,
        )
        logger.info(f"创建 AI 分析固定 worktree: branch={expected_branch}, path={worktree_path}")
        if local_branch_check.returncode == 0:
            cls._run_git_command(
                ["worktree", "add", str(worktree_path), expected_branch],
                cwd=cache_dir,
                timeout_sec=900,
            )
        else:
            cls._run_git_command(
                ["worktree", "add", "-b", expected_branch, str(worktree_path), f"origin/{expected_branch}"],
                cwd=cache_dir,
                timeout_sec=900,
            )
        cls._ensure_repo_branch_matches(worktree_path, expected_branch)
        return worktree_path

    @staticmethod
    def _persist_worker_streams(workspace_dir: Path, stdout_text: str | None, stderr_text: str | None) -> None:
        """
        将 Worker 的 stdout 和 stderr 记录到任务工作区。
        :param workspace_dir: 任务工作区
        :param stdout_text: 标准输出
        :param stderr_text: 标准错误
        :return: 无
        """
        try:
            workspace_dir.mkdir(parents=True, exist_ok=True)
            (workspace_dir / "worker.stdout.txt").write_text(stdout_text or "", encoding="utf-8")
            (workspace_dir / "worker.stderr.txt").write_text(stderr_text or "", encoding="utf-8")
        except Exception as exc:
            logger.warning(f"写入 Worker 流文件失败: {exc}")

    @staticmethod
    async def _run_worker_process(
        command: list[str],
        resolved_prompt: str,
        cwd: Path,
        env_values: dict[str, str],
        timeout_sec: int,
    ) -> subprocess.CompletedProcess:
        """
        在后台线程中执行 Worker 进程，避免阻塞 Agent 事件循环。
        cwd 统一为 workspace_dir，各工具通过自身参数定位代码目录
        （Codex 用 -C，Claude Code 用 --add-dir）。
        :param command: Worker 命令
        :param resolved_prompt: 发送给 Worker 的提示词
        :param cwd: 工作目录（workspace_dir）
        :param env_values: 执行环境变量
        :param timeout_sec: 超时时间
        :return: 进程执行结果
        """
        return await asyncio.to_thread(
            subprocess.run,
            command,
            input=resolved_prompt,
            text=True,
            capture_output=True,
            cwd=str(cwd),
            env=env_values,
            timeout=max(timeout_sec, 60),
            **TicketAiAnalysisService._build_hidden_subprocess_kwargs(),
        )

    @staticmethod
    def _read_json_file(path: Path) -> dict[str, Any] | None:
        """
        读取 JSON 文件并转换为字典。
        :param path: JSON 文件路径
        :return: 解析后的字典，失败返回 None
        """
        try:
            if not path.exists():
                return None
            text = path.read_text(encoding="utf-8")
            try:
                payload = json.loads(text)
            except Exception:
                # Codex 的最后消息可能带 ```json 围栏，缓存读取与 Worker 输出解析保持一致。
                payload = TicketAiAnalysisService._extract_json_from_text(text)
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None

    @staticmethod
    def _is_valid_cached_result(payload: dict[str, Any] | None) -> bool:
        """
        判断本地结果是否可作为缓存直接返回。
        :param payload: 结果内容
        :return: 是否可直接复用
        """
        if not isinstance(payload, dict):
            return False
        return any(
            key in payload
            for key in (
                "analysis_result",
                "analysisResult",
                "root_cause",
                "rootCause",
                "analysis_summary",
                "analysisSummary",
            )
        )

    @classmethod
    def _load_cached_result(
        cls,
        result_file: Path,
        schema_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        读取已完成的分析结果缓存。
        :param result_file: 结果文件路径
        :param schema_payload: 本次任务要求的 JSON Schema
        :return: 缓存结果，失败返回 None
        """
        payload = cls._read_json_file(result_file)
        if not cls._is_valid_cached_result(payload):
            return None
        if schema_payload and not cls._validate_json_schema(payload, schema_payload):
            return None
        return payload

    @staticmethod
    def _acquire_task_lock(lock_file: Path, payload: dict[str, Any]) -> bool:
        """
        尝试获取任务运行锁。
        :param lock_file: 锁文件路径
        :param payload: 锁文件内容
        :return: 是否获取成功
        """
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with lock_file.open("x", encoding="utf-8") as file_obj:
                file_obj.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return True
        except FileExistsError:
            return False
        except Exception as exc:
            logger.warning(f"创建 AI 分析任务锁失败: {exc}")
            return False

    @staticmethod
    def _refresh_task_lock_heartbeat(lock_file: Path) -> None:
        """
        刷新任务锁心跳时间戳（Worker 存活证明，纯本地文件写）。
        :param lock_file: 锁文件路径
        :return: 无
        """
        try:
            if not lock_file.exists():
                return
            payload = json.loads(lock_file.read_text(encoding="utf-8") or "{}")
            if not isinstance(payload, dict):
                return
            payload["lastHeartbeatAt"] = datetime.now().isoformat()
            lock_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"刷新 AI 分析任务锁心跳失败: {exc}")

    @classmethod
    async def _run_lock_heartbeat(cls, lock_file: Path, interval_sec: float = 15.0) -> None:
        """
        Worker 执行期间周期刷新锁心跳，直到被取消（finally 中随执行结束取消）。
        :param lock_file: 锁文件路径
        :param interval_sec: 心跳间隔秒数
        :return: 无
        """
        try:
            while True:
                await asyncio.sleep(interval_sec)
                await asyncio.to_thread(cls._refresh_task_lock_heartbeat, lock_file)
        except asyncio.CancelledError:
            # 正常取消：Worker 已结束，锁即将释放。
            raise

    @staticmethod
    def _release_task_lock(lock_file: Path) -> None:
        """
        释放任务运行锁。
        :param lock_file: 锁文件路径
        :return: 无
        """
        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception as exc:
            logger.warning(f"释放 AI 分析任务锁失败: {exc}")

    @staticmethod
    def _parse_iso_datetime(value: Any) -> datetime | None:
        """
        解析 ISO 格式时间字符串。
        :param value: 时间值
        :return: 解析后的时间对象
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except Exception:
            return None

    @classmethod
    def _is_stale_lock(cls, lock_payload: dict[str, Any] | None, timeout_sec: int) -> bool:
        """
        判断锁文件是否已经过期（可被安全接管）。

        心跳续租优先：锁内有 lastHeartbeatAt 时按心跳判活——Worker 存活期间持续刷新，
        心跳停止超过 max(间隔×4, 60) 秒视为 Worker 已死，锁过期可接管。
        无心跳字段的旧版本锁回退到"启动时间 + 超时×2"的时间窗判定，保持兼容。
        :param lock_payload: 锁文件内容
        :param timeout_sec: 当前任务超时时间
        :return: 是否过期
        """
        if not isinstance(lock_payload, dict):
            return True
        # 新版心跳锁：以最近心跳时间为存活依据。
        heartbeat_at = cls._parse_iso_datetime(lock_payload.get("lastHeartbeatAt"))
        if heartbeat_at:
            # 心跳间隔 15 秒，4 倍窗口容忍单次刷新抖动；下限 60 秒防止过激接管。
            stale_after = max(60.0, 15.0 * 4)
            return (datetime.now() - heartbeat_at).total_seconds() > stale_after
        started_at = cls._parse_iso_datetime(lock_payload.get("startedAt") or lock_payload.get("started_at"))
        if not started_at:
            return True
        stale_after = max(int(timeout_sec or cls.DEFAULT_TIMEOUT_SEC), 60) * 2
        return (datetime.now() - started_at).total_seconds() > stale_after

    @staticmethod
    def _download_archive(url: str, target_path: Path) -> Path | None:
        """
        下载日志压缩包到本地工作区。
        :param url: 压缩包下载地址
        :param target_path: 本地保存路径
        :return: 保存后的路径，失败返回 None
        """
        if not url.strip():
            return None
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, timeout=httpx.Timeout(300.0, connect=10.0)) as response:
            response.raise_for_status()
            with target_path.open("wb") as file_obj:
                for chunk in response.iter_bytes():
                    if chunk:
                        file_obj.write(chunk)
        return target_path

    @staticmethod
    def _resolve_log_cache_paths(
        workspace_root: Path,
        ticket_id: int,
        log_record_id: int,
        source_key: str,
    ) -> tuple[Path, Path, Path]:
        """
        根据工单、日志记录和日志来源生成 Agent 本地固定缓存路径。

        :param workspace_root: AI 工作区根目录
        :param ticket_id: 工单ID
        :param log_record_id: 日志拉取记录ID
        :param source_key: 日志来源标识（本地归档路径或下载地址）
        :return: 压缩包缓存路径、解压目录、缓存元数据路径
        """
        source_hash = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:16]
        cache_dir = (
            workspace_root
            / "log_cache"
            / f"ticket_{ticket_id}"
            / f"log_pull_{log_record_id}"
            / source_hash
        )
        return cache_dir / "source_logs.zip", cache_dir / "source_logs", cache_dir / "cache_manifest.json"

    @classmethod
    def _load_log_archive_cache(
        cls,
        cache_manifest_path: Path,
        source_key: str,
        archive_path: Path,
        extract_dir: Path,
    ) -> list[str]:
        """
        校验并读取已完成的日志缓存。

        :param cache_manifest_path: 缓存元数据文件路径
        :param source_key: 本次日志来源标识
        :param archive_path: 本次可用压缩包路径
        :param extract_dir: 缓存解压目录
        :return: 已缓存的解压文件相对路径；无可用缓存时返回空列表
        """
        manifest = cls._read_json_file(cache_manifest_path)
        if not manifest or str(manifest.get("sourceKey") or "") != source_key:
            return []
        if not archive_path.is_file() or archive_path.stat().st_size <= 0 or not extract_dir.is_dir():
            return []
        extracted_files = [
            str(path.relative_to(extract_dir))
            for path in extract_dir.rglob("*")
            if path.is_file()
        ]
        return extracted_files

    @staticmethod
    def _resolve_existing_local_archive(storage_path: str) -> Path | None:
        """
        解析 Agent 当前机器可直接访问的日志归档文件。

        :param storage_path: 服务端记录的归档路径
        :return: 存在且非空的本地归档文件；当前机器不可访问时返回 None
        """
        if not storage_path:
            return None
        try:
            archive_path = Path(storage_path).expanduser()
            if archive_path.is_file() and archive_path.stat().st_size > 0:
                return archive_path
        except OSError:
            return None
        return None

    @staticmethod
    def _extract_archive(archive_path: Path, extract_dir: Path) -> list[str]:
        """
        解压日志压缩包到工作区目录。支持 zip / 7z / tar / tar.gz / tgz / bz2 / xz / gz 等常见格式。
        :param archive_path: 压缩包路径
        :param extract_dir: 解压目录
        :return: 解压后的文件相对路径列表
        """
        extract_dir.mkdir(parents=True, exist_ok=True)
        name = archive_path.name.lower()
        if name.endswith(".7z"):
            return TicketAiAnalysisService._extract_7z(archive_path, extract_dir)
        if name.endswith(".zip"):
            return TicketAiAnalysisService._extract_zip(archive_path, extract_dir)
        if tarfile.is_tarfile(archive_path):
            return TicketAiAnalysisService._extract_tar(archive_path, extract_dir)
        if name.endswith(".gz"):
            return TicketAiAnalysisService._extract_gz(archive_path, extract_dir)
        if name.endswith(".bz2"):
            return TicketAiAnalysisService._extract_bz2(archive_path, extract_dir)
        if name.endswith(".xz"):
            return TicketAiAnalysisService._extract_xz(archive_path, extract_dir)
        # 兜底：尝试 py7zr（不依赖后缀的场景），再失败则走系统 7z
        try:
            return TicketAiAnalysisService._extract_7z(archive_path, extract_dir)
        except Exception:
            return TicketAiAnalysisService._extract_by_system_7z(archive_path, extract_dir)

    @staticmethod
    def _extract_zip(archive_path: Path, extract_dir: Path) -> list[str]:
        extracted_files: list[str] = []
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                if member.endswith("/"):
                    continue
                zip_ref.extract(member, extract_dir)
                extracted_files.append(member)
        return extracted_files

    @staticmethod
    def _extract_7z(archive_path: Path, extract_dir: Path) -> list[str]:
        extracted_files: list[str] = []
        with py7zr.SevenZipFile(archive_path, "r") as archive:
            archive.extractall(path=extract_dir)
            extracted_files = archive.getnames()
        return [f for f in extracted_files if not f.endswith("/")]

    @staticmethod
    def _extract_tar(archive_path: Path, extract_dir: Path) -> list[str]:
        extracted_files: list[str] = []
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                if member.isdir() or member.issym():
                    continue
                archive.extract(member, extract_dir)
                extracted_files.append(member.name)
        return extracted_files

    @staticmethod
    def _extract_gz(archive_path: Path, extract_dir: Path) -> list[str]:
        output_name = archive_path.with_suffix("").name
        output_path = extract_dir / output_name
        with gzip.open(archive_path, "rb") as source, output_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        return [output_name]

    @staticmethod
    def _extract_bz2(archive_path: Path, extract_dir: Path) -> list[str]:
        output_name = archive_path.with_suffix("").name
        output_path = extract_dir / output_name
        with bz2.open(archive_path, "rb") as source, output_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        return [output_name]

    @staticmethod
    def _extract_xz(archive_path: Path, extract_dir: Path) -> list[str]:
        output_name = archive_path.with_suffix("").name
        output_path = extract_dir / output_name
        with lzma.open(archive_path, "rb") as source, output_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        return [output_name]

    @staticmethod
    def _extract_by_system_7z(archive_path: Path, extract_dir: Path) -> list[str]:
        """使用系统 7z 命令解压（兜底方案，支持 rar 等 py7zr 不支持的格式）。"""
        executable = shutil.which("7z") or shutil.which("7z.exe")
        if not executable:
            raise RuntimeError("当前环境未找到 7z 命令行工具，无法解压该格式压缩包")
        process = subprocess.run(
            [executable, "x", "-y", f"-o{extract_dir}", str(archive_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "7z 解压失败")
        # 扫描解压后的非目录文件列表
        extracted: list[str] = []
        for root, _dirs, files in os.walk(extract_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                extracted.append(os.path.relpath(abs_path, extract_dir))
        return extracted

    @classmethod
    def _build_log_digest_keywords(cls, ticket: dict[str, Any], context_payload: dict[str, Any]) -> list[str]:
        """
        从工单和日志提示中提取日志预筛选关键词。
        :param ticket: 工单信息
        :param context_payload: AI 上下文
        :return: 去重后的关键词列表
        """
        source_log_pull = context_payload.get("sourceLogPull") if isinstance(context_payload, dict) else {}
        log_hints = (
            ticket.get("extraData", {}).get("log_pull_hints")
            if isinstance(ticket.get("extraData"), dict)
            else {}
        ) or {}
        text_sources = [
            ticket.get("ticketNo"),
            ticket.get("ticket_no"),
            ticket.get("title"),
            ticket.get("description"),
            context_payload.get("extraInstruction") if isinstance(context_payload, dict) else "",
            source_log_pull.get("contentSummary") if isinstance(source_log_pull, dict) else "",
            log_hints.get("storeId") if isinstance(log_hints, dict) else "",
            log_hints.get("posNo") if isinstance(log_hints, dict) else "",
            log_hints.get("modifyTime") if isinstance(log_hints, dict) else "",
        ]
        default_keywords = [
            "error",
            "exception",
            "fail",
            "failed",
            "timeout",
            "payment",
            "pay",
            "nets",
            "cash",
            "withdrawal",
            "duplicate",
            "reversal",
            "refund",
            "receipt",
            "terminal",
            "ref.no",
            "transaction",
            "offline",
        ]
        candidates: list[str] = []
        for value in text_sources:
            text = str(value or "")
            candidates.extend(re.findall(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,}", text))
        candidates.extend(default_keywords)
        seen: set[str] = set()
        keywords: list[str] = []
        for item in candidates:
            normalized = str(item or "").strip().lower()
            if len(normalized) < 3 or normalized in seen:
                continue
            seen.add(normalized)
            keywords.append(normalized)
        return keywords[:80]

    @classmethod
    def _read_log_lines(cls, file_path: Path) -> list[str]:
        """
        读取日志文件行，兼容常见编码并忽略坏字符。
        :param file_path: 日志文件路径
        :return: 日志行列表
        """
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                return file_path.read_text(encoding=encoding, errors="ignore").splitlines()
            except Exception:
                continue
        return []

    @staticmethod
    def _parse_context_datetime(value: Any) -> datetime | None:
        """
        解析上下文中的日志时间。
        :param value: 时间值
        :return: datetime，无法解析时返回 None
        """
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text[: len(fmt)], fmt)
            except Exception:
                continue
        try:
            return datetime.fromisoformat(text)
        except Exception:
            return None

    @classmethod
    def _extract_window_logs(
        cls,
        *,
        extract_dir: Path,
        extracted_files: list[str],
        begin_time: datetime | None,
        end_time: datetime | None,
        max_chars: int = 800000,
    ) -> dict[str, Any]:
        """
        从解压目录中按时间窗口截取日志正文。
        :param extract_dir: 解压目录
        :param extracted_files: 解压文件相对路径
        :param begin_time: 开始时间
        :param end_time: 结束时间
        :param max_chars: 最大字符数
        :return: 截取结果
        """
        content_parts: list[str] = []
        matched_entries = 0
        current_chars = 0
        for relative_name in extracted_files:
            lowered_name = str(relative_name or "").lower()
            if ".log" not in lowered_name:
                continue
            file_path = extract_dir / relative_name
            lines = cls._read_log_lines(file_path)
            if not lines:
                continue
            current_lines: list[str] = []
            current_timestamp: datetime | None = None

            def flush_entry() -> None:
                nonlocal matched_entries, current_chars
                if not current_lines or current_timestamp is None:
                    return
                if begin_time and current_timestamp < begin_time:
                    return
                if end_time and current_timestamp > end_time:
                    return
                entry_text = "\n".join(current_lines)
                if not entry_text.strip():
                    return
                separator_length = 2 if content_parts else 0
                projected_length = current_chars + len(entry_text) + separator_length
                if projected_length > max_chars:
                    return
                content_parts.append(entry_text)
                matched_entries += 1
                current_chars = projected_length

            for line in lines:
                match = cls.TIMESTAMP_PATTERN.match(line)
                if match:
                    flush_entry()
                    try:
                        current_timestamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
                    except Exception:
                        current_timestamp = None
                    current_lines = [f"[{Path(relative_name).name}]{line}"] if current_timestamp else []
                    continue
                if current_lines:
                    current_lines.append(line)
            flush_entry()
        full_text = "\n\n".join(content_parts)
        return {
            "text": full_text,
            "matchedEntries": matched_entries,
            "charCount": len(full_text),
            "truncated": bool(current_chars >= max_chars),
            "beginTime": begin_time.isoformat() if begin_time else "",
            "endTime": end_time.isoformat() if end_time else "",
            "maxChars": max_chars,
        }

    @classmethod
    def _build_log_digest(
        cls,
        *,
        extract_dir: Path,
        extracted_files: list[str],
        ticket: dict[str, Any],
        context_payload: dict[str, Any],
        digest_path: Path,
    ) -> dict[str, Any]:
        """
        从整包日志中生成受控大小的 AI 摘要，避免 Codex 默认读取全量几十 MB 日志。
        :param extract_dir: 解压目录
        :param extracted_files: 解压出的相对文件列表
        :param ticket: 工单信息
        :param context_payload: AI 上下文
        :param digest_path: 摘要文件路径
        :return: 摘要元数据
        """
        keywords = cls._build_log_digest_keywords(ticket, context_payload)
        keyword_tuple = tuple(keywords)
        digest_parts: list[str] = [
            "# AI 日志预筛选摘要",
            "",
            "说明：本文件由 Agent 从完整日志包中按工单关键词、错误关键词和支付关键词预筛选生成。",
            "digest 模式可优先基于本摘要分析；hybrid 模式下本摘要只作为定位索引，仍必须检索 source_logs 原始日志。",
            "",
            f"关键词：{', '.join(keywords[:60])}",
            "",
            "## 文件清单",
        ]
        total_size = 0
        matched_files = 0
        matched_lines = 0
        for relative_name in extracted_files:
            file_path = extract_dir / relative_name
            if not file_path.exists() or not file_path.is_file():
                continue
            try:
                total_size += file_path.stat().st_size
                digest_parts.append(f"- {relative_name} ({file_path.stat().st_size} bytes)")
            except Exception:
                digest_parts.append(f"- {relative_name}")
        digest_parts.append("")
        digest_parts.append("## 命中片段")

        for relative_name in extracted_files:
            file_path = extract_dir / relative_name
            if not file_path.exists() or not file_path.is_file():
                continue
            lowered_name = relative_name.lower()
            if not any(marker in lowered_name for marker in (".log", "fault", "error", "request")):
                continue
            lines = cls._read_log_lines(file_path)
            if not lines:
                continue
            file_matches = 0
            used_line_indexes: set[int] = set()
            file_blocks: list[str] = []
            for index, line in enumerate(lines):
                lowered_line = line.lower()
                if not any(keyword in lowered_line for keyword in keyword_tuple):
                    continue
                start = max(0, index - cls.DEFAULT_LOG_DIGEST_CONTEXT_LINES)
                end = min(len(lines), index + cls.DEFAULT_LOG_DIGEST_CONTEXT_LINES + 1)
                block_lines: list[str] = []
                for line_index in range(start, end):
                    if line_index in used_line_indexes:
                        continue
                    used_line_indexes.add(line_index)
                    line_text = lines[line_index]
                    if len(line_text) > cls.DEFAULT_LOG_DIGEST_MAX_LINE_CHARS:
                        line_text = f"{line_text[:cls.DEFAULT_LOG_DIGEST_MAX_LINE_CHARS]} ...<line truncated>"
                    block_lines.append(f"{line_index + 1}: {line_text}")
                if block_lines:
                    file_matches += 1
                    matched_lines += len(block_lines)
                    file_blocks.append("\n".join(block_lines))
                if file_matches >= cls.DEFAULT_LOG_DIGEST_MAX_MATCHES_PER_FILE:
                    break
            if not file_blocks:
                continue
            matched_files += 1
            digest_parts.append("")
            digest_parts.append(f"### {relative_name}")
            digest_parts.extend(file_blocks)
            digest_text = "\n".join(digest_parts)
            if len(digest_text) >= cls.DEFAULT_LOG_DIGEST_MAX_CHARS:
                digest_parts.append(
                    f"\n... 摘要已达到 {cls.DEFAULT_LOG_DIGEST_MAX_CHARS} 字符上限，后续日志未继续写入 ...\n"
                )
                break

        digest_text = "\n".join(digest_parts)
        if len(digest_text) > cls.DEFAULT_LOG_DIGEST_MAX_CHARS:
            digest_text = digest_text[: cls.DEFAULT_LOG_DIGEST_MAX_CHARS] + "\n... 摘要已截断 ...\n"
        digest_path.write_text(digest_text, encoding="utf-8")
        return {
            "digestPath": str(digest_path),
            "digestCharCount": len(digest_text),
            "maxDigestChars": cls.DEFAULT_LOG_DIGEST_MAX_CHARS,
            "keywordCount": len(keywords),
            "matchedFiles": matched_files,
            "matchedLines": matched_lines,
            "sourceTotalBytes": total_size,
        }

    @staticmethod
    def _extract_stderr_context(
        stderr_text: str | None,
        keywords: tuple[str, ...] = (
            "openai_error",
            "bad_response_status_code",
            "invalid_request_error",
            "stream disconnected",
            "error sending request",
            "concurrency limit exceeded",
        ),
    ) -> str:
        """
        从 stderr 中提取更长上下文。
        :param stderr_text: 标准错误
        :param keywords: 关键词列表
        :return: 摘要文本
        """
        if not stderr_text:
            return ""
        lines = [line.rstrip() for line in str(stderr_text).splitlines() if line.strip()]
        if not lines:
            return ""
        lowered_keywords = tuple(keyword.lower() for keyword in keywords)
        matched_windows: list[str] = []
        for idx, line in enumerate(lines):
            lower_line = line.strip().lower()
            if any(keyword in lower_line for keyword in lowered_keywords):
                start = max(0, idx - 2)
                end = min(len(lines), idx + 11)
                window = [
                    re.sub(r"\s+", " ", item.strip())
                    for item in lines[start:end]
                    if item.strip() not in {"{", "}", "[", "]"}
                ]
                if window:
                    matched_windows.extend(window)
        if matched_windows:
            # Codex 会把检索到的业务日志也写入 stderr，这里只返回命中的错误窗口，避免污染工单错误摘要。
            return " | ".join(dict.fromkeys(matched_windows))[:4000]
        tail_lines = [
            re.sub(r"\s+", " ", item.strip())
            for item in lines[-20:]
            if item.strip() not in {"{", "}", "[", "]"}
        ]
        return " | ".join(tail_lines)[:4000] if tail_lines else ""

    @staticmethod
    def _summarize_worker_error(stderr_text: str | None, stdout_text: str | None, default_message: str) -> str:
        """
        提取 Worker 失败摘要。
        :param stderr_text: 标准错误
        :param stdout_text: 标准输出
        :param default_message: 默认消息
        :return: 失败摘要
        """
        for raw_text in (stderr_text, stdout_text):
            if not raw_text:
                continue
            lines = [line.rstrip() for line in str(raw_text).splitlines() if line.strip()]
            if not lines:
                continue
            error_context = TicketAiAnalysisService._extract_stderr_context(str(raw_text))
            if error_context:
                return error_context
            tail_lines = [
                re.sub(r"\s+", " ", item.strip())
                for item in lines[-20:]
                if item.strip() not in {"{", "}", "[", "]"}
            ]
            if tail_lines:
                return " | ".join(tail_lines)[:4000]
        return default_message

    @staticmethod
    def _find_worker_error_line(text: str | None, markers: tuple[str, ...]) -> str:
        """
        从 Worker 输出中提取明确的系统错误行，不将工单正文中的普通 Error 文本当作异常。
        :param text: Worker 标准输出或标准错误
        :param markers: 允许识别的系统错误标记
        :return: 错误行，未找到时返回空字符串
        """
        if not text:
            return ""
        lowered_markers = tuple(marker.lower() for marker in markers)
        for line in reversed(str(text).splitlines()):
            normalized_line = re.sub(r"\s+", " ", line.strip())
            lowered_line = normalized_line.lower()
            if normalized_line and any(marker in lowered_line for marker in lowered_markers):
                return normalized_line[:4000]
        return ""

    @classmethod
    def _classify_worker_failure(
        cls,
        stderr_text: str | None,
        stdout_text: str | None,
        return_code: int | None,
    ) -> dict[str, Any]:
        """
        将 Worker 的明确系统错误转换为稳定错误码和错误信息。
        :param stderr_text: Worker 标准错误
        :param stdout_text: Worker 标准输出
        :param return_code: Worker 进程退出码
        :return: 错误码、错误信息、退出码和诊断信息
        """
        combined_text = "\n".join(item for item in (stderr_text, stdout_text) if item)
        diagnostics: list[dict[str, Any]] = []
        permission_line = cls._find_worker_error_line(
            combined_text,
            ("permissiondenied", "permission denied", "access is denied", "拒绝访问"),
        )
        if permission_line:
            diagnostics.append(
                {
                    "code": "AI_WORKER_PERMISSION_DENIED",
                    "severity": "warning",
                    "message": permission_line,
                }
            )

        # 配额错误优先级高于本地日志告警，避免 PermissionDenied 覆盖真正的终止原因。
        quota_line = cls._find_worker_error_line(
            combined_text,
            ("allocated quota exceeded", "quota exceeded", "token limit"),
        )
        if quota_line:
            return {
                "error_code": "AI_PROVIDER_QUOTA_EXCEEDED",
                "error_message": quota_line,
                "worker_exit_code": return_code,
                "diagnostics": diagnostics,
            }

        auth_line = cls._find_worker_error_line(
            combined_text,
            ("401 unauthorized", "unauthorized", "authentication failed", "invalid api key"),
        )
        if auth_line:
            return {
                "error_code": "AI_PROVIDER_AUTH_FAILED",
                "error_message": auth_line,
                "worker_exit_code": return_code,
                "diagnostics": diagnostics,
            }

        if permission_line:
            return {
                "error_code": "AI_WORKER_PERMISSION_DENIED",
                "error_message": permission_line,
                "worker_exit_code": return_code,
                "diagnostics": diagnostics,
            }

        provider_line = cls._find_worker_error_line(
            combined_text,
            (
                "bad_response_status_code",
                "invalid_request_error",
                "error sending request",
                "stream disconnected",
            ),
        )
        if provider_line:
            return {
                "error_code": "AI_PROVIDER_REQUEST_FAILED",
                "error_message": provider_line,
                "worker_exit_code": return_code,
                "diagnostics": diagnostics,
            }

        return {
            "error_code": "AI_WORKER_EXIT_NONZERO",
            "error_message": f"AI Worker 返回非零退出码: {return_code}",
            "worker_exit_code": return_code,
            "diagnostics": diagnostics,
        }

    @staticmethod
    def _normalize_worker_failure_message(message: str) -> str:
        """
        将 Codex/模型侧错误归一为面向业务的失败说明。
        :param message: 原始失败摘要
        :return: 归一化后的失败说明
        """
        normalized = str(message or "").strip() or "AI Worker 未返回可解析的 JSON 结果"
        lower_message = normalized.lower()
        if "concurrency limit exceeded" in lower_message:
            return f"Codex 账号并发限制，请稍后重试或更换可用账号/Provider：{normalized}"
        if "openai_error" in lower_message or "bad_response_status_code" in lower_message:
            return f"AI模型接口返回异常，请检查模型配置、请求上下文大小或上游服务状态：{normalized}"
        return normalized

    @staticmethod
    async def _check_task_canceled(event_sender: EventSender | None, task_id: int) -> bool:
        """
        取消检查点：查询 Agent 消息层的取消标记表。

        标记存在时发送状态事件、清理标记并返回 True；查询失败按未取消处理，
        保证取消机制异常不影响正常执行链路。
        :param event_sender: 事件发送器
        :param task_id: 任务ID
        :return: 是否已取消
        """
        try:
            from server.agent_server import WebSocketClient

            if not await WebSocketClient.is_task_canceled(task_id):
                return False
        except Exception as exc:
            logger.warning(f"查询任务取消标记失败，按未取消处理: task_id={task_id}, error={exc}")
            return False
        await TicketAiAnalysisService._emit_event(event_sender, "ai_analysis_status", task_id, "任务已被取消")
        try:
            from server.agent_server import WebSocketClient

            await WebSocketClient.clear_task_cancel_flag(task_id)
        except Exception:
            pass
        return True

    @staticmethod
    async def _emit_event(event_sender: EventSender | None, event_type: str, task_id: int, message: str, **extra: Any) -> None:
        """
        向服务端发送执行阶段事件。
        :param event_sender: 事件发送器
        :param event_type: 事件类型
        :param task_id: 任务ID
        :param message: 事件消息
        :param extra: 额外信息
        :return: 无
        """
        logger.info(f"AI分析Agent任务[{task_id}] {event_type}: {message} | {extra if extra else ''}".rstrip())
        if not event_sender:
            return
        payload = {"type": event_type, "task_id": task_id, "message": message, **extra}
        await event_sender(payload)

    @staticmethod
    def _build_prompt(
        workspace_path: str,
        mapping: dict[str, Any],
        ticket: dict[str, Any],
        *,
        repo_path: str | None = None,
        workspace_root: str | None = None,
        log_analysis_mode: str = "digest",
        source_logs_path: str | None = None,
    ) -> str:
        """
        构建分析提示词。
        :param workspace_path: 本地工作区路径
        :param mapping: 仓库映射
        :param ticket: 工单信息
        :param repo_path: 实际使用的本地仓库路径。
        :param workspace_root: 实际使用的工作区根目录。
        :param log_analysis_mode: 日志分析模式（digest/full_directory/hybrid）。
        :param source_logs_path: 实际读取的原始日志目录。
        :return: 提示词文本
        """
        resolved_repo_path = repo_path or mapping.get("resolvedLocalRepoPath") or mapping.get("resolved_local_repo_path")
        resolved_repo_path = resolved_repo_path or mapping.get("localRepoPath") or mapping.get("local_repo_path") or ""
        resolved_workspace_root = workspace_root or mapping.get("workspaceRoot") or mapping.get("workspace_root") or ""
        fallback_workspace_root = str(Path(workspace_path).parent.parent)
        resolved_source_logs_path = source_logs_path or str(Path(workspace_path) / "source_logs")
        return f"""你是工单自动分析 Worker，请基于当前工作区中的上下文进行根因分析。

当前任务目录:
{workspace_path}

仓库信息:
- 项目: {mapping.get("projectName") or mapping.get("project_name") or ""}
- 版本: {mapping.get("versionKey") or mapping.get("version_key") or ""}
- 仓库地址: {mapping.get("repoUrl") or mapping.get("repo_url") or ""}
- 分支: {mapping.get("branchName") or mapping.get("branch_name") or ""}
- 本地仓库路径: {mapping.get("localRepoPath") or mapping.get("local_repo_path") or ""}
- 实际分析代码目录: {resolved_repo_path}
- 工作区根目录: {resolved_workspace_root or fallback_workspace_root}
- 说明: Agent 启动 Worker 前会校验实际分析代码目录的当前分支必须等于上面的分支；如果映射未提供 localRepoPath，则会在工作区下创建固定 Git worktree 后再执行。

工单要求:
1. 只做分析，不修改代码、不提交代码。
2. 优先阅读 {workspace_path}/ticket.json、{workspace_path}/timeline.json、{workspace_path}/logs.txt。
3. **本次日志分析模式为 `{log_analysis_mode}`**（已写入 context.json 的 logAnalysisMode 字段）：
   - `digest`：优先阅读 {workspace_path}/logs_ai_digest.txt，证据不足时按摘要中的文件名和行号去
     {resolved_source_logs_path}/ 定点读取原始日志。
   - `full_directory`：不要依赖摘要，直接读取 {resolved_source_logs_path}/；先用 rg 搜索错误关键词、
     工单号、门店/POS、交易号和用户额外说明中的关键词，再打开命中文件上下文。
   - `hybrid`：摘要只作为定位索引。阅读摘要后，必须查看 {workspace_path}/source_logs_manifest.json
     或列出 {resolved_source_logs_path}/ 文件清单，并至少对 {resolved_source_logs_path}/ 执行一次
     rg 关键词检索；最终证据尽量引用原始日志文件路径和行号，不要只引用 logs_ai_digest.txt。
   **请严格按照上述模式执行，不要自行切换为其他模式。**
4. 如果 `sourceLogPull.agentShouldExtractWindow` 为 true，请按 `requestedBeginTime/requestedEndTime`
   在 {resolved_source_logs_path}/ 中筛选对应时间窗口；内存问题必须检索 MemoryError、OOM、
   OutOfMemory、out of memory、heap、GC overhead、内存不足等关键词。
4. 工单不是一次性分析，请结合 context.json 中的 messages、snapshots 和 similarTickets：
   - messages 是持续追问和协同排查上下文，必须优先参考最新用户追问。
   - snapshots 是历史 ACR 版本，新的结论需要说明相对上一版的变化。
   - similarTickets 是历史相似工单，若可复用经验，请写入 similar_cases、sop_suggestion、
     owner_suggestion、monitoring_suggestion。
5. 输出严格 JSON，不要输出多余说明文本。不要调用 shell、python 或 PowerShell
   去创建、写入、拼接任何结果文件；尤其不要使用 heredoc（如 `<<EOF`、`@'...'@`）
   写 JSON。直接把最终 JSON 作为最后一条回复输出，系统会自动保存结果文件。
   注意：JSON 字符串值内部的英文双引号必须写成 \\" 转义；描述中引用中文术语请使用
   中文引号（“”），不要直接输出未转义的英文双引号，否则结果无法通过解析校验。
6. 结果必须包含以下字段；如果某些扩展字段暂时无法确定，请用空字符串、空数组或 false 占位，不要省略：
   - ticket_id
   - project_id
   - version_key
   - repo_url
   - branch_name
   - root_cause
   - analysis_summary
   - related_files
   - related_functions
   - fix_suggestion
   - confidence
   - evidence
   - risk_items
   - next_steps
   - symptom
   - investigation_steps
   - prevention_actions
   - similar_cases
   - sop_suggestion
   - owner_suggestion
   - monitoring_suggestion
   - needs_human_review

工单基础信息:
- ticket_id: {ticket.get("ticketId") or ticket.get("ticket_id") or ""}
- ticket_no: {ticket.get("ticketNo") or ticket.get("ticket_no") or ""}
- title: {ticket.get("title") or ""}
- description: {ticket.get("description") or ""}
"""

    @classmethod
    def _resolve_ai_repo_runtime_settings(
        cls,
        mapping: dict[str, Any],
    ) -> tuple[Path, Path, str]:
        """
        解析 Agent 本地 AI 仓库运行目录。
        :param mapping: 仓库映射数据。
        :return: (工作区根目录, 实际仓库路径, 当前分支)
        """
        config = AgentConfig.read_config()
        workspace_root_text = str(
            getattr(config, "ticket_ai_workspace_root", "")
            or mapping.get("workspaceRoot")
            or mapping.get("workspace_root")
            or ""
        ).strip()
        if workspace_root_text:
            workspace_root = Path(workspace_root_text).expanduser()
            if not workspace_root.is_absolute():
                workspace_root = workspace_root.resolve()
        else:
            workspace_root = get_client_root_dir() / "storage" / "ticket_ai_analysis"

        workspace_root.mkdir(parents=True, exist_ok=True)
        branch_name = cls._normalize_branch_name(mapping.get("branchName") or mapping.get("branch_name"))
        repo_url = str(mapping.get("repoUrl") or mapping.get("repo_url") or "").strip()
        repo_path_text = str(mapping.get("localRepoPath") or mapping.get("local_repo_path") or "").strip()

        if repo_path_text:
            repo_path = Path(repo_path_text).expanduser()
            if not repo_path.is_absolute():
                repo_path = repo_path.resolve()
            try:
                current_branch = cls._ensure_repo_branch_matches(repo_path, branch_name)
                mapping["resolvedLocalRepoPath"] = str(repo_path)
                mapping["resolvedBranchName"] = current_branch
                return workspace_root, repo_path, current_branch
            except Exception as exc:
                if not branch_name:
                    raise
                logger.warning(
                    f"AI 分析映射本地仓库不可直接使用，改用本地仓库派生 worktree: "
                    f"local_repo_path={repo_path}, branch={branch_name}, reason={exc}"
                )
                repo_path = cls._ensure_local_worktree_repo(
                    workspace_root=workspace_root,
                    source_repo_path=repo_path,
                    branch_name=branch_name,
                )
                current_branch = cls._ensure_repo_branch_matches(repo_path, branch_name)
                mapping["resolvedLocalRepoPath"] = str(repo_path)
                mapping["resolvedBranchName"] = current_branch
                return workspace_root, repo_path, current_branch

        repo_path = cls._ensure_worktree_repo(
            workspace_root=workspace_root,
            repo_url=repo_url,
            branch_name=branch_name,
        )
        current_branch = cls._ensure_repo_branch_matches(repo_path, branch_name)
        mapping["localRepoPath"] = str(repo_path)
        mapping["resolvedLocalRepoPath"] = str(repo_path)
        mapping["resolvedBranchName"] = current_branch
        return workspace_root, repo_path, current_branch

    @classmethod
    async def handle_request(
        cls,
        req_data: dict[str, Any],
        event_sender: EventSender | None = None,
    ) -> dict[str, Any]:
        """
        处理工单 AI 分析请求。
        :param req_data: 服务端下发的请求体
        :param event_sender: 事件发送器
        :return: 处理结果
        """
        task_id = int(req_data.get("taskId") or req_data.get("task_id") or 0)
        ticket_id = int(req_data.get("ticketId") or req_data.get("ticket_id") or 0)
        ticket = req_data.get("ticket") or {}
        mapping = req_data.get("mapping") or {}
        context_payload = req_data.get("context") or {}
        timeline_payload = req_data.get("timeline") or {}
        prompt_template = str(req_data.get("promptTemplate") or req_data.get("prompt_template") or "").strip()
        schema_payload = req_data.get("resultSchema") or {}
        provider_env_overrides = req_data.get("providerEnv") or {}
        selected_worker_model = str(context_payload.get("selectedWorkerModel") or "").strip()
        request_provider_code = str(context_payload.get("selectedAiProviderCode") or "").strip()
        try:
            timeout_sec = int(req_data.get("timeoutSec") or req_data.get("timeout_sec") or cls.DEFAULT_TIMEOUT_SEC)
        except Exception:
            timeout_sec = cls.DEFAULT_TIMEOUT_SEC
        # 缓存命中时也要返回统一的 token_usage 字段，避免引用尚未进入 Worker 分支的局部变量。
        token_usage_payload: dict[str, Any] | None = None
        if not task_id or not ticket_id:
            return {
                "request_type": req_data.get("requestType"),
                "command": req_data.get("command"),
                "success": False,
                "status": "failed",
                "message": "taskId 或 ticketId 不能为空",
                "error_code": "AI_REQUEST_INVALID",
                "error_message": "taskId 或 ticketId 不能为空",
            }
        try:
            workspace_root, repo_path, current_branch = cls._resolve_ai_repo_runtime_settings(mapping)
            workspace_dir = workspace_root / f"ticket_{ticket_id}" / f"task_{task_id}"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            schema_file = workspace_dir / "result.schema.json"
            result_file = workspace_dir / "result.json"
            prompt_file = workspace_dir / "prompt.txt"
            ticket_file = workspace_dir / "ticket.json"
            timeline_file = workspace_dir / "timeline.json"
            context_file = workspace_dir / "context.json"
            logs_file = workspace_dir / "logs.txt"
            log_digest_file = workspace_dir / "logs_ai_digest.txt"
            source_logs_dir = workspace_dir / "source_logs"
            source_logs_zip = workspace_dir / "source_logs.zip"
            source_logs_manifest = workspace_dir / "source_logs_manifest.json"
            task_lock_file = workspace_dir / "analysis.lock"
            request_snapshot_file = workspace_dir / "request.snapshot.json"

            await cls._emit_event(
                event_sender,
                "ai_analysis_status",
                task_id,
                "准备本地工作区",
                workspace_root=str(workspace_root),
                workspace_path=str(workspace_dir),
                repo_path=str(repo_path),
                branch_name=current_branch,
            )
            try:
                request_snapshot_file.write_text(
                cls._dumps(
                        {
                            "taskId": task_id,
                            "ticketId": ticket_id,
                            "requestType": req_data.get("requestType"),
                            "command": req_data.get("command"),
                            "payloadSize": len(cls._dumps(req_data, indent=None)),
                            "providerCode": request_provider_code,
                            "workerModel": selected_worker_model,
                            "resolvedLocalRepoPath": str(repo_path),
                            "resolvedBranchName": current_branch,
                            "createdAt": datetime.now().isoformat(),
                        }
                    ),
                    encoding="utf-8",
                )
            except Exception as exc:
                logger.warning(f"写入 AI 分析请求快照失败: {exc}")
            cached_result = cls._load_cached_result(result_file, schema_payload)
            if cached_result:
                await cls._emit_event(
                    event_sender,
                    "ai_analysis_finished",
                    task_id,
                    "命中本地缓存结果，直接返回",
                    workspace_path=str(workspace_dir),
                )
                result_text = cls._dumps(cached_result)
                # 缓存命中也要尽力恢复 token：结果来自历史 Worker 执行，token 消耗真实存在。
                # 优先读取结果文件内嵌的 usage；否则按 Provider 从落盘的 stdout 事件流解析。
                cached_token_usage = cls._extract_token_usage_payload(cached_result)
                if cached_token_usage is None:
                    cached_stdout = ""
                    stdout_file = workspace_dir / "worker.stdout.txt"
                    if stdout_file.exists():
                        try:
                            cached_stdout = stdout_file.read_text(encoding="utf-8")
                        except Exception:
                            cached_stdout = ""
                    cached_token_usage = cls._parse_failure_token_usage(
                        provider_type=cls._resolve_provider_type(context_payload),
                        raw_stdout=cached_stdout,
                        raw_stderr=None,
                        result_file=result_file,
                    )
                if cached_token_usage is not None:
                    token_usage_payload = cached_token_usage
                    logger.info(f"缓存命中恢复 Token 用量: {token_usage_payload}")
                return {
                    "request_type": req_data.get("requestType"),
                    "command": req_data.get("command"),
                    "success": True,
                    "status": "success",
                    "message": "AI 分析已完成，直接返回缓存结果",
                    "token_usage": token_usage_payload,
                    "result": {
                        "analysis_result": cached_result,
                        "raw_output": result_text,
                        "workspace_path": str(workspace_dir),
                        "result_path": str(result_file),
                        "command_line": "cached:result.json",
                        "stdout_path": str(workspace_dir / "worker.stdout.txt"),
                        "stderr_path": str(workspace_dir / "worker.stderr.txt"),
                        "token_usage": token_usage_payload,
                    },
                }
            lock_payload = cls._read_json_file(task_lock_file)
            if task_lock_file.exists() and not cls._is_stale_lock(lock_payload, timeout_sec):
                failure_message = "当前任务正在分析中，请稍后重试"
                # 携带锁持有者任务ID：服务端可据此定位并接管/取消原任务，而不是只能盲等。
                lock_holder_task_id = (lock_payload or {}).get("taskId")
                await cls._emit_event(event_sender, "ai_analysis_status", task_id, failure_message)
                return {
                    "request_type": req_data.get("requestType"),
                    "command": req_data.get("command"),
                    "success": False,
                    "status": "running",
                    "message": failure_message,
                    "error_code": "AI_TASK_ALREADY_RUNNING",
                    "error_message": failure_message,
                    "running_task_id": int(lock_holder_task_id) if lock_holder_task_id else task_id,
                    "running_ticket_id": ticket_id,
                }
            cls._release_task_lock(task_lock_file)
            if not cls._acquire_task_lock(
                task_lock_file,
                {
                    "taskId": task_id,
                    "ticketId": ticket_id,
                    "status": "running",
                    "startedAt": datetime.now().isoformat(),
                    "lastHeartbeatAt": datetime.now().isoformat(),
                    "requestType": req_data.get("requestType"),
                    "command": req_data.get("command"),
                },
            ):
                failure_message = "当前任务正在分析中，请稍后重试"
                await cls._emit_event(event_sender, "ai_analysis_status", task_id, failure_message)
                return {
                    "request_type": req_data.get("requestType"),
                    "command": req_data.get("command"),
                    "success": False,
                    "status": "running",
                    "message": failure_message,
                    "error_code": "AI_TASK_ALREADY_RUNNING",
                    "error_message": failure_message,
                    "running_task_id": task_id,
                    "running_ticket_id": ticket_id,
                }
            # 锁心跳续租：Worker 执行期间周期刷新 lastHeartbeatAt，证明 Worker 存活；
            # 心跳停止（Worker 崩溃/被杀）后短窗口即可被安全接管，避免长任务锁假死。
            lock_heartbeat_task = asyncio.create_task(cls._run_lock_heartbeat(task_lock_file))
            try:
                ticket_file.write_text(cls._dumps(ticket), encoding="utf-8")
                timeline_file.write_text(cls._dumps(timeline_payload), encoding="utf-8")
                context_file.write_text(cls._dumps(context_payload), encoding="utf-8")
                source_log_pull = context_payload.get("sourceLogPull") or {}
                logs_text = str(source_log_pull.get("text") or "")
                command_result_url = str(source_log_pull.get("commandResultUrl") or "").strip()
                storage_path = str(source_log_pull.get("storagePath") or "").strip()
                try:
                    source_log_record_id = int(source_log_pull.get("recordId") or 0)
                except (TypeError, ValueError):
                    source_log_record_id = 0
                whole_archive_mode = bool(source_log_pull.get("wholeArchiveMode"))
                log_analysis_mode = str(
                    context_payload.get("logAnalysisMode")
                    or source_log_pull.get("analysisMode")
                    or "digest"
                ).strip().lower() or "digest"
                if log_analysis_mode not in {"digest", "full_directory", "hybrid"}:
                    log_analysis_mode = "digest"
                agent_should_extract_window = bool(source_log_pull.get("agentShouldExtractWindow"))
                requested_begin_time = cls._parse_context_datetime(
                    source_log_pull.get("requestedBeginTime") or context_payload.get("logRequestedBeginTime")
                )
                requested_end_time = cls._parse_context_datetime(
                    source_log_pull.get("requestedEndTime") or context_payload.get("logRequestedEndTime")
                )
                extracted_files: list[str] = []
                if logs_text:
                    logs_file.write_text(logs_text, encoding="utf-8")
                    archive_url = ""
                else:
                    archive_url = command_result_url or storage_path
                    if whole_archive_mode:
                        logs_file.write_text(
                            "\n".join(
                                [
                                    "日志内容未入库，已改为整包分析模式。",
                                    f"日志分析模式: {log_analysis_mode}",
                                    f"AI预筛选摘要: {log_digest_file if log_analysis_mode in {'digest', 'hybrid'} else '<disabled>'}",
                                    f"压缩包地址: {archive_url or '<none>'}",
                                    f"压缩包本地路径: {source_logs_zip}",
                                    f"解压目录: {source_logs_dir}",
                                    f"请求时间窗口: {requested_begin_time or '<none>'} ~ {requested_end_time or '<none>'}",
                                    "请按 context.json 中的 logAnalysisMode 决定读取摘要或完整目录。",
                                ]
                            ),
                            encoding="utf-8",
                        )
                    else:
                        logs_file.write_text(
                            "日志内容未入库，当前任务为时间范围模式或未配置整包分析。",
                            encoding="utf-8",
                        )
                    if whole_archive_mode:
                        local_archive = cls._resolve_existing_local_archive(storage_path)
                        source_key = ""
                        active_archive_path: Path | None = local_archive
                        cache_manifest_path: Path | None = None
                        cache_hit = False
                        if local_archive:
                            source_key = (
                                f"file:{local_archive.resolve()}:{local_archive.stat().st_size}:"
                                f"{local_archive.stat().st_mtime_ns}"
                            )
                        elif archive_url.lower().startswith(("http://", "https://")):
                            source_key = f"url:{archive_url}"

                        if source_key and source_log_record_id:
                            cache_archive_path, cache_extract_dir, cache_manifest_path = cls._resolve_log_cache_paths(
                                workspace_root,
                                ticket_id,
                                source_log_record_id,
                                source_key,
                            )
                            if not active_archive_path:
                                active_archive_path = cache_archive_path
                            cached_files = cls._load_log_archive_cache(
                                cache_manifest_path,
                                source_key,
                                active_archive_path,
                                cache_extract_dir,
                            )
                            if cached_files:
                                source_logs_zip = active_archive_path
                                source_logs_dir = cache_extract_dir
                                extracted_files = cached_files
                                cache_hit = True
                                await cls._emit_event(
                                    event_sender,
                                    "ai_analysis_status",
                                    task_id,
                                    "复用本地整包日志缓存",
                                    log_record_id=source_log_record_id,
                                    archive_path=str(source_logs_zip),
                                    extract_dir=str(source_logs_dir),
                                    extracted_file_count=len(extracted_files),
                                )

                        if not cache_hit and active_archive_path:
                            if local_archive:
                                source_logs_zip = local_archive
                                await cls._emit_event(
                                    event_sender,
                                    "ai_analysis_status",
                                    task_id,
                                    "使用本地归档并解压整包日志",
                                    log_record_id=source_log_record_id or None,
                                    archive_path=str(local_archive),
                                )
                            else:
                                source_logs_zip = active_archive_path
                                await cls._emit_event(
                                    event_sender,
                                    "ai_analysis_status",
                                    task_id,
                                    "下载并解压整包日志",
                                    archive_url=archive_url,
                                    archive_path=str(source_logs_zip),
                                    extract_dir=str(source_logs_dir),
                                )
                                active_archive_path = cls._download_archive(archive_url, source_logs_zip)
                            if active_archive_path:
                                if cache_manifest_path:
                                    source_logs_dir = cache_manifest_path.parent / "source_logs"
                                extracted_files = cls._extract_archive(active_archive_path, source_logs_dir)
                                if cache_manifest_path:
                                    cache_manifest_path.parent.mkdir(parents=True, exist_ok=True)
                                    cache_manifest_path.write_text(
                                        cls._dumps(
                                            {
                                                "sourceKey": source_key,
                                                "archivePath": str(active_archive_path),
                                                "extractDir": str(source_logs_dir),
                                                "extractedFiles": extracted_files,
                                                "cachedAt": datetime.now().isoformat(),
                                            }
                                        ),
                                        encoding="utf-8",
                                    )

                        digest_payload: dict[str, Any] = {}
                        window_payload: dict[str, Any] = {}
                        if extracted_files:
                            if agent_should_extract_window and (requested_begin_time or requested_end_time):
                                window_payload = cls._extract_window_logs(
                                    extract_dir=source_logs_dir,
                                    extracted_files=extracted_files,
                                    begin_time=requested_begin_time,
                                    end_time=requested_end_time,
                                )
                                window_text = str(window_payload.get("text") or "")
                                logs_file.write_text(
                                    window_text
                                    or "\n".join(
                                        [
                                            "Agent 已按请求时间窗口截取日志，但未命中日志条目。",
                                            f"解压目录: {source_logs_dir}",
                                            f"请求时间窗口: {requested_begin_time or '<none>'} ~ {requested_end_time or '<none>'}",
                                        ]
                                    ),
                                    encoding="utf-8",
                                )
                            if log_analysis_mode in {"digest", "hybrid"}:
                                digest_payload = cls._build_log_digest(
                                    extract_dir=source_logs_dir,
                                    extracted_files=extracted_files,
                                    ticket=ticket,
                                    context_payload=context_payload,
                                    digest_path=log_digest_file,
                                )
                        source_logs_manifest.write_text(
                            cls._dumps(
                                {
                                    "archiveUrl": archive_url or "",
                                    "archivePath": str(source_logs_zip),
                                    "extractDir": str(source_logs_dir),
                                    "extractedFiles": extracted_files,
                                    "cacheHit": cache_hit,
                                    "logAnalysisMode": log_analysis_mode,
                                    "aiDigest": digest_payload,
                                    "windowExtract": window_payload,
                                }
                            ),
                            encoding="utf-8",
                        )
                schema_file.write_text(cls._dumps(schema_payload), encoding="utf-8")

                mapping["resolvedLocalRepoPath"] = str(repo_path)
                mapping["resolvedBranchName"] = current_branch
                resolved_prompt = (
                    prompt_template.replace("{workspace_path}", str(workspace_dir))
                    .replace("{source_logs_path}", str(source_logs_dir))
                )
                if not resolved_prompt:
                    resolved_prompt = cls._build_prompt(
                        str(workspace_dir),
                        mapping,
                        ticket,
                        repo_path=str(repo_path),
                        workspace_root=str(workspace_root),
                        log_analysis_mode=log_analysis_mode,
                        source_logs_path=str(source_logs_dir),
                    )
                prompt_file.write_text(resolved_prompt, encoding="utf-8")

                # --- 按 Provider 类型构建命令和准备环境 ---
                provider_type = cls._resolve_provider_type(context_payload)
                worker_config = cls._get_provider_worker_config(provider_type)

                # Resume 支持：同工单同 Provider 时复制上次会话数据
                resume_flags: list[str] = []
                resume_from_workspace = str(req_data.get("resumeFromWorkspacePath") or "").strip()
                resume_requested = bool(req_data.get("resume"))
                if resume_requested and resume_from_workspace:
                    _, resume_flags = cls._copy_session_for_resume(
                        workspace_dir, provider_type, resume_from_workspace
                    )

                command = cls._build_worker_command(
                    provider_type=provider_type,
                    worker_config=worker_config,
                    repo_path=repo_path,
                    workspace_dir=workspace_dir,
                    schema_file=schema_file,
                    result_file=result_file,
                    selected_worker_model=selected_worker_model,
                )
                if resume_flags:
                    command.extend(resume_flags)

                ai_home = cls._prepare_ai_home(workspace_dir, provider_type, provider_env_overrides)
                env_values = cls._load_worker_env(ai_home, provider_type)
                env_values = cls._apply_env_overrides(env_values, provider_env_overrides)

                await cls._emit_event(
                    event_sender,
                    "ai_analysis_step",
                    task_id,
                    "开始执行 Worker",
                    command_line=" ".join(command),
                    provider_type=provider_type,
                    repo_path=str(repo_path),
                    branch_name=current_branch,
                    workspace_root=str(workspace_root),
                    workspace_path=str(workspace_dir),
                    provider_code=request_provider_code or "<none>",
                    worker_model=selected_worker_model or "<default>",
                )
                # 执行前取消检查点：服务端已取消的任务直接放弃执行，避免白耗模型调用。
                if await cls._check_task_canceled(event_sender, task_id):
                    return {
                        "request_type": req_data.get("requestType"),
                        "command": req_data.get("command"),
                        "success": False,
                        "status": "canceled",
                        "message": "任务已被取消，未执行分析",
                        "error_code": "AI_TASK_CANCELED",
                        "error_message": "任务已被取消，未执行分析",
                    }
                worker_started_at = time.monotonic()
                process = await cls._run_worker_process(command, resolved_prompt, workspace_dir, env_values, timeout_sec)
                worker_elapsed = round(time.monotonic() - worker_started_at, 3)
                raw_stdout = process.stdout or ""
                raw_stderr = process.stderr or ""
                cls._persist_worker_streams(workspace_dir, raw_stdout, raw_stderr)
                # 执行后取消检查点：Worker 执行期间收到取消通知时，结果不回传
                # （服务端已置取消态，迟到回传会被丢弃），尽力提取已消耗 token 供审计。
                if await cls._check_task_canceled(event_sender, task_id):
                    canceled_token_usage = cls._parse_failure_token_usage(
                        provider_type=provider_type,
                        raw_stdout=raw_stdout,
                        raw_stderr=raw_stderr,
                        result_file=result_file,
                    )
                    logger.info(
                        f"AI分析Agent任务[{task_id}] 执行期间被取消，丢弃结果并保留已消耗token: "
                        f"token_usage={canceled_token_usage}"
                    )
                    return {
                        "request_type": req_data.get("requestType"),
                        "command": req_data.get("command"),
                        "success": False,
                        "status": "canceled",
                        "message": "任务在执行期间被取消，结果已放弃",
                        "error_code": "AI_TASK_CANCELED",
                        "error_message": "任务在执行期间被取消，结果已放弃",
                        "token_usage": canceled_token_usage,
                    }
                worker_auth_diagnostic, worker_api_key = cls._build_worker_auth_diagnostic(
                    provider_type=provider_type,
                    provider_code=request_provider_code,
                    worker_model=selected_worker_model,
                    ai_home=ai_home,
                    env_values=env_values,
                )
                worker_failure_payload = (
                    cls._classify_worker_failure(raw_stderr, raw_stdout, process.returncode)
                    if process.returncode != 0
                    else None
                )
                await cls._emit_event(
                    event_sender,
                    "ai_analysis_step",
                    task_id,
                    "Worker 执行结束",
                    return_code=process.returncode,
                    elapsed_sec=worker_elapsed,
                    stdout_len=len(raw_stdout),
                    stderr_len=len(raw_stderr),
                    stderr_context=(worker_failure_payload or {}).get("error_message", ""),
                )

                parsed_result = cls._parse_worker_output(
                    provider_type=provider_type,
                    worker_config=worker_config,
                    result_file=result_file,
                    raw_stdout=raw_stdout,
                    raw_stderr=raw_stderr,
                    schema_payload=schema_payload,
                )

                if process.returncode != 0:
                    failure_payload = worker_failure_payload or cls._classify_worker_failure(
                        raw_stderr, raw_stdout, process.returncode
                    )
                    failure_message = str(failure_payload["error_message"])
                    # 失败也要尽力提取已消耗 token：模型调用可能已发生，消耗真实存在。
                    failure_token_usage = cls._parse_failure_token_usage(
                        provider_type=provider_type,
                        raw_stdout=raw_stdout,
                        raw_stderr=raw_stderr,
                        result_file=result_file,
                    )
                    await cls._emit_event(
                        event_sender,
                        "ai_analysis_error",
                        task_id,
                        failure_message,
                        error_code=failure_payload["error_code"],
                        worker_exit_code=failure_payload["worker_exit_code"],
                        diagnostics=failure_payload["diagnostics"],
                    )
                    return {
                        "request_type": req_data.get("requestType"),
                        "command": req_data.get("command"),
                        "success": False,
                        "status": "failed",
                        "message": failure_message,
                        "error_code": failure_payload["error_code"],
                        "error_message": failure_message,
                        "worker_exit_code": failure_payload["worker_exit_code"],
                        "diagnostics": failure_payload["diagnostics"],
                        "token_usage": failure_token_usage,
                    }

                if parsed_result is None:
                    # Worker 正常退出但结果不可用时，尽量给出具体违规原因：
                    # 优先按 schema 校验收集违规字段；连 JSON 都解析不出时报告原始文本特征。
                    result_text = cls._resolve_worker_result_text(
                        provider_type=provider_type,
                        worker_config=worker_config,
                        result_file=result_file,
                        raw_stdout=raw_stdout,
                        raw_stderr=raw_stderr,
                    )
                    failure_diagnostics: list[dict[str, Any]] = []
                    invalid_result_message = "AI Worker 已正常退出，但结果无法解析或未通过 JSON Schema 校验"
                    if result_text.strip() and schema_payload:
                        candidate_payload: Any = None
                        try:
                            candidate_payload = json.loads(result_text)
                        except Exception:
                            candidate_payload = cls._extract_json_from_text(result_text)
                        if isinstance(candidate_payload, dict):
                            schema_violations = cls._collect_json_schema_violations(candidate_payload, schema_payload)
                            if schema_violations:
                                violation_summary = "; ".join(schema_violations[:10])
                                invalid_result_message = (
                                    f"AI Worker 结果未通过 JSON Schema 校验: {violation_summary}"
                                )
                                failure_diagnostics.append(
                                    {
                                        "code": "AI_WORKER_SCHEMA_VIOLATION",
                                        "severity": "error",
                                        "message": violation_summary,
                                    }
                                )
                    if not failure_diagnostics and result_text.strip():
                        # JSON 解析失败或非对象结构：给出原始文本头部，便于判断是否为模型自由文本。
                        text_preview = re.sub(r"\s+", " ", result_text.strip())[:200]
                        failure_diagnostics.append(
                            {
                                "code": "AI_WORKER_RESULT_UNPARSEABLE",
                                "severity": "error",
                                "message": text_preview,
                            }
                        )
                    failure_payload = {
                        "error_code": "AI_WORKER_RESULT_INVALID",
                        "error_message": invalid_result_message,
                        "worker_exit_code": process.returncode,
                        "diagnostics": failure_diagnostics,
                    }
                    if (
                        provider_type == "codex"
                        and process.returncode != 0
                        and cls._is_unauthorized_worker_failure(raw_stdout, raw_stderr)
                    ):
                        auth_probe = await cls._probe_codex_authentication(
                            str(worker_auth_diagnostic.get("base_url") or ""),
                            worker_api_key,
                        )
                        worker_auth_diagnostic.update(auth_probe)
                        logger.warning(
                            f"AI分析Agent任务[{task_id}] Worker 鉴权失败诊断: {worker_auth_diagnostic}"
                        )
                        await cls._emit_event(
                            event_sender,
                            "ai_analysis_step",
                            task_id,
                            "Worker 401 后鉴权探测完成",
                            auth_diagnostic=worker_auth_diagnostic,
                        )
                    else:
                        logger.warning(
                            f"AI分析Agent任务[{task_id}] Worker 执行失败诊断: {worker_auth_diagnostic}"
                        )
                    await cls._emit_event(
                        event_sender,
                        "ai_analysis_error",
                        task_id,
                        failure_payload["error_message"],
                        error_code=failure_payload["error_code"],
                        worker_exit_code=failure_payload["worker_exit_code"],
                        diagnostics=failure_payload["diagnostics"],
                        auth_diagnostic=worker_auth_diagnostic,
                    )
                    # 结果无效同样可能已产生模型消耗（如结果不符合 schema），尽力提取 token。
                    invalid_result_token_usage = cls._parse_failure_token_usage(
                        provider_type=provider_type,
                        raw_stdout=raw_stdout,
                        raw_stderr=raw_stderr,
                        result_file=result_file,
                    )
                    return {
                        "request_type": req_data.get("requestType"),
                        "command": req_data.get("command"),
                        "success": False,
                        "status": "failed",
                        "message": failure_payload["error_message"],
                        "error_code": failure_payload["error_code"],
                        "error_message": failure_payload["error_message"],
                        "worker_exit_code": failure_payload["worker_exit_code"],
                        "diagnostics": failure_payload["diagnostics"],
                        "token_usage": invalid_result_token_usage,
                    }

                normalized_result = parsed_result
                # Token 用量解析：Codex 从 --json 事件流累加；Claude 从单行 JSON 的
                # modelUsage 按模型累加；都没有时回退通用候选提取（结果文件内嵌 usage 等）。
                if provider_type == "codex":
                    token_usage_payload = cls._parse_codex_jsonl_token_usage(raw_stdout)
                elif provider_type == "claude":
                    token_usage_payload = cls._parse_claude_token_usage(raw_stdout)
                else:
                    token_usage_payload = None
                if token_usage_payload is None:
                    token_usage_payload = cls._extract_token_usage_payload(
                        normalized_result,
                        parsed_result,
                        cls._extract_json_from_text(raw_stdout) if raw_stdout.strip() else None,
                        cls._extract_json_from_text(raw_stderr) if raw_stderr.strip() else None,
                    )
                await cls._emit_event(
                    event_sender,
                    "ai_analysis_finished",
                    task_id,
                    "Worker 已完成分析",
                    workspace_path=str(workspace_dir),
                )
                return {
                    "request_type": req_data.get("requestType"),
                    "command": req_data.get("command"),
                    "success": True,
                    "status": "success",
                    "message": "AI 分析完成",
                    "token_usage": token_usage_payload,
                    "result": {
                        "analysis_result": normalized_result,
                        "raw_output": raw_stdout or raw_stderr,
                        "workspace_path": str(workspace_dir),
                        "result_path": str(result_file),
                        "command_line": " ".join(command),
                        "stdout_path": str(workspace_dir / "worker.stdout.txt"),
                        "stderr_path": str(workspace_dir / "worker.stderr.txt"),
                        "token_usage": token_usage_payload,
                    },
                }
            finally:
                # 先停心跳再释放锁：锁文件删除后心跳刷新会自动跳过（文件不存在）。
                lock_heartbeat_task.cancel()
                try:
                    await lock_heartbeat_task
                except asyncio.CancelledError:
                    pass
                cls._release_task_lock(task_lock_file)
                # 任务已结束，清理取消标记避免标记表残留（迟到取消无意义）。
                try:
                    from server.agent_server import WebSocketClient

                    await WebSocketClient.clear_task_cancel_flag(task_id)
                except Exception:
                    pass
        except subprocess.TimeoutExpired as exc:
            failure_message = f"AI Worker 执行超时：{exc}"
            # 超时分支拿不到进程内 stdout，从工作区已落盘的流文件尽力提取已消耗 token。
            timeout_token_usage = cls._recover_token_usage_from_workspace(
                workspace_dir,
                provider_type=cls._resolve_provider_type(context_payload),
            )
            await cls._emit_event(
                event_sender,
                "ai_analysis_error",
                task_id,
                failure_message,
                error_code="AI_WORKER_TIMEOUT",
            )
            return {
                "request_type": req_data.get("requestType"),
                "command": req_data.get("command"),
                "success": False,
                "status": "timeout",
                "message": failure_message,
                "error_code": "AI_WORKER_TIMEOUT",
                "error_message": failure_message,
                "token_usage": timeout_token_usage,
            }
        except Exception as exc:
            logger.exception(f"AI分析Agent任务[{task_id}] 执行失败: {exc}")
            failure_message = str(exc)
            # 异常分支同样尽力从工作区落盘文件恢复已消耗 token（可能为空目录则返回 None）。
            exception_token_usage = cls._recover_token_usage_from_workspace(
                workspace_dir if "workspace_dir" in locals() else None,
                provider_type=cls._resolve_provider_type(context_payload),
            )
            await cls._emit_event(
                event_sender,
                "ai_analysis_error",
                task_id,
                failure_message,
                error_code="AI_WORKER_EXECUTION_ERROR",
                error=str(exc),
            )
            return {
                "request_type": req_data.get("requestType"),
                "command": req_data.get("command"),
                "success": False,
                "status": "failed",
                "message": failure_message,
                "error_code": "AI_WORKER_EXECUTION_ERROR",
                "error_message": failure_message,
                "token_usage": exception_token_usage,
            }
