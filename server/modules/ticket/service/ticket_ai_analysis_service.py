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
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from sqlalchemy.orm import Session

from config.database import SessionLocal
from module_admin.entity.do.config_do import SysConfig
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum, TstepTypeEnum
from module_qtr.service.agent_service import agents as connected_agents
from module_qtr.service.agent_service import send_message as agent_send_message
from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketAiAnalysisTask, TicketAiRepoMapping, TicketEvent, TicketRca
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullRecord
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullContentQueryModel
from modules.ticket.entity.vo.ticket_vo import (
    TicketAiAnalysisRequestModel,
    TicketAiAnalysisTaskQueryModel,
    TicketAiRepoMappingCreateModel,
    TicketAiRepoMappingQueryModel,
    TicketAiRepoMappingUpdateModel,
)
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus, TicketEventType
from modules.ticket.service.ticket_log_pull_service import TicketLogPullService
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
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
    DEFAULT_WORKER_COMMAND = "codex exec"
    DEFAULT_WORKER_MODEL = ""
    DEFAULT_WORKER_SANDBOX = "workspace-write"
    DEFAULT_WORKER_TIMEOUT = 3600
    DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[4] / "logs" / "ticket_ai_analysis"
    DEFAULT_AGENT_CODE = ""
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
                "未找到可执行的 codex Worker，请检查 codex 是否已安装并加入 PATH，"
                "或在系统参数中配置完整命令"
            )

        if resolved_executable.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", resolved_executable, *parts[1:]]
        return [resolved_executable, *parts[1:]]

    @classmethod
    def _prepare_codex_home(cls, workspace_dir: Path) -> Path:
        """
        准备独立的 Codex home 目录。
        :param workspace_dir: 当前任务工作区
        :return: Codex home 目录
        """
        source_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
        codex_home = workspace_dir / ".codex_home"
        codex_home.mkdir(parents=True, exist_ok=True)
        for file_name in ("config.toml", "config.self.toml", "auth.json", "version.json"):
            source_file = source_home / file_name
            target_file = codex_home / file_name
            if source_file.exists() and not target_file.exists():
                shutil.copy2(source_file, target_file)
        source_env = source_home / ".env"
        target_env = codex_home / ".env"
        if source_env.exists() and not target_env.exists():
            shutil.copy2(source_env, target_env)
        return codex_home

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
                logger.warning("读取 Codex .env 失败: %s", exc)
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
    def _resolve_version_key(cls, ticket: Ticket, request: TicketAiAnalysisRequestModel | None = None) -> str:
        """
        解析版本标识。
        :param ticket: 工单对象
        :param request: AI分析请求对象
        :return: 版本标识
        """
        if request and str(request.version_key or "").strip():
            return str(request.version_key).strip()
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        for key in ("versionKey", "version_key", "version", "deployVersion", "deploy_version", "appVersion"):
            value = extra_data.get(key)
            if str(value or "").strip():
                return str(value).strip()
        return ""

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
        version_key = cls._resolve_version_key(ticket, request)
        if not version_key:
            return None
        if request and request.mapping_id:
            mapping = TicketAiDao.get_repo_mapping_by_id(db, request.mapping_id)
            if (
                mapping
                and mapping.enabled
                and mapping.project_id == ticket.project_id
                and mapping.version_key == version_key
            ):
                return mapping
        if ticket.project_id:
            mapping = TicketAiDao.get_repo_mapping_by_project_and_version(db, ticket.project_id, version_key)
            if mapping:
                return mapping
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
            return TicketLogPullDao.get_record_by_id(db, record_id)
        latest_summary = TicketLogPullService.get_latest_summary(db, ticket_id)
        if not latest_summary or not latest_summary.get("id"):
            return None
        return TicketLogPullDao.get_record_by_id(db, int(latest_summary["id"]))

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

    @staticmethod
    def _build_agent_request_payload(
        *,
        task_id: int,
        ticket: Ticket,
        mapping: TicketAiRepoMapping,
        context_payload: dict[str, Any],
        ticket_payload: dict[str, Any],
        timeline_payload: Any,
        prompt_template: str,
        schema_payload: dict[str, Any],
        result_path: str,
        timeout_sec: int,
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
        :return: 请求体
        """
        return {
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
        }

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

    @classmethod
    def _build_context_payload(
        cls,
        db: Session,
        ticket: Ticket,
        mapping: TicketAiRepoMapping,
        log_record: TicketLogPullRecord | None,
    ) -> dict[str, Any]:
        """
        构建 AI 分析上下文快照。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param mapping: 仓库映射对象
        :param log_record: 日志拉取记录
        :return: 上下文字典
        """
        ticket_payload = CamelCaseUtil.transform_result(ticket)
        timeline_payload = TicketDao.get_timeline(db, ticket.ticket_id)
        latest_log_summary = TicketLogPullService.get_latest_summary(db, ticket.ticket_id)
        log_content_payload: dict[str, Any] | None = None
        source_log_view_mode = "stored"
        source_log_record_id: int | None = None
        if log_record:
            source_log_record_id = log_record.id
            try:
                log_content_model = TicketLogPullService.get_log_pull_content_services(
                    db,
                    log_record.id,
                    TicketLogPullContentQueryModel(view_mode="stored"),
                )
                if log_content_model:
                    log_content_payload = {
                        "recordId": log_content_model.record_id,
                        "viewBeginTime": log_content_model.view_begin_time,
                        "viewEndTime": log_content_model.view_end_time,
                        "viewSource": log_content_model.view_source,
                        "wholeArchiveMode": not bool(
                            log_content_model.view_begin_time or log_content_model.view_end_time
                        ),
                        "contentSummary": log_content_model.content_summary,
                        "matchedEntryCount": log_content_model.matched_entry_count,
                        "archiveEntryCount": log_content_model.archive_entry_count,
                        "storagePath": log_content_model.storage_path,
                        "commandResultUrl": log_content_model.command_result_url,
                        "text": cls._decode_log_text(log_content_model.text),
                    }
                    source_log_view_mode = str(log_content_model.view_source or "stored")
            except Exception as exc:
                logger.warning("获取工单日志上下文失败: %s", exc)
        return {
            "ticket": ticket_payload,
            "timeline": cls._json_safe_value(CamelCaseUtil.transform_result(timeline_payload)),
            "latestLogPull": cls._json_safe_value(latest_log_summary),
            "sourceLogPull": cls._json_safe_value(log_content_payload),
            "mapping": cls._json_safe_value(CamelCaseUtil.transform_result(mapping)),
            "sourceLogPullRecordId": source_log_record_id,
            "sourceLogViewMode": source_log_view_mode,
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
        snapshot: dict[str, Any] = {
            "ticketId": (context_payload.get("ticket") or {}).get("ticketId") if isinstance(context_payload, dict) else None,
            "projectId": (context_payload.get("ticket") or {}).get("projectId") if isinstance(context_payload, dict) else None,
            "versionKey": (context_payload.get("mapping") or {}).get("versionKey") if isinstance(context_payload, dict) else None,
            "sourceLogPullRecordId": context_payload.get("sourceLogPullRecordId") if isinstance(context_payload, dict) else None,
            "sourceLogViewMode": context_payload.get("sourceLogViewMode") if isinstance(context_payload, dict) else None,
            "forceRefresh": bool(request.force_refresh) if request else bool(context_payload.get("forceRefresh")) if isinstance(context_payload, dict) else False,
            "selectedAgentCode": str(request.agent_code or "").strip() if request and request.agent_code else str(context_payload.get("selectedAgentCode") or "").strip() if isinstance(context_payload, dict) else "",
        }
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
            for key in ("selectedAgentCode", "forceRefresh", "sourceLogPullRecordId", "sourceLogViewMode"):
                if key not in context_payload or context_payload.get(key) in (None, "", {}):
                    context_payload[key] = compact_context.get(key)
        return cls._json_safe_value(context_payload)

    @classmethod
    def _build_prompt(cls, workspace_path: str, mapping: TicketAiRepoMapping, ticket: Ticket) -> str:
        """
        构建 Codex 分析提示词。
        :param workspace_path: 任务工作区路径
        :param mapping: 仓库映射
        :param ticket: 工单对象
        :return: 提示词文本
        """
        return f"""你是工单自动分析 Worker，请基于当前工作区中的上下文进行根因分析。

当前任务目录:
{workspace_path}

仓库信息:
- 项目: {mapping.project_name}
- 版本: {mapping.version_key}
- 仓库地址: {mapping.repo_url}
- 分支: {mapping.branch_name}
- 本地仓库路径: {mapping.local_repo_path}

工单要求:
1. 只做分析，不修改代码、不提交代码。
2. 优先阅读 {workspace_path}/ticket.json、{workspace_path}/timeline.json、{workspace_path}/logs.txt。
3. 如果 `sourceLogPull.wholeArchiveMode` 为 true，或
   {workspace_path}/logs.txt 只是整包分析说明，请优先阅读 {workspace_path}/source_logs/ 目录中的解压日志文件，
   再结合代码搜索、调用链、日志和历史事件分析根因。
4. 输出严格 JSON，不要输出多余说明文本。
5. 结果必须包含以下字段:
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
   - needs_human_review

工单基础信息:
- ticket_id: {ticket.ticket_id}
- ticket_no: {ticket.ticket_no}
- title: {ticket.title}
- description: {ticket.description or ""}
"""

    @classmethod
    def _build_result_schema(cls, ticket: Ticket, mapping: TicketAiRepoMapping) -> dict[str, Any]:
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
                "version_key": {"type": ["string", "null"], "default": mapping.version_key},
                "repo_url": {"type": ["string", "null"], "default": mapping.repo_url},
                "branch_name": {"type": ["string", "null"], "default": mapping.branch_name},
                "root_cause": {"type": "string"},
                "analysis_summary": {"type": "string"},
                "related_files": {"type": "array", "items": {"type": "string"}},
                "related_functions": {"type": "array", "items": {"type": "string"}},
                "fix_suggestion": {"type": "string"},
                "confidence": {"type": "number"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "risk_items": {"type": "array", "items": {"type": "string"}},
                "next_steps": {"type": "array", "items": {"type": "string"}},
                "needs_human_review": {"type": "boolean"},
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
                "needs_human_review",
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
        worker_model = str(settings.get("model") or "").strip()
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
        return command, repo_path, timeout_sec, cls._prepare_codex_home(workspace_dir)

    @classmethod
    def _execute_worker(
        cls,
        *,
        command: list[str],
        prompt_text: str,
        timeout_sec: int,
        cwd: Path,
        codex_home: Path,
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
            logger.warning("写入 Worker 流文件失败: %s", exc)

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
            re.sub(r"\s+", " ", item.strip())
            for item in lines[-20:]
            if item.strip() not in {"{", "}", "[", "]"}
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
                re.sub(r"\s+", " ", item.strip())
                for item in lines[-5:]
                if item.strip() not in {"{", "}", "[", "]"}
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
        normalized.setdefault("version_key", mapping.version_key)
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
                symptom=ticket.description or result_payload.get("analysis_summary") or "",
                root_cause_category="AI分析",
                root_cause_detail=str(result_payload.get("root_cause") or ""),
                trigger_reason=str(result_payload.get("analysis_summary") or ""),
                impact_scope="",
                reproduce_steps="",
                investigation_process=str(result_payload.get("analysis_summary") or ""),
                fix_solution=str(result_payload.get("fix_suggestion") or ""),
                verify_method="",
                prevention_solution="\n".join(result_payload.get("next_steps") or []),
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
                "root_cause": str(result_payload.get("root_cause") or ticket.root_cause or ""),
                "solution": str(result_payload.get("fix_suggestion") or ticket.solution or ""),
                "update_by": cls._user_name(current_user) if current_user else "system",
                "update_time": now,
            },
        )
        cls._create_rca_from_result(db, ticket, result_payload, current_user)
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
                    "version_key": task.version_key,
                    "repo_url": task.repo_url,
                    "branch_name": task.branch_name,
                    "analysis_result": cls._json_safe_value(result_payload),
                    "raw_output": raw_output[:5000],
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
        version_key = cls._resolve_version_key(ticket, request)
        if not version_key:
            return CrudResponseModel(is_success=False, message="请先完善版本号信息后再发起AI分析")
        mapping = cls._resolve_mapping(db, ticket, request)
        if not mapping:
            return CrudResponseModel(is_success=False, message="未找到可用的项目版本仓库映射，请先维护映射配置")
        log_record = cls._resolve_log_pull_record(db, ticket_id, request.log_pull_record_id)
        context_payload = cls._build_context_payload(db, ticket, mapping, log_record)
        context_payload["forceRefresh"] = bool(request.force_refresh)
        if request.agent_code:
            context_payload["selectedAgentCode"] = request.agent_code
        workspace_root = cls._resolve_workspace_root(db)
        task_id = snowIdWorker.get_id()
        workspace_dir = workspace_root / f"ticket_{ticket.ticket_id}" / f"task_{task_id}"
        task_context_payload = cls._build_task_context_snapshot(context_payload, request)

        prompt_template = cls._build_prompt("{workspace_path}", mapping, ticket)
        schema_payload = cls._build_result_schema(ticket, mapping)

        now = datetime.now()
        task = TicketAiAnalysisTask(
            task_id=task_id,
            ticket_id=ticket.ticket_id,
            project_id=ticket.project_id,
            mapping_id=mapping.mapping_id,
            project_name=cls._resolve_project_name(db, ticket.project_id),
            version_key=mapping.version_key,
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
                        "version_key": mapping.version_key,
                        "repo_url": mapping.repo_url,
                        "branch_name": mapping.branch_name,
                        "agent_code": request.agent_code or None,
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
                        "version_key": task.version_key,
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
    def list_repo_mapping_services(
        cls, db: Session, query: TicketAiRepoMappingQueryModel
    ):
        """
        查询工单 AI 仓库映射列表。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 分页结果或列表
        """
        result = TicketAiDao.list_repo_mappings(db, query)
        if query.is_page:
            result.rows = [CamelCaseUtil.transform_result(row) for row in result.rows]
            return result
        return [CamelCaseUtil.transform_result(row) for row in result]

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
        payload["project_name"] = (
            payload.get("project_name") or cls._resolve_project_name(db, payload.get("project_id"))
        )
        payload["worker_command"] = payload.get("worker_command") or cls._get_config_text(
            db, cls.CONFIG_WORKER_COMMAND, cls.DEFAULT_WORKER_COMMAND
        )
        payload["workspace_root"] = payload.get("workspace_root") or cls._get_config_text(
            db, cls.CONFIG_WORKSPACE_ROOT, str(cls.DEFAULT_WORKSPACE_ROOT)
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
    def get_task_list_services(
        cls, db: Session, ticket_id: int, query: TicketAiAnalysisTaskQueryModel
    ):
        """
        查询工单 AI 分析任务列表。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param query: 查询参数
        :return: 分页结果或列表
        """
        result = TicketAiDao.list_ticket_tasks(db, ticket_id, query)
        if query.is_page:
            result.rows = [CamelCaseUtil.transform_result(row) for row in result.rows]
            return result
        return [CamelCaseUtil.transform_result(row) for row in result]

    @classmethod
    def get_latest_summary_map(cls, db: Session, ticket_ids: list[int]) -> dict[int, dict[str, Any]]:
        """
        查询多个工单的最新 AI 分析摘要。
        :param db: 数据库会话
        :param ticket_ids: 工单ID列表
        :return: 以工单ID为键的摘要映射
        """
        latest_map = TicketAiDao.list_latest_tasks_by_ticket_ids(db, ticket_ids)
        return {ticket_id: cls._serialize_task_summary(task) for ticket_id, task in latest_map.items()}

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
        return cls._serialize_task_summary(task)

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
        服务启动后恢复待执行和运行中的 AI 任务。
        :return: 无
        """
        with SessionLocal() as db:
            tasks = TicketAiDao.list_recoverable_tasks(db, list(cls.ACTIVE_STATUSES))
            for task in tasks:
                cls.queue_task(task.task_id)

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
        cls._log_task_step(
            task_id,
            "RESOLVE",
            "解析仓库映射",
            project_id=ticket.project_id,
            version_key=task.version_key,
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
                version_key=task.version_key,
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
        prompt_template = task.prompt_text or cls._build_prompt("{workspace_path}", mapping, ticket)
        schema_payload = cls._build_result_schema(ticket, mapping)
        timeout_sec = cls._get_config_int(db, cls.CONFIG_WORKER_TIMEOUT, cls.DEFAULT_WORKER_TIMEOUT)
        context_payload = cls._load_workspace_context_payload(db, task, ticket, mapping, workspace_dir)
        requested_agent_code = str((context_payload or {}).get("selectedAgentCode") or "").strip()
        agent_code = cls._resolve_agent_code(db, requested_agent_code)
        cls._log_task_step(
            task_id,
            "AGENT",
            "解析 AI 执行 Agent",
            agent_code=agent_code or "<none>",
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
            normalized = cls._normalize_analysis_result(result_payload=parsed_result, ticket=ticket, mapping=mapping)
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
            return
