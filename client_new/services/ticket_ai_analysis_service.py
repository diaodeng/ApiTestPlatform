from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import zipfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from dotenv import dotenv_values
from loguru import logger
import httpx

from server.config import AgentConfig
from utils.common import get_client_root_dir

EventSender = Callable[[dict[str, Any]], Awaitable[None]]


class TicketAiAnalysisService:
    """
    client_new 侧工单 AI 分析执行服务。
    """

    DEFAULT_TIMEOUT_SEC = 3600
    DEFAULT_WORKER_COMMAND = "codex exec"
    DEFAULT_WORKER_SANDBOX = "workspace-write"
    DEFAULT_LOG_DIGEST_MAX_CHARS = 300000
    DEFAULT_LOG_DIGEST_MAX_MATCHES_PER_FILE = 80
    DEFAULT_LOG_DIGEST_CONTEXT_LINES = 3
    DEFAULT_LOG_DIGEST_MAX_LINE_CHARS = 1200

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
        repo_path: Path,
        env_values: dict[str, str],
        timeout_sec: int,
    ) -> subprocess.CompletedProcess:
        """
        在后台线程中执行 Worker 进程，避免阻塞 Agent 事件循环。
        :param command: Worker 命令
        :param resolved_prompt: 发送给 Worker 的提示词
        :param repo_path: 仓库路径
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
            cwd=str(repo_path),
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
            payload = json.loads(path.read_text(encoding="utf-8"))
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
    def _load_cached_result(cls, result_file: Path) -> dict[str, Any] | None:
        """
        读取已完成的分析结果缓存。
        :param result_file: 结果文件路径
        :return: 缓存结果，失败返回 None
        """
        payload = cls._read_json_file(result_file)
        if not cls._is_valid_cached_result(payload):
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
        判断锁文件是否已经过期。
        :param lock_payload: 锁文件内容
        :param timeout_sec: 当前任务超时时间
        :return: 是否过期
        """
        if not isinstance(lock_payload, dict):
            return True
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
    def _extract_archive(archive_path: Path, extract_dir: Path) -> list[str]:
        """
        解压日志压缩包到工作区目录。
        :param archive_path: 压缩包路径
        :param extract_dir: 解压目录
        :return: 解压后的文件相对路径列表
        """
        extract_dir.mkdir(parents=True, exist_ok=True)
        extracted_files: list[str] = []
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                if member.endswith("/"):
                    continue
                zip_ref.extract(member, extract_dir)
                extracted_files.append(member)
        return extracted_files

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
            "请优先基于本摘要分析；只有摘要证据不足时，才按本文件中的文件名和行号去 source_logs 定点读取原始日志。",
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
            "error:",
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
    ) -> str:
        """
        构建分析提示词。
        :param workspace_path: 本地工作区路径
        :param mapping: 仓库映射
        :param ticket: 工单信息
        :param repo_path: 实际使用的本地仓库路径。
        :param workspace_root: 实际使用的工作区根目录。
        :return: 提示词文本
        """
        resolved_repo_path = repo_path or mapping.get("resolvedLocalRepoPath") or mapping.get("resolved_local_repo_path")
        resolved_repo_path = resolved_repo_path or mapping.get("localRepoPath") or mapping.get("local_repo_path") or ""
        resolved_workspace_root = workspace_root or mapping.get("workspaceRoot") or mapping.get("workspace_root") or ""
        fallback_workspace_root = str(Path(workspace_path).parent.parent)
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
3. 如果 `sourceLogPull.wholeArchiveMode` 为 true，或 {workspace_path}/logs.txt 只有说明而没有正文，请优先阅读
   {workspace_path}/logs_ai_digest.txt；只有摘要证据不足时，才按摘要中的文件名和行号去
   {workspace_path}/source_logs/ 目录定点读取原始日志，禁止无目标地通读整包日志。
4. 输出严格 JSON，不要输出多余说明文本。
4. 工单不是一次性分析，请结合 context.json 中的 messages、snapshots 和 similarTickets：
   - messages 是持续追问和协同排查上下文，必须优先参考最新用户追问。
   - snapshots 是历史 ACR 版本，新的结论需要说明相对上一版的变化。
   - similarTickets 是历史相似工单，若可复用经验，请写入 similar_cases、sop_suggestion、
     owner_suggestion、monitoring_suggestion。
