from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from sqlalchemy.orm import Session

from config.database import SessionLocal
from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.entity.do.config_do import SysConfig
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
from module_admin.service.ai_provider_capability_service import AiProviderCapabilityService
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum, TstepTypeEnum
from module_qtr.service.agent_service import agents as connected_agents
from module_qtr.service.agent_service import send_message as agent_send_message
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
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ai.ticket_prompt_service import TicketPromptService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.notification.ticket_notify_service import TicketNotifyService
from utils.api_key_util import ApiKeyUtil
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
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
    CONFIG_LOG_ANALYSIS_MODE = "ticket.ai.logAnalysis.mode"
    CONFIG_LOG_WINDOW_MISSING_STRATEGY = "ticket.ai.logAnalysis.windowMissingStrategy"
    DEFAULT_WORKER_COMMAND = "codex exec"
    DEFAULT_WORKER_MODEL = ""
    DEFAULT_WORKER_SANDBOX = "workspace-write"
    DEFAULT_WORKER_TIMEOUT = 3600
    DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[4] / "logs" / "ticket_ai_analysis"
    DEFAULT_AGENT_CODE = ""
    DEFAULT_LOG_ANALYSIS_MODE = "digest"
    DEFAULT_LOG_WINDOW_MISSING_STRATEGY = "agent_extract"
    LOG_ANALYSIS_MODES = {"digest", "full_directory", "hybrid"}
    LOG_WINDOW_MISSING_STRATEGIES = {"server_extract", "agent_extract"}
    DEFAULT_CONTEXT_LOG_MAX_CHARS = 800_000
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
        if str(requested_agent_code or "").strip():
            return str(requested_agent_code).strip()
        configured_agent_code = cls._get_config_text(db, cls.CONFIG_AGENT_CODE, cls.DEFAULT_AGENT_CODE)
        if configured_agent_code:
            return configured_agent_code
        if connected_agents:
            return next(iter(connected_agents.keys()))
        return ""

    @classmethod
    def _validate_agent_connected(cls, db: Session, requested_agent_code: str | None = None) -> tuple[bool, str, str]:
        """
        校验 AI 分析任务提交时是否存在可用在线 Agent。
        :param db: 数据库会话
        :param requested_agent_code: 请求或 Provider 指定的 Agent 编码
        :return: (是否可用, 错误信息, 实际解析到的 Agent 编码)
        """
        agent_code = cls._resolve_agent_code(db, requested_agent_code)
        if not agent_code:
            return False, "未找到可用的在线 Agent，请先启动本地 Agent 并连接到服务端", ""
        if agent_code not in connected_agents:
            return False, f"Agent[{agent_code}]未连接服务端，请先启动本地 Agent 并确认连接正常", agent_code
        return True, "", agent_code

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
    def _build_provider_env_overrides(cls, provider) -> dict[str, str]:
        """
        根据 Provider 配置构建 Worker 环境变量覆盖项。
        Codex 使用 OPENAI_API_KEY，Claude Code 使用 ANTHROPIC_API_KEY，
        同时保留对方 key 的兼容性。
        :param provider: Provider数据库对象
        :return: 环境变量覆盖项
        """
        if not provider:
            return {}
        env_overrides: dict[str, str] = {}
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
        if provider_name:
            env_overrides["AI_PROVIDER_NAME"] = provider_name
        platform_code = str(getattr(provider, "platform_code", "") or "").strip()
        if platform_code:
            env_overrides["AI_PROVIDER_PLATFORM"] = platform_code
        if getattr(provider, "provider_level", None) is not None:
            env_overrides["AI_PROVIDER_LEVEL"] = str(provider.provider_level)
        env_overrides.update(cls._normalize_provider_worker_env(getattr(provider, "worker_env", None)))
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
        version_key: str,
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
5. 输出严格 JSON，不要输出多余说明文本。
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
                "ticket_id": {"type": "integer", "default": ticket.ticket_id},
                "project_id": {"type": ["integer", "null"], "default": ticket.project_id},
                "version_key": {"type": ["string", "null"], "default": version_key},
                "repo_url": {"type": ["string", "null"], "default": mapping.repo_url},
                "branch_name": {"type": ["string", "null"], "default": mapping.branch_name},
                "root_cause": {"type": "string", "default": ""},
                "analysis_summary": {"type": "string", "default": ""},
                "related_files": {"type": "array", "items": {"type": "string"}, "default": []},
                "related_functions": {"type": "array", "items": {"type": "string"}, "default": []},
                "fix_suggestion": {"type": "string", "default": ""},
                "confidence": {"type": "number", "default": 0},
                "evidence": {"type": "array", "items": {"type": "string"}, "default": []},
                "risk_items": {"type": "array", "items": {"type": "string"}, "default": []},
                "next_steps": {"type": "array", "items": {"type": "string"}, "default": []},
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
        normalized.setdefault("ticket_id", ticket.ticket_id)
        normalized.setdefault("project_id", ticket.project_id)
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
        return cls._json_safe_value(normalized)

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
        cls._create_rca_from_result(db, ticket, result_payload, current_user)
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
                owner=str(result_payload.get("owner_suggestion") or ""),
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
    def _mark_task_status(
        cls,
        db: Session,
        task_id: int,
        *,
        status: str,
        status_desc: str,
        error_message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        analysis_result: dict[str, Any] | None = None,
        raw_output: str | None = None,
        command_line: str | None = None,
    ) -> None:
        """
        更新 AI 分析任务状态。
        :param db: 数据库会话
        :param task_id: 任务ID
        :param status: 任务状态
        :param status_desc: 状态描述
        :param error_message: 错误信息
        :param started_at: 开始时间
        :param finished_at: 结束时间
        :param analysis_result: 分析结果
        :param raw_output: 原始输出
        :param command_line: 执行命令
        :return: 无
        """
        update_data = {
            "status": status,
            "status_desc": status_desc,
            "error_message": error_message,
            "started_at": started_at,
            "finished_at": finished_at,
            "command_line": command_line,
            "update_time": datetime.now(),
        }
        if analysis_result is not None:
            update_data["analysis_result"] = analysis_result
        if raw_output is not None:
            update_data["raw_output"] = raw_output
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
        if selected_provider_code:
            selected_provider = cls._resolve_ai_provider(db, selected_provider_code)
            if not selected_provider:
                return CrudResponseModel(is_success=False, message="未找到可用的AI Provider配置")
            try:
                AiProviderCapabilityService.require_provider_eligibility(
                    selected_provider,
                    usage="ticket_analysis_worker",
                    executor="codex",
                )
            except ValueError as exc:
                return CrudResponseModel(is_success=False, message=str(exc))
            context_payload["selectedAiProviderCode"] = selected_provider.provider_code
            context_payload["selectedAiProviderName"] = selected_provider.provider_name
            context_payload["selectedAiProviderPlatform"] = selected_provider.platform_code
            context_payload["selectedAiProviderProtocol"] = selected_provider.api_protocol
            context_payload["selectedWorkerModel"] = selected_provider.default_model
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
                context_payload["selectedAgentCode"] = str(selected_provider.preferred_agent_code).strip()
        if request.agent_code:
            context_payload["selectedAgentCode"] = request.agent_code
        agent_available, agent_error_message, resolved_agent_code = cls._validate_agent_connected(
            db, str(context_payload.get("selectedAgentCode") or "").strip()
        )
        if not agent_available:
            return CrudResponseModel(is_success=False, message=agent_error_message)
        context_payload["selectedAgentCode"] = resolved_agent_code
        if str(request.extra_instruction or "").strip():
            context_payload["extraInstruction"] = str(request.extra_instruction).strip()
        context_payload["promptLayers"] = prompt_layers
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

        now = datetime.now()
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
            source_log_pull_record_id=context_payload.get("sourceLogPullRecordId"),
            source_log_view_mode=str(context_payload.get("sourceLogViewMode") or "stored"),
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
            return CrudResponseModel(is_success=True, message="AI分析任务已提交", result=result)
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
        if task.status == TicketAiAnalysisStatus.SUCCESS.value and task.analysis_result:
            return CrudResponseModel(
                is_success=True,
                message="AI分析任务已完成，直接返回历史结果",
                result=CamelCaseUtil.transform_result(task),
            )
        with cls._executor_lock:
            if task_id in cls._active_task_ids:
                return CrudResponseModel(is_success=False, message="当前AI分析任务正在执行中，请稍后重试")
        now = datetime.now()
        update_data: dict[str, Any] = {
            "update_by": cls._user_name(current_user),
            "update_time": now,
        }
        if task.status in (TicketAiAnalysisStatus.FAILED.value, TicketAiAnalysisStatus.CANCELED.value):
            update_data.update(
                {
                    "status": TicketAiAnalysisStatus.CREATED.value,
                    "status_desc": "待重试",
                    "error_message": None,
                    "started_at": None,
                    "finished_at": None,
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
            )
        except Exception:
            db.rollback()
            raise

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
        :param task: 任务对象
        :return: 摘要字典
        """
        item = CamelCaseUtil.transform_result(task)
        result_payload = item.get("analysisResult") if isinstance(item, dict) else None
        item["analysisSummary"] = (
            (result_payload or {}).get("analysisSummary") if isinstance(result_payload, dict) else None
        )
        item["rootCause"] = (result_payload or {}).get("rootCause") if isinstance(result_payload, dict) else None
        item["fixSuggestion"] = (
            (result_payload or {}).get("fixSuggestion") if isinstance(result_payload, dict) else None
        )
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
        :return: 无
        """
        with SessionLocal() as db:
            tasks = TicketAiDao.list_recoverable_tasks(db, list(cls.ACTIVE_STATUSES))
            now = datetime.now()
            for task in tasks:
                cls._mark_task_status(
                    db,
                    task.task_id,
                    status=TicketAiAnalysisStatus.FAILED.value,
                    status_desc="服务重启前任务未完成，已清理为失败",
                    error_message="服务重启前任务未完成，已清理为失败",
                    finished_at=now,
                )
            if tasks:
                db.commit()

    @classmethod
    def _run_task(cls, task_id: int) -> None:
        """
        在线程池中执行单条 AI 分析任务。
        :param task_id: 任务ID
        :return: 无
        """
        try:
            with SessionLocal() as db:
                cls._log_task_step(task_id, "RUN", "开始执行 AI 分析任务")
                cls._process_task(db, task_id)
        except Exception as exc:
            logger.exception(f"AI分析任务[{task_id}] 线程执行异常: {exc}")
        finally:
            with cls._executor_lock:
                cls._active_task_ids.discard(task_id)

    @classmethod
    def _finalize_sync_publish_after_ai(cls, db: Session, *, ticket_id: int, status: str) -> None:
        """
        AI 任务终态后回写工单同步发布状态。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param status: AI任务状态
        :return: 无
        """
        try:
            from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService

            TicketSyncGroupPushService.finalize_sync_after_ai(
                db,
                ticket_id=ticket_id,
                ai_task_status=status,
                sync_scene="external_sync",
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
        cls._log_task_step(task_id, "LOAD", "读取工单记录", ticket_id=getattr(task, "ticket_id", None))
        ticket = TicketDao.get_ticket_by_id(db, task.ticket_id)
        if not ticket:
            cls._log_task_step(task_id, "FAIL", "工单不存在或已删除", ticket_id=task.ticket_id)
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                status_desc="工单不存在",
                error_message="工单不存在或已删除",
                finished_at=datetime.now(),
            )
            db.commit()
            return
        source_log_pull_record = None
        notify_config: dict[str, Any] | None = None
        if getattr(task, "source_log_pull_record_id", None):
            source_log_pull_record = TicketLogPullDao.get_record_by_id(db, int(task.source_log_pull_record_id))
        if source_log_pull_record and isinstance(source_log_pull_record.command_content, dict):
            notify_config = source_log_pull_record.command_content.get(
                "notifyConfig"
            ) or source_log_pull_record.command_content.get("notify_config")
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
                error_message="未找到可用的项目版本仓库映射",
                finished_at=datetime.now(),
            )
            db.commit()
            cls._finalize_sync_publish_after_ai(
                db,
                ticket_id=ticket.ticket_id,
                status=TicketAiAnalysisStatus.FAILED.value,
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
        if isinstance(task.analysis_context, dict):
            fallback_log_mode = str(task.analysis_context.get("logAnalysisMode") or "digest")
        version_key = cls._get_version_key(db, task.version_id)
        prompt_template = task.prompt_text or cls._build_prompt(
            "{workspace_path}",
            mapping,
            ticket,
            version_key=version_key,
            log_analysis_mode=fallback_log_mode,
            source_logs_path="{source_logs_path}",
        )
        schema_payload = cls._build_result_schema(ticket, mapping, version_key)
        timeout_sec = cls._get_config_int(db, cls.CONFIG_WORKER_TIMEOUT, cls.DEFAULT_WORKER_TIMEOUT)
        context_payload = cls._load_workspace_context_payload(db, task, ticket, mapping, workspace_dir)
        requested_provider_code = str((context_payload or {}).get("selectedAiProviderCode") or "").strip()
        selected_provider = cls._resolve_ai_provider(db, requested_provider_code) if requested_provider_code else None
        if selected_provider:
            AiProviderCapabilityService.require_provider_eligibility(
                selected_provider,
                usage="ticket_analysis_worker",
                executor="codex",
            )
        provider_env_overrides = cls._build_provider_env_overrides(selected_provider) if selected_provider else {}
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
            connected_agent_count=len(connected_agents),
        )
        if not agent_code:
            cls._log_task_step(task_id, "FAIL", "未找到可用的在线 Agent")
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                status_desc="未找到Agent",
                error_message="未找到可用的在线 Agent，请先启动本地 Agent 并连接到服务端",
                finished_at=datetime.now(),
                command_line="agent:<none>",
            )
            db.commit()
            cls._finalize_sync_publish_after_ai(
                db,
                ticket_id=ticket.ticket_id,
                status=TicketAiAnalysisStatus.FAILED.value,
            )
            return
        started_at = datetime.now()
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
            )
            cls._log_task_step(
                task_id,
                "EXEC",
                "发送 AI 分析任务到 Agent",
                agent_code=agent_code,
                request_type=TstepTypeEnum.ai_analysis.value,
                timeout_sec=timeout_sec,
            )
            agent_response = asyncio.run(
                agent_send_message(
                    agent_code,
                    request_payload,
                    timeout_seconds=timeout_sec,
                )
            )
            response_object = getattr(agent_response, "response", None)
            if isinstance(response_object, dict):
                response_dump = response_object
            elif response_object is not None and hasattr(response_object, "model_dump"):
                response_dump = response_object.model_dump()
            else:
                response_dump = {}
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
                response_result_preview=response_result_preview,
            )
            if getattr(agent_response, "status_code", 500) != 200 or not bool(
                getattr(response_object, "success", True)
            ):
                failure_message = (
                    getattr(response_object, "message", None)
                    or getattr(agent_response, "message", None)
                    or "Agent 返回失败"
                )
                cls._log_task_step(task_id, "FAIL", "Agent 执行失败", error=failure_message)
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
                cls._log_task_step(task_id, "FAIL", "Agent 未返回可解析的分析结果")
                failure_message = (
                    response_payload.get("error_message")
                    or response_payload.get("message")
                    or getattr(agent_response, "message", None)
                    or "AI Agent 未返回可解析的分析结果"
                )
                raise ValueError(failure_message)
            normalized = cls._normalize_analysis_result(
                result_payload=parsed_result,
                ticket=ticket,
                mapping=mapping,
                version_key=version_key,
            )
            cls._log_task_step(task_id, "PERSIST", "写回工单与 RCA 结果")
            cls._persist_success_result(db, task, ticket, normalized, result_text or raw_stdout, None)
            finished_at = datetime.now()
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.SUCCESS.value,
                status_desc="分析成功",
                finished_at=finished_at,
                analysis_result=normalized,
                raw_output=result_text or raw_stdout,
                command_line=f"agent:{agent_code}",
            )
            db.commit()
            cls._finalize_sync_publish_after_ai(
                db,
                ticket_id=ticket.ticket_id,
                status=TicketAiAnalysisStatus.SUCCESS.value,
            )
            TicketNotifyService.send_ticket_notification(
                db,
                ticket,
                title="工单AI分析结果通知",
                status="success",
                message="AI分析已完成",
                detail=f"task_id={task_id}, version_id={task.version_id}",
                notify_config=notify_config,
            )
            cls._log_task_step(task_id, "DONE", "AI 分析任务完成")
            return
        except Exception as exc:
            cls._log_task_step(task_id, "ERROR", "AI 分析任务执行失败", error=str(exc))
            logger.exception(f"AI分析任务[{task_id}] 执行失败")
            failure_message = cls._summarize_worker_error(raw_stderr, raw_stdout, str(exc))
            cls._mark_task_status(
                db,
                task_id,
                status=TicketAiAnalysisStatus.FAILED.value,
                status_desc="分析失败",
                error_message=failure_message,
                finished_at=datetime.now(),
                command_line=f"agent:{agent_code}",
            )
            db.commit()
            if "ticket" in locals() and ticket:
                cls._finalize_sync_publish_after_ai(
                    db,
                    ticket_id=ticket.ticket_id,
                    status=TicketAiAnalysisStatus.FAILED.value,
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
                )
            return
