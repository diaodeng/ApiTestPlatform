from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
from dotenv import dotenv_values
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import SessionLocal
from config.env import AppConfig
from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.dao.ai_provider_model_dao import AiProviderModelDao
from module_admin.dao.ai_task_execution_dao import AiTaskExecutionDao
from module_admin.entity.do.config_do import SysConfig
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
from module_admin.service.ai_provider_capability_service import AiProviderCapabilityService
from module_hrm.dao.agent_dao import AgentDao
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import AgentResponseEnum, QtrDataStatusEnum, TstepTypeEnum
from module_qtr.service.agent_dispatch_service import AgentDispatchService
from module_qtr.service.agent_service import HandleResponse
from module_qtr.util.agent_dispatch_config import AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_CONFIG_KEY
from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.dao.ticket_version_dao import TicketVersionDao
from modules.ticket.entity.do.ticket_do import (
    Ticket,
    TicketAiAnalysisTask,
    TicketAiRepoMapping,
    TicketEvent,
    TicketMessage,
    TicketRca,
    TicketSnapshot,
    TicketVersion,
)
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullRecord
from modules.ticket.entity.model.ticket_version_model import TicketAiRepoMappingListItem
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullContentQueryModel
from modules.ticket.entity.vo.ticket_vo import (
    TicketAiAnalysisRequestModel,
    TicketAiAnalysisTaskQueryModel,
    TicketAiRepoMappingCreateModel,
    TicketAiRepoMappingQueryModel,
    TicketAiRepoMappingResponseModel,
    TicketAiRepoMappingUpdateModel,
)
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus, TicketEventType
from modules.ticket.service.ai.ticket_ai_observability_service import TicketAiObservabilityService
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ai.ticket_prompt_service import TicketPromptService
from modules.ticket.service.ai.ticket_similarity_case_service import TicketSimilarityCaseService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.notification.ticket_notify_service import TicketNotifyService
from modules.ticket.util.ticket_ai_result_schema_util import TicketAiResultSchemaUtil
from utils.api_key_util import ApiKeyUtil
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.metrics.task_memory import get_task_memory_observer
from utils.page_util import PageResponseModel
from utils.snowflake import snowIdWorker


