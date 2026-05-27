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

from utils.common import get_client_root_dir

EventSender = Callable[[dict[str, Any]], Awaitable[None]]


class TicketAiAnalysisService:
    """
    client_new 侧工单 AI 分析执行服务。
    """

    DEFAULT_TIMEOUT_SEC = 3600
    DEFAULT_WORKER_COMMAND = "codex exec"
    DEFAULT_WORKER_SANDBOX = "workspace-write"

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
            raise FileNotFoundError("未找到可执行的 codex Worker，请检查 codex 是否已安装并加入 PATH")
        if resolved_executable.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", resolved_executable, *parts[1:]]
        return [resolved_executable, *parts[1:]]

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

    @staticmethod
    def _extract_stderr_context(stderr_text: str | None, keywords: tuple[str, ...] = ("invalid_request_error", "stream disconnected", "error sending request")) -> str:
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
        for idx, line in enumerate(lines):
            lower_line = line.strip().lower()
            if any(keyword in lower_line for keyword in lowered_keywords):
                start = max(0, idx - 10)
                end = min(len(lines), idx + 11)
                window = [re.sub(r"\s+", " ", item.strip()) for item in lines[start:end] if item.strip() not in {"{", "}", "[", "]"}]
                if window:
                    return " | ".join(window)[:4000]
        tail_lines = [re.sub(r"\s+", " ", item.strip()) for item in lines[-20:] if item.strip() not in {"{", "}", "[", "]"}]
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
            tail_lines = [re.sub(r"\s+", " ", item.strip()) for item in lines[-20:] if item.strip() not in {"{", "}", "[", "]"}]
            if tail_lines:
                return " | ".join(tail_lines)[:4000]
        return default_message

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
    def _build_prompt(workspace_path: str, mapping: dict[str, Any], ticket: dict[str, Any]) -> str:
        """
        构建分析提示词。
        :param workspace_path: 本地工作区路径
        :param mapping: 仓库映射
        :param ticket: 工单信息
        :return: 提示词文本
        """
        return f"""你是工单自动分析 Worker，请基于当前工作区中的上下文进行根因分析。

当前任务目录:
{workspace_path}

仓库信息:
- 项目: {mapping.get("projectName") or mapping.get("project_name") or ""}
- 版本: {mapping.get("versionKey") or mapping.get("version_key") or ""}
- 仓库地址: {mapping.get("repoUrl") or mapping.get("repo_url") or ""}
- 分支: {mapping.get("branchName") or mapping.get("branch_name") or ""}
- 本地仓库路径: {mapping.get("localRepoPath") or mapping.get("local_repo_path") or ""}

工单要求:
1. 只做分析，不修改代码、不提交代码。
2. 优先阅读 {workspace_path}/ticket.json、{workspace_path}/timeline.json、{workspace_path}/logs.txt。
3. 如果 `sourceLogPull.wholeArchiveMode` 为 true，或 {workspace_path}/logs.txt 只有说明而没有正文，请先阅读 {workspace_path}/source_logs/ 目录中的解压日志文件，再结合代码搜索、调用链、日志和历史事件分析根因。
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
- ticket_id: {ticket.get("ticketId") or ticket.get("ticket_id") or ""}
- ticket_no: {ticket.get("ticketNo") or ticket.get("ticket_no") or ""}
- title: {ticket.get("title") or ""}
- description: {ticket.get("description") or ""}
"""

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
            workspace_root = get_client_root_dir() / "storage" / "ticket_ai_analysis"
            workspace_dir = workspace_root / f"ticket_{ticket_id}" / f"task_{task_id}"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            schema_file = workspace_dir / "result.schema.json"
            result_file = workspace_dir / "result.json"
            prompt_file = workspace_dir / "prompt.txt"
            ticket_file = workspace_dir / "ticket.json"
            timeline_file = workspace_dir / "timeline.json"
            context_file = workspace_dir / "context.json"
            logs_file = workspace_dir / "logs.txt"
            source_logs_dir = workspace_dir / "source_logs"
            source_logs_zip = workspace_dir / "source_logs.zip"
            source_logs_manifest = workspace_dir / "source_logs_manifest.json"
            task_lock_file = workspace_dir / "analysis.lock"
            request_snapshot_file = workspace_dir / "request.snapshot.json"

            await cls._emit_event(event_sender, "ai_analysis_status", task_id, "准备本地工作区", workspace_path=str(workspace_dir))
            try:
                request_snapshot_file.write_text(
                    cls._dumps(
                        {
                            "taskId": task_id,
                            "ticketId": ticket_id,
                            "requestType": req_data.get("requestType"),
                            "command": req_data.get("command"),
                            "payloadSize": len(cls._dumps(req_data, indent=None)),
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
                                    f"压缩包地址: {archive_url or '<none>'}",
                                    f"压缩包本地路径: {source_logs_zip}",
                                    f"解压目录: {source_logs_dir}",
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
                        if downloaded:
                            extracted_files = cls._extract_archive(downloaded, source_logs_dir)
                        source_logs_manifest.write_text(
                            cls._dumps(
                                {
                                    "archiveUrl": archive_url or "",
                                    "archivePath": str(source_logs_zip),
                                    "extractDir": str(source_logs_dir),
                                    "extractedFiles": extracted_files,
                                }
                            ),
                            encoding="utf-8",
                        )
                schema_file.write_text(cls._dumps(schema_payload), encoding="utf-8")

                resolved_prompt = prompt_template.replace("{workspace_path}", str(workspace_dir))
                if not resolved_prompt:
                    resolved_prompt = cls._build_prompt(str(workspace_dir), mapping, ticket)
                prompt_file.write_text(resolved_prompt, encoding="utf-8")

                repo_path_text = str(mapping.get("localRepoPath") or mapping.get("local_repo_path") or "").strip()
                repo_path = Path(repo_path_text).expanduser()
                if not repo_path.is_absolute():
                    repo_path = repo_path.resolve()
                if not repo_path.exists():
                    raise FileNotFoundError(f"本地仓库路径不存在: {repo_path}")

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
                codex_home = cls._prepare_codex_home(workspace_dir)
                env_values = cls._load_codex_env(codex_home)
                env_values["CODEX_HOME"] = str(codex_home)

                await cls._emit_event(
                    event_sender,
                    "ai_analysis_step",
                    task_id,
                    "开始执行 Worker",
                    command_line=" ".join(command),
                    repo_path=str(repo_path),
                    codex_home=str(codex_home),
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
                            "stdout": raw_stdout,
                            "stderr": raw_stderr,
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