5. 输出严格 JSON，不要输出多余说明文本。
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
        if not task_id or not ticket_id:
            return {
                "request_type": req_data.get("requestType"),
                "command": req_data.get("command"),
                "success": False,
                "status": "failed",
                "message": "taskId 或 ticketId 不能为空",
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
            cached_result = cls._load_cached_result(result_file)
            if cached_result:
                await cls._emit_event(
                    event_sender,
                    "ai_analysis_finished",
                    task_id,
                    "命中本地缓存结果，直接返回",
                    workspace_path=str(workspace_dir),
                )
                result_text = cls._dumps(cached_result)
                return {
                    "request_type": req_data.get("requestType"),
                    "command": req_data.get("command"),
                    "success": True,
                    "status": "success",
                    "message": "AI 分析已完成，直接返回缓存结果",
                    "result": {
                        "analysis_result": cached_result,
                        "raw_output": result_text,
                        "workspace_path": str(workspace_dir),
                        "result_path": str(result_file),
                        "command_line": "cached:result.json",
                        "stdout_path": str(workspace_dir / "worker.stdout.txt"),
                        "stderr_path": str(workspace_dir / "worker.stderr.txt"),
                    },
                }
            lock_payload = cls._read_json_file(task_lock_file)
            if task_lock_file.exists() and not cls._is_stale_lock(lock_payload, timeout_sec):
                failure_message = "当前任务正在分析中，请稍后重试"
                await cls._emit_event(event_sender, "ai_analysis_status", task_id, failure_message)
                return {
                    "request_type": req_data.get("requestType"),
                    "command": req_data.get("command"),
                    "success": False,
                    "status": "running",
                    "message": failure_message,
                    "error_message": failure_message,
                }
            cls._release_task_lock(task_lock_file)
            if not cls._acquire_task_lock(
                task_lock_file,
                {
                    "taskId": task_id,
                    "ticketId": ticket_id,
                    "status": "running",
                    "startedAt": datetime.now().isoformat(),
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
                    "error_message": failure_message,
                }
            try:
                ticket_file.write_text(cls._dumps(ticket), encoding="utf-8")
                timeline_file.write_text(cls._dumps(timeline_payload), encoding="utf-8")
                context_file.write_text(cls._dumps(context_payload), encoding="utf-8")
                source_log_pull = context_payload.get("sourceLogPull") or {}
                logs_text = str(source_log_pull.get("text") or "")
                command_result_url = str(source_log_pull.get("commandResultUrl") or "").strip()
                storage_path = str(source_log_pull.get("storagePath") or "").strip()
                whole_archive_mode = bool(source_log_pull.get("wholeArchiveMode"))
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
                                    f"AI预筛选摘要: {log_digest_file}",
                                    f"压缩包地址: {archive_url or '<none>'}",
                                    f"压缩包本地路径: {source_logs_zip}",
                                    f"解压目录: {source_logs_dir}",
                                    "请优先阅读 AI 预筛选摘要，摘要不足时再定点读取原始日志。",
                                ]
                            ),
                            encoding="utf-8",
                        )
                    else:
                        logs_file.write_text(
                            "日志内容未入库，当前任务为时间范围模式或未配置整包分析。",
                            encoding="utf-8",
                        )
                    if whole_archive_mode and archive_url and str(archive_url).lower().startswith(("http://", "https://")):
                        await cls._emit_event(
                            event_sender,
                            "ai_analysis_status",
                            task_id,
                            "下载并解压整包日志",
                            archive_url=archive_url,
                            archive_path=str(source_logs_zip),
                            extract_dir=str(source_logs_dir),
                        )
                        downloaded = cls._download_archive(str(archive_url), source_logs_zip)
                        digest_payload: dict[str, Any] = {}
                        if downloaded:
                            extracted_files = cls._extract_archive(downloaded, source_logs_dir)
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
                                    "aiDigest": digest_payload,
                                }
                            ),
                            encoding="utf-8",
                        )
                schema_file.write_text(cls._dumps(schema_payload), encoding="utf-8")

                mapping["resolvedLocalRepoPath"] = str(repo_path)
                mapping["resolvedBranchName"] = current_branch
                resolved_prompt = prompt_template.replace("{workspace_path}", str(workspace_dir))
                if not resolved_prompt:
                    resolved_prompt = cls._build_prompt(
                        str(workspace_dir),
                        mapping,
                        ticket,
                        repo_path=str(repo_path),
                        workspace_root=str(workspace_root),
                    )
                prompt_file.write_text(resolved_prompt, encoding="utf-8")

                command = cls._resolve_worker_command_parts(
                    [
                        *cls.DEFAULT_WORKER_COMMAND.split(),
                        "-s",
                        cls.DEFAULT_WORKER_SANDBOX,
                        "-C",
                        str(repo_path),
                        "--skip-git-repo-check",
                        "--output-schema",
                        str(schema_file),
                        "--output-last-message",
                        str(result_file),
                    ]
                )
                command = cls._inject_worker_model(command, selected_worker_model)
                codex_home = cls._prepare_codex_home(workspace_dir)
                env_values = cls._load_codex_env(codex_home)
                env_values["CODEX_HOME"] = str(codex_home)
                env_values = cls._apply_env_overrides(env_values, provider_env_overrides)

                await cls._emit_event(
                    event_sender,
                    "ai_analysis_step",
                    task_id,
                    "开始执行 Worker",
                    command_line=" ".join(command),
                    repo_path=str(repo_path),
                    branch_name=current_branch,
                    workspace_root=str(workspace_root),
                    workspace_path=str(workspace_dir),
                    codex_home=str(codex_home),
                    provider_code=request_provider_code or "<none>",
                    worker_model=selected_worker_model or "<default>",
                )
                worker_started_at = time.monotonic()
                process = await cls._run_worker_process(command, resolved_prompt, repo_path, env_values, timeout_sec)
                worker_elapsed = round(time.monotonic() - worker_started_at, 3)
                raw_stdout = process.stdout or ""
                raw_stderr = process.stderr or ""
                cls._persist_worker_streams(workspace_dir, raw_stdout, raw_stderr)
                await cls._emit_event(
                    event_sender,
                    "ai_analysis_step",
                    task_id,
                    "Worker 执行结束",
                    return_code=process.returncode,
                    elapsed_sec=worker_elapsed,
                    stdout_len=len(raw_stdout),
                    stderr_len=len(raw_stderr),
                    stderr_context=cls._extract_stderr_context(raw_stderr),
                )

                result_text = ""
                if result_file.exists():
                    result_text = result_file.read_text(encoding="utf-8")
                elif raw_stdout.strip():
                    result_text = raw_stdout.strip().splitlines()[-1]
                elif raw_stderr.strip():
                    result_text = raw_stderr.strip()

                parsed_result: dict[str, Any] | None = None
                if result_text.strip():
                    try:
                        parsed_result = json.loads(result_text)
                    except Exception:
                        try:
                            parsed_result = json.loads(raw_stdout.strip().splitlines()[-1])
                        except Exception:
                            parsed_result = None
                if not parsed_result:
                    failure_message = (
                        cls._extract_stderr_context(raw_stderr)
                        or cls._extract_stderr_context(raw_stdout)
                        or cls._summarize_worker_error(raw_stderr, raw_stdout, "AI Worker 未返回可解析的 JSON 结果")
                    )
                    failure_message = cls._normalize_worker_failure_message(failure_message)
                    await cls._emit_event(event_sender, "ai_analysis_error", task_id, failure_message)
                    return {
                        "request_type": req_data.get("requestType"),
                        "command": req_data.get("command"),
                        "success": False,
                        "status": "failed",
                        "message": failure_message,
                        "error_message": failure_message,
                        "result": {
                            "workspace_path": str(workspace_dir),
                            "result_path": str(result_file),
                            "command_line": " ".join(command),
                            "stdout_path": str(workspace_dir / "worker.stdout.txt"),
                            "stderr_path": str(workspace_dir / "worker.stderr.txt"),
                            "stderr_context": cls._extract_stderr_context(raw_stderr),
                        },
                    }

                normalized_result = parsed_result
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
                    "result": {
                        "analysis_result": normalized_result,
                        "raw_output": result_text or raw_stdout,
                        "workspace_path": str(workspace_dir),
                        "result_path": str(result_file),
                        "command_line": " ".join(command),
                        "stdout_path": str(workspace_dir / "worker.stdout.txt"),
                        "stderr_path": str(workspace_dir / "worker.stderr.txt"),
                    },
                }
            finally:
                cls._release_task_lock(task_lock_file)
        except subprocess.TimeoutExpired as exc:
            failure_message = f"AI Worker 执行超时：{exc}"
            await cls._emit_event(event_sender, "ai_analysis_error", task_id, failure_message)
            return {
                "request_type": req_data.get("requestType"),
                "command": req_data.get("command"),
                "success": False,
                "status": "timeout",
                "message": failure_message,
                "error_message": failure_message,
            }
        except Exception as exc:
            logger.exception(f"AI分析Agent任务[{task_id}] 执行失败: {exc}")
            failure_message = cls._summarize_worker_error(None, None, str(exc))
            await cls._emit_event(event_sender, "ai_analysis_error", task_id, failure_message, error=str(exc))
            return {
                "request_type": req_data.get("requestType"),
                "command": req_data.get("command"),
                "success": False,
                "status": "failed",
                "message": failure_message,
                "error_message": failure_message,
            }