class TicketAiAnalysisService:
    """
    工单 AI 分析服务层，负责仓库映射、分析任务编排和 Codex 执行结果回写。
    """

    CONFIG_WORKER_COMMAND = "ticket.ai.worker.command"
    CONFIG_WORKER_MODEL = "ticket.ai.worker.model"
    CONFIG_WORKER_SANDBOX = "ticket.ai.worker.sandbox"
    CONFIG_WORKER_TIMEOUT = "ticket.ai.worker.timeoutSec"
    CONFIG_WORKSPACE_ROOT = "ticket.ai.workspace.root"
    CONFIG_AGENT_CODE = "ticket.ai.agent.code"
    CONFIG_AGENT_MAX_CONCURRENT_TASKS = AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_CONFIG_KEY
    CONFIG_LOG_ANALYSIS_MODE = "ticket.ai.logAnalysis.mode"
    CONFIG_LOG_WINDOW_MISSING_STRATEGY = "ticket.ai.logAnalysis.windowMissingStrategy"
    DEFAULT_WORKER_COMMAND = "codex exec"
    DEFAULT_WORKER_MODEL = ""
    DEFAULT_WORKER_SANDBOX = "workspace-write"
    DEFAULT_WORKER_TIMEOUT = 3600
    DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[4] / "logs" / "ticket_ai_analysis"
    DEFAULT_AGENT_CODE = ""
    DEFAULT_AGENT_MAX_CONCURRENT_TASKS = 1
    DEFAULT_LOG_ANALYSIS_MODE = "digest"
    DEFAULT_LOG_WINDOW_MISSING_STRATEGY = "agent_extract"
    LOG_ANALYSIS_MODES = {"digest", "full_directory", "hybrid"}
    LOG_WINDOW_MISSING_STRATEGIES = {"server_extract", "agent_extract"}
    DEFAULT_CONTEXT_LOG_MAX_CHARS = 800_000
    SNAPSHOT_OWNER_MAX_LENGTH = 100
    # 连接中断恢复期限的额外缓冲（秒）：恢复截止时间 = 任务超时 + 本缓冲，
    # 覆盖 Agent 断连重连与 Worker 收尾回传所需的最长时间
    PENDING_RECOVERY_EXTRA_SECONDS = 15 * 60
    ACTIVE_STATUSES = {
        TicketAiAnalysisStatus.CREATED.value,
        TicketAiAnalysisStatus.RUNNING.value,
    }
    _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ticket-ai-analysis")
    _executor_lock = threading.Lock()
    _active_task_ids: set[int] = set()

    @staticmethod
    def _user_id(current_user: CurrentUserModel) -> int | None:
        """
        获取当前登录用户ID。
        :param current_user: 当前登录用户
        :return: 用户ID
        """
        return current_user.user.user_id if current_user and current_user.user else None

    @staticmethod
    def _user_name(current_user: CurrentUserModel) -> str:
        """
        获取当前登录用户名。
        :param current_user: 当前登录用户
        :return: 用户名
        """
        if not current_user or not current_user.user:
            return "system"
        return current_user.user.user_name or current_user.user.nick_name or "system"

    @staticmethod
    def _submission_user_placeholder(task: TicketAiAnalysisTask | None) -> CurrentUserModel | None:
        """
        根据任务上的提交人信息构造写回用的用户占位模型。

        任务执行线程中没有登录态，成功写回（AI 消息、RCA、快照）的创建者
        应归属任务提交人而不是 system。这里用提交人ID/名称构造一个最小占位，
        仅使用 _user_id/_user_name 读取的两个字段。
        :param task: AI 分析任务
        :return: 提交人占位模型，任务缺失提交人时返回 None
        """
        if not task or not getattr(task, "submitted_by_id", None):
            return None
        return CurrentUserModel(
            permissions=[],
            roles=[],
            user=SimpleNamespace(user_id=task.submitted_by_id, user_name=task.submitted_by_name, nick_name=None),
        )

    @classmethod
    def _record_reuse_event(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        reused_task: TicketAiAnalysisTask,
        request_fingerprint: str,
        current_user: CurrentUserModel,
    ) -> None:
        """
        记录一次"复用历史成功结果"事件（轻量审计）。

        复用不发起模型调用，不产生 token 消耗，因此独立记一条 status=reused、
        usage_state=not_called 的事件，与真实调用的审计区分开，避免：
        1) 页面把复用误认为一次新的模型调用；
        2) Token 统计把复用事件重复累计。
        写失败只告警不影响幂等返回。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param reused_task: 被复用的历史成功任务
        :param request_fingerprint: 本次请求指纹
        :param current_user: 当前登录用户
        :return: 无
        """
        try:
            AiTaskExecutionDao.add_ai_task_execution_dao(
                db,
                cls._build_execution_payload(
                    task_type="ticket_ai_analysis",
                    task_name="工单AI分析",
                    source_type="ticket",
                    source_id=ticket.ticket_id,
                    source_ref=ticket.ticket_no or str(ticket.ticket_id),
                    request_payload={
                        "task_id": reused_task.task_id,
                        "ticket_id": ticket.ticket_id,
                        "request_fingerprint": request_fingerprint,
                        "reused_from_task_id": reused_task.task_id,
                        "reused_from_audit_execution_id": getattr(reused_task, "audit_execution_id", None),
                        "usage_state": "not_called",
                    },
                    status="reused",
                    created_by_id=cls._user_id(current_user),
                    created_by_name=cls._user_name(current_user),
                ),
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"记录复用事件审计失败（不影响结果返回）: task_id={reused_task.task_id}, error={exc}")

    @classmethod
    def _resolve_task_attempt_no(cls, task: TicketAiAnalysisTask) -> int:
        """
        解析任务当前已有的调用尝试序号（按审计链回溯），新重试将使用序号+1。
        首次创建的任务没有 attempt_of_task_id 记录，序号视为 1。
        :param task: AI 分析任务
        :return: 当前尝试次数
        """
        audit_execution_id = getattr(task, "audit_execution_id", None)
        if not audit_execution_id:
            return 1
        try:
            with SessionLocal() as audit_db:
                execution = AiTaskExecutionDao.get_ai_task_execution_by_id(audit_db, int(audit_execution_id))
                payload = getattr(execution, "request_payload", None) if execution else None
                if isinstance(payload, str):
                    payload = cls._loads(payload, {})
                if isinstance(payload, dict) and payload.get("attempt_of_task_id"):
                    return int(payload.get("attempt_no") or 1)
        except Exception as exc:
            logger.warning(f"解析任务尝试序号失败，按首次重试处理: task_id={task.task_id}, error={exc}")
        return 1

    @classmethod
    def _resolve_task_provider_code(cls, task: TicketAiAnalysisTask) -> str | None:
        """从任务上下文快照解析 Provider 编码，供重试审计记录沿用原配置。"""
        context = task.analysis_context if isinstance(task.analysis_context, dict) else {}
        return str(context.get("selectedAiProviderCode") or "").strip() or None

    @classmethod
    def _resolve_task_model_name(cls, task: TicketAiAnalysisTask) -> str | None:
        """从任务上下文快照解析模型名，供重试审计记录沿用原配置。"""
        context = task.analysis_context if isinstance(task.analysis_context, dict) else {}
        return str(context.get("selectedWorkerModel") or "").strip() or None

    @staticmethod
    def _log_task_step(task_id: int, stage: str, message: str, **extra: Any) -> None:
        """
        记录 AI 分析任务阶段日志。
        :param task_id: 任务ID
        :param stage: 当前阶段
        :param message: 阶段说明
        :param extra: 额外上下文信息
        :return: 无
        """
        context = ", ".join(f"{key}={value}" for key, value in extra.items() if value not in (None, "", [], {}))
        if context:
            logger.info(f"AI分析任务[{task_id}] {stage}: {message} | {context}")
        else:
            logger.info(f"AI分析任务[{task_id}] {stage}: {message}")

    @staticmethod
    def _truncate_snapshot_owner(value: Any) -> str:
        """
        将 AI 建议负责人转换为快照字段可保存的长度。
        :param value: AI 返回的负责人建议文本
        :return: 最多 100 个字符的负责人建议；完整内容仍保留在结构化分析结果中
        """
        owner_text = str(value or "")
        if len(owner_text) <= TicketAiAnalysisService.SNAPSHOT_OWNER_MAX_LENGTH:
            return owner_text
        truncated = owner_text[: TicketAiAnalysisService.SNAPSHOT_OWNER_MAX_LENGTH - 3] + "..."
        logger.warning(
            f"AI分析结果建议负责人字段超长，已截断写入快照 | "
            f"original_length={len(owner_text)}, max_length={TicketAiAnalysisService.SNAPSHOT_OWNER_MAX_LENGTH}"
        )
        return truncated

    @staticmethod
    def _json_safe_value(value: Any) -> Any:
        """
        将值递归转换为可 JSON 序列化内容。
        :param value: 原始值
        :return: 可序列化内容
        """
        if isinstance(value, (datetime,)):
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
        将对象序列化为 JSON 字符串。
        :param value: 原始值
        :param indent: 缩进数
        :return: JSON 字符串
        """
        return json.dumps(cls._json_safe_value(value), ensure_ascii=False, indent=indent)

    @classmethod
    def _loads(cls, raw_value: Any, default: Any):
        """
        安全解析 JSON 数据。
        :param raw_value: 原始值
        :param default: 默认值
        :return: 解析结果
        """
        if raw_value in (None, ""):
            return default
        if isinstance(raw_value, (dict, list)):
            return raw_value
        try:
            return json.loads(str(raw_value))
        except Exception:
            return default

    @classmethod
    def _get_config_text(cls, db: Session, config_key: str, default: str) -> str:
        """
        获取系统参数文本值。
        :param db: 数据库会话
        :param config_key: 参数键名
        :param default: 默认值
        :return: 参数值
        """
        config_row = db.query(SysConfig).filter(SysConfig.config_key == config_key).first()
        if not config_row or config_row.config_value in (None, ""):
            return default
        return str(config_row.config_value).strip()

    @classmethod
    def _get_config_int(cls, db: Session, config_key: str, default: int) -> int:
        """
        获取系统参数整数值。
        :param db: 数据库会话
        :param config_key: 参数键名
        :param default: 默认值
        :return: 整数值
        """
        raw_value = cls._get_config_text(db, config_key, "")
        if not raw_value:
            return default
        try:
            return int(raw_value)
        except Exception:
            return default

    @classmethod
    def _resolve_workspace_root(cls, db: Session) -> Path:
        """
        解析 AI 分析工作区根目录。
        :param db: 数据库会话
        :return: 工作区根目录
        """
        raw_root = cls._get_config_text(db, cls.CONFIG_WORKSPACE_ROOT, str(cls.DEFAULT_WORKSPACE_ROOT))
        root = Path(raw_root).expanduser()
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[4] / root
        return root.resolve()

    @classmethod
    def _resolve_worker_settings(cls, db: Session) -> dict[str, Any]:
        """
        解析 AI Worker 执行配置。
        :param db: 数据库会话
        :return: 配置字典
        """
        return {
            "command": cls._get_config_text(db, cls.CONFIG_WORKER_COMMAND, cls.DEFAULT_WORKER_COMMAND),
            "model": cls._get_config_text(db, cls.CONFIG_WORKER_MODEL, cls.DEFAULT_WORKER_MODEL),
            "sandbox": cls._get_config_text(db, cls.CONFIG_WORKER_SANDBOX, cls.DEFAULT_WORKER_SANDBOX),
            "timeout_sec": cls._get_config_int(db, cls.CONFIG_WORKER_TIMEOUT, cls.DEFAULT_WORKER_TIMEOUT),
            "workspace_root": str(cls._resolve_workspace_root(db)),
        }

    @classmethod
    def _resolve_worker_command_parts(cls, command_parts: list[str]) -> list[str]:
        """
        解析 Worker 命令为可直接执行的进程参数。
        :param command_parts: 原始命令参数
        :return: 可执行的命令参数
        """
        parts = [str(part).strip() for part in command_parts if str(part).strip()]
        if not parts:
            parts = ["codex", "exec"]

        executable = parts[0]
        if Path(executable).suffix:
            return parts

        resolved_executable = shutil.which(executable)
        if not resolved_executable and Path(r"C:\nvm4w\nodejs\codex.cmd").exists():
            resolved_executable = str(Path(r"C:\nvm4w\nodejs\codex.cmd"))
        if not resolved_executable and Path(r"C:\nvm4w\nodejs\codex.exe").exists():
            resolved_executable = str(Path(r"C:\nvm4w\nodejs\codex.exe"))
        if not resolved_executable and Path(r"C:\nvm4w\nodejs\codex").exists():
            resolved_executable = str(Path(r"C:\nvm4w\nodejs\codex"))

        if not resolved_executable:
            raise FileNotFoundError(
                "未找到可执行的 codex Worker，请检查 codex 是否已安装并加入 PATH，或在系统参数中配置完整命令"
            )

        if resolved_executable.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", resolved_executable, *parts[1:]]
        return [resolved_executable, *parts[1:]]

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
        codex_home.mkdir(parents=True, exist_ok=True)
        overrides = provider_env_overrides or {}
        has_provider_keys = bool(overrides.get("OPENAI_BASE_URL") or overrides.get("OPENAI_API_KEY"))
        for file_name in ("config.toml", "config.self.toml", "auth.json", "version.json"):
            source_file = source_home / file_name
            target_file = codex_home / file_name
            if source_file.exists() and not target_file.exists():
                shutil.copy2(source_file, target_file)
        source_env = source_home / ".env"
        target_env = codex_home / ".env"
        if source_env.exists() and not target_env.exists():
            shutil.copy2(source_env, target_env)
        if has_provider_keys:
            cls._patch_codex_config_for_provider(codex_home, overrides)
        return codex_home

    @staticmethod
    def _patch_codex_config_for_provider(codex_home: Path, overrides: dict[str, str]) -> None:
        """
        修改副本 config.toml 和 .env，使 Provider 下发的 base_url 和 api_key 生效。
        Codex CLI 读 config.toml 中 model_providers 的 base_url 优先级高于 OPENAI_BASE_URL 环境变量，
        读 auth.json 中的 OPENAI_API_KEY 优先级也高于环境变量，因此需要直接修改副本文件。
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
                    new_config = re.sub(
                        r'^(base_url\s*=\s*)"[^"]*"',
                        rf'\1"{base_url}"',
                        config_text,
                        flags=re.MULTILINE,
                    )
                    if new_config != config_text:
                        config_file.write_text(new_config, encoding="utf-8")
                        logger.info(f"已修改 Codex config.toml base_url: {base_url}")
                except Exception as exc:
                    logger.warning(f"修改 Codex config.toml 失败: {exc}")
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
        # 修改 auth.json 中的 OPENAI_API_KEY，Codex CLI 的 requires_openai_auth 从 auth.json 读取认证
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

    @classmethod
    def _describe_worker_env(cls, codex_home: Path) -> dict[str, bool]:
        """
        仅描述 Worker 关键环境变量是否存在。
        :param codex_home: Codex home 目录
        :return: 环境状态
        """
        env_values = cls._load_codex_env(codex_home)
        return {
            "CODEX_HOME": bool(env_values.get("CODEX_HOME")),
            "OPENAI_API_KEY": bool(env_values.get("OPENAI_API_KEY")),
            "K_CODEX": bool(env_values.get("K_CODEX")),
            "HTTP_PROXY": bool(env_values.get("HTTP_PROXY") or env_values.get("http_proxy")),
            "HTTPS_PROXY": bool(env_values.get("HTTPS_PROXY") or env_values.get("https_proxy")),
            "NO_PROXY": bool(env_values.get("NO_PROXY") or env_values.get("no_proxy")),
            "ALL_PROXY": bool(env_values.get("ALL_PROXY") or env_values.get("all_proxy")),
        }

    @classmethod
    def _describe_worker_env_detail(cls, codex_home: Path) -> dict[str, Any]:
        """
        描述 Worker 运行环境的关键来源，便于排查与手工终端差异。
        :param codex_home: Codex home 目录
        :return: 环境详情
        """
        env_values = cls._load_codex_env(codex_home)
        source_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
        detail = {
            "codex_home": str(codex_home),
            "source_home": str(source_home),
            "codex_home_exists": codex_home.exists(),
            "source_home_exists": source_home.exists(),
            "config_toml": (codex_home / "config.toml").exists(),
            "config_self_toml": (codex_home / "config.self.toml").exists(),
            "auth_json": (codex_home / "auth.json").exists(),
            "version_json": (codex_home / "version.json").exists(),
            "env_file": (codex_home / ".env").exists(),
            "openai_api_key_length": len(str(env_values.get("OPENAI_API_KEY") or "")),
            "k_codex_length": len(str(env_values.get("K_CODEX") or "")),
            "http_proxy_present": bool(env_values.get("HTTP_PROXY") or env_values.get("http_proxy")),
            "https_proxy_present": bool(env_values.get("HTTPS_PROXY") or env_values.get("https_proxy")),
            "no_proxy_present": bool(env_values.get("NO_PROXY") or env_values.get("no_proxy")),
            "all_proxy_present": bool(env_values.get("ALL_PROXY") or env_values.get("all_proxy")),
        }
        return detail

    @classmethod
    def ensure_param_config_rows(cls, db: Session) -> None:
        """
        初始化工单 AI 分析相关系统参数。
        :param db: 数据库会话
        :return: 无
        """
        defaults = [
            (cls.CONFIG_WORKER_COMMAND, "工单AI分析Worker命令", cls.DEFAULT_WORKER_COMMAND, "AI分析Worker执行命令"),
            (cls.CONFIG_WORKER_MODEL, "工单AI分析Worker模型", cls.DEFAULT_WORKER_MODEL, "AI分析Worker默认模型"),
            (cls.CONFIG_WORKER_SANDBOX, "工单AI分析Worker沙箱", cls.DEFAULT_WORKER_SANDBOX, "AI分析Worker沙箱模式"),
            (
                cls.CONFIG_WORKER_TIMEOUT,
                "工单AI分析Worker超时秒数",
                str(cls.DEFAULT_WORKER_TIMEOUT),
                "AI分析Worker最大执行时长",
            ),
            (
                cls.CONFIG_WORKSPACE_ROOT,
                "工单AI分析工作区根目录",
                str(cls.DEFAULT_WORKSPACE_ROOT),
                "AI分析任务工作区根目录",
            ),
            (
                cls.CONFIG_AGENT_CODE,
                "工单AI分析Agent编码",
                cls.DEFAULT_AGENT_CODE,
                "AI分析任务优先投递的Agent编码，留空则自动选择在线Agent",
            ),
            (
                cls.CONFIG_AGENT_MAX_CONCURRENT_TASKS,
                "工单AI分析Agent并发任务数",
                str(cls.DEFAULT_AGENT_MAX_CONCURRENT_TASKS),
                "单个Agent同时允许执行的AI分析任务数量，超出部分进入排队等待",
            ),
            (
                cls.CONFIG_LOG_ANALYSIS_MODE,
                "工单AI日志分析模式",
                cls.DEFAULT_LOG_ANALYSIS_MODE,
                "AI分析日志处理模式：digest摘要、full_directory完整目录、hybrid摘要加完整目录",
            ),
            (
                cls.CONFIG_LOG_WINDOW_MISSING_STRATEGY,
                "工单AI时间窗口缺失策略",
                cls.DEFAULT_LOG_WINDOW_MISSING_STRATEGY,
                "时间窗口模式下数据库无截取正文时的处理策略：server_extract服务端截取、agent_extract由Agent截取",
            ),
        ]
        now = datetime.now()
        for config_key, config_name, config_value, remark in defaults:
            existing = db.query(SysConfig).filter(SysConfig.config_key == config_key).first()
            if existing:
                continue
            db.add(
                SysConfig(
                    config_name=config_name,
                    config_key=config_key,
                    config_value=config_value,
                    config_type="Y",
                    create_by="system",
                    update_by="system",
                    create_time=now,
                    update_time=now,
                    remark=remark,
                )
            )
        db.flush()

    @classmethod
    def _resolve_project_name(cls, db: Session, project_id: int | None) -> str:
        """
        根据项目ID获取项目名称。
        :param db: 数据库会话
        :param project_id: 项目ID
        :return: 项目名称
        """
        if not project_id:
            return ""
        project = (
            db.query(HrmProject)
            .filter(
                HrmProject.project_id == project_id,
                HrmProject.status == QtrDataStatusEnum.normal.value,
                HrmProject.del_flag == "0",
            )
            .first()
        )
        return getattr(project, "project_name", "") or ""

    @classmethod
    def _resolve_version_id(cls, ticket: Ticket, request: TicketAiAnalysisRequestModel | None = None) -> int | None:
        """解析 AI 分析使用的版本中心ID。"""
        return request.version_id if request and request.version_id else ticket.affected_version_id

    @classmethod
    def _get_version_key(cls, db: Session, version_id: int | None) -> str:
        """按版本中心ID读取版本标识，仅用于 AI 提示词和结果展示。"""
        version = TicketVersionDao.get_version_by_id(db, version_id) if version_id else None
        return version.version_key if version else ""

    @classmethod
    def _resolve_mapping(
        cls,
        db: Session,
        ticket: Ticket,
        request: TicketAiAnalysisRequestModel | None = None,
    ) -> TicketAiRepoMapping | None:
        """
        解析 AI 仓库映射。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param request: AI分析请求对象
        :return: 仓库映射对象
        """
        version_id = cls._resolve_version_id(ticket, request)
        if not version_id:
            return None
        if request and request.mapping_id:
            mapping = TicketAiDao.get_repo_mapping_by_id(db, request.mapping_id)
            if (
                mapping
                and mapping.enabled
                and mapping.project_id == ticket.project_id
                and (mapping.version_id == version_id)
            ):
                return mapping
        if ticket.project_id:
            return TicketAiDao.get_repo_mapping_by_project_and_version_id(db, ticket.project_id, version_id)
        return None

    @classmethod
    def _resolve_log_pull_record(
        cls, db: Session, ticket_id: int, record_id: int | None = None
    ) -> TicketLogPullRecord | None:
        """
        解析用于 AI 分析的日志拉取记录。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param record_id: 指定日志记录ID
        :return: 日志拉取记录对象
        """
        if record_id:
            record = TicketLogPullDao.get_record_by_id(db, record_id)
            if not record or record.ticket_id != ticket_id or record.status != "success":
                return None
            return record
        # AI 分析只使用已完成下载的日志，避免“最新”记录仍在拉取或已经失败时下发无效日志。
        return TicketLogPullDao.get_latest_success_record_by_ticket_id(db, ticket_id)

    @classmethod
    def _ensure_version_id_for_analysis(
        cls,
        db: Session,
        ticket: Ticket,
        request: TicketAiAnalysisRequestModel | None = None,
    ) -> tuple[int | None, TicketLogPullRecord | None]:
        """
        解析 AI 分析版本中心ID，缺失时尝试从日志拉取记录提取并回填。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param request: AI分析请求对象
        :return: 版本中心ID与用于分析的日志记录
        """
        selected_log_record = cls._resolve_log_pull_record(
            db,
            ticket.ticket_id,
            request.log_pull_record_id if request else None,
        )
        version_id = cls._resolve_version_id(ticket, request)
        if version_id:
            return version_id, selected_log_record

        candidate_records: list[TicketLogPullRecord] = []
        if selected_log_record:
            candidate_records.append(selected_log_record)
        latest_success_record = TicketLogPullDao.get_latest_success_record_by_ticket_id(db, ticket.ticket_id)
        if latest_success_record and all(record.id != latest_success_record.id for record in candidate_records):
            candidate_records.append(latest_success_record)

        for record in candidate_records:
            version_id = TicketLogPullService.ensure_ticket_version_id_from_log(db, ticket.ticket_id, record.id)
            if version_id:
                refreshed_ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id)
                if refreshed_ticket:
                    ticket.affected_version_id = refreshed_ticket.affected_version_id
                return version_id, record
        return None, selected_log_record or latest_success_record

    @classmethod
    def _resolve_agent_code(cls, db: Session, requested_agent_code: str | None = None) -> str:
        """
        解析 AI 分析任务使用的 Agent 编码。
        :param db: 数据库会话
        :param requested_agent_code: 请求指定的 Agent 编码
        :return: Agent 编码
        """
        requested_code = str(requested_agent_code or "").strip()
        if requested_code:
            if AgentDao.get_agent_by_code(db, requested_code):
                return requested_code
            return ""
        configured_agent_code = cls._get_config_text(db, cls.CONFIG_AGENT_CODE, cls.DEFAULT_AGENT_CODE)
        if configured_agent_code and AgentDao.get_agent_by_code(db, configured_agent_code):
            return configured_agent_code
        agent_model = cls._agent_model()
        online_agent = (
            db.query(agent_model.agent_code)
            .filter(
                agent_model.del_flag == 1,
                agent_model.status == 2,
                agent_model.agent_code.isnot(None),
                agent_model.agent_code != "",
            )
            .order_by(agent_model.agent_id)
            .first()
        )
        if online_agent and online_agent[0]:
            return str(online_agent[0]).strip()
        return ""

    @classmethod
    def _validate_agent_connected(cls, db: Session, requested_agent_code: str | None = None) -> tuple[bool, str, str]:
        """
        校验 AI 分析任务提交时是否存在可用 Agent。
        :param db: 数据库会话
        :param requested_agent_code: 请求或 Provider 指定的 Agent 编码
        :return: (是否可用, 错误信息, 实际解析到的 Agent 编码)
        """
        requested_code = str(requested_agent_code or "").strip()
        if requested_code and not AgentDao.get_agent_by_code(db, requested_code):
            return False, f"Agent[{requested_code}]不存在，请先在 Agent 管理中创建记录", ""
        agent_code = cls._resolve_agent_code(db, requested_agent_code)
        if not agent_code:
            return False, "未找到可用的 Agent，请先启动本地 Agent 并连接到服务端", ""
        return True, "", agent_code

    @staticmethod
    def _agent_model():
        """
        返回 Agent ORM 模型，避免循环导入时提前实例化。
        :return: Agent ORM 模型
        """
        from module_hrm.entity.do.agent_do import QtrAgent

        return QtrAgent

    @classmethod
    def _count_online_agents(cls, db: Session) -> int:
        """
        统计当前数据库里标记为在线的 Agent 数量。
        :param db: 数据库会话
        :return: 在线 Agent 数量
        """
        agent_model = cls._agent_model()
        return (
            db.query(agent_model)
            .filter(
                agent_model.del_flag == 1,
                agent_model.status == 2,
                agent_model.agent_code.isnot(None),
                agent_model.agent_code != "",
            )
            .count()
        )

    @classmethod
    def _build_agent_gateway_url(cls, path: str) -> str:
        """
        构建本机 FastAPI 网关地址。

        该请求通过 127.0.0.1 直连当前 FastAPI 进程，不经过反向代理，
        因此不能拼接面向浏览器的 ``app_root_path``。``root_path`` 只由
        反向代理转发外部请求时使用；拼接到本机请求会在未配置同样
        ``root_path`` 的 API 进程中直接命中 404。
        :param path: 访问路径
        :return: 完整 URL
        """
        normalized_path = str(path or "").strip()
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"
        return f"http://127.0.0.1:{AppConfig.app_port}{normalized_path}"

    @classmethod
    def _build_agent_request_id(cls, task_id: int | str) -> str:
        """
        为一次 Agent 执行尝试生成唯一请求ID。

        服务端任务重试必须绕过 Agent 网关对旧请求的失败缓存，但同一个任务的
        请求指纹仍保持不变，用于服务端成功结果幂等。因此请求ID要区分每次
        执行尝试，不能直接使用任务ID。
        :param task_id: 工单 AI 分析任务ID
        :return: 本次 Agent 执行尝试的唯一请求ID
        """
        return f"ticket-ai-analysis:{task_id}:attempt:{snowIdWorker.get_id()}"

    @classmethod
    def _send_agent_request_via_gateway(
        cls,
        agent_code: str,
        request_payload: dict[str, Any],
        request_id: str,
        timeout_seconds: int | float,
    ) -> HandleResponse:
        """
        通过本机 FastAPI 网关发送 AI 分析请求。
        :param agent_code: Agent 编码
        :param request_payload: 发给 Agent 的请求内容
        :param request_id: 请求ID
        :param timeout_seconds: 请求超时时间
        :return: 网关返回结果
        """
        gateway_url = cls._build_agent_gateway_url(f"/qtr/agent/ai-analysis/send/{agent_code}")
        request_timeout = max(float(timeout_seconds or 120), 60.0) + 120.0
        payload = {
            "message": request_payload,
            "requestId": request_id,
            "timeoutSeconds": timeout_seconds,
        }
        with httpx.Client(timeout=request_timeout) as client:
            response = client.post(gateway_url, json=payload)
            response.raise_for_status()
            return HandleResponse.validate_transport_payload(response.text)


    @classmethod
    def _normalize_log_analysis_mode(cls, mode: str | None) -> str:
        """
        归一化日志分析模式。
        :param mode: 原始模式值
        :return: 可识别的日志分析模式
        """
        normalized = str(mode or "").strip().lower()
        return normalized if normalized in cls.LOG_ANALYSIS_MODES else cls.DEFAULT_LOG_ANALYSIS_MODE

    @classmethod
    def _normalize_log_window_missing_strategy(cls, strategy: str | None) -> str:
        """
        归一化时间窗口缺失策略。
        :param strategy: 原始策略值
        :return: 可识别的缺失策略
        """
        normalized = str(strategy or "").strip().lower()
        return (
            normalized if normalized in cls.LOG_WINDOW_MISSING_STRATEGIES else cls.DEFAULT_LOG_WINDOW_MISSING_STRATEGY
        )

    @classmethod
    def _resolve_log_analysis_options(
        cls,
        db: Session,
        request: TicketAiAnalysisRequestModel | None = None,
    ) -> dict[str, str]:
        """
        解析 AI 日志分析选项，手动请求优先，系统配置兜底。
        :param db: 数据库会话
        :param request: AI分析请求对象
        :return: 日志分析选项
        """
        configured_mode = cls._get_config_text(db, cls.CONFIG_LOG_ANALYSIS_MODE, cls.DEFAULT_LOG_ANALYSIS_MODE)
        configured_strategy = cls._get_config_text(
            db,
            cls.CONFIG_LOG_WINDOW_MISSING_STRATEGY,
            cls.DEFAULT_LOG_WINDOW_MISSING_STRATEGY,
        )
        return {
            "mode": cls._normalize_log_analysis_mode(
                request.log_analysis_mode if request and request.log_analysis_mode else configured_mode
            ),
            "windowMissingStrategy": cls._normalize_log_window_missing_strategy(
                request.log_window_missing_strategy
                if request and request.log_window_missing_strategy
                else configured_strategy
            ),
        }

    @staticmethod
    def _parse_request_datetime(value: datetime | str | None) -> datetime | None:
        """
        解析 AI 分析请求中的时间值。
        :param value: datetime 或字符串
        :return: datetime，无法解析时返回 None
        """
        if value is None or value == "":
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
    def _resolve_request_log_time_range(
        cls,
        request: TicketAiAnalysisRequestModel | None = None,
    ) -> tuple[datetime | None, datetime | None]:
        """
        解析本次 AI 分析指定的日志时间窗口。
        :param request: AI分析请求对象
        :return: 开始时间和结束时间
        """
        if not request:
            return None, None
        begin_time = cls._parse_request_datetime(request.log_begin_time)
        end_time = cls._parse_request_datetime(request.log_end_time)
        if begin_time or end_time:
            return begin_time, end_time
        point_time = cls._parse_request_datetime(request.log_point_time)
        if not point_time:
            return None, None
        before_minutes = max(int(request.range_before_minutes or 0), 0)
        after_minutes = max(int(request.range_after_minutes or 0), 0)
        if before_minutes == 0 and after_minutes == 0:
            return None, None
        return point_time - timedelta(minutes=before_minutes), point_time + timedelta(minutes=after_minutes)

    @classmethod
    def _resolve_ai_provider(cls, db: Session, provider_code: str | None = None):
        """
        解析 AI Provider 配置。
        :param db: 数据库会话
        :param provider_code: Provider编码
        :return: Provider数据库对象或None
        """
        normalized_code = str(provider_code or "").strip()
        if not normalized_code:
            return None
        return AiProviderDao.get_ai_provider_by_code(db, normalized_code)

    @classmethod
    def _resolve_executor(
        cls,
        provider,
        requested_executor: str | None = None,
    ) -> str | None:
        """
        解析工单 AI 分析本次使用的执行器。
        解析优先级：请求显式指定 > Provider 默认执行器 > Provider 支持的首个分析执行器 > codex 兜底。
        :param provider: Provider 数据库对象
        :param requested_executor: 请求指定的执行器编码
        :return: 解析后的执行器编码
        """
        requested = str(requested_executor or "").strip()
        if requested:
            return requested
        if provider:
            preferred = AiProviderCapabilityService.resolve_preferred_executor(provider)
            if preferred:
                return preferred
        return "codex"

    @staticmethod
    def _normalize_provider_worker_env(worker_env: Any) -> dict[str, str]:
        """
        将 Provider Worker环境配置归一化为环境变量字典。
        :param worker_env: Worker环境配置
        :return: 环境变量字典
        """
        if not isinstance(worker_env, dict):
            return {}
        env_overrides: dict[str, str] = {}
        for key, value in worker_env.items():
            if key in (None, "") or value in (None, ""):
                continue
            env_overrides[str(key)] = str(value)
        return env_overrides

    @classmethod
    def _build_provider_env_overrides(
        cls,
        provider,
        observability_config: dict[str, Any] | None = None,
        session_id: str | None = None,
        traceparent: str | None = None,
        observability_trace: dict[str, str] | None = None,
        user_id: str | None = None,
    ) -> dict[str, str]:
        """
        根据 Provider 配置构建 Worker 环境变量覆盖项。
        Codex 使用 OPENAI_API_KEY，Claude Code 使用 ANTHROPIC_API_KEY，
        同时保留对方 key 的兼容性。
        :param provider: Provider数据库对象
        :param observability_config: 可观测上报配置，非空且Provider开启CLI遥测时注入OTEL变量
        :param session_id: 可观测会话ID，用于Agent任务span与平台Sessions聚合
        :param traceparent: W3C trace上下文，Claude Code -p 模式会读取并挂接到任务trace
        :param observability_trace: 任务级trace上下文（trace_id/span_id），下发供Agent任务span复用
        :return: 环境变量覆盖项
        """
        if not provider:
            return {}
        # 先合并扩展环境变量，再写入 Provider 的核心连接信息。
        # workerEnv 只用于补充 Worker 参数，不能覆盖当前工单明确选择的 Provider
        # 的密钥、地址和模型，否则会出现“界面选择了 Provider，但 Agent 仍调用旧地址”的问题。
        env_overrides: dict[str, str] = cls._normalize_provider_worker_env(getattr(provider, "worker_env", None))
        try:
            secret_key = ApiKeyUtil.decrypt_api_key(provider.api_key_cipher_text)
        except Exception as exc:
            raise ValueError(f"Provider密钥解密失败: {exc}") from exc
        api_protocol = str(getattr(provider, "api_protocol", "") or "").strip().lower()
        if secret_key:
            if api_protocol == "anthropic_messages":
                env_overrides["ANTHROPIC_API_KEY"] = secret_key
                env_overrides["OPENAI_API_KEY"] = secret_key
            else:
                env_overrides["OPENAI_API_KEY"] = secret_key
                env_overrides["ANTHROPIC_API_KEY"] = secret_key
        base_url = str(getattr(provider, "base_url", "") or "").strip()
        if base_url:
            if api_protocol == "anthropic_messages":
                env_overrides["ANTHROPIC_BASE_URL"] = base_url
            env_overrides["OPENAI_BASE_URL"] = base_url
        model_name = str(getattr(provider, "default_model", "") or "").strip()
        if model_name:
            env_overrides["OPENAI_MODEL"] = model_name
            env_overrides["ANTHROPIC_MODEL"] = model_name
        provider_code = str(getattr(provider, "provider_code", "") or "").strip()
        provider_name = str(getattr(provider, "provider_name", "") or "").strip()
        if provider_code:
            env_overrides["AI_PROVIDER_CODE"] = provider_code
        # 可观测环境注入分两层：
        # 1) 主开关开启即下发基础 OTLP 配置——任务级 span 由 Agent 侧直连平台上报
        #    （服务端与可观测平台可能网络隔离，Agent 机器天然可达，CLI 遥测同样从 Agent 上报）；
        # 2) CLI 原生遥测开关额外下发 CLI 专属开关与 TRACEPARENT——Codex 走任务级
        #    config.toml [otel]（客户端按 CODEX_OTEL_ENABLED 写入），Claude 走环境变量。
        if observability_config and provider is not None and bool(
            getattr(provider, "observability_enabled", False)
        ):
            otel_endpoint = str(observability_config.get("endpoint") or "").strip()
            otel_auth = str(observability_config.get("auth_header") or "").strip()
            if otel_endpoint and otel_auth:
                env_overrides.update(
                    {
                        "OTEL_EXPORTER_OTLP_ENDPOINT": otel_endpoint,
                        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                        "OTEL_EXPORTER_OTLP_HEADERS": f"Authorization={otel_auth}",
                        "OTEL_SERVICE_NAME": str(observability_config.get("service_name") or "ticket-ai-analysis"),
                    }
                )
                if session_id:
                    env_overrides["OTEL_SESSION_ID"] = session_id
                if user_id:
                    env_overrides["OTEL_USER_ID"] = user_id
                if observability_trace:
                    env_overrides["OTEL_TRACE_ID"] = str(observability_trace.get("trace_id") or "")
                    env_overrides["OTEL_SPAN_ID"] = str(observability_trace.get("span_id") or "")
                if bool(getattr(provider, "observability_cli_enabled", False)):
                    env_overrides.update(
                        {
                            "OTEL_TRACES_EXPORTER": "otlp",
                            "OTEL_METRICS_EXPORTER": "otlp",
                            "OTEL_LOGS_EXPORTER": "otlp",
                            "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
                            "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",
                            "CODEX_OTEL_ENABLED": "1",
                        }
                    )
                    if traceparent:
                        env_overrides["TRACEPARENT"] = traceparent
        if provider_name:
            env_overrides["AI_PROVIDER_NAME"] = provider_name
        platform_code = str(getattr(provider, "platform_code", "") or "").strip()
        if platform_code:
            env_overrides["AI_PROVIDER_PLATFORM"] = platform_code
        if getattr(provider, "provider_level", None) is not None:
            env_overrides["AI_PROVIDER_LEVEL"] = str(provider.provider_level)
        return env_overrides

    @staticmethod
    def _build_agent_request_payload(
        *,
        task_id: int,
        ticket: Ticket,
        mapping: TicketAiRepoMapping,
        context_payload: dict[str, Any],
        provider_env_overrides: dict[str, str] | None = None,
        ticket_payload: dict[str, Any],
        timeline_payload: Any,
        prompt_template: str,
        schema_payload: dict[str, Any],
        result_path: str,
        timeout_sec: int,
        resume: bool = False,
        resume_from_workspace_path: str | None = None,
        submitted_by_name: str | None = None,
        submitted_by_id: int | None = None,
    ) -> dict[str, Any]:
        """
        构建发送给 Agent 的 AI 分析请求体。
        :param task_id: 任务ID
        :param ticket: 工单对象
        :param mapping: 仓库映射对象
        :param context_payload: 上下文快照
        :param ticket_payload: 工单快照
        :param timeline_payload: 工单时间线快照
        :param prompt_template: 提示词模板
        :param schema_payload: JSON Schema
        :param result_path: 结果文件路径
        :param resume: 是否复用上次分析会话
        :param resume_from_workspace_path: 上次任务 workspace 路径
        :return: 请求体
        """
        payload = {
            "requestType": TstepTypeEnum.ai_analysis.value,
            "command": "run_ticket_ai_analysis",
            "taskId": task_id,
            "ticketId": ticket.ticket_id,
            "projectId": ticket.project_id,
            "ticketNo": ticket.ticket_no,
            "mapping": TicketAiAnalysisService._json_safe_value(CamelCaseUtil.transform_result(mapping)),
            "context": TicketAiAnalysisService._json_safe_value(context_payload),
            "ticket": TicketAiAnalysisService._json_safe_value(ticket_payload),
            "timeline": TicketAiAnalysisService._json_safe_value(timeline_payload),
            "promptTemplate": prompt_template,
            "resultSchema": schema_payload,
            "resultPath": result_path,
            "timeoutSec": timeout_sec,
            "providerEnv": TicketAiAnalysisService._json_safe_value(provider_env_overrides or {}),
        }
        # 提交人信息随 payload 下发：Agent 上报可观测 span 时映射为 user.id（平台 Users 页签）
        if submitted_by_name:
            payload["submittedByName"] = submitted_by_name
        if submitted_by_id:
            payload["submittedById"] = submitted_by_id
        if resume:
            payload["resume"] = True
        if resume_from_workspace_path:
            payload["resumeFromWorkspacePath"] = resume_from_workspace_path
        return payload

    @staticmethod
    def _extract_agent_response_result(response: Any) -> dict[str, Any]:
        """
        提取 Agent 响应中的 result 内容。
        :param response: Agent 响应对象
        :return: result 字典
        """
        if response is None:
            return {}
        if isinstance(response, dict):
            result = response.get("result")
            if isinstance(result, dict):
                return result
            if isinstance(response.get("analysis_result"), dict):
                return response["analysis_result"]
            return {}
        result = getattr(response, "result", None)
        if isinstance(result, dict):
            return result
        return {}

    # 旧版 Agent 兜底截断长度：与新版 Agent 回传摘要长度（RAW_OUTPUT_SUMMARY_CHARS=8000）
    # 保持同量级，超长部分就地丢弃；完整内容以 Agent 本地 stdout_path 文件为准。
    RESPONSE_RAW_OUTPUT_MAX_CHARS = 8000

    @classmethod
    def _truncate_response_raw_output(cls, response_object: Any) -> None:
        """
        就地截断 Agent 响应 result 内的超大 raw_output 字段。

        背景：raw_output 曾整包回传完整 stdout（实测单次 8MB），WebSocket 分片
        接收 + JSON 序列化 + 响应模型驻留会叠加出百 MB 级内存峰值，是两次容器
        OOM 的直接诱因。新版 Agent 已在回传前截断；本方法兜底旧版 Agent。截断
        只影响响应在服务端的驻留与审计摘要，不影响 analysis_result 的解析与写回。

        :param response_object: Agent 内层响应对象（dict 或 pydantic 模型）
        :return: 无
        """
        if response_object is None:
            return
        try:
            result: Any
            if isinstance(response_object, dict):
                result = response_object.get("result")
            else:
                result = getattr(response_object, "result", None)
            if not isinstance(result, dict):
                return
            raw_output = result.get("raw_output")
            if isinstance(raw_output, str) and len(raw_output) > cls.RESPONSE_RAW_OUTPUT_MAX_CHARS:
                result["raw_output"] = raw_output[: cls.RESPONSE_RAW_OUTPUT_MAX_CHARS]
                logger.warning(
                    f"Agent响应raw_output超长已截断: originalChars={len(raw_output)}, "
                    f"truncatedTo={cls.RESPONSE_RAW_OUTPUT_MAX_CHARS}"
                )
        except Exception as exc:
            # 截断失败不影响响应解析主流程。
            logger.debug(f"截断Agent响应raw_output失败: error={exc}")

    @staticmethod
    def _resolve_agent_failure_message(
        response_object: Any,
        agent_response: Any,
        response_payload: dict[str, Any],
        raw_stdout: str = "",
        raw_stderr: str = "",
    ) -> str:
        """
        提取 Agent 失败原因，优先使用内层响应的真实错误而不是外层通用成功消息。
        :param response_object: Agent 内层响应对象
        :param agent_response: 网关包装响应对象
        :param response_payload: Agent result 字典
        :param raw_stdout: 网关响应原始文本
        :param raw_stderr: 网关错误文本
        :return: 面向任务记录的失败原因
        """
        candidates: list[Any] = []
        if isinstance(response_payload, dict):
            candidates.extend([response_payload.get("error_message"), response_payload.get("message")])
        if isinstance(response_object, dict):
            candidates.extend([response_object.get("error_message"), response_object.get("message")])
        else:
            candidates.extend(
                [
                    getattr(response_object, "error_message", None),
                    getattr(response_object, "message", None),
                ]
            )
        candidates.extend(
            [
                getattr(agent_response, "error_message", None),
                getattr(agent_response, "message", None),
            ]
        )
        generic_messages = {"操作成功", "success", "ok"}
        for candidate in candidates:
            message = str(candidate or "").strip()
            if message and message.lower() not in generic_messages:
                return message
        return TicketAiAnalysisService._summarize_worker_error(
            raw_stderr,
            raw_stdout,
            "AI Agent 未返回可解析的分析结果",
        )

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
        text_value = str(value).strip().replace(",", "")
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
    def _find_token_usage_payload(cls, candidate: Any) -> dict[str, Any] | None:
        """
        递归查找结构中的 Token 用量对象。
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
            for key in ("result", "data", "message", "response", "structured_output", "structuredOutput"):
                payload = cls._find_token_usage_payload(candidate.get(key))
                if payload is not None:
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
        从多个候选对象中提取原始 Token 用量。
        :param candidates: 候选对象列表
        :return: 原始 Token 用量字典
        """
        for candidate in candidates:
            payload = cls._find_token_usage_payload(candidate)
            if payload is not None:
                return payload
        return None

    @classmethod
    def _normalize_token_usage(cls, token_usage: Any) -> dict[str, int | None] | None:
        """
        归一化 Token 用量字段，统一输入/输出/总量键名。
        :param token_usage: 原始 Token 用量对象
        :return: 归一化后的 Token 统计
        """
        if not isinstance(token_usage, dict):
            return None
        input_token_count = cls._to_optional_int(
            token_usage.get("input_tokens")
            if token_usage.get("input_tokens") is not None
            else token_usage.get("inputTokens")
        )
        if input_token_count is None:
            input_token_count = cls._to_optional_int(token_usage.get("prompt_tokens"))

        output_token_count = cls._to_optional_int(
            token_usage.get("output_tokens")
            if token_usage.get("output_tokens") is not None
            else token_usage.get("outputTokens")
        )
        if output_token_count is None:
            output_token_count = cls._to_optional_int(token_usage.get("completion_tokens"))

        total_token_count = cls._to_optional_int(
            token_usage.get("total_tokens")
            if token_usage.get("total_tokens") is not None
            else token_usage.get("totalTokens")
        )
        if total_token_count is None and input_token_count is not None and output_token_count is not None:
            total_token_count = input_token_count + output_token_count

        if input_token_count is None and output_token_count is None and total_token_count is None:
            return None
        return {
            "input_token_count": input_token_count,
            "output_token_count": output_token_count,
            "total_token_count": total_token_count,
        }

    @classmethod
    def _build_execution_payload(
        cls,
        *,
        task_type: str,
        task_name: str,
        source_type: str | None = None,
        source_id: int | None = None,
        source_ref: str | None = None,
        provider_code: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        request_payload: Any = None,
        response_payload: Any = None,
        response_text: str | None = None,
        token_usage: dict[str, Any] | None = None,
        status: str = "pending",
        error_message: str | None = None,
        created_by_id: int | None = None,
        created_by_name: str | None = None,
    ) -> dict[str, Any]:
        """
        构建工单 AI 审计记录载荷。
        :return: 审计记录字典
        """
        return {
            "task_type": task_type,
            "task_name": task_name,
            "source_type": source_type,
            "source_id": source_id,
            "source_ref": source_ref,
            "provider_code": provider_code,
            "model_name": model_name,
            "base_url": base_url,
            "status": status,
            "request_payload": cls._json_safe_value(request_payload) if request_payload is not None else None,
            "response_payload": cls._json_safe_value(response_payload) if response_payload is not None else None,
            "response_text": response_text,
            "token_usage": cls._json_safe_value(token_usage) if token_usage is not None else None,
            "error_message": error_message,
            "created_by_id": created_by_id,
            "created_by_name": created_by_name or "system",
        }

    @classmethod
    def _ensure_task_execution_record(
        cls,
        db: Session,
        task: TicketAiAnalysisTask,
        ticket: Ticket | None = None,
    ) -> int | None:
        """
        为工单 AI 任务补齐审计记录，并回写审计ID。
        :param db: 数据库会话
        :param task: AI任务
        :param ticket: 工单对象
        :return: 审计ID
        """
        if getattr(task, "audit_execution_id", None):
            return int(task.audit_execution_id)

        context_payload = (
            task.analysis_context if isinstance(task.analysis_context, dict) else cls._loads(task.analysis_context, {})
        )
        provider_code = str((context_payload or {}).get("selectedAiProviderCode") or "").strip() or None
        selected_provider = AiProviderDao.get_ai_provider_by_code(db, provider_code) if provider_code else None
        model_name = str((context_payload or {}).get("selectedWorkerModel") or "").strip() or None
        if not model_name and selected_provider and str(selected_provider.default_model or "").strip():
            model_name = str(selected_provider.default_model).strip()

        execution = AiTaskExecutionDao.add_ai_task_execution_dao(
            db,
            cls._build_execution_payload(
                task_type="ticket_ai_analysis",
                task_name="工单AI分析",
                source_type="ticket",
                source_id=int(getattr(ticket, "ticket_id", None) or task.ticket_id),
                source_ref=str(getattr(ticket, "ticket_no", "") or getattr(task, "ticket_id", "") or ""),
                provider_code=provider_code,
                model_name=model_name,
                base_url=(str(getattr(selected_provider, "base_url", "") or "").strip() or None),
                request_payload={
                    "task_id": task.task_id,
                    "ticket_id": task.ticket_id,
                    "version_id": task.version_id,
                    "agent_code": (context_payload or {}).get("selectedAgentCode"),
                },
                status="pending",
                created_by_id=getattr(task, "submitted_by_id", None),
                created_by_name=getattr(task, "submitted_by_name", None),
            ),
        )
        TicketAiDao.update_task(
            db,
            task.task_id,
            {
                "audit_execution_id": execution.execution_id,
                "update_time": datetime.now(),
            },
        )
        task.audit_execution_id = execution.execution_id
        return int(execution.execution_id)

    # 审计记录响应文本与 JSON 载荷的最大保留长度。
    # 完整内容已随任务/工作区文件留档（result_path、raw_output），审计只保留定位所需的头部信息，
    # 避免每次分析把几十万字节的上下文和响应整包写入内存再落到数据库长文本列。
    EXECUTION_TEXT_MAX_CHARS = 20000
    EXECUTION_PAYLOAD_MAX_CHARS = 20000

    @classmethod
    def _truncate_execution_text(cls, value: Any) -> str | None:
        """
        将审计文本按上限截断。
        :param value: 原始文本
        :return: 截断后的文本，空值返回 None
        """
        text = str(value).strip() if value not in (None, "") else ""
        if not text:
            return None
        if len(text) <= cls.EXECUTION_TEXT_MAX_CHARS:
            return text
        return (
            f"{text[: cls.EXECUTION_TEXT_MAX_CHARS]}\n...（审计文本超长已截断，原始 {len(text)} 字符，"
            f"完整内容见任务工作区）..."
        )

    @classmethod
    def _compact_execution_payload(cls, value: Any) -> Any:
        """
        将审计 JSON 载荷归一化并裁剪超大字符串字段。

        AI 分析请求载荷中包含 80 万字符级的日志正文（context.sourceLogPull.text）、
        工单描述和时间线等大文本；直接整包序列化会在执行线程内翻倍占用内存，
        且审计查询页并不需要完整正文。这里递归遍历载荷，把超过阈值的字符串字段
        替换为"前缀 + 长度说明"的占位文本，小字段原样保留。

        :param value: 原始载荷（dict/list/str 等任意 JSON 安全结构）
        :return: 裁剪后的载荷
        """

        def _walk(node: Any, depth: int = 0):
            if depth > 8:  # 防御异常深嵌套，超深的整体截断为占位文本
                return "<deep payload truncated>"
            if isinstance(node, str):
                if len(node) <= cls.EXECUTION_PAYLOAD_MAX_CHARS:
                    return node
                return f"{node[:512]}...（审计载荷长文本已截断，原始 {len(node)} 字符）"
            if isinstance(node, dict):
                return {key: _walk(item, depth + 1) for key, item in node.items()}
            if isinstance(node, list):
                walk_result = [_walk(item, depth + 1) for item in node]
                if len(walk_result) > 200:  # 列表项过多时仅保留前 200 项，避免大列表膨胀
                    return walk_result[:200]
                return walk_result
            return node

        return _walk(cls._json_safe_value(value))

    @classmethod
    def _update_execution_record(
        cls,
        db: Session,
        execution_id: int | None,
        **kwargs: Any,
    ) -> None:
        """
        更新工单 AI 审计记录。响应文本和 JSON 载荷会先做超长裁剪，控制审计写入的内存峰值。
        :param db: 数据库会话
        :param execution_id: 审计ID
        :param kwargs: 更新字段
        :return: 无
        """
        if not execution_id:
            return
        update_data: dict[str, Any] = {}
        for key in (
            "status",
            "provider_code",
            "model_name",
            "base_url",
            "error_code",
            "response_text",
            "error_message",
        ):
            if key in kwargs:
                value = kwargs.get(key)
                update_data[key] = cls._truncate_execution_text(value)
        for key in ("request_payload", "response_payload", "token_usage"):
            if key in kwargs:
                value = kwargs.get(key)
                update_data[key] = cls._compact_execution_payload(value) if value is not None else None
        if not update_data:
            return
        update_data["update_time"] = datetime.now()
        AiTaskExecutionDao.edit_ai_task_execution_dao(db, execution_id, update_data)

    @classmethod
    def _decode_log_text(cls, text: str | None) -> str:
        """
        将日志内容解码为可读文本。
        :param text: 原始日志文本
        :return: 可读文本
        """
        if not text:
            return ""
        try:
            return TicketLogPullService._decompress_text(text)
        except Exception:
            return str(text)

    @staticmethod
    def _truncate_middle(text: str | None, max_chars: int) -> str:
        """
        对长文本做中间截断，保留首尾关键上下文。
        :param text: 原始文本
        :param max_chars: 最大字符数
        :return: 截断后的文本
        """
        raw_text = str(text or "")
        if max_chars <= 0 or len(raw_text) <= max_chars:
            return raw_text
        head_size = max_chars // 2
        tail_size = max_chars - head_size
        return "\n".join(
            [
                raw_text[:head_size],
                f"\n... 日志内容已截断，原始长度 {len(raw_text)} 字符，仅保留首尾 {max_chars} 字符 ...\n",
                raw_text[-tail_size:],
            ]
        )

    @classmethod
    def _build_context_payload(
        cls,
        db: Session,
        ticket: Ticket,
        mapping: TicketAiRepoMapping,
        log_record: TicketLogPullRecord | None,
        request: TicketAiAnalysisRequestModel | None = None,
    ) -> dict[str, Any]:
        """
        构建 AI 分析上下文快照。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param mapping: 仓库映射对象
        :param log_record: 日志拉取记录
        :param request: AI分析请求对象
        :return: 上下文字典
        """
        ticket_payload = CamelCaseUtil.transform_result(ticket)
        timeline_payload = TicketDao.get_timeline(db, ticket.ticket_id)
        latest_log_summary = TicketLogPullService.get_latest_summary(db, ticket.ticket_id)
        messages_payload = CamelCaseUtil.transform_result(TicketDao.list_messages(db, ticket.ticket_id, 80))
        snapshots_payload = CamelCaseUtil.transform_result(TicketDao.list_snapshots(db, ticket.ticket_id, 10))
        search_text = " ".join(
            str(item)
            for item in [
                ticket.title,
                ticket.description,
                ticket.root_cause,
                ticket.solution,
                ticket.module_name,
                ticket.category_name,
            ]
            if item
        )
        similar_tickets = [
            item
            for item in TicketEmbeddingService.search_tickets(db, search_text, 6)
            if item.get("ticketId") != ticket.ticket_id
        ][:5]
        log_content_payload: dict[str, Any] | None = None
        source_log_view_mode = "stored"
        source_log_record_id: int | None = None
        log_options = cls._resolve_log_analysis_options(db, request)
        request_begin_time, request_end_time = cls._resolve_request_log_time_range(request)
        has_request_time_window = bool(request_begin_time or request_end_time)
        if log_record:
            source_log_record_id = log_record.id
            try:
                log_query = TicketLogPullContentQueryModel(view_mode="stored")
                if has_request_time_window and log_options["windowMissingStrategy"] == "server_extract":
                    log_query = TicketLogPullContentQueryModel(
                        view_mode="original",
                        log_begin_time=request_begin_time,
                        log_end_time=request_end_time,
                    )
                log_content_model = TicketLogPullService.get_log_pull_content_services(db, log_record.id, log_query)
                if log_content_model:
                    log_text = cls._decode_log_text(log_content_model.text)
                    should_agent_extract_window = bool(
                        has_request_time_window
                        and log_options["windowMissingStrategy"] == "agent_extract"
                        and not log_text.strip()
                    )
                    log_content_payload = {
                        "recordId": log_content_model.record_id,
                        "viewBeginTime": log_content_model.view_begin_time,
                        "viewEndTime": log_content_model.view_end_time,
                        "viewSource": log_content_model.view_source,
                        "wholeArchiveMode": should_agent_extract_window
                        or not bool(log_content_model.view_begin_time or log_content_model.view_end_time),
                        "contentSummary": log_content_model.content_summary,
                        "matchedEntryCount": log_content_model.matched_entry_count,
                        "archiveEntryCount": log_content_model.archive_entry_count,
                        "storagePath": log_content_model.storage_path,
                        "commandResultUrl": log_content_model.command_result_url,
                        "text": cls._truncate_middle(log_text, cls.DEFAULT_CONTEXT_LOG_MAX_CHARS),
                        "textTruncatedForAi": len(log_text) > cls.DEFAULT_CONTEXT_LOG_MAX_CHARS,
                        "textOriginalCharCount": len(log_text),
                        "analysisMode": log_options["mode"],
                        "windowMissingStrategy": log_options["windowMissingStrategy"],
                        "requestedBeginTime": request_begin_time,
                        "requestedEndTime": request_end_time,
                        "serverExtractedForAi": bool(
                            has_request_time_window and log_options["windowMissingStrategy"] == "server_extract"
                        ),
                        "agentShouldExtractWindow": should_agent_extract_window,
                    }
                    source_log_view_mode = str(log_content_model.view_source or "stored")
                elif has_request_time_window:
                    log_content_payload = {
                        "recordId": log_record.id,
                        "viewBeginTime": None,
                        "viewEndTime": None,
                        "viewSource": "agent_extract",
                        "wholeArchiveMode": True,
                        "contentSummary": "数据库无已截取正文，AI 分析将由 Agent 按时间窗口从整包日志截取。",
                        "matchedEntryCount": 0,
                        "archiveEntryCount": getattr(log_record, "archive_entry_count", 0) or 0,
                        "storagePath": getattr(log_record, "storage_path", "") or "",
                        "commandResultUrl": getattr(log_record, "command_result_url", "") or "",
                        "text": "",
                        "textTruncatedForAi": False,
                        "textOriginalCharCount": 0,
                        "analysisMode": log_options["mode"],
                        "windowMissingStrategy": log_options["windowMissingStrategy"],
                        "requestedBeginTime": request_begin_time,
                        "requestedEndTime": request_end_time,
                        "agentShouldExtractWindow": True,
                    }
                    source_log_view_mode = "agent_extract"
            except Exception as exc:
                logger.warning(f"获取工单日志上下文失败: {exc}")
                if has_request_time_window:
                    log_content_payload = {
                        "recordId": log_record.id,
                        "viewBeginTime": None,
                        "viewEndTime": None,
                        "viewSource": "agent_extract_fallback",
                        "wholeArchiveMode": True,
                        "contentSummary": "服务端截取日志失败，AI 分析将降级为 Agent 按时间窗口从整包日志截取。",
                        "matchedEntryCount": 0,
                        "archiveEntryCount": getattr(log_record, "archive_entry_count", 0) or 0,
                        "storagePath": getattr(log_record, "storage_path", "") or "",
                        "commandResultUrl": getattr(log_record, "command_result_url", "") or "",
                        "text": "",
                        "textTruncatedForAi": False,
                        "textOriginalCharCount": 0,
                        "analysisMode": log_options["mode"],
                        "windowMissingStrategy": log_options["windowMissingStrategy"],
                        "requestedBeginTime": request_begin_time,
                        "requestedEndTime": request_end_time,
                        "agentShouldExtractWindow": True,
                    }
                    source_log_view_mode = "agent_extract_fallback"
        elif has_request_time_window:
            log_content_payload = {
                "recordId": None,
                "viewBeginTime": None,
                "viewEndTime": None,
                "viewSource": "missing",
                "wholeArchiveMode": False,
                "contentSummary": "本次 AI 分析指定了日志时间窗口，但未关联日志拉取记录。",
                "matchedEntryCount": 0,
                "archiveEntryCount": 0,
                "storagePath": "",
                "commandResultUrl": "",
                "text": "",
                "textTruncatedForAi": False,
                "textOriginalCharCount": 0,
                "analysisMode": log_options["mode"],
                "windowMissingStrategy": log_options["windowMissingStrategy"],
                "requestedBeginTime": request_begin_time,
                "requestedEndTime": request_end_time,
            }
        return {
            "ticket": ticket_payload,
            "timeline": cls._json_safe_value(CamelCaseUtil.transform_result(timeline_payload)),
            "messages": cls._json_safe_value(messages_payload),
            "snapshots": cls._json_safe_value(snapshots_payload),
            "latestSnapshot": cls._json_safe_value(snapshots_payload[0]) if snapshots_payload else None,
            "similarTickets": cls._json_safe_value(similar_tickets),
            "latestLogPull": cls._json_safe_value(latest_log_summary),
            "sourceLogPull": cls._json_safe_value(log_content_payload),
            "mapping": cls._json_safe_value(CamelCaseUtil.transform_result(mapping)),
            "sourceLogPullRecordId": source_log_record_id,
            "sourceLogViewMode": source_log_view_mode,
            "logAnalysisMode": log_options["mode"],
            "logWindowMissingStrategy": log_options["windowMissingStrategy"],
            "logRequestedBeginTime": request_begin_time,
            "logRequestedEndTime": request_end_time,
        }

    @classmethod
    def _build_task_context_snapshot(
        cls,
        context_payload: dict[str, Any],
        request: TicketAiAnalysisRequestModel | None = None,
    ) -> dict[str, Any]:
        """
        构建写入任务表的轻量上下文快照。
        :param context_payload: 完整任务上下文
        :param request: AI分析提交参数
        :return: 轻量上下文快照
        """
        latest_log_pull = context_payload.get("latestLogPull") if isinstance(context_payload, dict) else {}
        source_log_pull = context_payload.get("sourceLogPull") if isinstance(context_payload, dict) else {}
        is_context = isinstance(context_payload, dict)
        ticket_context = context_payload.get("ticket") or {} if is_context else {}
        mapping_context = context_payload.get("mapping") or {} if is_context else {}
        force_refresh = bool(request.force_refresh) if request else bool(context_payload.get("forceRefresh"))
        selected_agent_code = (
            str(request.agent_code or "").strip()
            if request and request.agent_code
            else str(context_payload.get("selectedAgentCode") or "").strip()
        )
        selected_prompt_template_codes = (
            list(request.prompt_template_codes or [])
            if request and request.prompt_template_codes
            else list(context_payload.get("selectedPromptTemplateCodes") or [])
        )
        extra_instruction = (
            str(request.extra_instruction or "").strip()
            if request and request.extra_instruction
            else str(context_payload.get("extraInstruction") or "").strip()
        )
        snapshot: dict[str, Any] = {
            "ticketId": ticket_context.get("ticketId"),
            "projectId": ticket_context.get("projectId"),
            "versionKey": mapping_context.get("versionKey"),
            "sourceLogPullRecordId": context_payload.get("sourceLogPullRecordId") if is_context else None,
            "sourceLogViewMode": context_payload.get("sourceLogViewMode") if is_context else None,
            "logAnalysisMode": context_payload.get("logAnalysisMode") if is_context else None,
            "logWindowMissingStrategy": context_payload.get("logWindowMissingStrategy") if is_context else None,
            "logRequestedBeginTime": context_payload.get("logRequestedBeginTime") if is_context else None,
            "logRequestedEndTime": context_payload.get("logRequestedEndTime") if is_context else None,
            "forceRefresh": force_refresh,
            "selectedAgentCode": selected_agent_code,
            "selectedPromptTemplateCodes": selected_prompt_template_codes,
            "extraInstruction": extra_instruction,
            # 手动触发时用户对"分析完成后回帖工单群话题"的三态选择，终态回帖时读取。
            "aiResultFollowUpOverride": (
                str(request.ai_result_follow_up or "").strip().lower()
                if request
                else str(context_payload.get("aiResultFollowUpOverride") or "").strip().lower()
            ),
        }
        selected_provider_code = (
            str(request.ai_provider_code or "").strip()
            if request and request.ai_provider_code
            else str(context_payload.get("selectedAiProviderCode") or "").strip()
        )
        if selected_provider_code:
            snapshot["selectedAiProviderCode"] = selected_provider_code
            snapshot["selectedAiProviderName"] = (
                str(context_payload.get("selectedAiProviderName") or "").strip() or None
            )
            snapshot["selectedAiProviderPlatform"] = (
                str(context_payload.get("selectedAiProviderPlatform") or "").strip() or None
            )
            snapshot["selectedAiProviderProtocol"] = (
                str(context_payload.get("selectedAiProviderProtocol") or "").strip() or None
            )
            snapshot["selectedWorkerModel"] = str(context_payload.get("selectedWorkerModel") or "").strip() or None
            snapshot["selectedExecutor"] = str(context_payload.get("selectedExecutor") or "").strip() or None

        if isinstance(context_payload.get("promptLayers"), dict):
            snapshot["promptLayers"] = context_payload.get("promptLayers")
        if isinstance(context_payload.get("selectedPromptTemplates"), list):
            snapshot["selectedPromptTemplates"] = context_payload.get("selectedPromptTemplates")
        if isinstance(latest_log_pull, dict) and latest_log_pull:
            snapshot["latestLogPullSummary"] = {
                "id": latest_log_pull.get("id"),
                "status": latest_log_pull.get("status"),
                "statusDesc": latest_log_pull.get("statusDesc"),
                "contentSummary": latest_log_pull.get("contentSummary"),
                "matchedEntryCount": latest_log_pull.get("matchedEntryCount"),
                "archiveEntryCount": latest_log_pull.get("archiveEntryCount"),
                "contentCharCount": latest_log_pull.get("contentCharCount"),
                "contentTruncated": latest_log_pull.get("contentTruncated"),
            }
        if isinstance(source_log_pull, dict) and source_log_pull:
            snapshot["sourceLogPullSummary"] = {
                "recordId": source_log_pull.get("recordId"),
                "viewBeginTime": source_log_pull.get("viewBeginTime"),
                "viewEndTime": source_log_pull.get("viewEndTime"),
                "viewSource": source_log_pull.get("viewSource"),
                "wholeArchiveMode": source_log_pull.get("wholeArchiveMode"),
                "contentSummary": source_log_pull.get("contentSummary"),
                "matchedEntryCount": source_log_pull.get("matchedEntryCount"),
                "archiveEntryCount": source_log_pull.get("archiveEntryCount"),
                "storagePath": source_log_pull.get("storagePath"),
                "commandResultUrl": source_log_pull.get("commandResultUrl"),
                "hasText": bool(str(source_log_pull.get("text") or "").strip()),
            }
        return cls._json_safe_value(snapshot)

    @staticmethod
    def _read_json_file(path: Path) -> dict[str, Any] | None:
        """
        读取 JSON 文件为字典。
        :param path: JSON 文件路径
        :return: 解析后的字典，失败返回 None
        """
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @classmethod
    def _load_workspace_context_payload(
        cls,
        db: Session,
        task: TicketAiAnalysisTask,
        ticket: Ticket,
        mapping: TicketAiRepoMapping,
        workspace_dir: Path,
    ) -> dict[str, Any]:
        """
        加载执行阶段完整上下文，优先读取工作区文件，失败时回退到数据库重建。
        :param db: 数据库会话
        :param task: AI分析任务
        :param ticket: 工单对象
        :param mapping: 仓库映射对象
        :param workspace_dir: 任务工作区目录
        :return: 完整上下文
        """
        context_payload = cls._read_json_file(workspace_dir / "context.json")
        if not context_payload:
            log_record = cls._resolve_log_pull_record(db, task.ticket_id, task.source_log_pull_record_id)
            context_payload = cls._build_context_payload(db, ticket, mapping, log_record)
        compact_context = cls._json_safe_value(task.analysis_context or {})
        if isinstance(compact_context, dict):
            # 用户配置项：始终优先使用紧凑快照中的值（代表用户提交时的原始选择），
            # 避免无 request 重建时被系统默认值覆盖。
            user_config_keys = (
                "logAnalysisMode",
                "logWindowMissingStrategy",
                "logRequestedBeginTime",
                "logRequestedEndTime",
                "forceRefresh",
                "extraInstruction",
                "selectedAgentCode",
                "selectedAiProviderCode",
                "selectedAiProviderName",
                "selectedAiProviderPlatform",
                "selectedAiProviderProtocol",
                "selectedWorkerModel",
                "selectedExecutor",
            )
            for key in user_config_keys:
                compact_val = compact_context.get(key)
                if compact_val not in (None, "", {}):
                    context_payload[key] = compact_val
            # 其他配置项：仅在缺失时从快照补充
            other_keys = (
                "sourceLogPullRecordId",
                "sourceLogViewMode",
                "promptLayers",
            )
            for key in other_keys:
                if key not in context_payload or context_payload.get(key) in (None, "", {}):
                    context_payload[key] = compact_context.get(key)
        return cls._json_safe_value(context_payload)

    @classmethod
    def _build_prompt(
        cls,
        workspace_path: str,
        mapping: TicketAiRepoMapping,
        ticket: Ticket,
        *,
        version_key: str = "",
        prompt_layers: dict[str, Any] | None = None,
        prompt_templates: list[dict[str, Any]] | None = None,
        extra_instruction: str = "",
        log_analysis_mode: str = "digest",
        source_logs_path: str | None = None,
    ) -> str:
        """
        构建 Codex 分析提示词。
        :param workspace_path: 任务工作区路径
        :param mapping: 仓库映射
        :param ticket: 工单对象
        :param prompt_layers: 项目/模块默认提示词分层。
        :param prompt_templates: 选择追加的提示词模板列表。
        :param extra_instruction: 本次提交的额外说明。
        :param log_analysis_mode: 日志分析模式（digest/full_directory/hybrid）。
        :param source_logs_path: Agent 实际读取的原始日志目录；未指定时使用任务目录中的 source_logs。
        :return: 提示词文本
        """
        prompt_layers = prompt_layers or {}
        default_prompt_text = str(prompt_layers.get("defaultPromptText") or "").strip()
        selected_prompt_texts = []
        for template in prompt_templates or []:
            prompt_content = str(template.get("promptContent") or "").strip()
            template_name = str(template.get("templateName") or template.get("templateCode") or "").strip()
            if not prompt_content:
                continue
            selected_prompt_texts.append(
                TicketPromptService._build_prompt_block(
                    f"选择提示词：{template_name}",
                    [prompt_content],
                )
            )
        extra_instruction_text = str(extra_instruction or "").strip()
        resolved_source_logs_path = str(source_logs_path or f"{workspace_path}/source_logs")
        layered_prompt_text = TicketPromptService._join_text(
            [
                default_prompt_text,
                TicketPromptService._join_text(selected_prompt_texts, separator="\n\n"),
                TicketPromptService._build_prompt_block(
                    "本次额外说明",
                    [
                        extra_instruction_text,
                        "额外说明只用于补充本次分析重点，不覆盖系统约束和输出 schema。",
                    ],
                ),
            ],
            separator="\n\n",
        )
        return f"""你是工单自动分析 Worker，请基于当前工作区中的上下文进行根因分析。

当前任务目录:
{workspace_path}

仓库信息:
- 项目: {mapping.project_name}
- 版本: {version_key}
- 仓库地址: {mapping.repo_url}
- 分支: {mapping.branch_name}
- 本地仓库路径: {mapping.local_repo_path}
        - 说明: 如果 Agent 本地配置中提供了本地仓库路径或工作区根目录，则以 Agent 本地配置为准；
          映射中的路径仅保留兼容和审计用途.

{layered_prompt_text}

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
4. 工单不是一次性分析，请结合 messages、snapshots 和 similarTickets：
   - messages 是持续追问和协同排查上下文，必须优先参考最新用户追问。
   - snapshots 是历史 ACR 版本，新的结论需要说明相对上一版的变化。
   - similarTickets 是历史相似工单，若可复用经验，请写入 similar_cases、sop_suggestion、
     owner_suggestion、monitoring_suggestion。
5. 输出严格 JSON，不要输出多余说明文本。不要调用 shell、python 或 PowerShell
   去创建、写入、拼接任何结果文件；尤其不要使用 heredoc（如 `<<EOF`、`@'...'@`）
   写 JSON。直接把最终 JSON 作为最后一条回复输出，系统会自动保存结果文件。
   注意：JSON 字符串值内部的英文双引号必须写成 \" 转义；描述中引用中文术语请使用
   中文引号（“”），不要直接输出未转义的英文双引号，否则结果无法通过解析校验。
6. 结果必须包含以下核心字段，输出严格按 schema 返回：
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
   除上述字段和 schema 中的扩展字段外，**禁止输出任何其他字段**（如 ticket_no、
   merchant_name、version、root_cause_type 等 schema 外字段），多出的字段会导致结果校验失败。
   evidence 必须是字符串数组：每条证据是一个字符串，格式为"来源文件路径:行号: 证据内容摘要"，
   禁止把证据写成 {{source, content}} 之类的 JSON 对象。
7. 如果你能从上下文中推断协同增强信息，可在分析内容里自然体现；服务端会负责把缺省增强字段补为空值。

工单基础信息:
- ticket_id: {ticket.ticket_id}
- ticket_no: {ticket.ticket_no}
- title: {ticket.title}
- description: {ticket.description or ""}
"""

    @classmethod
    def _build_result_schema(cls, ticket: Ticket, mapping: TicketAiRepoMapping, version_key: str) -> dict[str, Any]:
        """
        构建 Codex 输出 JSON Schema。
        :param ticket: 工单对象
        :param mapping: 仓库映射对象
        :return: JSON Schema
        """
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                # BIGINT 在接口和 Agent JSON 中允许按字符串传输，避免超过 JavaScript 安全整数范围。
                "ticket_id": {"type": ["integer", "string"], "default": str(ticket.ticket_id)},
                "project_id": {"type": ["integer", "string", "null"], "default": ticket.project_id},
                "version_key": {"type": ["string", "null"], "default": version_key},
                "repo_url": {"type": ["string", "null"], "default": mapping.repo_url},
                "branch_name": {"type": ["string", "null"], "default": mapping.branch_name},
                "root_cause": {"type": "string", "default": ""},
                "analysis_summary": {"type": "string", "default": ""},
                "related_files": {"type": "array", "items": {"type": "string"}, "default": []},
                "related_functions": {"type": "array", "items": {"type": "string"}, "default": []},
                "fix_suggestion": {"type": "string", "default": ""},
                "confidence": {"type": ["number", "string"], "default": 0},
                "evidence": {"type": "array", "items": {"type": "string"}, "default": []},
                "risk_items": {"type": "array", "items": {"type": "string"}, "default": []},
                "next_steps": {"type": "array", "items": {"type": "string"}, "default": []},
                "symptom": {"type": ["array", "string"], "default": []},
                "investigation_steps": {"type": ["array", "string"], "default": []},
                "prevention_actions": {"type": ["array", "string"], "default": []},
                # 与其他增强字段一致允许 string：模型倾向把历史相似工单写成叙述文字，
                # 仅允许 array 曾导致 AI_WORKER_RESULT_INVALID（如 INC00001894981 分析失败）。
                "similar_cases": {"type": ["array", "string"], "default": []},
                "sop_suggestion": {"type": ["array", "string"], "default": []},
                "owner_suggestion": {"type": "string", "default": ""},
                "monitoring_suggestion": {"type": ["array", "string"], "default": []},
                "needs_human_review": {"type": "boolean", "default": True},
            },
            "required": [
                "ticket_id",
                "project_id",
                "version_key",
                "repo_url",
                "branch_name",
                "root_cause",
                "analysis_summary",
                "related_files",
                "related_functions",
                "fix_suggestion",
                "confidence",
                "evidence",
                "risk_items",
                "next_steps",
            ],
        }

    @classmethod
    def _build_worker_command(
        cls,
        db: Session,
        mapping: TicketAiRepoMapping,
        workspace_dir: Path,
        schema_file: Path,
        result_file: Path,
        *,
        model_override: str | None = None,
        provider_env_overrides: dict[str, str] | None = None,
    ) -> tuple[list[str], Path, int, Path]:
        """
        构建 Codex Worker 命令行。
        :param db: 数据库会话
        :param mapping: 仓库映射对象
        :param workspace_dir: 工作区目录
        :param schema_file: 输出 schema 文件
        :param result_file: 结果文件
        :return: 命令参数、工作目录和超时时间
        """
        settings = cls._resolve_worker_settings(db)
        command_text = str(mapping.worker_command or settings["command"] or cls.DEFAULT_WORKER_COMMAND).strip()
        command_parts = shlex.split(command_text) if command_text else ["codex", "exec"]
        command_parts = cls._resolve_worker_command_parts(command_parts)

        repo_path = Path(mapping.local_repo_path or "").expanduser()
        if not repo_path.is_absolute():
            repo_path = Path(__file__).resolve().parents[4] / repo_path
        if not str(repo_path).strip() or not repo_path.exists():
            repo_path = Path(__file__).resolve().parents[4]
        timeout_sec = int(settings["timeout_sec"] or cls.DEFAULT_WORKER_TIMEOUT)
        worker_model = str(model_override or settings.get("model") or "").strip()
        worker_sandbox = (
            str(settings.get("sandbox") or cls.DEFAULT_WORKER_SANDBOX).strip() or cls.DEFAULT_WORKER_SANDBOX
        )

        command = list(command_parts)
        if worker_model:
            command.extend(["-m", worker_model])
        if worker_sandbox:
            command.extend(["-s", worker_sandbox])
        command.extend(
            [
                "-C",
                str(repo_path),
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_file),
                "--output-last-message",
                str(result_file),
            ]
        )
        return command, repo_path, timeout_sec, cls._prepare_codex_home(workspace_dir, provider_env_overrides)

    @classmethod
    def _execute_worker(
        cls,
        *,
        command: list[str],
        prompt_text: str,
        timeout_sec: int,
        cwd: Path,
        codex_home: Path,
        env_overrides: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """
        执行 Codex Worker 命令。
        :param command: 命令参数
        :param prompt_text: 提示词
        :param timeout_sec: 超时时间
        :param cwd: 工作目录
        :return: 返回码、标准输出和标准错误
        """
        worker_env = os.environ.copy()
        worker_env.update(cls._load_codex_env(codex_home))
        if env_overrides:
            worker_env.update(
                {str(key): str(value) for key, value in env_overrides.items() if key and value is not None}
            )
        worker_env["CODEX_HOME"] = str(codex_home)
        process = subprocess.run(
            command,
            input=prompt_text,
            text=True,
            capture_output=True,
            cwd=str(cwd),
            env=worker_env,
            timeout=max(timeout_sec, 60),
        )
        return process.returncode, process.stdout or "", process.stderr or ""

    @staticmethod
    def _persist_worker_streams(workspace_dir: Path, stdout_text: str | None, stderr_text: str | None) -> None:
        """
        将 Worker 的 stdout 和 stderr 记录到任务工作区，便于后续离线排查。
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
    def _extract_stderr_context(
        stderr_text: str | None,
        keywords: tuple[str, ...] = ("invalid_request_error", "stream disconnected", "error sending request"),
    ) -> str:
        """
        从 stderr 中提取更长的上下文，便于定位上游错误。
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
        for idx, line in enumerate(lines):
            normalized = line.strip()
            lower_line = normalized.lower()
            if any(keyword in lower_line for keyword in lowered_keywords):
                start = max(0, idx - 10)
                end = min(len(lines), idx + 11)
                window = [
                    re.sub(r"\s+", " ", item.strip())
                    for item in lines[start:end]
                    if item.strip() not in {"{", "}", "[", "]"}
                ]
                if window:
                    return " | ".join(window)[:4000]
        tail_lines = [
            re.sub(r"\s+", " ", item.strip()) for item in lines[-20:] if item.strip() not in {"{", "}", "[", "]"}
        ]
        return " | ".join(tail_lines)[:4000] if tail_lines else ""

    @staticmethod
    def _summarize_worker_error(stderr_text: str | None, stdout_text: str | None, default_message: str) -> str:
        """
        提取 Worker 失败摘要，便于数据库回写。
        :param stderr_text: 标准错误
        :param stdout_text: 标准输出
        :param default_message: 默认失败信息
        :return: 失败摘要
        """
        priority_patterns = (
            "invalid_request_error",
            "stream disconnected",
            "error sending request",
            "failed to initialize",
            "request failed",
            "permission denied",
            "access denied",
            "refused",
            "not found",
            "拒绝访问",
            "找不到",
            "错误",
            "failed",
            "error:",
        )
        for raw_text in (stderr_text, stdout_text):
            if not raw_text:
                continue
            lines = [line.rstrip() for line in str(raw_text).splitlines() if line.strip()]
            if not lines:
                continue
            for idx, line in enumerate(lines):
                normalized = line.strip()
                lower_line = normalized.lower()
                if any(pattern.lower() in lower_line for pattern in priority_patterns):
                    start = max(0, idx - 4)
                    end = min(len(lines), idx + 5)
                    window = [
                        re.sub(r"\s+", " ", item.strip())
                        for item in lines[start:end]
                        if item.strip() not in {"{", "}", "[", "]"}
                    ]
                    if window:
                        return " | ".join(window)[:1000]
            tail_lines = [
                re.sub(r"\s+", " ", item.strip()) for item in lines[-5:] if item.strip() not in {"{", "}", "[", "]"}
            ]
            if tail_lines:
                return " | ".join(tail_lines)[:1000]
        return default_message

    @classmethod
    def _normalize_analysis_result(
        cls,
        *,
        result_payload: dict[str, Any],
        ticket: Ticket,
        mapping: TicketAiRepoMapping,
        version_key: str,
    ) -> dict[str, Any]:
        """
        将 AI 输出归一化为工单保存结构。
        :param result_payload: AI 输出结果
        :param ticket: 工单对象
        :param mapping: 仓库映射对象
        :return: 归一化结果
        """
        normalized = dict(result_payload or {})
        # 工单和项目 ID 以服务端实体为准，避免模型把项目名称或字符串描述误写入关联字段。
        normalized["ticket_id"] = ticket.ticket_id
        normalized["project_id"] = ticket.project_id
        normalized.setdefault("version_key", version_key)
        normalized.setdefault("repo_url", mapping.repo_url)
        normalized.setdefault("branch_name", mapping.branch_name)
        normalized.setdefault("root_cause", "")
        normalized.setdefault("analysis_summary", "")
        normalized.setdefault("related_files", [])
        normalized.setdefault("related_functions", [])
        normalized.setdefault("fix_suggestion", "")
        normalized.setdefault("confidence", 0)
        normalized.setdefault("evidence", [])
        normalized.setdefault("risk_items", [])
        normalized.setdefault("next_steps", [])
        normalized.setdefault("symptom", [])
        normalized.setdefault("investigation_steps", [])
        normalized.setdefault("prevention_actions", [])
        normalized.setdefault("similar_cases", [])
        normalized.setdefault("sop_suggestion", [])
        normalized.setdefault("owner_suggestion", "")
        normalized.setdefault("monitoring_suggestion", [])
        normalized.setdefault("needs_human_review", True)
        # 模型可能把增强字段写成叙述字符串而非数组（schema 已放宽为双类型），
        # 这里统一包装为单元素数组，保证下游 RCA 结构化数据和前端拿到稳定类型。
        flexible_fields = (
            "symptom",
            "investigation_steps",
            "prevention_actions",
            "similar_cases",
            "sop_suggestion",
            "monitoring_suggestion",
        )
        for flexible_field in flexible_fields:
            if isinstance(normalized.get(flexible_field), str):
                normalized[flexible_field] = [normalized[flexible_field]] if normalized[flexible_field].strip() else []
        return cls._json_safe_value(normalized)

    @classmethod
    def _build_analysis_request_fingerprint(
        cls,
        *,
        ticket: Ticket,
        mapping: TicketAiRepoMapping,
        version_key: str,
        context_payload: dict[str, Any],
        prompt_template: str,
        schema_payload: dict[str, Any],
        request: TicketAiAnalysisRequestModel,
        task_id: int,
    ) -> str:
        """
        根据会影响分析结果的输入生成稳定请求指纹。
        工单、版本、日志来源、仓库分支、提示词、Provider/模型/执行器和 schema 均纳入指纹；
        强制刷新额外使用当前任务ID，确保明确要求重新分析时不会命中历史成功结果。
        :param ticket: 工单对象
        :param mapping: 仓库映射对象
        :param version_key: 版本标识
        :param context_payload: 分析上下文
        :param prompt_template: 最终提示词
        :param schema_payload: 输出 schema
        :param request: 用户提交参数
        :param task_id: 当前任务ID，仅强制刷新时参与计算
        :return: 64位十六进制请求指纹
        """
        ticket_payload = cls._json_safe_value(CamelCaseUtil.transform_result(ticket))
        if isinstance(ticket_payload, dict):
            for field_name in (
                "aiAnalysis",
                "ai_analysis",
                "updateTime",
                "update_time",
                "updateBy",
                "update_by",
            ):
                ticket_payload.pop(field_name, None)
        fingerprint_context = cls._build_fingerprint_context(context_payload)
        material: dict[str, Any] = {
            "ticket": ticket_payload,
            "version_key": version_key,
            "mapping": {
                "mapping_id": mapping.mapping_id,
                "project_id": mapping.project_id,
                "repo_url": mapping.repo_url,
                "branch_name": mapping.branch_name,
                "local_repo_path": mapping.local_repo_path,
            },
            "context": fingerprint_context,
            "prompt_template": prompt_template,
            "schema": cls._json_safe_value(schema_payload),
            "provider": {
                "provider_code": context_payload.get("selectedAiProviderCode"),
                "provider_platform": context_payload.get("selectedAiProviderPlatform"),
                "provider_protocol": context_payload.get("selectedAiProviderProtocol"),
                "model": context_payload.get("selectedWorkerModel"),
                "executor": context_payload.get("selectedExecutor"),
                "agent_code": context_payload.get("selectedAgentCode") or request.agent_code,
            },
            "options": {
                "resume": bool(request.resume),
                "log_analysis_mode": context_payload.get("logAnalysisMode"),
                "log_window_missing_strategy": context_payload.get("logWindowMissingStrategy"),
            },
        }
        if request.force_refresh:
            material["force_refresh_task_id"] = task_id
        canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _build_fingerprint_context(cls, context_payload: dict[str, Any]) -> dict[str, Any]:
        """
        构建用于幂等指纹的上下文副本，排除本次 AI 分析产生的回写数据。
        用户消息、非 AI 历史快照和业务事件仍保留，后续人工追问会自然形成新指纹。
        :param context_payload: 完整 AI 分析上下文
        :return: 不包含 AI 自身回写数据的上下文副本
        """
        context = cls._json_safe_value(context_payload)
        if not isinstance(context, dict):
            return {}
        ticket_context = context.get("ticket")
        if isinstance(ticket_context, dict):
            for field_name in (
                "aiAnalysis",
                "ai_analysis",
                "updateTime",
                "update_time",
                "updateBy",
                "update_by",
            ):
                ticket_context.pop(field_name, None)
        messages = context.get("messages")
        if isinstance(messages, list):
            context["messages"] = [
                item
                for item in messages
                if not (
                    isinstance(item, dict)
                    and (
                        str(item.get("referenceType") or item.get("reference_type") or "").lower() == "ai_analysis"
                        or (
                            str(item.get("role") or "").lower() == "ai"
                            and str(item.get("messageType") or item.get("message_type") or "").lower() == "analysis"
                        )
                    )
                )
            ]
        snapshots = context.get("snapshots")
        if isinstance(snapshots, list):
            context["snapshots"] = [
                item
                for item in snapshots
                if not (
                    isinstance(item, dict)
                    and str(item.get("sourceType") or item.get("source_type") or "").lower() == "ai_analysis"
                )
            ]
        timeline = context.get("timeline")
        if isinstance(timeline, list):
            context["timeline"] = [
                item
                for item in timeline
                if not (
                    isinstance(item, dict)
                    and str(item.get("eventType") or item.get("event_type") or "").upper()
                    in {TicketEventType.AI_ANALYZED.value, TicketEventType.ANALYSIS.value}
                )
            ]
        latest_snapshot = context.get("latestSnapshot")
        if (
            isinstance(latest_snapshot, dict)
            and str(latest_snapshot.get("sourceType") or latest_snapshot.get("source_type") or "").lower()
            == "ai_analysis"
        ):
            context["latestSnapshot"] = None
        return context

    @classmethod
    def _validate_analysis_result_schema(cls, payload: Any, schema: dict[str, Any]) -> bool:
        """
        校验 Agent 返回的结构化分析结果。
        工单分析 schema 只使用基础 JSON Schema 类型、required、properties、items 和
        additionalProperties，服务端在归一化前再次校验，避免错误结果被补默认值后误写回。
        :param payload: Agent 返回结果
        :param schema: 本次任务的输出 schema
        :return: 是否通过校验
        """
        return not cls._collect_schema_violations(payload, schema)

    @classmethod
    def _collect_schema_violations(cls, payload: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
        """
        收集结构化分析结果相对输出 Schema 的全部违规路径，用于失败诊断。
        判定规则与 _validate_analysis_result_schema 完全一致，只是把违规点以
        `字段路径: 期望类型/实际类型` 的形式返回，便于直接写入日志和 error_message。
        :param payload: Agent 返回结果
        :param schema: 本次任务的输出 schema
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
                cls._collect_schema_violations(payload, {**schema, "type": item}, path) for item in expected_type
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
            violations.extend(f"{path}.{field}: required 字段缺失" for field in required if field not in payload)
            if schema.get("additionalProperties") is False:
                violations.extend(
                    f"{path}.{key}: additionalProperties 不允许的额外字段" for key in payload if key not in properties
                )
            for key, child_schema in properties.items():
                if key in payload:
                    violations.extend(cls._collect_schema_violations(payload[key], child_schema, f"{path}.{key}"))
            return violations
        if expected_type == "array":
            if not isinstance(payload, list):
                return [f"{path}: 期望 array，实际 {_type_name(payload)}"]
            violations = []
            items_schema = schema.get("items") or {}
            for index, item in enumerate(payload):
                violations.extend(cls._collect_schema_violations(item, items_schema, f"{path}[{index}]"))
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
    def _create_rca_from_result(
        cls,
        db: Session,
        ticket: Ticket,
        result_payload: dict[str, Any],
        current_user: CurrentUserModel | None = None,
    ) -> TicketRca:
        """
        根据 AI 分析结果生成/更新 RCA。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param result_payload: AI 分析结果
        :param current_user: 当前用户
        :return: RCA 对象
        """
        now = datetime.now()
        return TicketDao.upsert_rca(
            db,
            TicketRca(
                ticket_id=ticket.ticket_id,
                symptom=(
                    "\n".join(result_payload.get("symptom") or [])
                    or ticket.description
                    or result_payload.get("analysis_summary")
                    or ""
                ),
                root_cause_category="AI分析",
                root_cause_detail=str(result_payload.get("root_cause") or ""),
                trigger_reason=str(result_payload.get("analysis_summary") or ""),
                impact_scope="",
                reproduce_steps="",
                investigation_process=(
                    "\n".join(result_payload.get("investigation_steps") or [])
                    or str(result_payload.get("analysis_summary") or "")
                ),
                fix_solution=str(result_payload.get("fix_suggestion") or ""),
                verify_method="",
                prevention_solution="\n".join(
                    result_payload.get("prevention_actions") or result_payload.get("next_steps") or []
                ),
                structured_data=cls._json_safe_value(result_payload),
                created_by_id=cls._user_id(current_user) if current_user else None,
                created_by_name=cls._user_name(current_user) if current_user else "system",
                create_time=now,
                update_time=now,
            ),
        )

    @classmethod
    def _persist_success_result(
        cls,
        db: Session,
        task: TicketAiAnalysisTask,
        ticket: Ticket,
        result_payload: dict[str, Any],
        raw_output: str,
        current_user: CurrentUserModel | None = None,
    ) -> None:
        """
        持久化 AI 分析成功结果。
        :param db: 数据库会话
        :param task: 任务对象
        :param ticket: 工单对象
        :param result_payload: AI结果
        :param raw_output: 原始输出
        :param current_user: 当前用户
        :return: 无
        """
        now = datetime.now()
        TicketDao.update_ticket(
            db,
            ticket.ticket_id,
            {
                "ai_analysis": cls._json_safe_value(result_payload),
                "update_by": cls._user_name(current_user) if current_user else "system",
                "update_time": now,
            },
        )
        ai_message = TicketDao.add_message(
            db,
            TicketMessage(
                ticket_id=ticket.ticket_id,
                role="ai",
                message_type="analysis",
                content=str(result_payload.get("analysis_summary") or result_payload.get("root_cause") or "AI分析完成"),
                attachments=cls._json_safe_value(result_payload),
                reference_type="ai_analysis",
                reference_id=task.task_id,
                created_by_id=cls._user_id(current_user) if current_user else None,
                created_by_name=cls._user_name(current_user) if current_user else "system",
                create_time=now,
            ),
        )
        rca = cls._create_rca_from_result(db, ticket, result_payload, current_user)
        TicketSimilarityCaseService.upsert_draft(db, ticket, rca=rca, source="ai")
        TicketDao.add_snapshot(
            db,
            TicketSnapshot(
                ticket_id=ticket.ticket_id,
                version=TicketDao.get_next_snapshot_version(db, ticket.ticket_id),
                summary=str(result_payload.get("analysis_summary") or ""),
                root_cause=str(result_payload.get("root_cause") or ""),
                solution=str(result_payload.get("fix_suggestion") or ""),
                prevention="\n".join(
                    result_payload.get("prevention_actions") or result_payload.get("next_steps") or []
                ),
                risk="\n".join(result_payload.get("risk_items") or []),
                owner=cls._truncate_snapshot_owner(result_payload.get("owner_suggestion")),
                source_type="ai_analysis",
                source_id=task.task_id,
                structured_data=cls._json_safe_value(result_payload),
                created_by_id=cls._user_id(current_user) if current_user else None,
                created_by_name=cls._user_name(current_user) if current_user else "system",
                create_time=now,
            ),
        )
        TicketDao.add_event(
            db,
            TicketEvent(
                ticket_id=ticket.ticket_id,
                event_type=TicketEventType.AI_ANALYZED.value,
                operator_id=cls._user_id(current_user) if current_user else None,
                operator_name=cls._user_name(current_user) if current_user else "system",
                content="AI分析完成",
                event_data={
                    "task_id": task.task_id,
                    "version_id": task.version_id,
                    "repo_url": task.repo_url,
                    "branch_name": task.branch_name,
                    "analysis_result": cls._json_safe_value(result_payload),
                    "raw_output": raw_output[:5000],
                    "message_id": ai_message.id,
                },
                create_time=now,
            ),
        )

    @classmethod
    def _finish_duplicate_task_without_writeback(
        cls,
        db: Session,
        task: TicketAiAnalysisTask,
        winner: TicketAiAnalysisTask,
        audit_execution_id: int | None = None,
    ) -> None:
        """
        将并发重复任务标记为取消，不重复写入工单消息、RCA、快照和事件。
        :param db: 数据库会话
        :param task: 当前重复任务
        :param winner: 已成功占用指纹的任务
        :param audit_execution_id: 当前任务对应的审计记录ID
        :return: 无
        """
        cls._mark_task_status(
            db,
            task.task_id,
            status=TicketAiAnalysisStatus.CANCELED.value,
            status_desc="重复请求已复用成功结果",
            error_message=f"相同分析请求已由任务 {winner.task_id} 成功完成",
            finished_at=datetime.now(),
            command_line=task.command_line or "",
        )
        if audit_execution_id:
            cls._update_execution_record(
                db,
                audit_execution_id,
                status="canceled",
                error_message=f"相同分析请求已由任务 {winner.task_id} 成功完成",
            )
        db.commit()
        logger.info(
            f"工单 AI 分析并发重复任务跳过结果写回: task_id={task.task_id}, winner_task_id={winner.task_id}, "
            f"request_fingerprint={task.request_fingerprint}"
        )

    @classmethod
    def _mark_task_status(
        cls,
        db: Session,
        task_id: int,
        *,
        status: str,
        status_desc: str,
        error_code: str | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        analysis_result: dict[str, Any] | None = None,
        raw_output: str | None = None,
        command_line: str | None = None,
        input_token_count: int | None = None,
        output_token_count: int | None = None,
        total_token_count: int | None = None,
        active_lock_fingerprint: str | None = None,
    ) -> None:
        """
        更新 AI 分析任务状态。
        :param db: 数据库会话
        :param task_id: 任务ID
        :param status: 任务状态
        :param status_desc: 状态描述
        :param error_code: 稳定的业务错误码
        :param error_message: 错误信息
        :param started_at: 开始时间
        :param finished_at: 结束时间
        :param analysis_result: 分析结果
        :param raw_output: 原始输出
        :param command_line: 执行命令
        :param active_lock_fingerprint: 活跃锁指纹；活跃态（created/running）传请求指纹占锁，
            终态无需传（自动清锁）。占锁冲突由唯一索引兜底，并发同指纹任务写入失败。
        :return: 无
        """
        update_data = {
            "status": status,
            "status_desc": status_desc,
            "error_code": error_code,
            "error_message": error_message,
            "started_at": started_at,
            "finished_at": finished_at,
            # 数据库字段 command_line 为非空字段；历史任务恢复时可能没有执行命令，
            # 此时统一写入空字符串，避免批量更新显式写入 NULL 导致启动失败。
            "command_line": command_line if command_line is not None else "",
            "update_time": datetime.now(),
        }
        if status != TicketAiAnalysisStatus.SUCCESS.value:
            update_data["success_fingerprint"] = None
        # 活跃锁维护：终态释放；活跃态（含恢复等待 pending_recovery）按调用方传入的指纹占锁
        # （未传则同样释放，兼容无指纹的历史任务）。并发同指纹占锁冲突由唯一索引兜底。
        if status in (
            TicketAiAnalysisStatus.CREATED.value,
            TicketAiAnalysisStatus.RUNNING.value,
            TicketAiAnalysisStatus.PENDING_RECOVERY.value,
        ):
            update_data["active_lock"] = active_lock_fingerprint
        else:
            update_data["active_lock"] = None
        if analysis_result is not None:
            update_data["analysis_result"] = analysis_result
        if raw_output is not None:
            update_data["raw_output"] = raw_output
        if input_token_count is not None:
            update_data["input_token_count"] = input_token_count
        if output_token_count is not None:
            update_data["output_token_count"] = output_token_count
        if total_token_count is not None:
            update_data["total_token_count"] = total_token_count
        TicketAiDao.update_task(db, task_id, update_data)

    @classmethod
    def ensure_pending_task_support(cls) -> None:
        """
        保持与启动恢复逻辑兼容的说明占位。
        :return: 无
        """
        return None

    @classmethod
    def create_analysis_task_services(
        cls,
        db: Session,
        ticket_id: int,
        request: TicketAiAnalysisRequestModel,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """
        创建工单 AI 分析任务。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param request: AI分析提交参数
        :param current_user: 当前登录用户
        :return: 创建结果
        """
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        version_id, log_record = cls._ensure_version_id_for_analysis(db, ticket, request)
        if request.log_pull_record_id and not log_record:
            return CrudResponseModel(
                is_success=False,
                message="选择的日志记录不存在、不属于当前工单，或尚未下载成功",
            )
        if not version_id:
            return CrudResponseModel(
                is_success=False,
                message="未获取到版本中心记录，请先选择版本或确认日志中包含版本号",
            )
        mapping = cls._resolve_mapping(db, ticket, request)
        if not mapping:
            return CrudResponseModel(is_success=False, message="未找到可用的项目版本仓库映射，请先维护映射配置")
        version_key = cls._get_version_key(db, version_id)
        context_payload = cls._build_context_payload(db, ticket, mapping, log_record, request)
        prompt_layers = TicketPromptService.resolve_prompt_layers(db, ticket)
        selected_prompt_templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(
            db, request.prompt_template_codes
        )
        context_payload["forceRefresh"] = bool(request.force_refresh)
        if request.prompt_template_codes:
            context_payload["selectedPromptTemplateCodes"] = request.prompt_template_codes
        if selected_prompt_templates:
            context_payload["selectedPromptTemplates"] = selected_prompt_templates
        selected_provider = None
        selected_provider_code = str(request.ai_provider_code or "").strip()
        selected_executor = None
        if selected_provider_code:
            selected_provider = cls._resolve_ai_provider(db, selected_provider_code)
            if not selected_provider:
                return CrudResponseModel(is_success=False, message="未找到可用的AI Provider配置")
            selected_executor = cls._resolve_executor(selected_provider, request.executor)
            try:
                AiProviderCapabilityService.require_provider_eligibility(
                    selected_provider,
                    usage="ticket_analysis_worker",
                    executor=selected_executor,
                )
            except ValueError as exc:
                return CrudResponseModel(is_success=False, message=str(exc))
            context_payload["selectedAiProviderCode"] = selected_provider.provider_code
            context_payload["selectedAiProviderName"] = selected_provider.provider_name
            context_payload["selectedAiProviderPlatform"] = selected_provider.platform_code
            context_payload["selectedAiProviderProtocol"] = selected_provider.api_protocol
            requested_model_name = str(request.ai_model_name or "").strip()
            if requested_model_name:
                selected_model = AiProviderModelDao.get_provider_model_by_id(
                    db, selected_provider.provider_id, requested_model_name
                )
                if not selected_model or not bool(selected_model.enabled):
                    return CrudResponseModel(
                        is_success=False,
                        message=f"模型[{requested_model_name}]不属于当前Provider的启用模型目录",
                    )
            context_payload["selectedWorkerModel"] = requested_model_name or selected_provider.default_model
            context_payload["selectedExecutor"] = selected_executor
            # 判断是否需要 resume
            resume_from_workspace_path: str | None = None
            if request.resume and selected_provider_code:
                last_task = TicketAiDao.get_last_successful_task_by_ticket(db, ticket.ticket_id)
                if last_task:
                    last_ctx = last_task.analysis_context or {}
                    last_provider = str(last_ctx.get("selectedAiProviderCode") or "").strip()
                    last_provider_protocol = str(last_ctx.get("selectedAiProviderProtocol") or "").strip()
                    current_provider_protocol = str(selected_provider.api_protocol or "").strip().lower()
                    if last_provider == selected_provider_code and last_provider_protocol == current_provider_protocol:
                        last_ws = str(getattr(last_task, "workspace_path", "") or "").strip()
                        if last_ws:
                            resume_from_workspace_path = last_ws
                            logger.info(
                                f"工单 AI 分析 resume: ticket_id={ticket.ticket_id}, "
                                f"provider={selected_provider_code}, protocol={current_provider_protocol}, "
                                f"from={resume_from_workspace_path}"
                            )
            if not request.agent_code and str(selected_provider.preferred_agent_code or "").strip():
                provider_agent_code = str(selected_provider.preferred_agent_code).strip()
                context_payload["selectedAgentCode"] = (
                    provider_agent_code if AgentDao.get_agent_by_code(db, provider_agent_code) else ""
                )
        if request.agent_code:
            context_payload["selectedAgentCode"] = request.agent_code
        if str(request.extra_instruction or "").strip():
            context_payload["extraInstruction"] = str(request.extra_instruction).strip()
        context_payload["promptLayers"] = prompt_layers
        schema_payload = cls._build_result_schema(ticket, mapping, version_key)
        workspace_root = cls._resolve_workspace_root(db)
        task_id = snowIdWorker.get_id()
        workspace_dir = workspace_root / f"ticket_{ticket.ticket_id}" / f"task_{task_id}"
        task_context_payload = cls._build_task_context_snapshot(context_payload, request)

        prompt_template = cls._build_prompt(
            "{workspace_path}",
            mapping,
            ticket,
            version_key=version_key,
            prompt_layers=prompt_layers,
            prompt_templates=selected_prompt_templates,
            extra_instruction=request.extra_instruction or "",
            log_analysis_mode=str(context_payload.get("logAnalysisMode") or "digest"),
            source_logs_path="{source_logs_path}",
        )
        # 最终提示词包含系统约束和用户选择，必须以最终文本参与指纹计算。
        request_fingerprint = cls._build_analysis_request_fingerprint(
            ticket=ticket,
            mapping=mapping,
            version_key=version_key,
            context_payload=context_payload,
            prompt_template=prompt_template,
            schema_payload=schema_payload,
            request=request,
            task_id=task_id,
        )
        task_context_payload["requestFingerprint"] = request_fingerprint

        if not request.force_refresh:
            successful_task = TicketAiDao.get_successful_task_by_request_fingerprint(db, request_fingerprint)
            if successful_task:
                logger.info(
                    f"工单 AI 分析命中成功指纹，复用历史结果: ticket_id={ticket_id}, "
                    f"request_fingerprint={request_fingerprint}, task_id={successful_task.task_id}"
                )
                cls._record_reuse_event(
                    db,
                    ticket=ticket,
                    reused_task=successful_task,
                    request_fingerprint=request_fingerprint,
                    current_user=current_user,
                )
                return CrudResponseModel(
                    is_success=True,
                    message="AI分析请求已命中，直接返回历史成功结果",
                    result=CamelCaseUtil.transform_result(successful_task),
                    outcome="reused",
                )
            active_task = TicketAiDao.get_active_task_by_request_fingerprint(db, request_fingerprint)
            if active_task:
                logger.info(
                    f"工单 AI 分析命中执行中的请求，复用任务: ticket_id={ticket_id}, "
                    f"request_fingerprint={request_fingerprint}, task_id={active_task.task_id}"
                )
                return CrudResponseModel(
                    is_success=True,
                    message="相同AI分析请求已在执行中，直接返回原任务",
                    result=CamelCaseUtil.transform_result(active_task),
                    outcome="attached",
                )

        # 幂等命中不需要 Agent 在线；只有确实要创建新任务时才校验连接状态。
        agent_available, agent_error_message, resolved_agent_code = cls._validate_agent_connected(
            db, str(context_payload.get("selectedAgentCode") or "").strip()
        )
        if not agent_available:
            return CrudResponseModel(is_success=False, message=agent_error_message)
        context_payload["selectedAgentCode"] = resolved_agent_code
        task_context_payload = cls._build_task_context_snapshot(context_payload, request)
        task_context_payload["requestFingerprint"] = request_fingerprint

        now = datetime.now()
        audit_execution = AiTaskExecutionDao.add_ai_task_execution_dao(
            db,
            cls._build_execution_payload(
                task_type="ticket_ai_analysis",
                task_name="工单AI分析",
                source_type="ticket",
                source_id=ticket.ticket_id,
                source_ref=ticket.ticket_no or str(ticket.ticket_id),
                provider_code=(
                    selected_provider.provider_code if selected_provider else (selected_provider_code or None)
                ),
                model_name=requested_model_name or (selected_provider.default_model if selected_provider else None),
                base_url=(str(selected_provider.base_url or "").strip() or None) if selected_provider else None,
                request_payload={
                    "task_id": task_id,
                    "ticket_id": ticket.ticket_id,
                    "version_id": version_id,
                    "mapping_id": mapping.mapping_id,
                    "agent_code": context_payload.get("selectedAgentCode"),
                    "source_log_pull_record_id": context_payload.get("sourceLogPullRecordId"),
                    "prompt_template_codes": list(request.prompt_template_codes or []),
                },
                status="pending",
                created_by_id=cls._user_id(current_user),
                created_by_name=cls._user_name(current_user),
            ),
        )
        task = TicketAiAnalysisTask(
            task_id=task_id,
            ticket_id=ticket.ticket_id,
            project_id=ticket.project_id,
            mapping_id=mapping.mapping_id,
            version_id=version_id,
            project_name=cls._resolve_project_name(db, ticket.project_id),
            repo_url=mapping.repo_url,
            branch_name=mapping.branch_name,
            local_repo_path=mapping.local_repo_path,
            workspace_root=str(workspace_root),
            workspace_path=str(workspace_dir),
            prompt_path=str(workspace_dir / "prompt.txt"),
            result_path=str(workspace_dir / "result.json"),
            command_line="",
            status=TicketAiAnalysisStatus.CREATED.value,
            status_desc="待执行",
            error_message=None,
            prompt_text=prompt_template,
            raw_output="",
            analysis_result=None,
            analysis_context=task_context_payload,
            audit_execution_id=audit_execution.execution_id,
            source_log_pull_record_id=context_payload.get("sourceLogPullRecordId"),
            source_log_view_mode=str(context_payload.get("sourceLogViewMode") or "stored"),
            request_fingerprint=request_fingerprint,
            success_fingerprint=None,
            # 新任务即为活跃任务：直接占活跃锁，同指纹并发创建由唯一索引兜底。
            active_lock=request_fingerprint,
            submitted_by_id=cls._user_id(current_user),
            submitted_by_name=cls._user_name(current_user),
            create_by=cls._user_name(current_user),  # type: ignore[arg-type]
            update_by=cls._user_name(current_user),  # type: ignore[arg-type]
            create_time=now,
            update_time=now,
        )
        try:
            cls._mark_repo_default_if_needed(db, mapping)
            TicketAiDao.add_task(db, task)
            # 实际创建新任务时，把用户本次分析的重点说明（追问内容）写入消息流，
            # 供 AI 分析记录区完整展示“我的追问 → AI分析”链路。
            # 协同消息链路已提前写入 question 消息（skip_question_message=True），此处不再重复。
            extra_instruction_text = str(request.extra_instruction or "").strip()
            if not request.skip_question_message and extra_instruction_text:
                TicketDao.add_message(
                    db,
                    TicketMessage(
                        ticket_id=ticket.ticket_id,
                        role="user",
                        message_type="question",
                        content=extra_instruction_text,
                        reference_type="ai_analysis",
                        reference_id=task.task_id,
                        created_by_id=cls._user_id(current_user),
                        created_by_name=cls._user_name(current_user) or "system",
                        create_time=now,
                    ),
                )
            TicketDao.add_event(
                db,
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=TicketEventType.ANALYSIS.value,
                    operator_id=cls._user_id(current_user),
                    operator_name=cls._user_name(current_user),
                    content="提交AI分析任务",
                    event_data={
                        "task_id": task.task_id,
                        "mapping_id": mapping.mapping_id,
                        "version_id": version_id,
                        "repo_url": mapping.repo_url,
                        "branch_name": mapping.branch_name,
                        "agent_code": request.agent_code or None,
                        "ai_provider_code": selected_provider.provider_code if selected_provider else None,
                    },
                    create_time=now,
                ),
            )
            db.commit()
            cls.queue_task(task.task_id)
            result = CamelCaseUtil.transform_result(task)
            return CrudResponseModel(is_success=True, message="AI分析任务已提交", result=result, outcome="created")
        except IntegrityError:
            # 并发提交同一指纹：活跃锁唯一索引冲突。回滚后按幂等语义返回原活跃任务。
            db.rollback()
            active_task = TicketAiDao.get_active_task_by_request_fingerprint(db, request_fingerprint)
            if active_task:
                logger.info(
                    f"工单 AI 分析并发提交命中活跃锁，复用原任务: request_fingerprint={request_fingerprint}, "
                    f"task_id={active_task.task_id}"
                )
                return CrudResponseModel(
                    is_success=True,
                    message="相同AI分析请求已在执行中，直接返回原任务",
                    result=CamelCaseUtil.transform_result(active_task),
                    outcome="attached",
                )
            raise
        except Exception:
            db.rollback()
            raise

    @classmethod
    def retry_analysis_task_services(
        cls,
        db: Session,
        ticket_id: int,
        task_id: int,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """
        重新提交指定任务ID的 AI 分析任务。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param task_id: 任务ID
        :param current_user: 当前登录用户
        :return: 重试结果
        """
        task = TicketAiDao.get_task_by_id(db, task_id)
        if not task or task.ticket_id != ticket_id:
            return CrudResponseModel(is_success=False, message="AI分析任务不存在")
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="AI分析任务不存在")
        if task.status == TicketAiAnalysisStatus.PENDING_RECOVERY.value:
            # 恢复等待中的任务不允许重试：补交结果随时可能到达并自动写回，
            # 重新派发会与客户端仍在执行的 Worker 冲突；需要立即重跑请先取消。
            return CrudResponseModel(
                is_success=False,
                message="任务正在等待 Agent 补交结果自动恢复，请稍候；如需立即重新执行请先取消任务",
                result=CamelCaseUtil.transform_result(task),
            )
        if task.status == TicketAiAnalysisStatus.SUCCESS.value and task.analysis_result:
            cls._record_reuse_event(
                db,
                ticket=ticket,
                reused_task=task,
                request_fingerprint=str(getattr(task, "request_fingerprint", "") or ""),
                current_user=current_user,
            )
            return CrudResponseModel(
                is_success=True,
                message="AI分析任务已完成，直接返回历史结果",
                result=CamelCaseUtil.transform_result(task),
                outcome="reused",
            )
        request_fingerprint = str(getattr(task, "request_fingerprint", "") or "").strip()
        if request_fingerprint:
            successful_task = TicketAiDao.get_successful_task_by_request_fingerprint(db, request_fingerprint)
            if successful_task and successful_task.task_id != task.task_id:
                logger.info(
                    f"工单 AI 分析重试命中成功指纹，复用历史结果: ticket_id={ticket_id}, "
                    f"request_fingerprint={request_fingerprint}, task_id={successful_task.task_id}"
                )
                cls._record_reuse_event(
                    db,
                    ticket=ticket,
                    reused_task=successful_task,
                    request_fingerprint=request_fingerprint,
                    current_user=current_user,
                )
                return CrudResponseModel(
                    is_success=True,
                    message="AI分析请求已命中，直接返回历史成功结果",
                    result=CamelCaseUtil.transform_result(successful_task),
                    outcome="reused",
                )
            active_task = TicketAiDao.get_active_task_by_request_fingerprint(db, request_fingerprint)
            if active_task and active_task.task_id != task.task_id:
                return CrudResponseModel(
                    is_success=True,
                    message="相同AI分析请求已在执行中，直接返回原任务",
                    result=CamelCaseUtil.transform_result(active_task),
                    outcome="attached",
                )
        with cls._executor_lock:
            if task_id in cls._active_task_ids:
                return CrudResponseModel(is_success=False, message="当前AI分析任务正在执行中，请稍后重试")
        now = datetime.now()
        update_data: dict[str, Any] = {
            "update_by": cls._user_name(current_user),
            "update_time": now,
        }
        new_audit_execution_id: int | None = None
        if task.status in (TicketAiAnalysisStatus.FAILED.value, TicketAiAnalysisStatus.CANCELED.value):
            # 重试=一次新的真实调用尝试：新建独立审计记录并关联到任务，
            # 原审计记录保持终态不可变，历次尝试的 token 与失败原因各自可追溯。
            prior_audit_id = getattr(task, "audit_execution_id", None)
            prior_attempt_no = cls._resolve_task_attempt_no(task)
            new_audit_execution = AiTaskExecutionDao.add_ai_task_execution_dao(
                db,
                cls._build_execution_payload(
                    task_type="ticket_ai_analysis",
                    task_name="工单AI分析",
                    source_type="ticket",
                    source_id=task.ticket_id,
                    # 来源引用与首次创建保持同一口径：优先业务工单号，工单号缺失时才回退系统ID，
                    # 避免重试审计的来源引用从 INC 编号变成纯数字 ticket_id。
                    source_ref=str(getattr(ticket, "ticket_no", "") or task.ticket_id),
                    provider_code=cls._resolve_task_provider_code(task),
                    model_name=cls._resolve_task_model_name(task),
                    request_payload={
                        "task_id": task.task_id,
                        "ticket_id": task.ticket_id,
                        "version_id": task.version_id,
                        "mapping_id": task.mapping_id,
                        "request_fingerprint": request_fingerprint or None,
                        "attempt_of_task_id": task.task_id,
                        "attempt_no": prior_attempt_no + 1,
                        "attempt_source": "retry",
                        "prior_audit_execution_id": prior_audit_id,
                    },
                    status="pending",
                    created_by_id=cls._user_id(current_user),
                    created_by_name=cls._user_name(current_user),
                ),
            )
            new_audit_execution_id = int(new_audit_execution.execution_id)
            update_data.update(
                {
                    "status": TicketAiAnalysisStatus.CREATED.value,
                    "status_desc": "待重试",
                    "error_message": None,
                    "started_at": None,
                    "finished_at": None,
                    "success_fingerprint": None,
                    "audit_execution_id": new_audit_execution_id,
                }
            )
        try:
            if update_data:
                TicketAiDao.update_task(db, task_id, update_data)
            TicketDao.add_event(
                db,
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.ANALYSIS.value,
                    operator_id=cls._user_id(current_user),
                    operator_name=cls._user_name(current_user),
                    content="重试AI分析任务",
                    event_data={
                        "task_id": task.task_id,
                        "origin_status": task.status,
                        "version_id": task.version_id,
                        "repo_url": task.repo_url,
                        "branch_name": task.branch_name,
                    },
                    create_time=now,
                ),
            )
            db.commit()
            cls.queue_task(task_id)
            return CrudResponseModel(
                is_success=True,
                message="AI分析任务已重新提交",
                result=CamelCaseUtil.transform_result(TicketAiDao.get_task_by_id(db, task_id) or task),
                outcome="retried",
            )
        except Exception:
            db.rollback()
            raise

    @classmethod
    def cancel_analysis_task_services(
        cls,
        db: Session,
        ticket_id: int,
        task_id: int,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """
        协作式取消指定 AI 分析任务。

        只允许取消 created/running/pending_recovery 任务（终态任务无需取消，直接返回当前状态）。
        数据库状态先落为 canceled 并写审计与工单事件；执行中的任务再向 Agent
        发送取消通知，Agent 在 Worker 前后检查点感知后放弃继续执行/回传。
        Worker 若已完成，迟到结果由"回传后重读状态"逻辑丢弃写回（不覆盖取消态）。
        恢复等待中的任务取消后同样进入终态，后续补交的迟到结果不再写回。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param task_id: 任务ID
        :param current_user: 当前登录用户
        :return: 取消结果
        """
        task = TicketAiDao.get_task_by_id(db, task_id)
        if not task or task.ticket_id != ticket_id:
            return CrudResponseModel(is_success=False, message="AI分析任务不存在")
        if task.status not in (
            TicketAiAnalysisStatus.CREATED.value,
            TicketAiAnalysisStatus.RUNNING.value,
            TicketAiAnalysisStatus.PENDING_RECOVERY.value,
        ):
            return CrudResponseModel(
                is_success=True,
                message="任务已结束，无需取消",
                result=CamelCaseUtil.transform_result(task),
            )
        now = datetime.now()
        notify_agent_code = str((task.analysis_context or {}).get("selectedAgentCode") or "").strip() if isinstance(
            task.analysis_context, dict
        ) else ""
        if not notify_agent_code:
            notify_agent_code = cls._resolve_agent_code(db, None)
        cls._mark_task_status(
            db,
            task_id,
            status=TicketAiAnalysisStatus.CANCELED.value,
            status_desc="用户取消",
            error_message=f"任务由 {cls._user_name(current_user)} 手动取消",
            finished_at=now,
            command_line=task.command_line or "",
        )
        audit_execution_id = getattr(task, "audit_execution_id", None)
        cls._update_execution_record(
            db,
            audit_execution_id,
            status="canceled",
            error_message=f"任务由 {cls._user_name(current_user)} 手动取消",
        )
        TicketDao.add_event(
            db,
            TicketEvent(
                ticket_id=ticket_id,
                event_type=TicketEventType.ANALYSIS.value,
                operator_id=cls._user_id(current_user),
                operator_name=cls._user_name(current_user),
                content="取消AI分析任务",
                event_data={
                    "task_id": task.task_id,
                    "origin_status": task.status,
                    "version_id": task.version_id,
                },
                create_time=now,
            ),
        )
        db.commit()
        logger.info(
            f"工单 AI 分析任务已取消: task_id={task_id}, ticket_id={ticket_id}, operator={cls._user_name(current_user)}"
        )
        # 执行中的任务向 Agent 发送取消通知（协作式：Agent 尽力停止 Worker，
        # 通知失败不影响取消结果，Worker 迟到结果会被服务端丢弃写回）。
        if task.status == TicketAiAnalysisStatus.RUNNING.value and notify_agent_code:
            cls._notify_agent_task_canceled(notify_agent_code, task_id)
        return CrudResponseModel(
            is_success=True,
            message="AI分析任务已取消",
            result=CamelCaseUtil.transform_result(TicketAiDao.get_task_by_id(db, task_id) or task),
        )

    @staticmethod
    def _notify_agent_task_canceled(agent_code: str, task_id: int) -> None:
        """
        向 Agent 发送任务取消通知（fire-and-forget，不等待响应）。

        直接经 WebSocket 发送 request_chunk 消息，不走通用 send_message 的
        Future 等待通道——取消通知无需响应，Agent 收到后注册取消标记即可。
        Agent 离线或发送失败时仅告警：取消已在服务端生效，Worker 迟到结果
        会被"回传后重读状态"逻辑丢弃。
        :param agent_code: Agent 编码
        :param task_id: 任务ID
        :return: 无
        """
        try:
            from module_hrm.utils.util import compress_dict_to_str
            from module_qtr.service.agent_service import CHUNK_SIZE, agents

            websocket = agents.get(agent_code)
            if websocket is None:
                logger.warning(f"Agent 不在线，跳过取消通知: task_id={task_id}, agent={agent_code}")
                return
            message = {
                "requestType": "cancel_task",
                "command": "cancel_ticket_ai_analysis",
                "taskId": task_id,
            }
            compress_data = compress_dict_to_str(message)
            request_chunks = [compress_data[i:i + CHUNK_SIZE] for i in range(0, len(compress_data), CHUNK_SIZE)]
            total = len(request_chunks) or 1
            cancel_request_id = f"cancel-{task_id}"
            chunks_payload = [
                {
                    "type": "request_chunk",
                    "index": idx,
                    "total": total,
                    "request_id": cancel_request_id,
                    "data": chunk,
                    "finished": (idx == total - 1),
                    "binary": False,
                    "meta": {},
                }
                for idx, chunk in enumerate(request_chunks)
            ]

            async def _send() -> None:
                for chunk_message in chunks_payload:
                    await websocket.send_text(json.dumps(chunk_message))

            asyncio.run(_send())
            logger.info(f"任务取消通知已发送到 Agent: task_id={task_id}, agent={agent_code}")
        except Exception as exc:
            logger.warning(
                f"发送任务取消通知失败（取消已在服务端生效）: task_id={task_id}, agent={agent_code}, error={exc}"
            )

    @classmethod
    def _mark_repo_default_if_needed(
        cls, db: Session, mapping: TicketAiRepoMapping, exclude_mapping_id: int | None = None
    ) -> None:
        """
        若映射被设置为默认，则清理同项目下其他默认项。
        :param db: 数据库会话
        :param mapping: 仓库映射对象
        :return: 无
        """
        if not mapping.is_default:
            return
        filters = [
            TicketAiRepoMapping.project_id == mapping.project_id,
            TicketAiRepoMapping.is_default.is_(True),
        ]
        if exclude_mapping_id:
            filters.append(TicketAiRepoMapping.mapping_id != exclude_mapping_id)
        db.query(TicketAiRepoMapping).filter(*filters).update(
            {"is_default": False, "update_time": datetime.now()}, synchronize_session=False
        )

    @classmethod
    def list_repo_mapping_services(cls, db: Session, query: TicketAiRepoMappingQueryModel):
        """
        查询工单 AI 仓库映射列表。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 分页结果或列表
        """
        mapping_query = TicketAiDao.build_repo_mapping_query(db, query)

        def decorate(rows: list[TicketAiRepoMapping]) -> list[TicketAiRepoMappingResponseModel]:
            version_ids = {row.version_id for row in rows if row.version_id}
            version_map = (
                {
                    version.version_id: version
                    for version in db.query(TicketVersion).filter(TicketVersion.version_id.in_(version_ids)).all()
                }
                if version_ids
                else {}
            )
            items = [TicketAiRepoMappingListItem(mapping=row, version=version_map.get(row.version_id)) for row in rows]
            return [
                TicketAiRepoMappingResponseModel(
                    mapping_id=item.mapping.mapping_id,
                    project_id=item.mapping.project_id,
                    project_name=item.mapping.project_name,
                    version_id=item.mapping.version_id,
                    repo_url=item.mapping.repo_url,
                    branch_name=item.mapping.branch_name,
                    local_repo_path=item.mapping.local_repo_path,
                    workspace_root=item.mapping.workspace_root,
                    worker_command=item.mapping.worker_command,
                    is_default=item.mapping.is_default,
                    enabled=item.mapping.enabled,
                    remark=item.mapping.remark,
                    extra_data=item.mapping.extra_data,
                    create_by=item.mapping.create_by,
                    update_by=item.mapping.update_by,
                    create_time=item.mapping.create_time,
                    update_time=item.mapping.update_time,
                    version_name=item.version.version_name if item.version else "",
                    version_key=item.version.version_key if item.version else "",
                )
                for item in items
            ]

        if query.is_page:
            total = mapping_query.count()
            rows = mapping_query.offset((query.page_num - 1) * query.page_size).limit(query.page_size).all()
            return PageResponseModel(
                rows=decorate(rows),
                page_num=query.page_num,
                page_size=query.page_size,
                total=total,
                has_next=total > query.page_num * query.page_size,
            )
        return decorate(mapping_query.all())

    @classmethod
    def save_repo_mapping_services(
        cls,
        db: Session,
        mapping_object: TicketAiRepoMappingCreateModel | TicketAiRepoMappingUpdateModel,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """
        保存工单 AI 仓库映射。
        :param db: 数据库会话
        :param mapping_object: 映射参数
        :param current_user: 当前登录用户
        :return: 保存结果
        """
        now = datetime.now()
        payload = mapping_object.model_dump(exclude_none=True, by_alias=False)
        version = (
            TicketVersionDao.get_version_by_id(db, int(payload["version_id"])) if payload.get("version_id") else None
        )
        if not version:
            return CrudResponseModel(is_success=False, message="请选择版本中心中的有效版本")
        payload["version_id"] = version.version_id
        payload["project_id"] = version.project_id
        payload["project_name"] = version.project_name
        payload["worker_command"] = payload.get("worker_command") or cls._get_config_text(
            db, cls.CONFIG_WORKER_COMMAND, cls.DEFAULT_WORKER_COMMAND
        )
        payload["create_by"] = payload.get("create_by") or cls._user_name(current_user)
        payload["update_by"] = cls._user_name(current_user)
        payload["update_time"] = now
        try:
            if "mapping_id" in payload and payload["mapping_id"]:
                mapping = TicketAiDao.get_repo_mapping_by_id(db, int(payload["mapping_id"]))
                if not mapping:
                    return CrudResponseModel(is_success=False, message="仓库映射不存在")
                payload.pop("mapping_id", None)
                mapping.is_default = bool(payload.get("is_default"))
                if mapping.is_default:
                    cls._mark_repo_default_if_needed(db, mapping, mapping.mapping_id)
                TicketAiDao.update_repo_mapping(db, mapping.mapping_id, payload)
                db.commit()
                return CrudResponseModel(is_success=True, message="更新成功")
            payload["create_time"] = now
            mapping = TicketAiRepoMapping(**payload)
            TicketAiDao.add_repo_mapping(db, mapping)
            if mapping.is_default:
                cls._mark_repo_default_if_needed(db, mapping, mapping.mapping_id)
            db.commit()
            return CrudResponseModel(is_success=True, message="新增成功")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def delete_repo_mapping_services(cls, db: Session, mapping_id: int) -> CrudResponseModel:
        """
        删除仓库映射。
        :param db: 数据库会话
        :param mapping_id: 映射ID
        :return: 删除结果
        """
        mapping = TicketAiDao.get_repo_mapping_by_id(db, mapping_id)
        if not mapping:
            return CrudResponseModel(is_success=False, message="仓库映射不存在")
        try:
            TicketAiDao.delete_repo_mapping(db, mapping_id)
            db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def get_task_list_services(cls, db: Session, ticket_id: int, query: TicketAiAnalysisTaskQueryModel):
        """
        查询工单 AI 分析任务列表。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param query: 查询参数
        :return: 分页结果或列表
        """
        result = TicketAiDao.list_ticket_tasks(db, ticket_id, query)
        if query.is_page:
            result.rows = cls._attach_task_version_labels(
                db, [CamelCaseUtil.transform_result(row) for row in result.rows]
            )
            return result
        return cls._attach_task_version_labels(db, [CamelCaseUtil.transform_result(row) for row in result])

    @staticmethod
    def _attach_task_version_labels(db: Session, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按任务版本中心ID补充展示字段，不将版本文本写回任务表。"""
        version_ids = {int(item["versionId"]) for item in items if item.get("versionId")}
        version_map = (
            {
                version.version_id: version
                for version in db.query(TicketVersion).filter(TicketVersion.version_id.in_(version_ids)).all()
            }
            if version_ids
            else {}
        )
        for item in items:
            version_id = int(item["versionId"]) if item.get("versionId") else None
            version = version_map.get(version_id)
            for field_name in (
                "taskId",
                "ticketId",
                "projectId",
                "mappingId",
                "auditExecutionId",
                "sourceLogPullRecordId",
                "submittedById",
            ):
                if item.get(field_name) not in (None, ""):
                    item[field_name] = str(item[field_name])
            version = version_map.get(version_id)
            if version_id:
                item["versionId"] = str(version_id)
            item["versionKey"] = version.version_key if version else ""
            item["versionName"] = version.version_name if version else ""
        return items

    @classmethod
    def get_latest_summary_map(cls, db: Session, ticket_ids: list[int]) -> dict[int, dict[str, Any]]:
        """
        查询多个工单的最新 AI 分析摘要。
        :param db: 数据库会话
        :param ticket_ids: 工单ID列表
        :return: 以工单ID为键的摘要映射
        """
        latest_map = TicketAiDao.list_latest_tasks_by_ticket_ids(db, ticket_ids)
        summary_map = {ticket_id: cls._serialize_task_summary(task) for ticket_id, task in latest_map.items()}
        cls._attach_task_version_labels(db, list(summary_map.values()))
        return summary_map

    @classmethod
    def get_latest_summary(cls, db: Session, ticket_id: int) -> dict[str, Any] | None:
        """
        查询单个工单的最新 AI 分析摘要。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 摘要信息
        """
        task = TicketAiDao.get_latest_task_by_ticket_id(db, ticket_id)
        if not task:
            return None
        return cls._attach_task_version_labels(db, [cls._serialize_task_summary(task)])[0]

    @classmethod
    def _serialize_task_summary(cls, task: TicketAiAnalysisTask) -> dict[str, Any]:
        """
        将分析任务转换为摘要字典。

        大字段（promptText/rawOutput/analysisContext）由 DAO 层 defer 延迟加载，
        摘要场景不需要这些内容，这里显式置空，避免 transform_result 逐行访问
        属性时触发 SQLAlchemy 按需回表，把大文本重新拉进内存。

        :param task: 任务对象（大列为延迟加载）
        :return: 不包含大字段的摘要字典
        """
        item = CamelCaseUtil.transform_result(task)
        # 摘要只保留轻量元数据，防止访问延迟列触发回表加载。
        for heavy_key in ("promptText", "rawOutput", "analysisContext"):
            item.pop(heavy_key, None)
        result_payload = item.get("analysisResult") if isinstance(item, dict) else None
        if not isinstance(result_payload, dict):
            result_payload = {}
        # analysis_result 入库键为 snake_case（_normalize_analysis_result 写入），
        # 兼容驼峰键仅防止历史上存在异常写入；取值顺序 snake_case 优先。
        item["analysisSummary"] = result_payload.get("analysis_summary") or result_payload.get("analysisSummary")
        item["rootCause"] = result_payload.get("root_cause") or result_payload.get("rootCause")
        item["fixSuggestion"] = result_payload.get("fix_suggestion") or result_payload.get("fixSuggestion")
        return item

    @classmethod
    def queue_task(cls, task_id: int) -> None:
        """
        将 AI 分析任务放入后台线程池执行。
        :param task_id: 任务ID
        :return: 无
        """
        with cls._executor_lock:
            if task_id in cls._active_task_ids:
                return
            cls._active_task_ids.add(task_id)
        cls._executor.submit(cls._run_task, task_id)

    @classmethod
    def resume_pending_tasks(cls) -> None:
        """
        服务启动后清理待执行和运行中的 AI 任务。

        恢复前先按任务上次的 Agent request_id 查询 Redis 结果缓存：
        Agent 在服务重启期间执行完成并通过补交机制回传了结果时，
        任务不标记失败，改为重新排队走正常执行流程——执行开头命中缓存
        结果直接补写回，任务最终成功，token 如实入库。
        注意：pending_recovery（连接中断恢复等待）任务不在此处理——
        其恢复期限由恢复扫描任务（TicketAiRecoveryService）负责判定，
        启动时保持等待状态，Agent 重连补交后由扫描任务自动写回。
        :return: 无
        """
        with SessionLocal() as db:
            tasks = TicketAiDao.list_recoverable_tasks(db, list(cls.ACTIVE_STATUSES))
            now = datetime.now()
            recoverable_request_ids: dict[int, str] = {}
            for task in tasks:
                # 审计 payload 中的 requestId 是上次真实派发的调用标识；
                # 有缓存结果说明 Agent 已完成，可重新排队恢复。
                request_id = cls._resolve_task_last_request_id(task)
                if request_id and cls._peek_agent_result_cache(request_id):
                    recoverable_request_ids[task.task_id] = request_id
                    logger.info(
                        f"AI分析任务[{task.task_id}] 检测到迟到结果缓存，重新排队恢复写回: request_id={request_id}"
                    )
                    continue
                interrupted_message = "服务重启前任务未完成，已清理为失败"
                cls._mark_task_status(
                    db,
                    task.task_id,
                    status=TicketAiAnalysisStatus.FAILED.value,
                    status_desc="服务重启前任务未完成，已清理为失败",
                    error_code="AI_TASK_INTERRUPTED",
                    error_message=interrupted_message,
                    finished_at=now,
                )
                cls._update_execution_record(
                    db,
                    getattr(task, "audit_execution_id", None),
                    status="failed",
                    error_code="AI_TASK_INTERRUPTED",
                    error_message=interrupted_message,
                )
            if tasks:
                db.commit()
            # 提交后再入队，避免未提交状态被执行线程提前读取。
            for task_id in recoverable_request_ids:
                cls.queue_task(task_id)

    @classmethod
    def _resolve_task_last_request_id(cls, task: TicketAiAnalysisTask) -> str | None:
        """
        从任务审计记录的请求载荷中解析上次派发的 Agent request_id。
        :param task: AI 分析任务
        :return: request_id，无法解析时返回 None
        """
        audit_execution_id = getattr(task, "audit_execution_id", None)
        if not audit_execution_id:
            return None
        try:
            with SessionLocal() as audit_db:
                execution = AiTaskExecutionDao.get_ai_task_execution_by_id(audit_db, int(audit_execution_id))
                payload = getattr(execution, "request_payload", None) if execution else None
                if isinstance(payload, str):
                    payload = cls._loads(payload, {})
                if isinstance(payload, dict):
                    return str(payload.get("requestId") or "").strip() or None
        except Exception as exc:
            logger.warning(f"解析任务上次 request_id 失败: task_id={task.task_id}, error={exc}")
        return None

    @classmethod
    def _peek_agent_result_cache(cls, request_id: str) -> bool:
        """
        检查 Redis 结果缓存中是否存在指定请求的迟到结果（只查询不消费）。

        同步上下文驱动短生命周期异步查询，兼容两种调用环境：
        - 后台线程（无运行中事件循环）：直接 asyncio.run；
        - 事件循环内（如 FastAPI lifespan 启动恢复）：asyncio.run 会抛
          "cannot be called from a running event loop"，改用独立线程 +
          run_coroutine_threadsafe 串行等待结果。
        缓存后端可能是 redis 或 memory，统一走 RedisUtil 创建。
        :param request_id: Agent 请求ID
        :return: 是否存在缓存结果
        """
        try:
            import asyncio
            import concurrent.futures

            from config.get_redis import RedisUtil

            async def _exists() -> bool:
                redis = await RedisUtil.create_redis_pool()
                try:
                    return bool(await redis.get(AgentDispatchService._result_key(request_id)))
                finally:
                    await redis.close()

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(_exists())

            # 事件循环已运行：借独立线程驱动协程，避免在循环内嵌套 asyncio.run。
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(_exists())).result(timeout=10)
        except Exception as exc:
            logger.warning(f"查询迟到结果缓存失败，按无缓存处理: request_id={request_id}, error={exc}")
            return False

    @classmethod
    def _run_task(cls, task_id: int) -> None:
        """
        在线程池中执行单条 AI 分析任务。
        :param task_id: 任务ID
        :return: 无
        """
        observation = get_task_memory_observer().start(
            {
                "task_id": task_id,
                "task_key": "ticket_ai_analysis",
                "task_family": "ticket_ai_analysis",
                "queue_name": "ticket-ai-analysis",
                "owner_type": "ticket",
                "trigger_type": "background",
            }
        )
        status = "success"
        try:
            with SessionLocal() as db:
                cls._log_task_step(task_id, "RUN", "开始执行 AI 分析任务")
                cls._process_task(db, task_id)
        except Exception as exc:
            status = "failed"
            logger.exception(f"AI分析任务[{task_id}] 线程执行异常: {exc}")
        finally:
            with cls._executor_lock:
                cls._active_task_ids.discard(task_id)
            get_task_memory_observer().finish(
                {
                    "task_id": task_id,
                    "task_key": "ticket_ai_analysis",
                    "task_family": "ticket_ai_analysis",
                    "queue_name": "ticket-ai-analysis",
                    "owner_type": "ticket",
                    "trigger_type": "background",
                },
                observation,
                status,
            )

    @classmethod
    def _enter_pending_recovery(
        cls,
        db: Session,
        task: TicketAiAnalysisTask,
        *,
        agent_code: str,
        timeout_sec: int,
        audit_execution_id: int | None,
    ) -> None:
        """
        Agent 连接中途断开时把任务置为 pending_recovery（连接中断，等待补交结果）。

        该状态为非终态：不发送失败通知（网络闪断不是真实失败）；恢复期限写入任务
        上下文 pendingRecoveryDeadline，恢复扫描任务按该期限决定自动写回或置败。
        Agent 侧 Worker 在后台线程继续执行，完成后结果经待补交机制回传并写入
        Redis 结果缓存，由恢复扫描任务重新排队走迟到结果写回（不重复消耗 token）。
        :param db: 数据库会话
        :param task: AI 分析任务
        :param agent_code: Agent 编码
        :param timeout_sec: 本次任务超时时间（秒）
        :param audit_execution_id: 审计执行记录ID
        :return: 无
        """
        task_id = task.task_id
        recovery_deadline = datetime.now() + timedelta(
            seconds=max(int(timeout_sec or cls.DEFAULT_WORKER_TIMEOUT), 60) + cls.PENDING_RECOVERY_EXTRA_SECONDS
        )
        context = dict(task.analysis_context) if isinstance(task.analysis_context, dict) else {}
        context["pendingRecoveryDeadline"] = recovery_deadline.isoformat(timespec="seconds")
        cls._log_task_step(
            task_id,
            "STATUS",
            "Agent 连接中断，任务进入恢复等待",
            agent_code=agent_code,
            recovery_deadline=context["pendingRecoveryDeadline"],
        )
        cls._mark_task_status(
            db,
            task_id,
            status=TicketAiAnalysisStatus.PENDING_RECOVERY.value,
            status_desc="连接中断，等待Agent补交结果",
            error_code="AI_AGENT_CONNECTION_LOST",
            error_message="Agent 连接中断，等待 Agent 重连补交结果后自动恢复",
            command_line=f"agent:{agent_code}",
        )
        TicketAiDao.update_task(db, task_id, {"analysis_context": context})
        cls._update_execution_record(
            db,
            audit_execution_id,
            status="running",
            error_message="Agent 连接中断，等待补交结果恢复",
        )
        db.commit()
        logger.info(
            f"AI分析任务[{task_id}] Agent 连接中断，进入恢复等待 | "
            f"agent_code={agent_code}, recovery_deadline={context['pendingRecoveryDeadline']}"
        )

    @classmethod
    def _load_recovered_agent_response(
        cls,
        task_id: int,
        task: TicketAiAnalysisTask,
    ) -> dict[str, Any] | None:
        """
        读取服务重启期间 Agent 补交的迟到结果。

        按审计 payload 中记录的上次 request_id 查询 Redis 结果缓存，
        仅接受传输成功且业务成功的响应，其余情况返回 None 交由正常执行流程处理。
        :param task_id: 任务ID
        :param task: AI 分析任务
        :return: 迟到的 Agent 响应 dict，无可用结果时返回 None
        """
        request_id = cls._resolve_task_last_request_id(task)
        if not request_id:
            return None
        try:
            import asyncio

            from config.get_redis import RedisUtil

            async def _load() -> str | None:
                redis = await RedisUtil.create_redis_pool()
                try:
                    return await redis.get(AgentDispatchService._result_key(request_id))
                finally:
                    await redis.close()

            cached_raw = asyncio.run(_load())
            if not cached_raw:
                return None
            cached_response = HandleResponse.validate_transport_payload(cached_raw)
            response_object = getattr(cached_response, "response", None)
            if getattr(cached_response, "status_code", 500) != 200 or not bool(
                getattr(response_object, "success", True)
            ):
                logger.warning(
                    f"AI分析任务[{task_id}] 迟到结果缓存不可用（非成功响应），按正常流程执行: "
                    f"request_id={request_id}"
                )
                return None
            logger.info(
                f"AI分析任务[{task_id}] 命中迟到结果缓存，跳过重新调用直接写回: request_id={request_id}"
            )
            response_dump = (
                response_object
                if isinstance(response_object, dict)
                else (response_object.model_dump() if hasattr(response_object, "model_dump") else {})
            )
            return response_dump
        except Exception as exc:
            logger.warning(f"读取迟到结果缓存失败，按正常流程执行: task_id={task_id}, error={exc}")
            return None

    @classmethod
    def _process_recovered_success(
        cls,
        db: Session,
        task: TicketAiAnalysisTask,
        ticket: Ticket,
        response_dump: dict[str, Any],
        audit_execution_id: int | None,
    ) -> None:
        """
        使用迟到结果完成成功写回（消息、RCA、快照、任务与审计状态、token）。
        :param db: 数据库会话
        :param task: AI 分析任务
        :param ticket: 工单对象
        :param response_dump: 迟到的 Agent 响应字典
        :param audit_execution_id: 审计记录ID
        :return: 无
        """
        task_id = task.task_id
        cls._mark_task_status(
            db,
            task_id,
            status=TicketAiAnalysisStatus.RUNNING.value,
            status_desc="恢复迟到结果，写回中",
        )
        response_payload = cls._extract_agent_response_result(response_dump)
        parsed_result = (
            response_payload.get("analysis_result")
            or response_payload.get("analysisResult")
            or response_payload.get("result")
        )
        if isinstance(parsed_result, str):
            try:
                parsed_result = json.loads(parsed_result)
            except Exception:
                parsed_result = None
        if not isinstance(parsed_result, dict):
            # 缓存结果损坏时按中断失败处理，让用户重试真实执行。
            failure_message = "恢复的迟到结果无法解析，任务已标记失败，请重试"
            cls._log_task_step(task_id, "FAIL", failure_message)
            db.rollback()
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                status_desc="恢复迟到结果失败",
                error_code="AI_TASK_RECOVERED_RESULT_INVALID",
                error_message=failure_message,
                finished_at=datetime.now(),
            )
            cls._update_execution_record(
                db,
                audit_execution_id,
                status="failed",
                error_code="AI_TASK_RECOVERED_RESULT_INVALID",
                error_message=failure_message,
            )
            db.commit()
            return
        token_usage_payload = cls._extract_token_usage_payload(response_payload, response_dump)
        # 与主执行链路同口径：Agent 回传的是本地缓存结果时，恢复出的 token 属于历史尝试，
        # 本次审计不再重复计入，避免服务重启恢复把同一次消耗再记一遍。
        recovered_cache_hit = bool(
            response_dump.get("cache_hit")
            or response_payload.get("cache_hit")
            or str(response_payload.get("command_line") or "").strip() == "cached:result.json"
        )
        if recovered_cache_hit:
            logger.info(
                f"AI分析任务[{task_id}] 恢复的迟到结果来自 Agent 本地缓存，不重复计入 Token"
            )
            token_usage_payload = None
        normalized_token_usage = cls._normalize_token_usage(token_usage_payload)
        mapping = TicketAiDao.get_repo_mapping_by_id(db, getattr(task, "mapping_id", None) or 0)
        version_key = cls._get_version_key(db, task.version_id)
        normalized = cls._normalize_analysis_result(
            result_payload=parsed_result,
            ticket=ticket,
            mapping=mapping,
            version_key=version_key,
        )
        result_text = cls._dumps(response_payload)
        cls._persist_success_result(
            db,
            task,
            ticket,
            normalized,
            result_text,
            cls._submission_user_placeholder(task),
        )
        cls._mark_task_status(
            db,
            task_id,
            status=TicketAiAnalysisStatus.SUCCESS.value,
            status_desc=(
                "复用 Agent 缓存结果（恢复服务重启前的执行结果）" if recovered_cache_hit
                else "分析成功（恢复服务重启前的执行结果）"
            ),
            finished_at=datetime.now(),
            analysis_result=normalized,
            raw_output=result_text[:5000],
            command_line="agent:recovered",
            input_token_count=(normalized_token_usage or {}).get("input_token_count"),
            output_token_count=(normalized_token_usage or {}).get("output_token_count"),
            total_token_count=(normalized_token_usage or {}).get("total_token_count"),
        )
        cls._update_execution_record(
            db,
            audit_execution_id,
            status="success",
            response_payload=response_payload,
            response_text=result_text,
            # 缓存命中时不写 token_usage，避免把历史尝试的消耗重复计入本次恢复。
            token_usage=None if recovered_cache_hit else token_usage_payload,
        )
        db.commit()

        cls._log_task_step(task_id, "DONE", "迟到结果恢复写回完成")
        TicketSimilarityCaseService.enqueue_index_for_ticket(ticket.ticket_id)

    @classmethod
    def _finalize_sync_publish_after_ai(
        cls,
        db: Session,
        *,
        ticket_id: int,
        status: str,
        task_id: int | None = None,
        result_payload: dict[str, Any] | None = None,
        error_message: str = "",
        follow_up_override: str = "",
    ) -> None:
        """
        AI 任务终态后回写工单同步发布状态并按配置回帖 AI 结果。
        不再硬编码同步场景：由 finalize_sync_after_ai 从工单同步元数据解析最近一次入库场景，
        避免多维表格拉取等场景的工单被 external_sync 场景开关误拦截。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param status: AI任务状态
        :param task_id: AI任务ID，用于结果回帖幂等
        :param result_payload: AI分析结果载荷（成功时供回帖渲染）
        :param error_message: AI失败原因（失败时供回帖渲染）
        :param follow_up_override: 结果回帖覆盖意图（follow/on/off，手动触发时使用）
        :return: 无
        """
        try:
            from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService

            TicketSyncGroupPushService.finalize_sync_after_ai(
                db,
                ticket_id=ticket_id,
                ai_task_status=status,
                ai_task_id=task_id,
                ai_result_payload=result_payload,
                ai_error_message=error_message,
                follow_up_override=follow_up_override,
            )
        except Exception as exc:
            logger.warning(f"AI任务终态回写同步发布状态失败: ticket_id={ticket_id}, status={status}, error={exc}")

    @classmethod
    def _process_task(cls, db: Session, task_id: int) -> None:
        """
        执行 AI 分析全流程。
        :param db: 数据库会话
        :param task_id: 任务ID
        :return: 无
        """
        cls._log_task_step(task_id, "LOAD", "读取任务记录")
        task = TicketAiDao.get_task_by_id(db, task_id)
        if not task or task.status == TicketAiAnalysisStatus.SUCCESS.value:
            cls._log_task_step(task_id, "LOAD", "任务不存在或已成功，跳过")
            return
        # 手动触发时快照在任务上下文里的"结果回帖"三态选择；自动触发快照缺失时按跟随全局处理。
        task_context = task.analysis_context if isinstance(task.analysis_context, dict) else {}
        follow_up_override = str(task_context.get("aiResultFollowUpOverride") or "").strip().lower()
        # 执行入口状态白名单：只允许新建、重试后的任务和恢复等待中的任务进入执行，
        # 防止并发失败者（canceled）或其它终态任务被误排队后再次执行、重复消耗模型调用。
        if task.status not in (
            TicketAiAnalysisStatus.CREATED.value,
            TicketAiAnalysisStatus.RUNNING.value,
            TicketAiAnalysisStatus.PENDING_RECOVERY.value,
        ):
            cls._log_task_step(
                task_id,
                "LOAD",
                f"任务状态为 {task.status}，不在可执行白名单内，跳过",
            )
            return
        cls._log_task_step(task_id, "LOAD", "读取工单记录", ticket_id=getattr(task, "ticket_id", None))
        ticket = TicketDao.get_ticket_by_id(db, task.ticket_id)
        if not ticket:
            cls._log_task_step(task_id, "FAIL", "工单不存在或已删除", ticket_id=task.ticket_id)
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                status_desc="工单不存在",
                error_code="AI_TICKET_NOT_FOUND",
                error_message="工单不存在或已删除",
                finished_at=datetime.now(),
            )
            cls._update_execution_record(
                db,
                getattr(task, "audit_execution_id", None),
                status="failed",
                error_code="AI_TICKET_NOT_FOUND",
                error_message="工单不存在或已删除",
            )
            db.commit()
            return
        source_log_pull_record = None
        notify_config: dict[str, Any] | None = None
        if getattr(task, "source_log_pull_record_id", None):
            # 仅读取 command_content 中的通知配置，使用轻量查询避免加载压缩正文。
            source_log_pull_record = TicketLogPullDao.get_record_meta_by_id(db, int(task.source_log_pull_record_id))
        if source_log_pull_record and isinstance(source_log_pull_record.command_content, dict):
            notify_config = source_log_pull_record.command_content.get(
                "notifyConfig"
            ) or source_log_pull_record.command_content.get("notify_config")
        audit_execution_id = cls._ensure_task_execution_record(db, task, ticket)
        cls._log_task_step(
            task_id,
            "RESOLVE",
            "解析仓库映射",
            project_id=ticket.project_id,
            version_id=task.version_id,
        )
        mapping = TicketAiDao.get_repo_mapping_by_id(db, getattr(task, "mapping_id", None) or 0)
        if not mapping:
            mapping = cls._resolve_mapping(db, ticket)
        if not mapping:
            cls._log_task_step(
                task_id,
                "FAIL",
                "未找到仓库映射",
                project_id=ticket.project_id,
                version_id=task.version_id,
            )
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                status_desc="未找到仓库映射",
                error_code="AI_REPO_MAPPING_NOT_FOUND",
                error_message="未找到可用的项目版本仓库映射",
                finished_at=datetime.now(),
            )
            cls._update_execution_record(
                db,
                audit_execution_id,
                status="failed",
                error_code="AI_REPO_MAPPING_NOT_FOUND",
                error_message="未找到可用的项目版本仓库映射",
            )
            db.commit()
            cls._finalize_sync_publish_after_ai(
                db,
                ticket_id=ticket.ticket_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                task_id=task_id,
                error_message='未找到可用的项目版本仓库映射',
                follow_up_override=follow_up_override,
            )
            return

        cls._log_task_step(
            task_id,
            "WORKSPACE",
            "准备工作区",
            workspace_path=task.workspace_path,
            workspace_root=task.workspace_root,
            result_path=task.result_path,
        )
        workspace_dir = Path(task.workspace_path or "").expanduser()
        if not workspace_dir.is_absolute():
            workspace_dir = (
                Path(task.workspace_root or cls.DEFAULT_WORKSPACE_ROOT)
                / f"ticket_{ticket.ticket_id}"
                / f"task_{task.task_id}"
            )
        result_file = str(task.result_path or workspace_dir / "result.json")
        # 优先使用任务创建时生成的 prompt；若缺失则重建，从紧凑快照中取 logAnalysisMode
        fallback_log_mode = "digest"
        fallback_prompt_layers: dict[str, Any] = {}
        fallback_prompt_templates: list[dict[str, Any]] = []
        fallback_extra_instruction = ""
        if isinstance(task.analysis_context, dict):
            fallback_log_mode = str(task.analysis_context.get("logAnalysisMode") or "digest")
            if isinstance(task.analysis_context.get("promptLayers"), dict):
                fallback_prompt_layers = task.analysis_context.get("promptLayers")
            if isinstance(task.analysis_context.get("selectedPromptTemplates"), list):
                fallback_prompt_templates = task.analysis_context.get("selectedPromptTemplates")
            fallback_extra_instruction = str(task.analysis_context.get("extraInstruction") or "").strip()
        version_key = cls._get_version_key(db, task.version_id)
        prompt_template = task.prompt_text or cls._build_prompt(
            "{workspace_path}",
            mapping,
            ticket,
            version_key=version_key,
            prompt_layers=fallback_prompt_layers,
            prompt_templates=fallback_prompt_templates,
            extra_instruction=fallback_extra_instruction,
            log_analysis_mode=fallback_log_mode,
            source_logs_path="{source_logs_path}",
        )
        schema_payload = cls._build_result_schema(ticket, mapping, version_key)
        timeout_sec = cls._get_config_int(db, cls.CONFIG_WORKER_TIMEOUT, cls.DEFAULT_WORKER_TIMEOUT)
        context_payload = cls._load_workspace_context_payload(db, task, ticket, mapping, workspace_dir)
        requested_provider_code = str((context_payload or {}).get("selectedAiProviderCode") or "").strip()
        selected_provider = cls._resolve_ai_provider(db, requested_provider_code) if requested_provider_code else None
        selected_executor = str((context_payload or {}).get("selectedExecutor") or "").strip()
        if not selected_executor:
            selected_executor = cls._resolve_executor(selected_provider)
        if selected_provider:
            AiProviderCapabilityService.require_provider_eligibility(
                selected_provider,
                usage="ticket_analysis_worker",
                executor=selected_executor,
            )
        # 可观测上报为旁路能力：配置解析失败只记日志，绝不阻断分析任务执行。
        try:
            observability_config = TicketAiObservabilityService.build_provider_config(selected_provider)
        except Exception as obs_exc:
            logger.warning(f"AI分析任务[{task_id}] 可观测配置解析失败，跳过上报: {obs_exc}")
            observability_config = None
        # 可观测链路上下文：任务级 traceId/spanId 同时用于服务端任务span与CLI的TRACEPARENT，
        # 使 Claude Code 的原生span挂接到同一trace；Codex 不支持traceparent，靠session.id关联。
        observability_trace: dict[str, str] | None = None
        observability_session_id: str | None = None
        if observability_config:
            # 任务级 trace 上下文始终生成：Agent 侧上报任务span需要（服务端可能与平台网络隔离），
            # CLI 原生遥测开启时 TRACEPARENT 也复用同一 trace，使 CLI span 挂接到任务链路。
            observability_session_id = f"ticket-ai-task-{task_id}"
            observability_trace = {
                "trace_id": secrets.token_hex(16),
                "span_id": secrets.token_hex(8),
            }
        if selected_provider:
            provider_env_overrides = cls._build_provider_env_overrides(
                selected_provider,
                observability_config=observability_config,
                session_id=observability_session_id,
                traceparent=(
                    f'00-{observability_trace["trace_id"]}-{observability_trace["span_id"]}-01'
                    if observability_trace
                    else None
                ),
                observability_trace=observability_trace,
                user_id=str(getattr(task, "submitted_by_name", None) or "") or None,
            )
        else:
            provider_env_overrides = {}
        requested_agent_code = str((context_payload or {}).get("selectedAgentCode") or "").strip()
        if not requested_agent_code and selected_provider and str(selected_provider.preferred_agent_code or "").strip():
            requested_agent_code = str(selected_provider.preferred_agent_code).strip()
        worker_model_override = str((context_payload or {}).get("selectedWorkerModel") or "").strip()
        if not worker_model_override and selected_provider and str(selected_provider.default_model or "").strip():
            worker_model_override = str(selected_provider.default_model).strip()
        agent_code = cls._resolve_agent_code(db, requested_agent_code)
        cls._log_task_step(
            task_id,
            "AGENT",
            "解析 AI 执行 Agent",
            agent_code=agent_code or "<none>",
            provider_code=requested_provider_code or "<none>",
            configured_agent_code=cls._get_config_text(db, cls.CONFIG_AGENT_CODE, cls.DEFAULT_AGENT_CODE) or "<auto>",
            online_agent_count=cls._count_online_agents(db),
        )
        if not agent_code:
            cls._log_task_step(task_id, "FAIL", "未找到可用的 Agent")
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                status_desc="未找到Agent",
                error_code="AI_AGENT_NOT_AVAILABLE",
                error_message="未找到可用的 Agent，请先启动本地 Agent 并连接到服务端",
                finished_at=datetime.now(),
                command_line="agent:<none>",
            )
            cls._update_execution_record(
                db,
                audit_execution_id,
                status="failed",
                provider_code=requested_provider_code or None,
                model_name=worker_model_override or None,
                base_url=(str(selected_provider.base_url or "").strip() or None) if selected_provider else None,
                error_code="AI_AGENT_NOT_AVAILABLE",
                error_message="未找到可用的 Agent，请先启动本地 Agent 并连接到服务端",
            )
            db.commit()
            cls._finalize_sync_publish_after_ai(
                db,
                ticket_id=ticket.ticket_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                task_id=task_id,
                error_message='未找到可用的 Agent，请先启动本地 Agent 并连接到服务端',
                follow_up_override=follow_up_override,
            )
            return
        started_at = datetime.now()
        # 服务重启恢复场景：Agent 迟到结果已进入 Redis 结果缓存时，直接读取缓存
        # 走成功写回，不再重新派发调用（避免重复消耗 token）。
        recovered_response = cls._load_recovered_agent_response(task_id, task)
        if recovered_response is not None:
            cls._process_recovered_success(db, task, ticket, recovered_response, audit_execution_id)
            return
        if recovered_response is None and task.status == TicketAiAnalysisStatus.PENDING_RECOVERY.value:
            # 恢复等待中且尚无补交结果：保持 pending_recovery 继续等待，不派发新尝试，
            # 避免与客户端仍在执行的 Worker 并发跑同一任务（Agent 端会拒绝并发同任务执行）。
            cls._log_task_step(task_id, "LOAD", "恢复等待中，尚未收到 Agent 补交结果，继续等待")
            return
        cls._log_task_step(
            task_id,
            "STATUS",
            "更新任务状态为执行中",
            started_at=started_at.isoformat(),
            agent_code=agent_code,
            timeout_sec=timeout_sec,
        )
        cls._mark_task_status(
            db,
            task_id,
            status=TicketAiAnalysisStatus.RUNNING.value,
            status_desc="分析中",
            started_at=started_at,
            command_line=f"agent:{agent_code}",
        )
        db.commit()

        ticket_payload = cls._json_safe_value(CamelCaseUtil.transform_result(ticket))
        timeline_payload = cls._json_safe_value(
            CamelCaseUtil.transform_result(TicketDao.get_timeline(db, ticket.ticket_id))
        )
        raw_stdout = ""
        raw_stderr = ""
        result_text = ""
        request_payload: dict[str, Any] | None = None
        response_payload: dict[str, Any] = {}
        token_usage_payload: dict[str, Any] | None = None
        error_code: str | None = None
        failure_message: str | None = None
        try:
            request_payload = cls._build_agent_request_payload(
                task_id=task_id,
                ticket=ticket,
                mapping=mapping,
                context_payload=context_payload,
                provider_env_overrides=provider_env_overrides,
                ticket_payload=ticket_payload,
                timeline_payload=timeline_payload,
                prompt_template=prompt_template,
                schema_payload=schema_payload,
                result_path=result_file,
                timeout_sec=timeout_sec,
                submitted_by_name=getattr(task, "submitted_by_name", None),
                submitted_by_id=getattr(task, "submitted_by_id", None),
            )
            request_id = cls._build_agent_request_id(task_id)
            # request_id 是本次真实 Agent 调用的唯一标识，写入审计 payload 后
            # 迟到结果补全、重试对账都能按 request_id 关联（重试新增 attempt 的前置条件）。
            if request_payload is None:
                request_payload = {}
            request_payload["requestId"] = request_id
            cls._update_execution_record(
                db,
                audit_execution_id,
                status="running",
                provider_code=requested_provider_code or None,
                model_name=worker_model_override or None,
                base_url=(str(selected_provider.base_url or "").strip() or None) if selected_provider else None,
                request_payload=request_payload,
            )
            cls._log_task_step(
                task_id,
                "EXEC",
                "发送 AI 分析任务到 Agent",
                agent_code=agent_code,
                request_type=TstepTypeEnum.ai_analysis.value,
                request_id=request_id,
                timeout_sec=timeout_sec,
            )
            agent_response = cls._send_agent_request_via_gateway(
                agent_code,
                request_payload,
                request_id,
                timeout_sec,
            )
            response_object = getattr(agent_response, "response", None)
            if isinstance(response_object, dict):
                response_dump = response_object
            elif response_object is not None and hasattr(response_object, "model_dump"):
                response_dump = response_object.model_dump()
            else:
                response_dump = {}
            # 响应瘦身兜底：新版 Agent 已把 raw_output 截断为头部摘要，但旧版
            # Agent 仍可能回传数 MB 的完整 stdout（历史 OOM 诱因）。在内存驻留
            # 之前就地截断，完整内容以 Agent 本地 stdout_path 文件为准。
            cls._truncate_response_raw_output(response_object)
            raw_stdout = cls._dumps(cls._json_safe_value(response_dump))
            raw_stderr = ""
            response_result_preview = None
            if hasattr(response_object, "result"):
                try:
                    response_result_preview = getattr(response_object, "result", None)
                    if isinstance(response_result_preview, dict):
                        response_result_preview = list(response_result_preview.keys())
                except Exception:
                    response_result_preview = "<error>"
            cls._log_task_step(
                task_id,
                "EXEC",
                "Agent 返回结果",
                status_code=getattr(agent_response, "status_code", None),
                response_type=type(response_object).__name__ if response_object is not None else "None",
                response_message=getattr(agent_response, "message", None),
                response_error_code=getattr(response_object, "error_code", None),
                response_error_message=getattr(response_object, "error_message", None),
                response_result_preview=response_result_preview,
            )
            # 回传后重读任务状态：任务在等待 Agent 执行期间被用户取消时，
            # 丢弃结果不做写回（不覆盖取消态），仅把已发生的真实 token 消耗补进审计。
            refreshed_task = TicketAiDao.get_task_by_id(db, task_id)
            if refreshed_task and refreshed_task.status == TicketAiAnalysisStatus.CANCELED.value:
                canceled_token_usage = cls._extract_token_usage_payload(response_dump, response_object)
                logger.info(
                    f"AI分析任务[{task_id}] 已被取消，丢弃Agent结果不写回，"
                    f"仅保留已消耗token进审计: token_usage={canceled_token_usage}"
                )
                db.rollback()
                cls._update_execution_record(
                    db,
                    audit_execution_id,
                    token_usage=canceled_token_usage,
                )
                db.commit()
                cls._finalize_sync_publish_after_ai(
                    db,
                    ticket_id=ticket.ticket_id,
                    status=TicketAiAnalysisStatus.CANCELED.value,
                    task_id=task_id,
                    follow_up_override=follow_up_override,
                )
                return

            # Agent 连接中途断开：区别于真实执行失败，任务进入 pending_recovery
            # 等待 Agent 重连后补交结果自动写回，恢复扫描任务负责超期置败兜底。
            if getattr(agent_response, "status_code", None) == AgentResponseEnum.AGENT_CONNECTION_LOST.value:
                cls._enter_pending_recovery(
                    db,
                    task,
                    agent_code=agent_code,
                    timeout_sec=timeout_sec,
                    audit_execution_id=audit_execution_id,
                )
                return

            if getattr(agent_response, "status_code", 500) != 200:
                error_code = "AI_AGENT_TRANSPORT_ERROR"
                failure_message = (
                    getattr(response_object, "error_message", None)
                    or getattr(response_object, "message", None)
                    or getattr(agent_response, "message", None)
                    or "Agent 网关传输失败"
                )
                response_payload = response_dump
                cls._log_task_step(task_id, "FAIL", "Agent HTTP 请求失败", error=failure_message)
                raise ValueError(failure_message)

            # Agent 业务失败与网关传输成功是两个独立状态。失败时不再尝试从
            # result、响应文本或工单正文推断异常，直接使用客户端返回的结构化错误。
            if not bool(getattr(response_object, "success", True)):
                error_code = str(getattr(response_object, "error_code", None) or "AI_AGENT_EXECUTION_ERROR")
                failure_message = str(
                    getattr(response_object, "error_message", None)
                    or getattr(response_object, "message", None)
                    or "Agent 执行失败，但未返回错误信息"
                )
                response_payload = response_dump
                # 失败也可能已产生真实模型消耗（Agent 失败 payload 内嵌 token_usage），
                # 失败路径同样提取 token，供审计记录真实消耗。
                token_usage_payload = cls._extract_token_usage_payload(response_dump, response_object)
                if token_usage_payload is not None:
                    logger.info(
                        f"AI分析任务[{task_id}] 失败路径提取到Token用量，将计入审计: {token_usage_payload}"
                    )
                cls._log_task_step(
                    task_id,
                    "FAIL",
                    "Agent 返回结构化失败",
                    error_code=error_code,
                    error=failure_message,
                    worker_exit_code=getattr(response_object, "worker_exit_code", None),
                    diagnostics=getattr(response_object, "diagnostics", None),
                )
                raise ValueError(failure_message)

            response_payload = cls._extract_agent_response_result(response_object)
            result_text = ""
            if response_payload:
                result_text = cls._dumps(response_payload)
            parsed_result = (
                response_payload.get("analysis_result")
                or response_payload.get("analysisResult")
                or response_payload.get("result")
            )
            if isinstance(parsed_result, str):
                try:
                    parsed_result = json.loads(parsed_result)
                except Exception:
                    parsed_result = None
            if not isinstance(parsed_result, dict):
                error_code = "AI_WORKER_RESULT_INVALID"
                failure_message = "Agent 未返回可解析的分析结果"
                # 结果不可解析时同样尽力提取已消耗 token（响应中可能内嵌 usage）。
                token_usage_payload = cls._extract_token_usage_payload(response_payload, response_dump, response_object)
                cls._log_task_step(
                    task_id,
                    "FAIL",
                    failure_message,
                    error_code=error_code,
                )
                raise ValueError(failure_message)
            token_usage_payload = cls._extract_token_usage_payload(response_payload, response_dump, response_object)
            # 缓存命中（Agent 直接回传工作区历史 result.json）说明本次没有发生新的模型调用。
            # 恢复出的 token 属于历史尝试的真实消耗（已随原失败/中断审计留痕），本次不再重复计入，
            # 否则重试一次就会把同一次消耗在"失败审计"和"缓存成功审计"各记一遍，Token 统计翻倍。
            cache_hit = bool(
                getattr(response_object, "cache_hit", False)
                or response_dump.get("cache_hit")
                or response_payload.get("cache_hit")
                # 兼容未回传 cache_hit 字段的旧版 Agent：缓存命中时 result 内
                # command_line 固定为 cached:result.json（真实执行时是完整命令行）。
                or str(response_payload.get("command_line") or "").strip() == "cached:result.json"
            )
            if cache_hit:
                logger.info(
                    f"AI分析任务[{task_id}] Agent 命中本地缓存结果，本次未发生模型调用，"
                    f"不重复计入 Token: recovered_token_usage={token_usage_payload}"
                )
                token_usage_payload = None
            # Schema 校验前先做保守清洗：部分模型未被 --output-schema 真实约束，
            # 会输出 schema 外字段或把 evidence 写成对象数组，清洗后再校验可挽救此类结果。
            parsed_result, sanitize_actions = TicketAiResultSchemaUtil.sanitize_result_payload(
                parsed_result, schema_payload
            )
            if sanitize_actions:
                logger.info(f"AI分析任务[{task_id}] 分析结果已按 schema 清洗: {sanitize_actions}")
            normalized_token_usage = cls._normalize_token_usage(token_usage_payload)
            normalized = cls._normalize_analysis_result(
                result_payload=parsed_result,
                ticket=ticket,
                mapping=mapping,
                version_key=version_key,
            )
            if not cls._validate_analysis_result_schema(parsed_result, schema_payload):
                error_code = "AI_WORKER_RESULT_INVALID"
                # 输出具体违规字段，避免只留笼统信息导致需要人工比对 result.json 定位。
                schema_violations = cls._collect_schema_violations(parsed_result, schema_payload)
                violation_summary = "; ".join(schema_violations[:10])
                failure_message = "AI Agent 返回的分析结果未通过 JSON Schema 校验"
                if violation_summary:
                    failure_message = f"{failure_message}: {violation_summary}"
                # Schema 校验失败时模型调用已真实发生，保留已提取的 token 用量。
                cls._log_task_step(
                    task_id,
                    "FAIL",
                    failure_message,
                    error_code=error_code,
                    violations=schema_violations,
                )
                raise ValueError(failure_message)

            # 先用成功指纹占位，再执行消息、RCA、快照和事件写回，确保并发重复任务只有
            # 一个事务可以进入成功写回流程。唯一约束冲突时，当前任务直接取消。
            request_fingerprint = str(getattr(task, "request_fingerprint", "") or "").strip()
            if request_fingerprint:
                winner = TicketAiDao.get_successful_task_by_request_fingerprint(db, request_fingerprint)
                if winner and winner.task_id != task.task_id:
                    db.rollback()
                    cls._finish_duplicate_task_without_writeback(db, task, winner, audit_execution_id)
                    return
                try:
                    task.success_fingerprint = request_fingerprint
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    winner = TicketAiDao.get_successful_task_by_request_fingerprint(db, request_fingerprint)
                    if winner and winner.task_id != task.task_id:
                        cls._finish_duplicate_task_without_writeback(db, task, winner, audit_execution_id)
                        return
                    raise
            cls._log_task_step(task_id, "PERSIST", "写回工单与 RCA 结果")
            # raw_output 仅保留摘要级输出；原始 Agent 响应中可能包含大体积日志上下文
            # 或 Codex --json 的 JSONL 事件流，完整内容以工作区 result.json /
            # 分析结果结构化字段为准，Token 用量经 token_usage 字段单独入库。
            # 写回创建者归属任务提交人（执行线程无登录态，用提交人占位）。
            cls._persist_success_result(
                db,
                task,
                ticket,
                normalized,
                result_text or raw_stdout,
                cls._submission_user_placeholder(task),
            )
            finished_at = datetime.now()
            # 缓存命中时状态描述明确提示"复用 Agent 缓存结果"，让用户知道本次没有重新跑模型。
            cache_status_desc = "复用 Agent 缓存结果" if cache_hit else "分析成功"
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.SUCCESS.value,
                status_desc=cache_status_desc,
                finished_at=finished_at,
                analysis_result=normalized,
                raw_output=(result_text or raw_stdout or "")[:5000],
                command_line=f"agent:{agent_code}",
                input_token_count=(normalized_token_usage or {}).get("input_token_count"),
                output_token_count=(normalized_token_usage or {}).get("output_token_count"),
                total_token_count=(normalized_token_usage or {}).get("total_token_count"),
            )
            cls._update_execution_record(
                db,
                audit_execution_id,
                status="success",
                provider_code=requested_provider_code or None,
                model_name=worker_model_override or None,
                base_url=(str(selected_provider.base_url or "").strip() or None) if selected_provider else None,
                response_payload=response_payload or response_dump,
                response_text=result_text or raw_stdout,
                # 缓存命中不写 token_usage：本次审计记录代表一次未发生的调用，
                # 真实消耗以首次尝试的失败/中断审计记录为准，避免统计翻倍。
                token_usage=None if cache_hit else token_usage_payload,
            )
            db.commit()
            TicketSimilarityCaseService.enqueue_index_for_ticket(ticket.ticket_id)
            cls._finalize_sync_publish_after_ai(
                db,
                ticket_id=ticket.ticket_id,
                status=TicketAiAnalysisStatus.SUCCESS.value,
                task_id=task_id,
                result_payload=normalized,
                follow_up_override=follow_up_override,
            )
            TicketNotifyService.send_ticket_notification(
                db,
                ticket,
                title="工单AI分析结果通知",
                status="success",
                message="AI分析已完成",
                detail=f"task_id={task_id}, version_id={task.version_id}",
                notify_config=notify_config,
                stage="ai_analysis",
            )

            cls._log_task_step(task_id, "DONE", "AI 分析任务完成")
            return
        except Exception as exc:
            failure_code = error_code or "AI_ANALYSIS_EXECUTION_ERROR"
            failure_message = failure_message or str(exc)
            cls._log_task_step(
                task_id,
                "ERROR",
                "AI 分析任务执行失败",
                error_code=failure_code,
                error=failure_message,
            )
            logger.exception(f"AI分析任务[{task_id}] 执行失败")
            # 持久化阶段可能已经触发数据库 flush 失败，必须先回滚才能继续写入失败终态；
            # 否则 SQLAlchemy 会拒绝后续状态更新，任务会长期停留在“执行中”。
            db.rollback()
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                status_desc="分析失败",
                error_code=failure_code,
                error_message=failure_message,
                finished_at=datetime.now(),
                command_line=f"agent:{agent_code}",
            )
            cls._update_execution_record(
                db,
                audit_execution_id,
                status="failed",
                error_code=failure_code,
                provider_code=locals().get("requested_provider_code") or None,
                model_name=locals().get("worker_model_override") or None,
                base_url=(
                    str(selected_provider.base_url or "").strip() or None
                    if "selected_provider" in locals() and selected_provider
                    else None
                ),
                response_payload=response_payload or None,
                response_text=result_text or raw_stdout or raw_stderr,
                token_usage=token_usage_payload,
                error_message=failure_message,
            )
            db.commit()

            if "ticket" in locals() and ticket:
                cls._finalize_sync_publish_after_ai(
                    db,
                    ticket_id=ticket.ticket_id,
                    status=TicketAiAnalysisStatus.FAILED.value,
                    task_id=task_id,
                    error_message=failure_message,
                    follow_up_override=follow_up_override,
                )
            if "ticket" in locals() and ticket:
                TicketNotifyService.send_ticket_notification(
                    db,
                    ticket,
                    title="工单AI分析结果通知",
                    status="failed",
                    message="AI分析执行失败",
                    detail=f"task_id={task_id}, error={failure_message}",
                    notify_config=notify_config,
                    stage="ai_analysis",
                )
            return

    # ---- AI 结果回帖手动补发（2026-09 阶段二）----

    REPLY_RESEND_ALLOWED_STATUSES = {
        TicketAiAnalysisStatus.SUCCESS.value,
        TicketAiAnalysisStatus.FAILED.value,
    }

    @classmethod
    def resend_result_reply_services(
        cls,
        db: Session,
        ticket_id: int,
        task_id: int,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """
        手动补发 AI 分析结果回帖到工单群话题。

        面向"分析已完成但结果未回帖"的任务（锚点丢失的历史工单、回帖发送失败、
        当时配置未开启等场景）；不重新执行分析，直接读取任务持久化结果渲染发送。
        补发视为明确手动意图：跳过回帖总开关与 sendOn 时机匹配、跳过工单级幂等，
        但保留任务级幂等（已回帖过的任务拒绝重复补发）与无锚点策略判定。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param task_id: AI任务ID
        :param current_user: 当前登录用户
        :return: 补发结果
        """
        from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
        from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService

        task = TicketAiDao.get_task_by_id(db, task_id)
        if not task or task.ticket_id != ticket_id:
            return CrudResponseModel(is_success=False, message="AI分析任务不存在")
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在或已删除")
        if task.status not in cls.REPLY_RESEND_ALLOWED_STATUSES:
            return CrudResponseModel(
                is_success=False,
                message=f"任务状态为 {task.status}，仅分析成功或失败的任务支持补发回帖",
            )
        if TicketAiDao.is_result_replied(db, task_id):
            return CrudResponseModel(
                is_success=False,
                message="该任务结果已回帖过，无需补发；如需再次通知请重新提交分析",
            )
        config = TicketSyncConfigService.load_sync_config(db)
        group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
        raw_follow_up = (
            group_config.get("aiResultFollowUp")
            if isinstance(group_config.get("aiResultFollowUp"), dict)
            else {}
        )
        # 手动补发为明确意图：强制 enabled+sendOn=always（终态非取消即匹配），
        # 保留 replyInThread/template/noAnchorStrategy 等形式配置跟随当前全局配置。
        follow_up_config = {**raw_follow_up, "enabled": True, "sendOn": "always"}
        meta = TicketSyncGroupPushService.build_meta(
            ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        )
        result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
            db,
            ticket=ticket,
            meta=meta,
            follow_up_config=follow_up_config,
            ai_task_status=str(task.status or ""),
            ai_task_id=task_id,
            ai_result_payload=task.analysis_result if isinstance(task.analysis_result, dict) else None,
            ai_error_message=str(getattr(task, "error_message", "") or ""),
            override="on",
            sync_scene=TicketSyncGroupPushService.resolve_sync_scene_from_meta(meta),
        )
        operator = cls._user_name(current_user) if current_user else "system"
        TicketDao.add_event(
            db,
            TicketEvent(
                ticket_id=ticket_id,
                event_type=TicketEventType.AI_ANALYZED.value,
                operator_id=cls._user_id(current_user) if current_user else None,
                operator_name=operator,
                content=(
                    f"手动补发AI结果回帖: task_id={task_id}, "
                    f"{'成功' if result.get('successCount') else '未成功'}"
                    + (f", 原因={result.get('skipReason')}" if result.get("skipped") else "")
                ),
                create_time=datetime.now(),
            ),
        )
        db.commit()
        if bool(result.get("skipped")):
            return CrudResponseModel(
                is_success=False,
                message=f"回帖未发送: {result.get('skipReason') or '-'}",
            )
        success_count = int(result.get("successCount") or 0)
        if success_count <= 0:
            return CrudResponseModel(is_success=False, message="回帖发送失败，请检查群锚点与飞书凭证后重试")
        return CrudResponseModel(
            is_success=True,
            message=f"回帖已补发到 {success_count} 个群",
        )
