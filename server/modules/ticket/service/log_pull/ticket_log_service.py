from __future__ import annotations

import codecs
import inspect
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from charset_normalizer import from_bytes
from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullRecord
from modules.ticket.entity.vo.ticket_log_pull_vo import (
    TicketLogContextLineModel,
    TicketLogContextModel,
    TicketLogErrorSummaryModel,
    TicketLogFileModel,
    TicketLogPrepareModel,
    TicketLogSearchHitModel,
)
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.util.ticket_log_archive_util import TicketLogArchiveUtil
from modules.ticket.util.ticket_log_search_limiter import TicketLogSearchLimiter
from utils.log_util import logger

_SEARCH_LIMITER = TicketLogSearchLimiter()


def _limit_search_concurrency(method):
    """
    为同步日志搜索入口增加进程内并发限制。
    :param method: 原始搜索方法
    :return: 受并发限制包装的方法
    """
    @wraps(method)
    def wrapper(cls, *args, **kwargs):
        bound = inspect.signature(method).bind_partial(cls, *args, **kwargs)
        db = bound.arguments.get("db")
        runtime_config = cls._get_runtime_config(db)
        max_concurrent = runtime_config.get("maxConcurrentSearches", 2)
        with _SEARCH_LIMITER.slot(max_concurrent):
            return method(cls, *args, **kwargs)

    return wrapper


class LogService:
    """
    工单日志统一服务，负责把日志拉取归档准备为可搜索文件，并提供搜索、上下文和异常摘要能力。
    """

    BASE_DIR = Path(__file__).resolve().parents[4] / "data" / "logs"
    SOURCE_FILE_NAME = "log.zip"
    META_FILE_NAME = "meta.json"
    TEXT_EXTENSIONS = {".log", ".txt", ".out"}
    ERROR_KEYWORDS = ("ERROR", "Exception", "Traceback", "timeout", "failed")
    LINE_INDEX_SUFFIX = ".lineidx"
    LINE_INDEX_ENCODING_VERSION = 2
    SEARCH_MODE_ENV = "TICKET_LOG_SEARCH_MODE"
    CONTEXT_MODE_ENV = "TICKET_LOG_CONTEXT_MODE"
    CONTEXT_LINE_TRUNCATE_ENV = "TICKET_LOG_CONTEXT_LINE_TRUNCATE"
    # 上下文单行内容最大字符数，超过则截断，避免超大行导致 JSON 序列化与前端渲染卡顿
    MAX_CONTEXT_LINE_LENGTH = 102400
    # rg 单次命令行文件数上限，超过后自动分批执行，避免 execve 参数过长导致进程启动失败
    RG_MAX_FILE_ARGS = 50

    @classmethod
    def prepare(
        cls,
        db: Session,
        ticket_id: int,
        record_id: int | None = None,
        progress_callback: Callable[[int, int | None, str], None] | None = None,
    ) -> TicketLogPrepareModel:
        """
        准备指定工单的日志目录：复用最新日志拉取归档，下载或复制到 source 后递归解压到 extract。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID，为空时使用当前工单最新日志记录
        :param progress_callback: 远程归档下载进度回调，参数依次为已下载字节数、总字节数、来源
        :return: 准备结果
        """
        prepare_started_at = time.monotonic()
        logger.info(f"开始准备工单日志查看目录，ticket_id={ticket_id}，record_id={record_id}")
        runtime_config = cls._get_runtime_config(db)
        ticket_dir = cls._ticket_dir(ticket_id, record_id)
        source_dir = ticket_dir / "source"
        extract_dir = ticket_dir / "extract"
        meta_path = ticket_dir / cls.META_FILE_NAME
        if extract_dir.exists() and any(extract_dir.iterdir()):
            cls._validate_extracted_resource_usage(extract_dir, runtime_config)
            files = cls.files(ticket_id, record_id)
            logger.info(
                f"工单日志已存在解压目录，跳过重复准备，ticket_id={ticket_id}，record_id={record_id}，"
                f"source_path={cls._find_source_archive(source_dir) or source_dir / cls.SOURCE_FILE_NAME}，"
                f"extract_path={extract_dir}，file_count={len(files)}，"
                f"elapsed_ms={int((time.monotonic() - prepare_started_at) * 1000)}"
            )
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                record_id=record_id,
                prepared=True,
                source_path=str(cls._find_source_archive(source_dir) or source_dir / cls.SOURCE_FILE_NAME),
                extract_path=str(extract_dir),
                file_count=len(files),
                message="日志已准备完成",
            )

        record = cls._resolve_record(db, ticket_id, record_id)
        if not record:
            logger.warning(f"未找到工单日志拉取记录，无法准备日志，ticket_id={ticket_id}")
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                record_id=record_id,
                prepared=False,
                file_count=0,
                message="未找到日志文件，且未配置下载地址",
            )

        record_ticket_id = int(record.ticket_id or 0)
        request_ticket_id = int(ticket_id or 0)
        # 记录已关联工单时，请求的 ticket_id 必须匹配；记录未关联工单时，允许任意 ticket_id（含 0）
        if record_id and record_ticket_id > 0 and record_ticket_id != request_ticket_id:
            logger.warning(
                f"日志拉取记录不属于当前工单，拒绝准备，ticket_id={ticket_id}, "
                f"record_id={record_id}, record_ticket_id={record.ticket_id}"
            )
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                record_id=record_id,
                prepared=False,
                file_count=0,
                message="日志拉取记录不属于当前工单",
            )

        archive_path, should_cleanup = TicketLogPullService._resolve_archive_source_for_view(
            record,
            db,
            progress_callback=progress_callback,
        )
        if not archive_path:
            logger.warning(f"未解析到可用日志归档文件，ticket_id={ticket_id}，record_id={record.id}")
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                record_id=record.id,
                prepared=False,
                file_count=0,
                message="未找到日志文件，且未配置下载地址",
            )

        try:
            source_dir.mkdir(parents=True, exist_ok=True)
            extract_dir.mkdir(parents=True, exist_ok=True)
            source_path = source_dir / cls._build_source_file_name(archive_path)
            logger.info(
                f"工单日志准备解析到归档，ticket_id={ticket_id}，record_id={record.id}，"
                f"archive_path={archive_path}，source_path={source_path}，extract_path={extract_dir}，"
                f"should_cleanup={should_cleanup}"
            )
            if archive_path.resolve() != source_path.resolve():
                shutil.copy2(archive_path, source_path)
            else:
                logger.info(f"工单日志源文件已位于 source 目录，跳过复制，archive_path={archive_path}")
            if should_cleanup:
                archive_path.unlink(missing_ok=True)
            cls._extract_recursive(source_path, extract_dir, runtime_config, time.monotonic())
            files = cls.files(ticket_id, record.id if record_id else None)
            cls._write_meta(
                meta_path,
                {
                    "ticket_id": ticket_id,
                    "record_id": record.id,
                    "source_path": str(source_path),
                    "extract_path": str(extract_dir),
                    "prepared_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                    "file_count": len(files),
                },
            )
            logger.info(
                f"工单日志准备完成，ticket_id={ticket_id}，record_id={record.id}，"
                f"archive_path={archive_path}，source_path={source_path}，extract_path={extract_dir}，"
                f"file_count={len(files)}，elapsed_ms={int((time.monotonic() - prepare_started_at) * 1000)}"
            )
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                record_id=record.id,
                prepared=True,
                source_path=str(source_path),
                extract_path=str(extract_dir),
                file_count=len(files),
                message="日志准备完成",
            )
        except Exception as exc:
            logger.exception(exc)
            failed_source_path = cls._find_source_archive(source_dir) or source_dir / cls.SOURCE_FILE_NAME
            logger.warning(
                f"工单日志准备失败，ticket_id={ticket_id}，record_id={record.id}，"
                f"archive_path={archive_path}，source_path={failed_source_path}，extract_path={extract_dir}，"
                f"elapsed_ms={int((time.monotonic() - prepare_started_at) * 1000)}"
            )
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                record_id=record.id,
                prepared=False,
                source_path=str(cls._find_source_archive(source_dir) or source_dir / cls.SOURCE_FILE_NAME),
                extract_path=str(extract_dir),
                file_count=0,
                message=f"日志准备失败：{exc}",
            )

    @classmethod
    def files(cls, ticket_id: int, record_id: int | None = None) -> list[TicketLogFileModel]:
        """
        查询指定工单已准备目录中的可读日志文本文件。
        :param ticket_id: 工单ID
        :return: 日志文件列表
        """
        extract_dir = cls._extract_dir(ticket_id, record_id)
        if not extract_dir.exists():
            return []
        result: list[TicketLogFileModel] = []
        for path in extract_dir.rglob("*"):
            if not path.is_file() or path.stat().st_size <= 0:
                continue
            if path.name.endswith(cls.LINE_INDEX_SUFFIX):
                continue
            if cls._is_archive(path):
                continue
            if not cls._is_text_file(path):
                continue
            result.append(
                TicketLogFileModel(
                    file=cls._relative_log_path(ticket_id, path, record_id),
                    size=path.stat().st_size,
                    modified_at=datetime.fromtimestamp(path.stat().st_mtime),
                )
            )
        return sorted(result, key=lambda item: item.file)

    @classmethod
    @_limit_search_concurrency
    def search(
        cls,
        ticket_id: int,
        keyword: str,
        context_before: int = 20,
        context_after: int = 20,
        limit: int = 100,
        with_context: bool = True,
        record_id: int | None = None,
        file_path: str | None = None,
        db: Session | None = None,
        file_paths: list[str] | None = None,
        ignore_case: bool = False,
        word_regexp: bool = False,
    ) -> list[TicketLogSearchHitModel]:
        """
        使用 ripgrep 搜索工单日志，并按需返回每个命中的上下文。
        :param ticket_id: 工单ID
        :param keyword: 搜索关键字
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param file_path: 指定单个相对日志文件路径，兼容旧调用
        :param db: 数据库会话，用于读取日志搜索资源保护配置
        :param file_paths: 指定多个相对日志文件路径，空值表示全局搜索
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :return: 搜索命中列表
        """
        search_started_at = time.monotonic()
        keyword = str(keyword or "").strip()
        if not keyword:
            return []
        extract_dir = cls._extract_dir(ticket_id, record_id)
        if not extract_dir.exists():
            return []
        runtime_config = cls._get_runtime_config(db)
        target_files = cls._resolve_search_files(ticket_id, record_id, file_path, runtime_config, file_paths)
        file_scope = ",".join(target_files) or None
        search_mode = cls._resolve_mode(cls.SEARCH_MODE_ENV, default="auto")
        if search_mode == "python":
            cls._log_search_execution(
                tool="python",
                ticket_id=ticket_id,
                record_id=record_id,
                extract_dir=extract_dir,
                keywords=[keyword],
                search_mode="any",
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                file_path=file_scope,
                target_file_count=len(target_files),
                args={
                    "reason": "env_python",
                    "maxPythonSearchBytes": runtime_config.get("maxPythonSearchBytes"),
                    "ignoreCase": ignore_case,
                    "wordRegexp": word_regexp,
                },
            )
            logger.info(f"日志搜索使用 Python 降级模式，ticket_id={ticket_id}，keyword={keyword}")
            hits = cls._search_by_python(
                ticket_id,
                keyword,
                context_before,
                context_after,
                limit,
                with_context,
                record_id,
                file_scope,
                runtime_config,
                target_files,
                ignore_case,
                word_regexp,
            )
            cls._log_search_completed("python", ticket_id, record_id, len(hits), search_started_at)
            return hits

        executable = (
            shutil.which("rg") or shutil.which("rg.exe") or shutil.which("ripgrep") or shutil.which("ripgrep.exe")
        )
        if not executable:
            cls._log_search_execution(
                tool="python",
                ticket_id=ticket_id,
                record_id=record_id,
                extract_dir=extract_dir,
                keywords=[keyword],
                search_mode="any",
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                file_path=file_scope,
                target_file_count=len(target_files),
                args={
                    "reason": "rg_not_found",
                    "maxPythonSearchBytes": runtime_config.get("maxPythonSearchBytes"),
                    "ignoreCase": ignore_case,
                    "wordRegexp": word_regexp,
                },
            )
            logger.warning(f"未找到 rg/ripgrep，日志搜索降级为 Python，ticket_id={ticket_id}，keyword={keyword}")
            hits = cls._search_by_python(
                ticket_id,
                keyword,
                context_before,
                context_after,
                limit,
                with_context,
                record_id,
                file_scope,
                runtime_config,
                target_files,
                ignore_case,
                word_regexp,
            )
            cls._log_search_completed("python", ticket_id, record_id, len(hits), search_started_at)
            return hits

        cls._log_search_execution(
            tool="rg",
            ticket_id=ticket_id,
            record_id=record_id,
            extract_dir=extract_dir,
            keywords=[keyword],
            search_mode="any",
            context_before=context_before,
            context_after=context_after,
            limit=limit,
            with_context=with_context,
            file_path=file_scope,
            target_file_count=len(target_files),
            args={
                "executable": executable,
                "rgArgs": [
                    "-n",
                    "--no-heading",
                    "--with-filename",
                    "--color",
                    "never",
                    "--fixed-strings",
                    *(["--ignore-case"] if ignore_case else []),
                    *(["--word-regexp"] if word_regexp else []),
                    "-m",
                    "<remaining_limit>",
                    "-e",
                    "<keyword...>",
                    "--",
                    "<target_file...>",
                ],
                "maxSearchSeconds": runtime_config.get("maxSearchSeconds"),
                "maxSearchLineBytes": runtime_config.get("maxSearchLineBytes"),
                "maxConcurrentSearches": runtime_config.get("maxConcurrentSearches"),
            },
        )
        return cls._search_by_rg_keywords(
            ticket_id=ticket_id,
            keywords=[keyword],
            search_mode="any",
            executable=executable,
            extract_dir=extract_dir,
            context_before=context_before,
            context_after=context_after,
            limit=limit,
            with_context=with_context,
            record_id=record_id,
            runtime_config=runtime_config,
            target_files=target_files,
            file_path=file_scope,
            ignore_case=ignore_case,
            word_regexp=word_regexp,
            search_started_at=search_started_at,
        )

    @classmethod
    @_limit_search_concurrency
    def search_keywords(
        cls,
        ticket_id: int,
        keywords: list[str],
        search_mode: str = "any",
        context_before: int = 20,
        context_after: int = 20,
        limit: int = 100,
        with_context: bool = True,
        record_id: int | None = None,
        file_path: str | None = None,
        db: Session | None = None,
        file_paths: list[str] | None = None,
        ignore_case: bool = False,
        word_regexp: bool = False,
    ) -> list[TicketLogSearchHitModel]:
        """
        使用多个固定字符串搜索工单日志，支持任一命中或同一行全部命中。
        :param ticket_id: 工单ID
        :param keywords: 搜索关键字列表
        :param search_mode: 匹配模式，any 表示任一命中，all 表示同一行全部命中
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param file_path: 指定单个相对日志文件路径，兼容旧调用
        :param db: 数据库会话，用于读取日志搜索资源保护配置
        :param file_paths: 指定多个相对日志文件路径，空值表示全局搜索
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :return: 搜索命中列表
        """
        search_started_at = time.monotonic()
        normalized_keywords = cls._normalize_keywords(keywords)
        if not normalized_keywords:
            return []
        normalized_mode = str(search_mode or "any").strip().lower()
        if normalized_mode not in {"any", "all"}:
            normalized_mode = "any"
        if len(normalized_keywords) == 1:
            return cls.search(
                ticket_id=ticket_id,
                keyword=normalized_keywords[0],
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                file_path=file_path,
                db=db,
                file_paths=file_paths,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
            )

        extract_dir = cls._extract_dir(ticket_id, record_id)
        if not extract_dir.exists():
            return []
        runtime_config = cls._get_runtime_config(db)
        target_files = cls._resolve_search_files(ticket_id, record_id, file_path, runtime_config, file_paths)
        file_scope = ",".join(target_files) or None
        search_mode_config = cls._resolve_mode(cls.SEARCH_MODE_ENV, default="auto")
        if search_mode_config == "python":
            cls._log_search_execution(
                tool="python",
                ticket_id=ticket_id,
                record_id=record_id,
                extract_dir=extract_dir,
                keywords=normalized_keywords,
                search_mode=normalized_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                file_path=file_scope,
                target_file_count=len(target_files),
                args={
                    "reason": "env_python",
                    "maxSearchSeconds": runtime_config.get("maxSearchSeconds"),
                    "maxSearchLineBytes": runtime_config.get("maxSearchLineBytes"),
                    "maxConcurrentSearches": runtime_config.get("maxConcurrentSearches"),
                    "maxPythonSearchBytes": runtime_config.get("maxPythonSearchBytes"),
                    "ignoreCase": ignore_case,
                    "wordRegexp": word_regexp,
                },
            )
            hits = cls._search_by_python_keywords(
                ticket_id=ticket_id,
                keywords=normalized_keywords,
                search_mode=normalized_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                runtime_config=runtime_config,
                target_files=target_files,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
            )
            cls._log_search_completed("python", ticket_id, record_id, len(hits), search_started_at)
            return hits

        executable = (
            shutil.which("rg") or shutil.which("rg.exe") or shutil.which("ripgrep") or shutil.which("ripgrep.exe")
        )
        if not executable:
            logger.warning(f"未找到 rg/ripgrep，多关键字日志搜索降级为 Python，ticket_id={ticket_id}")
            cls._log_search_execution(
                tool="python",
                ticket_id=ticket_id,
                record_id=record_id,
                extract_dir=extract_dir,
                keywords=normalized_keywords,
                search_mode=normalized_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                file_path=file_scope,
                target_file_count=len(target_files),
                args={
                    "reason": "rg_not_found",
                    "maxPythonSearchBytes": runtime_config.get("maxPythonSearchBytes"),
                    "ignoreCase": ignore_case,
                    "wordRegexp": word_regexp,
                },
            )
            hits = cls._search_by_python_keywords(
                ticket_id=ticket_id,
                keywords=normalized_keywords,
                search_mode=normalized_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                runtime_config=runtime_config,
                target_files=target_files,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
            )
            cls._log_search_completed("python", ticket_id, record_id, len(hits), search_started_at)
            return hits
        cls._log_search_execution(
            tool="rg",
            ticket_id=ticket_id,
            record_id=record_id,
            extract_dir=extract_dir,
            keywords=normalized_keywords,
            search_mode=normalized_mode,
            context_before=context_before,
            context_after=context_after,
            limit=limit,
            with_context=with_context,
            file_path=file_scope,
            target_file_count=len(target_files),
            args={
                "executable": executable,
                "rgArgs": [
                    "-n",
                    "--no-heading",
                    "--with-filename",
                    "--color",
                    "never",
                    "--fixed-strings",
                    *(["--ignore-case"] if ignore_case else []),
                    *(["--word-regexp"] if word_regexp else []),
                    "-m",
                    "<remaining_limit>",
                    "-e",
                    "<keyword...>",
                    "--",
                    "<target_file...>",
                ],
                "maxSearchSeconds": runtime_config.get("maxSearchSeconds"),
                "maxSearchLineBytes": runtime_config.get("maxSearchLineBytes"),
                "maxConcurrentSearches": runtime_config.get("maxConcurrentSearches"),
            },
        )
        hits = cls._search_by_rg_keywords(
            ticket_id=ticket_id,
            keywords=normalized_keywords,
            search_mode=normalized_mode,
            executable=executable,
            extract_dir=extract_dir,
            context_before=context_before,
            context_after=context_after,
            limit=limit,
            with_context=with_context,
            record_id=record_id,
            runtime_config=runtime_config,
            target_files=target_files,
            file_path=file_scope,
            ignore_case=ignore_case,
            word_regexp=word_regexp,
            search_started_at=search_started_at,
        )
        return hits

    @classmethod
    def context(
        cls,
        ticket_id: int,
        file_path: str,
        line_no: int,
        before: int,
        after: int,
        record_id: int | None = None,
    ) -> TicketLogContextModel:
        """
        按行号索引读取指定日志文件在某行附近的上下文，必要时跨轮转文件补足前后文。
        :param ticket_id: 工单ID
        :param file_path: 相对日志文件路径
        :param line_no: 中心行号
        :param before: 前置行数
        :param after: 后置行数
        :return: 上下文内容
        """
        context_mode = cls._resolve_mode(cls.CONTEXT_MODE_ENV, default="auto")
        if context_mode == "native":
            try:
                return cls._context_by_native(ticket_id, file_path, line_no, before, after, record_id)
            except Exception as exc:
                logger.warning(f"原生命令读取日志上下文失败，降级为 Python 行索引，ticket_id={ticket_id}，reason={exc}")
        elif context_mode == "auto":
            logger.debug(f"日志上下文读取使用 Python 行索引模式，ticket_id={ticket_id}，file={file_path}")
        return cls._context_by_python(ticket_id, file_path, line_no, before, after, record_id)

    @classmethod
    def _context_by_python(
        cls, ticket_id: int, file_path: str, line_no: int, before: int, after: int, record_id: int | None = None
    ) -> TicketLogContextModel:
        """
        使用 Python 行偏移索引读取日志上下文。
        :param ticket_id: 工单ID
        :param file_path: 相对日志文件路径
        :param line_no: 中心行号
        :param before: 前置行数
        :param after: 后置行数
        :return: 上下文内容
        """
        normalized_file = cls._normalize_relative_path(file_path)
        target_path = cls._resolve_log_file(ticket_id, normalized_file, record_id)
        center = max(int(line_no or 1), 1)
        before_count = max(int(before or 0), 0)
        after_count = max(int(after or 0), 0)
        index_data = cls._ensure_line_index(target_path)
        total = int(index_data.get("line_count") or 0)
        bounded_center = min(center, max(total, 1))
        start = max(bounded_center - before_count, 1)
        end = min(bounded_center + after_count, total)
        current_lines = cls._read_lines_by_index(target_path, start, end)
        return cls._build_context_model(
            ticket_id=ticket_id,
            file_path=normalized_file,
            center=bounded_center,
            start=start,
            end=end,
            total=total,
            before_count=before_count,
            after_count=after_count,
            current_lines=current_lines,
            record_id=record_id,
        )

    @classmethod
    def search_time(
        cls,
        ticket_id: int,
        time_keyword: str,
        context_before: int = 20,
        context_after: int = 20,
        limit: int = 100,
        with_context: bool = True,
        record_id: int | None = None,
        db: Session | None = None,
    ) -> list[TicketLogSearchHitModel]:
        """
        按时间文本搜索日志，典型输入为 14:32。
        :param ticket_id: 工单ID
        :param time_keyword: 时间关键字
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param db: 数据库会话，用于读取日志搜索资源保护配置
        :return: 搜索命中列表
        """
        return cls.search(
            ticket_id=ticket_id,
            keyword=time_keyword,
            context_before=context_before,
            context_after=context_after,
            limit=limit,
            with_context=with_context,
            record_id=record_id,
            db=db,
        )

    @classmethod
    def _search_by_python(
        cls,
        ticket_id: int,
        keyword: str,
        context_before: int,
        context_after: int,
        limit: int,
        with_context: bool,
        record_id: int | None = None,
        file_path: str | None = None,
        runtime_config: dict[str, Any] | None = None,
        target_files: list[str] | None = None,
        ignore_case: bool = False,
        word_regexp: bool = False,
    ) -> list[TicketLogSearchHitModel]:
        """
        Python 降级搜索实现，在没有 rg/ripgrep 时使用。
        :param ticket_id: 工单ID
        :param keyword: 搜索关键字
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param file_path: 指定相对日志文件路径，空值表示全局搜索
        :param runtime_config: 运行保护配置
        :param target_files: 已归一化的搜索文件列表
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :return: 搜索命中列表
        """
        hits: list[TicketLogSearchHitModel] = []
        resolved_config = runtime_config or cls._get_runtime_config()
        resolved_target_files = target_files or cls._resolve_search_files(
            ticket_id, record_id, file_path, resolved_config
        )
        max_scan_bytes = cls._config_int(resolved_config, "maxPythonSearchBytes", 268435456)
        max_line_bytes = cls._config_int(resolved_config, "maxSearchLineBytes", 524288)
        scanned_bytes = 0
        for target_file in resolved_target_files:
            if len(hits) >= limit:
                break
            path = cls._resolve_log_file(ticket_id, target_file, record_id)
            scanned_bytes += path.stat().st_size
            if scanned_bytes > max_scan_bytes:
                raise RuntimeError("日志搜索扫描量超过当前保护阈值，请缩小文件范围或调整日志拉取存储配置")
            encoding = cls._detect_file_encoding(path)
            with path.open("r", encoding=encoding, errors="replace") as file_obj:
                for line_no, content in enumerate(file_obj, start=1):
                    matched_keywords = cls._match_keywords(
                        content, [keyword], "any", ignore_case=ignore_case, word_regexp=word_regexp
                    )
                    if not matched_keywords:
                        continue
                    display_content, content_length, content_truncated = cls._truncate_search_content(
                        content, max_line_bytes
                    )
                    hit = TicketLogSearchHitModel(
                        file=target_file,
                        line=line_no,
                        content=display_content,
                        content_length=content_length,
                        content_truncated=content_truncated,
                        matched_keywords=matched_keywords,
                    )
                    if with_context:
                        hit.context = cls.context(
                            ticket_id, target_file, line_no, context_before, context_after, record_id
                        )
                    hits.append(hit)
                    if len(hits) >= limit:
                        break
        return hits

    @classmethod
    def _search_by_rg_keywords(
        cls,
        *,
        ticket_id: int,
        keywords: list[str],
        search_mode: str,
        executable: str,
        extract_dir: Path,
        context_before: int,
        context_after: int,
        limit: int,
        with_context: bool,
        record_id: int | None,
        runtime_config: dict[str, Any],
        target_files: list[str],
        file_path: str | None = None,
        ignore_case: bool = False,
        word_regexp: bool = False,
        search_started_at: float | None = None,
    ) -> list[TicketLogSearchHitModel]:
        """
        使用 rg 一次匹配多个 ASCII 固定字符串。
        :param ticket_id: 工单ID
        :param keywords: 已归一化的关键字列表
        :param executable: rg 可执行文件路径
        :param extract_dir: 日志解压目录
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param runtime_config: 运行保护配置
        :param target_files: 搜索文件列表
        :param file_path: 指定文件范围
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :param search_started_at: 搜索开始时间戳
        :return: 搜索命中列表
        """
        max_seconds = cls._config_int(runtime_config, "maxSearchSeconds", 30)
        if len(target_files) > cls.RG_MAX_FILE_ARGS:
            return cls._search_by_rg_keywords_batched(
                ticket_id=ticket_id,
                keywords=keywords,
                search_mode=search_mode,
                executable=executable,
                extract_dir=extract_dir,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                runtime_config=runtime_config,
                target_files=target_files,
                file_path=file_path,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
                search_started_at=search_started_at,
                max_seconds=max_seconds,
            )
        return cls._search_by_rg_keywords_single(
            ticket_id=ticket_id,
            keywords=keywords,
            search_mode=search_mode,
            executable=executable,
            extract_dir=extract_dir,
            context_before=context_before,
            context_after=context_after,
            limit=limit,
            with_context=with_context,
            record_id=record_id,
            runtime_config=runtime_config,
            target_files=target_files,
            file_path=file_path,
            ignore_case=ignore_case,
            word_regexp=word_regexp,
            search_started_at=search_started_at,
            max_seconds=max_seconds,
        )

    @classmethod
    def _search_by_rg_keywords_single(
        cls,
        *,
        ticket_id: int,
        keywords: list[str],
        search_mode: str,
        executable: str,
        extract_dir: Path,
        context_before: int,
        context_after: int,
        limit: int,
        with_context: bool,
        record_id: int | None,
        runtime_config: dict[str, Any],
        target_files: list[str],
        file_path: str | None = None,
        ignore_case: bool = False,
        word_regexp: bool = False,
        search_started_at: float | None = None,
        max_seconds: int = 30,
    ) -> list[TicketLogSearchHitModel]:
        """
        单批 rg 搜索：将文件列表一次性交给 rg，适用于文件数不超过 RG_MAX_FILE_ARGS 的场景。
        :param ticket_id: 工单ID
        :param keywords: 已归一化的关键字列表
        :param search_mode: 匹配模式
        :param executable: rg 可执行文件路径
        :param extract_dir: 日志解压目录
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param runtime_config: 运行保护配置
        :param target_files: 搜索文件列表
        :param file_path: 指定文件范围
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :param search_started_at: 搜索开始时间戳
        :param max_seconds: 管道最大执行秒数
        :return: 搜索命中列表
        """
        first_keyword = keywords[0]
        # 构建 rg 第一段命令：从指定文件中搜索关键字
        first_command = [
            executable,
            "-n",
            "--no-heading",
            "--with-filename",
            "--color",
            "never",
            "--fixed-strings",
            "-e",
            first_keyword,
        ]
        if ignore_case:
            first_command.append("--ignore-case")
        if word_regexp:
            first_command.append("--word-regexp")
        if search_mode == "any":
            for keyword in keywords[1:]:
                first_command.extend(["-e", keyword])
        first_command.extend(["--", *target_files])

        # 构建完整的 rg 管道命令链
        commands = [first_command]
        if search_mode == "all":
            for index, keyword in enumerate(keywords[1:], start=1):
                command = [executable, "--color", "never"]
                if index == len(keywords) - 1:
                    command.extend(cls._rg_max_columns_args(runtime_config))
                    command.extend(["-m", str(limit)])
                command.append(cls._build_rg_output_content_pattern(keyword, ignore_case, word_regexp))
                commands.append(command)
        else:
            commands.append(
                [
                    executable,
                    "--color",
                    "never",
                    *cls._rg_max_columns_args(runtime_config),
                    "-m",
                    str(limit),
                    ".",
                ]
            )

        try:
            hits = cls._collect_rg_hits(
                commands=commands,
                extract_dir=extract_dir,
                timeout_seconds=max_seconds,
                ticket_id=ticket_id,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
                max_line_bytes=cls._config_int(runtime_config, "maxSearchLineBytes", 524288),
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                f"rg 日志搜索达到保护超时，日志搜索降级为 Python，ticket_id={ticket_id}，record_id={record_id}"
            )
            cls._log_search_execution(
                tool="python",
                ticket_id=ticket_id,
                record_id=record_id,
                extract_dir=extract_dir,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                file_path=file_path,
                target_file_count=len(target_files),
                args={
                    "reason": "rg_timeout",
                    "maxSearchSeconds": runtime_config.get("maxSearchSeconds"),
                    "maxSearchLineBytes": runtime_config.get("maxSearchLineBytes"),
                    "maxConcurrentSearches": runtime_config.get("maxConcurrentSearches"),
                    "maxPythonSearchBytes": runtime_config.get("maxPythonSearchBytes"),
                    "ignoreCase": ignore_case,
                    "wordRegexp": word_regexp,
                },
            )
            fallback_hits = cls._search_by_python_keywords(
                ticket_id=ticket_id,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                runtime_config=runtime_config,
                target_files=target_files,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
            )
            if search_started_at is not None:
                cls._log_search_completed("python", ticket_id, record_id, len(fallback_hits), search_started_at)
            return fallback_hits
        except FileNotFoundError as exc:
            logger.warning(f"执行 rg 失败，日志搜索降级为 Python，ticket_id={ticket_id}，reason={exc}")
            cls._log_search_execution(
                tool="python",
                ticket_id=ticket_id,
                record_id=record_id,
                extract_dir=extract_dir,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                file_path=file_path,
                target_file_count=len(target_files),
                args={
                    "reason": "rg_file_not_found",
                    "maxPythonSearchBytes": runtime_config.get("maxPythonSearchBytes"),
                    "ignoreCase": ignore_case,
                    "wordRegexp": word_regexp,
                },
            )
            fallback_hits = cls._search_by_python_keywords(
                ticket_id=ticket_id,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                runtime_config=runtime_config,
                target_files=target_files,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
            )
            if search_started_at is not None:
                cls._log_search_completed("python", ticket_id, record_id, len(fallback_hits), search_started_at)
            return fallback_hits
        except RuntimeError as exc:
            logger.warning(f"rg 日志搜索返回异常，日志搜索降级为 Python，ticket_id={ticket_id}，reason={exc}")
            cls._log_search_execution(
                tool="python",
                ticket_id=ticket_id,
                record_id=record_id,
                extract_dir=extract_dir,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                file_path=file_path,
                target_file_count=len(target_files),
                args={
                    "reason": "rg_returncode",
                    "maxPythonSearchBytes": runtime_config.get("maxPythonSearchBytes"),
                    "ignoreCase": ignore_case,
                    "wordRegexp": word_regexp,
                },
            )
            fallback_hits = cls._search_by_python_keywords(
                ticket_id=ticket_id,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                runtime_config=runtime_config,
                target_files=target_files,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
            )
            if search_started_at is not None:
                cls._log_search_completed("python", ticket_id, record_id, len(fallback_hits), search_started_at)
            return fallback_hits
        except OSError as exc:
            logger.warning(
                f"rg 日志搜索系统错误，日志搜索降级为 Python，ticket_id={ticket_id}，reason={exc}"
            )
            cls._log_search_execution(
                tool="python",
                ticket_id=ticket_id,
                record_id=record_id,
                extract_dir=extract_dir,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                file_path=file_path,
                target_file_count=len(target_files),
                args={
                    "reason": "rg_os_error",
                    "maxPythonSearchBytes": runtime_config.get("maxPythonSearchBytes"),
                    "ignoreCase": ignore_case,
                    "wordRegexp": word_regexp,
                },
            )
            fallback_hits = cls._search_by_python_keywords(
                ticket_id=ticket_id,
                keywords=keywords,
                search_mode=search_mode,
                context_before=context_before,
                context_after=context_after,
                limit=limit,
                with_context=with_context,
                record_id=record_id,
                runtime_config=runtime_config,
                target_files=target_files,
                ignore_case=ignore_case,
                word_regexp=word_regexp,
            )
            if search_started_at is not None:
                cls._log_search_completed("python", ticket_id, record_id, len(fallback_hits), search_started_at)
            return fallback_hits

        if search_started_at is not None:
            cls._log_search_completed("rg", ticket_id, record_id, len(hits), search_started_at)
        # 建议 OS 释放本次搜索读取文件的页缓存，避免多次搜索不同工单日志后内存持续增长
        cls._release_page_cache(target_files, ticket_id, record_id)
        return hits

    @classmethod
    def _search_by_rg_keywords_batched(
        cls,
        *,
        ticket_id: int,
        keywords: list[str],
        search_mode: str,
        executable: str,
        extract_dir: Path,
        context_before: int,
        context_after: int,
        limit: int,
        with_context: bool,
        record_id: int | None,
        runtime_config: dict[str, Any],
        target_files: list[str],
        file_path: str | None = None,
        ignore_case: bool = False,
        word_regexp: bool = False,
        search_started_at: float | None = None,
        max_seconds: int = 30,
    ) -> list[TicketLogSearchHitModel]:
        """
        分批 rg 搜索：将文件列表按 RG_MAX_FILE_ARGS 拆分，每批独立执行后合并去重，适用于文件数过多的场景。
        :param ticket_id: 工单ID
        :param keywords: 已归一化的关键字列表
        :param search_mode: 匹配模式
        :param executable: rg 可执行文件路径
        :param extract_dir: 日志解压目录
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param runtime_config: 运行保护配置
        :param target_files: 搜索文件列表
        :param file_path: 指定文件范围
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :param search_started_at: 搜索开始时间戳
        :param max_seconds: 管道最大执行秒数
        :return: 搜索命中列表
        """
        total_files = len(target_files)
        batch_size = cls.RG_MAX_FILE_ARGS
        batch_count = (total_files + batch_size - 1) // batch_size
        logger.info(
            f"rg 日志搜索文件数过多({total_files})，按 {batch_size} 个文件分批执行，共 {batch_count} 批，"
            f"ticket_id={ticket_id}，record_id={record_id}"
        )

        hits: list[TicketLogSearchHitModel] = []
        seen_keys: set[tuple[str, int]] = set()

        for batch_index in range(batch_count):
            if len(hits) >= limit:
                logger.info(
                    f"rg 分批搜索已收集到足够的命中数({len(hits)}>={limit})，跳过剩余批次，"
                    f"batch={batch_index + 1}/{batch_count}，ticket_id={ticket_id}，record_id={record_id}"
                )
                break
            batch_files = target_files[batch_index * batch_size : (batch_index + 1) * batch_size]
            remaining_limit = limit - len(hits)
            logger.info(
                f"rg 分批搜索执行第 {batch_index + 1}/{batch_count} 批，文件数={len(batch_files)}，"
                f"剩余配额={remaining_limit}，ticket_id={ticket_id}，record_id={record_id}"
            )
            try:
                batch_hits = cls._search_by_rg_keywords_single(
                    ticket_id=ticket_id,
                    keywords=keywords,
                    search_mode=search_mode,
                    executable=executable,
                    extract_dir=extract_dir,
                    context_before=context_before,
                    context_after=context_after,
                    limit=remaining_limit,
                    with_context=with_context,
                    record_id=record_id,
                    runtime_config=runtime_config,
                    target_files=batch_files,
                    file_path=file_path,
                    ignore_case=ignore_case,
                    word_regexp=word_regexp,
                    # 分批时不重复记录 search_completed，由外层统一记录
                    search_started_at=None,
                    max_seconds=max_seconds,
                )
            except Exception:
                logger.exception(
                    f"rg 分批搜索第 {batch_index + 1}/{batch_count} 批异常，跳过本批，"
                    f"ticket_id={ticket_id}，record_id={record_id}"
                )
                continue
            for hit in batch_hits:
                unique_key = (hit.file, hit.line)
                if unique_key in seen_keys:
                    continue
                if len(hits) >= limit:
                    break
                hits.append(hit)
                seen_keys.add(unique_key)

        if search_started_at is not None:
            cls._log_search_completed("rg", ticket_id, record_id, len(hits), search_started_at)
        logger.info(
            f"rg 分批搜索完成，共 {batch_count} 批，命中 {len(hits)} 条，"
            f"ticket_id={ticket_id}，record_id={record_id}"
        )
        cls._release_page_cache(target_files, ticket_id, record_id)
        return hits

    @classmethod
    def _collect_rg_hits(
        cls,
        *,
        commands: list[list[str]],
        extract_dir: Path,
        timeout_seconds: int,
        ticket_id: int,
        keywords: list[str],
        search_mode: str,
        context_before: int,
        context_after: int,
        limit: int,
        with_context: bool,
        record_id: int | None,
        ignore_case: bool,
        word_regexp: bool,
        max_line_bytes: int,
    ) -> list[TicketLogSearchHitModel]:
        """
        流式消费 rg 最终输出并构造命中结果，避免整批 stdout 和拆分列表同时驻留内存。
        :param commands: rg 命令链
        :param extract_dir: 日志解压目录
        :param timeout_seconds: 管道最大执行秒数
        :param ticket_id: 工单ID
        :param keywords: 已归一化的关键字列表
        :param search_mode: 匹配模式
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :param max_line_bytes: 单行最大输出字节数
        :return: 搜索命中列表
        """
        hits: list[TicketLogSearchHitModel] = []
        seen_keys: set[tuple[str, int]] = set()
        output_stream = cls._run_rg_pipeline(commands, extract_dir, timeout_seconds)
        try:
            for raw_line in output_stream:
                if len(hits) >= limit:
                    break
                hit = cls._parse_rg_line(raw_line, max_line_bytes=max_line_bytes)
                if not hit:
                    continue
                unique_key = (hit.file, hit.line)
                if unique_key in seen_keys:
                    continue
                # rg 管道链已确保最终输出的每一行都满足关键字匹配条件，
                # 不需要 Python 侧再做 _match_keywords 二次校验。
                # 前端不使用 matched_keywords 按命中粒度高亮，统一传入所有关键字。
                hit.matched_keywords = keywords
                if with_context:
                    hit.context = cls.context(ticket_id, hit.file, hit.line, context_before, context_after, record_id)
                hits.append(hit)
                seen_keys.add(unique_key)
        finally:
            output_stream.close()
        return hits

    @classmethod
    def _run_rg_pipeline(cls, commands: list[list[str]], extract_dir: Path, timeout_seconds: int) -> Iterator[str]:
        """
        使用管道串联多个 rg 进程，并逐行产出最后一段输出。
        :param commands: rg 命令链，第一段读取日志文件，后续段从 stdin 过滤
        :param extract_dir: 日志解压目录
        :param timeout_seconds: 管道最大执行秒数
        :return: 最后一段 rg 的标准输出迭代器
        """
        processes: list[subprocess.Popen] = []
        previous_stdout = None
        output_queue: queue.Queue[object] = queue.Queue(maxsize=64)
        stream_end = object()
        stop_event = threading.Event()
        stderr_chunks: list[str] = []
        output_reader: threading.Thread | None = None
        stderr_reader: threading.Thread | None = None

        def enqueue(item: object) -> None:
            """向有界队列写入输出，停止清理时放弃未消费内容。"""
            while not stop_event.is_set():
                try:
                    output_queue.put(item, timeout=0.1)
                    return
                except queue.Full:
                    continue

        def read_output(stream) -> None:
            """在线程中读取最终 rg 输出，避免主线程阻塞在无超时 readline。"""
            try:
                for line in iter(stream.readline, ""):
                    enqueue(line)
            except BaseException as exc:
                enqueue(exc)
            finally:
                enqueue(stream_end)

        def read_stderr(stream) -> None:
            """后台读取最后一个 rg 的错误输出，避免 stderr 管道反压。"""
            try:
                text = stream.read()
                if text:
                    stderr_chunks.append(text)
            except Exception:
                return

        try:
            for index, command in enumerate(commands):
                process = subprocess.Popen(
                    command,
                    cwd=str(extract_dir),
                    stdin=previous_stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE if index == len(commands) - 1 else subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if previous_stdout is not None:
                    previous_stdout.close()
                previous_stdout = process.stdout
                processes.append(process)

            final_process = processes[-1]
            output_reader = threading.Thread(
                target=read_output,
                args=(final_process.stdout,),
                name="ticket-log-rg-stdout",
                daemon=True,
            )
            output_reader.start()
            if final_process.stderr is not None:
                stderr_reader = threading.Thread(
                    target=read_stderr,
                    args=(final_process.stderr,),
                    name="ticket-log-rg-stderr",
                    daemon=True,
                )
                stderr_reader.start()

            deadline = time.monotonic() + max(int(timeout_seconds), 1)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(commands[-1], timeout_seconds)
                try:
                    item = output_queue.get(timeout=remaining)
                except queue.Empty as exc:
                    raise subprocess.TimeoutExpired(commands[-1], timeout_seconds) from exc
                if item is stream_end:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield str(item)

            final_process.wait(timeout=max(deadline - time.monotonic(), 0.1))
            for process in processes[:-1]:
                process.wait(timeout=1)
            if stderr_reader is not None:
                stderr_reader.join(timeout=1)
            stderr_text = "".join(stderr_chunks)
            if final_process.returncode not in (0, 1):
                raise RuntimeError(stderr_text.strip() or "rg 搜索失败")
        finally:
            stop_event.set()
            for process in processes:
                if process.poll() is None:
                    process.kill()
            # 显式关闭最后一个进程的 stdout，确保 readline() 线程立即收到 EOF 退出
            if processes and processes[-1].stdout is not None:
                try:
                    processes[-1].stdout.close()
                except OSError:
                    pass
            for process in processes:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
            if output_reader is not None:
                output_reader.join(timeout=3)
            if stderr_reader is not None:
                stderr_reader.join(timeout=3)
            for process in processes:
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except OSError:
                            pass

    @staticmethod
    def _build_rg_output_content_pattern(keyword: str, ignore_case: bool, word_regexp: bool) -> str:
        """
        构造用于过滤 rg 输出内容区的正则，避免后续管道误匹配文件名或行号。
        :param keyword: 固定字符串关键字
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :return: rg 可用的正则表达式
        """
        pattern = re.escape(keyword)
        if word_regexp:
            pattern = rf"\b{{start-half}}{pattern}\b{{end-half}}"
        if ignore_case:
            pattern = rf"(?i:{pattern})"
        return rf"^[^:\r\n]+:\d+:.*{pattern}"

    @classmethod
    def _search_by_python_keywords(
        cls,
        *,
        ticket_id: int,
        keywords: list[str],
        search_mode: str,
        context_before: int,
        context_after: int,
        limit: int,
        with_context: bool,
        record_id: int | None,
        runtime_config: dict[str, Any],
        target_files: list[str],
        ignore_case: bool = False,
        word_regexp: bool = False,
    ) -> list[TicketLogSearchHitModel]:
        """
        Python 多关键字搜索实现，支持任一命中和同一行全部命中。
        :param ticket_id: 工单ID
        :param keywords: 已归一化的关键字列表
        :param search_mode: 匹配模式
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :param record_id: 日志拉取记录ID
        :param runtime_config: 运行保护配置
        :param target_files: 搜索文件列表
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :return: 搜索命中列表
        """
        hits: list[TicketLogSearchHitModel] = []
        max_scan_bytes = cls._config_int(runtime_config, "maxPythonSearchBytes", 268435456)
        max_line_bytes = cls._config_int(runtime_config, "maxSearchLineBytes", 524288)
        deadline = time.monotonic() + cls._config_int(runtime_config, "maxSearchSeconds", 30)
        scanned_bytes = 0
        for target_file in target_files:
            if len(hits) >= limit:
                break
            if time.monotonic() > deadline:
                logger.warning(f"Python 多关键字日志搜索达到保护超时，ticket_id={ticket_id}，record_id={record_id}")
                break
            path = cls._resolve_log_file(ticket_id, target_file, record_id)
            scanned_bytes += path.stat().st_size
            if scanned_bytes > max_scan_bytes:
                raise RuntimeError("日志搜索扫描量超过当前保护阈值，请缩小文件范围或调整日志拉取存储配置")
            encoding = cls._detect_file_encoding(path)
            with path.open("r", encoding=encoding, errors="replace") as file_obj:
                for line_no, content in enumerate(file_obj, start=1):
                    if time.monotonic() > deadline:
                        logger.warning(
                            f"Python 多关键字日志搜索达到保护超时，ticket_id={ticket_id}，record_id={record_id}"
                        )
                        return hits
                    matched_keywords = cls._match_keywords(
                        content, keywords, search_mode, ignore_case=ignore_case, word_regexp=word_regexp
                    )
                    if not matched_keywords:
                        continue
                    display_content, content_length, content_truncated = cls._truncate_search_content(
                        content, max_line_bytes
                    )
                    hit = TicketLogSearchHitModel(
                        file=target_file,
                        line=line_no,
                        content=display_content,
                        content_length=content_length,
                        content_truncated=content_truncated,
                        matched_keywords=matched_keywords,
                    )
                    if with_context:
                        hit.context = cls.context(
                            ticket_id, target_file, line_no, context_before, context_after, record_id
                        )
                    hits.append(hit)
                    if len(hits) >= limit:
                        break
        return hits

    @classmethod
    def _context_by_native(
        cls, ticket_id: int, file_path: str, line_no: int, before: int, after: int, record_id: int | None = None
    ) -> TicketLogContextModel:
        """
        使用系统命令读取当前文件上下文，再复用 Python 索引补跨文件边界。
        :param ticket_id: 工单ID
        :param file_path: 相对日志文件路径
        :param line_no: 中心行号
        :param before: 前置行数
        :param after: 后置行数
        :return: 上下文内容
        """
        normalized_file = cls._normalize_relative_path(file_path)
        target_path = cls._resolve_log_file(ticket_id, normalized_file, record_id)
        center = max(int(line_no or 1), 1)
        before_count = max(int(before or 0), 0)
        after_count = max(int(after or 0), 0)
        total = int(cls._ensure_line_index(target_path).get("line_count") or 0)
        bounded_center = min(center, max(total, 1))
        start = max(bounded_center - before_count, 1)
        end = min(bounded_center + after_count, total)
        current_lines = cls._read_current_file_lines_by_native(target_path, start, end)
        return cls._build_context_model(
            ticket_id=ticket_id,
            file_path=normalized_file,
            center=bounded_center,
            start=start,
            end=end,
            total=total,
            before_count=before_count,
            after_count=after_count,
            current_lines=current_lines,
            record_id=record_id,
        )

    @classmethod
    def errors(
        cls, ticket_id: int, limit: int = 100, record_id: int | None = None, db: Session | None = None
    ) -> TicketLogErrorSummaryModel:
        """
        提取常见异常关键字并聚合计数。
        :param ticket_id: 工单ID
        :param limit: 最大样例数量
        :param record_id: 日志拉取记录ID
        :param db: 数据库会话，用于读取日志搜索资源保护配置
        :return: 异常摘要
        """
        samples: list[TicketLogSearchHitModel] = []
        counter: Counter[str] = Counter()
        for keyword in cls.ERROR_KEYWORDS:
            remain = max(limit - len(samples), 0)
            if remain <= 0:
                break
            for hit in cls.search(ticket_id, keyword, 0, 0, remain, with_context=False, record_id=record_id, db=db):
                summary = cls._normalize_error_summary(hit.content)
                if not summary:
                    continue
                counter[summary] += 1
                samples.append(hit)
                if len(samples) >= limit:
                    break
        return TicketLogErrorSummaryModel(
            ticket_id=ticket_id,
            total=sum(counter.values()),
            items=dict(counter.most_common(50)),
            samples=samples,
        )

    @classmethod
    def _latest_record(cls, db: Session, ticket_id: int) -> TicketLogPullRecord | None:
        """
        查询指定工单最新一条可作为日志来源的日志拉取记录。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 日志拉取记录
        """
        rows = TicketLogPullDao.list_latest_records_by_ticket_ids(db, [ticket_id])
        return rows.get(ticket_id)

    @classmethod
    def _get_runtime_config(cls, db: Session | None = None) -> dict[str, Any]:
        """
        读取日志查看运行保护配置，数据库不可用时使用默认存储配置兜底。
        :param db: 数据库会话
        :return: 标准化后的运行配置
        """
        if db is None:
            return {
                "maxExtractSeconds": 300,
                "maxExtractFileCount": 2000,
                "maxExtractTotalBytes": 2147483648,
                "maxSearchSeconds": 30,
                "maxSearchFileCount": 1000,
                "maxPythonSearchBytes": 268435456,
                "maxConcurrentSearches": 2,
                "maxSearchLineBytes": 524288,
            }
        return TicketLogPullService.get_storage_config_dict(db)

    @classmethod
    def _log_search_execution(
        cls,
        *,
        tool: str,
        ticket_id: int,
        record_id: int | None,
        extract_dir: Path,
        keywords: list[str],
        search_mode: str,
        context_before: int,
        context_after: int,
        limit: int,
        with_context: bool,
        file_path: str | None,
        target_file_count: int,
        args: dict[str, Any],
    ) -> None:
        """
        记录日志搜索执行计划，便于定位实际使用的工具、参数和搜索目录。
        :param tool: 搜索工具名称，如 rg/python
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :param extract_dir: 本次搜索的日志解压目录
        :param keywords: 搜索关键字列表
        :param search_mode: 搜索模式
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回数量
        :param with_context: 是否返回上下文
        :param file_path: 指定文件范围
        :param target_file_count: 本次扫描的文件数量
        :param args: 工具相关参数
        :return: 无
        """
        logger.info(
            f"工单日志搜索开始，ticket_id={ticket_id}，record_id={record_id}，tool={tool}，"
            f"extract_dir={extract_dir}，file={file_path or '<all>'}，target_file_count={target_file_count}，"
            f"keywords={keywords}，search_mode={search_mode}，context_before={context_before}，"
            f"context_after={context_after}，limit={limit}，with_context={with_context}，args={args}"
        )

    @staticmethod
    def _log_search_completed(
        tool: str,
        ticket_id: int,
        record_id: int | None,
        hit_count: int,
        started_at: float,
    ) -> None:
        """
        记录日志搜索完成耗时和命中数量。
        :param tool: 搜索工具名称
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :param hit_count: 返回命中数量
        :param started_at: 搜索开始时间戳
        :return: 无
        """
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            f"工单日志搜索完成，ticket_id={ticket_id}，record_id={record_id}，tool={tool}，"
            f"hit_count={hit_count}，elapsed_ms={elapsed_ms}"
        )

    @staticmethod
    def _config_int(config: dict[str, Any], key: str, default: int) -> int:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.config_int(config, key, default)

    @staticmethod
    def _truncate_search_content(content: str, max_bytes: int) -> tuple[str, int, bool]:
        """
        按 UTF-8 字节上限截断搜索结果内容，并返回实际返回内容长度。
        :param content: 原始日志行内容
        :param max_bytes: 单行最大输出字节数
        :return: 截断后的内容、返回内容字符长度、是否截断
        """
        text = str(content or "").rstrip("\r\n")
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= max_bytes:
            return text, len(text), False
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
        return truncated, len(truncated), True

    @staticmethod
    def _rg_max_columns_args(runtime_config: dict[str, Any]) -> list[str]:
        """
        构造最终 rg 输出阶段的单行字节限制参数。
        :param runtime_config: 日志搜索运行保护配置
        :return: rg 命令参数
        """
        max_line_bytes = LogService._config_int(runtime_config, "maxSearchLineBytes", 524288)
        return ["--max-columns", str(max_line_bytes), "--max-columns-preview"]

    @staticmethod
    def _normalize_keywords(keywords: list[str] | tuple[str, ...] | None) -> list[str]:
        """
        归一化日志搜索关键字列表，保持输入顺序并去重。
        :param keywords: 原始关键字列表
        :return: 去重后的非空关键字列表
        """
        result: list[str] = []
        for item in keywords or []:
            keyword = str(item or "").strip()
            if keyword and keyword not in result:
                result.append(keyword[:200])
        return result[:20]

    @staticmethod
    def _match_keywords(
        content: str,
        keywords: list[str],
        search_mode: str,
        *,
        ignore_case: bool = False,
        word_regexp: bool = False,
    ) -> list[str]:
        """
        计算单行日志命中的关键字列表。
        :param content: 日志行内容
        :param keywords: 关键字列表
        :param search_mode: any/all 匹配模式
        :param ignore_case: 是否忽略关键字大小写
        :param word_regexp: 是否仅匹配完整单词
        :return: 命中的关键字；all 模式未全部命中时返回空列表
        """
        text = str(content or "")
        if not ignore_case and not word_regexp:
            matched = [keyword for keyword in keywords if keyword and keyword in text]
            if search_mode == "all" and len(matched) != len(keywords):
                return []
            return matched
        flags = re.IGNORECASE if ignore_case else 0
        matched = []
        for keyword in keywords:
            if not keyword:
                continue
            pattern = re.escape(keyword)
            if word_regexp:
                pattern = rf"(?<!\w){pattern}(?!\w)"
            if re.search(pattern, text, flags):
                matched.append(keyword)
        if search_mode == "all" and len(matched) != len(keywords):
            return []
        return matched

    @classmethod
    def _resolve_search_files(
        cls,
        ticket_id: int,
        record_id: int | None,
        file_path: str | None,
        runtime_config: dict[str, Any],
        file_paths: list[str] | None = None,
    ) -> list[str]:
        """
        解析本次日志搜索允许扫描的文件列表，并按配置做数量保护。
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :param file_path: 指定单个相对日志文件路径，兼容旧调用
        :param runtime_config: 运行保护配置
        :param file_paths: 指定多个相对日志文件路径
        :return: 相对日志文件列表
        """
        selected_files: list[str] = []
        for raw_path in [file_path, *(file_paths or [])]:
            path = str(raw_path or "").strip()
            if not path:
                continue
            normalized_path = cls._normalize_relative_path(path)
            if normalized_path not in selected_files:
                cls._resolve_log_file(ticket_id, normalized_path, record_id)
                selected_files.append(normalized_path)
        if selected_files:
            return selected_files
        max_file_count = cls._config_int(runtime_config, "maxSearchFileCount", 1000)
        files = [file_item.file for file_item in cls.files(ticket_id, record_id)]
        if len(files) > max_file_count:
            raise RuntimeError("日志文件数量超过当前搜索保护阈值，请指定文件范围或调整日志拉取存储配置")
        return files

    @classmethod
    def _resolve_record(cls, db: Session, ticket_id: int, record_id: int | None = None) -> TicketLogPullRecord | None:
        """
        解析本次日志查看使用的拉取记录。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param record_id: 指定日志拉取记录ID
        :return: 日志拉取记录
        """
        if record_id:
            return TicketLogPullDao.get_record_by_id(db, record_id)
        return cls._latest_record(db, ticket_id)

    @classmethod
    def _extract_recursive(
        cls, archive_path: Path, target_dir: Path, runtime_config: dict[str, Any], started_at: float
    ) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.extract_recursive(archive_path, target_dir, runtime_config, started_at, context="日志")

    @classmethod
    def _ensure_prepare_budget(cls, started_at: float, runtime_config: dict[str, Any]) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.ensure_prepare_budget(started_at, runtime_config, context="日志")

    @classmethod
    def _validate_extracted_resource_usage(cls, target_dir: Path, runtime_config: dict[str, Any]) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.validate_extracted_resource_usage(target_dir, runtime_config, context="日志")

    @classmethod
    def _extract_one(cls, archive_path: Path, target_dir: Path) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.extract_one(archive_path, target_dir)

    @classmethod
    def _extract_zip_safely(cls, archive_path: Path, target_dir: Path) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.extract_zip_safely(archive_path, target_dir)

    @classmethod
    def _extract_tar_safely(cls, archive_path: Path, target_dir: Path) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.extract_tar_safely(archive_path, target_dir)

    @classmethod
    def _extract_7z(cls, archive_path: Path, target_dir: Path) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.extract_7z(archive_path, target_dir)

    @classmethod
    def _extract_by_7z(cls, archive_path: Path, target_dir: Path) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.extract_by_7z(archive_path, target_dir)

    @classmethod
    def _is_archive(cls, path: Path) -> bool:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.is_archive(path)

    @classmethod
    def _is_relative_to(cls, path: Path, root: Path) -> bool:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.is_relative_to(path, root)

    @classmethod
    def _build_source_file_name(cls, archive_path: Path) -> str:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.build_source_file_name(archive_path, TicketLogArchiveUtil.DEFAULT_SOURCE_NAME)

    @classmethod
    def _find_source_archive(cls, source_dir: Path) -> Path | None:
        """
        查找 source 目录中已经缓存的源压缩包。
        :param source_dir: source 目录
        :return: 源压缩包路径
        """
        if not source_dir.exists():
            return None
        for path in sorted(source_dir.iterdir()):
            if path.is_file() and cls._is_archive(path):
                return path
        return None

    @classmethod
    def _is_text_file(cls, path: Path) -> bool:
        """
        判断文件是否可按文本日志处理。
        :param path: 文件路径
        :return: 是否文本文件
        """
        if path.suffix.lower() in cls.TEXT_EXTENSIONS:
            return True
        with path.open("rb") as file_obj:
            sample = file_obj.read(8192)
        if b"\x00" in sample:
            return False
        result = from_bytes(sample).best()
        return bool(result and result.encoding)

    @classmethod
    def _ensure_line_index(cls, path: Path) -> dict[str, Any]:
        """
        确保日志文件存在行号到字节偏移的索引，后续上下文读取可直接 seek 到目标行。
        :param path: 日志文件路径
        :return: 索引元数据
        """
        index_path = cls._line_index_path(path)
        stat = path.stat()
        detected_encoding = cls._detect_file_encoding(path)
        if index_path.exists():
            try:
                with index_path.open("r", encoding="utf-8") as file_obj:
                    meta = json.loads(file_obj.readline() or "{}")
                if (
                    meta.get("size") == stat.st_size
                    and meta.get("mtime_ns") == stat.st_mtime_ns
                    and meta.get("encoding_version") == cls.LINE_INDEX_ENCODING_VERSION
                    and meta.get("encoding") == detected_encoding
                ):
                    return meta
                if meta.get("encoding") != detected_encoding:
                    logger.info(
                        f"日志行索引编码与当前文件不一致，将重建索引，path={path}，"
                        f"cached_encoding={meta.get('encoding')}，detected_encoding={detected_encoding}"
                    )
            except Exception as exc:
                logger.warning(f"读取日志行索引失败，将重建索引，path={path}，reason={exc}")

        logger.info(f"开始构建日志行索引，path={path}，size={stat.st_size}")
        encoding = detected_encoding
        line_count = 0
        index_path.parent.mkdir(parents=True, exist_ok=True)
        temp_index_path = index_path.with_name(f"{index_path.name}.tmp")
        with path.open("rb") as source, temp_index_path.open("w", encoding="utf-8", newline="\n") as temp_index_file:
            while True:
                offset = source.tell()
                line = source.readline()
                if not line:
                    break
                line_count += 1
                temp_index_file.write(f"{offset}\n")
        meta = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "line_count": line_count,
            "encoding": encoding,
            "encoding_version": cls.LINE_INDEX_ENCODING_VERSION,
            "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
        }
        with index_path.open("w", encoding="utf-8", newline="\n") as index_file:
            index_file.write(json.dumps(meta, ensure_ascii=False) + "\n")
            with temp_index_path.open("r", encoding="utf-8") as temp_index_file:
                shutil.copyfileobj(temp_index_file, index_file)
        temp_index_path.unlink(missing_ok=True)
        logger.info(f"日志行索引构建完成，path={path}，line_count={line_count}")
        return meta

    @classmethod
    def _build_context_model(
        cls,
        ticket_id: int,
        file_path: str,
        center: int,
        start: int,
        end: int,
        total: int,
        before_count: int,
        after_count: int,
        current_lines: list[tuple[int, str, bool, int]],
        record_id: int | None = None,
    ) -> TicketLogContextModel:
        """
        统一组装上下文响应，并在当前文件边界不足时跨轮转文件补齐上下文。
        :param ticket_id: 工单ID
        :param file_path: 当前日志相对路径
        :param center: 当前中心行
        :param start: 当前文件开始行
        :param end: 当前文件结束行
        :param total: 当前文件总行数
        :param before_count: 需要的前置上下文行数
        :param after_count: 需要的后置上下文行数
        :param current_lines: 当前文件已读取行，四元组 (行号, 内容, 是否截断, 原始长度)
        :return: 上下文响应
        """
        context_parts: list[tuple[str, int, str, bool, int]] = []
        missing_before = max(before_count - (center - start), 0)
        missing_after = max(after_count - (end - center), 0)
        if missing_before > 0:
            previous_file = cls._adjacent_log_file(ticket_id, file_path, direction="previous", record_id=record_id)
            if previous_file:
                previous_path = cls._resolve_log_file(ticket_id, previous_file, record_id)
                previous_index = cls._ensure_line_index(previous_path)
                previous_total = int(previous_index.get("line_count") or 0)
                previous_start = max(previous_total - missing_before + 1, 1)
                context_parts.extend(
                    (previous_file, line, content, truncated, original_length)
                    for line, content, truncated, original_length in
                    cls._read_lines_by_index(previous_path, previous_start, previous_total)
                )

        context_parts.extend(
            (file_path, line, content, truncated, original_length)
            for line, content, truncated, original_length in current_lines
        )

        if missing_after > 0:
            next_file = cls._adjacent_log_file(ticket_id, file_path, direction="next", record_id=record_id)
            if next_file:
                next_path = cls._resolve_log_file(ticket_id, next_file, record_id)
                context_parts.extend(
                    (next_file, line, content, truncated, original_length)
                    for line, content, truncated, original_length in
                    cls._read_lines_by_index(next_path, 1, missing_after)
                )

        context_lines = [
            TicketLogContextLineModel(
                file=line_file,
                line=index,
                content=content.rstrip("\r\n"),
                content_length=original_length,
                content_truncated=truncated,
            )
            for line_file, index, content, truncated, original_length in context_parts
        ]
        has_prev = (
            start > 1
            or cls._adjacent_log_file(ticket_id, file_path, direction="previous", record_id=record_id) is not None
        )
        has_next = (
            end < total
            or cls._adjacent_log_file(ticket_id, file_path, direction="next", record_id=record_id) is not None
        )
        prev_file, prev_line = cls._build_context_page_pointer(
            ticket_id,
            file_path,
            start,
            end,
            total,
            before_count,
            after_count,
            direction="previous",
            record_id=record_id,
        )
        next_file, next_line = cls._build_context_page_pointer(
            ticket_id, file_path, start, end, total, before_count, after_count, direction="next", record_id=record_id
        )
        return TicketLogContextModel(
            ticket_id=ticket_id,
            record_id=record_id,
            file=file_path,
            line=center,
            start=start,
            end=end,
            has_prev=has_prev,
            has_next=has_next,
            prev_file=prev_file,
            prev_line=prev_line,
            next_file=next_file,
            next_line=next_line,
            total_lines=total,
            lines=context_lines,
        )

    @classmethod
    def _read_current_file_lines_by_native(cls, path: Path, start: int, end: int) -> list[tuple[int, str, bool, int]]:
        """
        使用系统工具读取当前文件指定行段，同样应用单行截断逻辑。
        :param path: 日志文件路径
        :param start: 起始行号
        :param end: 结束行号
        :return: 行号、内容、是否截断、原始长度 四元组列表
        """
        if end < start:
            return []
        truncate_value = os.environ.get(cls.CONTEXT_LINE_TRUNCATE_ENV, "1").strip().lower()
        truncate_enabled = truncate_value not in ("0", "false", "no", "off")
        max_line_length = cls.MAX_CONTEXT_LINE_LENGTH
        if os.name == "nt":
            executable = shutil.which("powershell") or shutil.which("powershell.exe")
            if not executable:
                raise RuntimeError("未找到 PowerShell")
            escaped_path = str(path).replace("'", "''")
            escaped_encoding = cls._detect_file_encoding(path).replace("'", "''")
            powershell_command = (
                "$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
                "$reader=$null;"
                "try {"
                f"$reader=[IO.StreamReader]::new('{escaped_path}',[Text.Encoding]::GetEncoding('{escaped_encoding}'),$true);"
                f"for($lineNo=1;$lineNo -le {end};$lineNo++){{"
                "$line=$reader.ReadLine();"
                "if($null -eq $line){break};"
                f"if($lineNo -ge {start}){{[Console]::Out.WriteLine($line)}}"
                "}"
                "} finally {if($null -ne $reader){$reader.Dispose()}}"
            )
            command = [
                executable,
                "-NoProfile",
                "-Command",
                powershell_command,
            ]
        else:
            executable = shutil.which("sed")
            if not executable:
                raise RuntimeError("未找到 sed")
            command = [executable, "-n", f"{start},{end}p", str(path)]

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "原生命令读取上下文失败")
        result: list[tuple[int, str, bool, int]] = []
        for line_no, content in enumerate(process.stdout.splitlines(), start=start):
            original_length = len(content)
            if truncate_enabled and original_length > max_line_length:
                content = content[:max_line_length]
                result.append((line_no, content, True, original_length))
            else:
                result.append((line_no, content, False, 0))
        return result

    @classmethod
    def _read_lines_by_index(cls, path: Path, start: int, end: int) -> list[tuple[int, str, bool, int]]:
        """
        基于行索引读取指定行范围，不扫描整份日志。
        超过 CONTEXT_LINE_TRUNCATE_ENV 控制阈值的行会被截断，避免超大行导致 JSON 序列化与前端渲染卡顿。
        :param path: 日志文件路径
        :param start: 起始行号
        :param end: 结束行号
        :return: 行号、文本内容、是否截断、原始长度 四元组列表
        """
        if end < start:
            return []
        # 检查是否启用单行截断，默认启用
        truncate_value = os.environ.get(cls.CONTEXT_LINE_TRUNCATE_ENV, "1").strip().lower()
        truncate_enabled = truncate_value not in ("0", "false", "no", "off")
        max_line_length = cls.MAX_CONTEXT_LINE_LENGTH
        meta = cls._ensure_line_index(path)
        total = int(meta.get("line_count") or 0)
        if total <= 0:
            return []
        normalized_start = max(int(start or 1), 1)
        normalized_end = min(int(end or total), total)
        offsets = cls._read_line_offsets(path, normalized_start, normalized_end)
        encoding = str(meta.get("encoding") or "utf-8")
        result: list[tuple[int, str, bool, int]] = []
        with path.open("rb") as source:
            for line_no, offset in offsets:
                source.seek(offset)
                content = source.readline().decode(encoding, errors="replace")
                original_length = len(content)
                if truncate_enabled and original_length > max_line_length:
                    content = content[:max_line_length]
                    last_newline = content.rfind("\n")
                    if last_newline > 0:
                        content = content[:last_newline]
                    result.append((line_no, content, True, original_length))
                else:
                    result.append((line_no, content, False, 0))
        return result

    @classmethod
    def _read_line_offsets(cls, path: Path, start: int, end: int) -> list[tuple[int, int]]:
        """
        从行索引中读取指定行范围的字节偏移。
        :param path: 日志文件路径
        :param start: 起始行号
        :param end: 结束行号
        :return: 行号与字节偏移列表
        """
        offsets: list[tuple[int, int]] = []
        index_path = cls._line_index_path(path)
        with index_path.open("r", encoding="utf-8") as index_file:
            next(index_file, None)
            for line_no, raw_offset in enumerate(index_file, start=1):
                if line_no < start:
                    continue
                if line_no > end:
                    break
                try:
                    offsets.append((line_no, int(raw_offset.strip())))
                except ValueError:
                    logger.warning(f"日志行索引偏移非法，path={path}，line={line_no}，offset={raw_offset.strip()}")
        return offsets

    @classmethod
    def _line_index_path(cls, path: Path) -> Path:
        """
        获取日志文件对应的行索引文件路径。
        :param path: 日志文件路径
        :return: 行索引路径
        """
        return path.with_name(f"{path.name}{cls.LINE_INDEX_SUFFIX}")

    @classmethod
    def _detect_file_encoding(cls, path: Path) -> str:
        """
        读取文件头部样本并探测编码，优先使用行索引中缓存的编码，避免重复 charset_normalizer 调用。
        :param path: 文件路径
        :return: 编码名称
        """
        # 优先从已有的行索引中读取缓存的编码
        cached_encoding = cls._read_encoding_from_line_index(path)
        if cached_encoding:
            return cached_encoding
        with path.open("rb") as file_obj:
            sample = file_obj.read(65536)
        if not sample:
            return "utf-8"
        if sample.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        try:
            codecs.getincrementaldecoder("utf-8")("strict").decode(sample, final=False)
            return "utf-8"
        except UnicodeDecodeError:
            pass
        for fallback_encoding in ("gb18030", "gbk", "big5"):
            try:
                codecs.getincrementaldecoder(fallback_encoding)("strict").decode(sample, final=False)
                return fallback_encoding
            except UnicodeDecodeError:
                continue
        detected = from_bytes(sample).best()
        detected_encoding = str(detected.encoding or "").strip() if detected else ""
        if detected_encoding:
            return detected_encoding
        try:
            sample.decode("latin-1")
            return "latin-1"
        except UnicodeDecodeError:
            pass
        return "utf-8"

    @classmethod
    def _read_encoding_from_line_index(cls, path: Path) -> str | None:
        """
        从已有的行索引文件中读取缓存的编码，避免重复探测。
        :param path: 日志文件路径
        :return: 缓存的编码名称，索引不存在或无效时返回 None
        """
        index_path = cls._line_index_path(path)
        try:
            if not index_path.exists():
                return None
            with index_path.open("r", encoding="utf-8") as file_obj:
                meta = json.loads(file_obj.readline() or "{}")
            encoding = str(meta.get("encoding") or "").strip()
            return encoding if encoding else None
        except Exception:
            return None

    @staticmethod
    def _clean_rg_preview_content(content: str) -> str:
        """
        移除 rg --max-columns-preview 为超长行附加的说明文本。
        :param content: rg 输出的行内容
        :return: 可直接返回给接口的日志内容
        """
        return re.sub(r"\s+\[\.\.\. omitted end of long line\]$", "", str(content or ""))

    @classmethod
    def _parse_rg_line(
        cls, raw_line: str, *, max_line_bytes: int | None = None
    ) -> TicketLogSearchHitModel | None:
        """
        解析 rg 的 no-heading 输出行。
        rg 已通过 --max-columns 限制单行输出字节数，不再做 Python 侧二次截断。
        content_truncated 通过 rg 的 --max-columns-preview 后缀判断。
        :param raw_line: rg 输出原始行
        :param max_line_bytes: 保留参数兼容调用方，不再使用
        :return: 搜索命中
        """
        remain = raw_line.lstrip(".\\/").rstrip("\r\n")
        parts = remain.split(":", 2)
        if len(parts) < 3:
            return None
        try:
            line_no = int(parts[1])
        except ValueError:
            return None
        raw_content = parts[2]
        cleaned_content = cls._clean_rg_preview_content(raw_content)
        # rg 的 --max-columns-preview 会在超长行末尾追加 "[... omitted end of long line]"
        # _clean_rg_preview_content 移除该后缀后，若 raw_content 与原内容不一致即表示 rg 已截断
        content_truncated = cleaned_content != raw_content
        return TicketLogSearchHitModel(
            file=cls._normalize_relative_path(parts[0]),
            line=line_no,
            content=cleaned_content,
            content_length=len(cleaned_content),
            content_truncated=content_truncated,
        )

    @classmethod
    def _adjacent_log_file(
        cls, ticket_id: int, file_path: str, direction: str, record_id: int | None = None
    ) -> str | None:
        """
        按日志轮转顺序查找相邻文件。数字越大越旧，数字越小越靠近当前，无数字文件最新。
        :param ticket_id: 工单ID
        :param file_path: 当前相对日志路径
        :param direction: previous 查更旧文件，next 查更新文件
        :return: 相邻相对日志路径
        """
        current = cls._resolve_log_file(ticket_id, file_path, record_id)
        current_key = cls._rotation_key(current.name)
        candidates: list[tuple[int, str]] = []
        for item in cls.files(ticket_id, record_id):
            candidate_path = cls._resolve_log_file(ticket_id, item.file, record_id)
            if candidate_path.parent != current.parent:
                continue
            candidate_key = cls._rotation_key(candidate_path.name)
            if candidate_key[0] != current_key[0]:
                continue
            candidates.append((candidate_key[1], item.file))
        ordered = sorted(candidates, key=lambda item: item[0], reverse=True)
        current_file = cls._normalize_relative_path(file_path)
        ordered_files = [item[1] for item in ordered]
        if current_file not in ordered_files:
            return None
        current_index = ordered_files.index(current_file)
        if direction == "previous" and current_index > 0:
            return ordered_files[current_index - 1]
        if direction == "next" and current_index < len(ordered_files) - 1:
            return ordered_files[current_index + 1]
        return None

    @classmethod
    def _rotation_key(cls, file_name: str) -> tuple[str, int]:
        """
        解析日志轮转文件名，返回同组基名和时间序。时间序越大越旧，0 表示当前文件。
        :param file_name: 文件名
        :return: 轮转基名和时间序
        """
        name = str(file_name or "")
        match = re.match(r"^(?P<base>.+?)(?:\.(?P<suffix>\d+))?$", name)
        if not match:
            return name, 0
        base = match.group("base") or name
        suffix = match.group("suffix")
        if not suffix:
            return base, 0
        if len(suffix) >= 8:
            # 日期轮转通常是 app.log.20260618，日期越大越新；转换成负数后排序仍是旧 -> 新。
            return base, -int(suffix)
        # 普通轮转通常是 app.log.2 -> app.log.1 -> app.log，数字越大越旧。
        return base, int(suffix)

    @classmethod
    def _build_context_page_pointer(
        cls,
        ticket_id: int,
        file_path: str,
        start: int,
        end: int,
        total: int,
        before_count: int,
        after_count: int,
        direction: str,
        record_id: int | None = None,
    ) -> tuple[str | None, int | None]:
        """
        生成上下文翻页建议位置，当前文件不足时跳到相邻轮转文件。
        :param ticket_id: 工单ID
        :param file_path: 当前文件
        :param start: 当前上下文开始行
        :param end: 当前上下文结束行
        :param total: 当前文件总行数
        :param before_count: 前置上下文行数
        :param after_count: 后置上下文行数
        :param direction: previous/next
        :return: 建议文件和中心行
        """
        page_size = max(before_count + after_count + 1, 1)
        if direction == "previous":
            if start > 1:
                previous_start = max(start - page_size, 1)
                previous_end = start - 1
                return file_path, min(previous_start + before_count, previous_end)
            previous_file = cls._adjacent_log_file(ticket_id, file_path, direction="previous", record_id=record_id)
            if previous_file:
                previous_path = cls._resolve_log_file(ticket_id, previous_file, record_id)
                previous_total = int(cls._ensure_line_index(previous_path).get("line_count") or 0)
                previous_start = max(previous_total - page_size + 1, 1)
                return previous_file, min(previous_start + before_count, max(previous_total, 1))
            return None, None
        if end < total:
            next_start = end + 1
            return file_path, min(next_start + before_count, total)
        next_file = cls._adjacent_log_file(ticket_id, file_path, direction="next", record_id=record_id)
        if next_file:
            next_path = cls._resolve_log_file(ticket_id, next_file, record_id)
            next_total = int(cls._ensure_line_index(next_path).get("line_count") or 0)
            return next_file, min(1 + before_count, max(next_total, 1))
        return None, None

    @classmethod
    def _resolve_log_file(cls, ticket_id: int, file_path: str, record_id: int | None = None) -> Path:
        """
        将前端传入的相对日志路径解析为解压目录内的安全绝对路径。
        :param ticket_id: 工单ID
        :param file_path: 相对路径
        :return: 绝对路径
        """
        extract_dir = cls._extract_dir(ticket_id, record_id).resolve()
        target_path = (extract_dir / cls._normalize_relative_path(file_path)).resolve()
        try:
            target_path.relative_to(extract_dir)
        except ValueError as exc:
            raise ValueError("日志文件路径非法") from exc
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError("日志文件不存在")
        return target_path

    @classmethod
    def _relative_log_path(cls, ticket_id: int, path: Path, record_id: int | None = None) -> str:
        """
        生成相对日志路径。
        :param ticket_id: 工单ID
        :param path: 绝对路径
        :return: 相对路径
        """
        return cls._normalize_relative_path(str(path.relative_to(cls._extract_dir(ticket_id, record_id))))

    @classmethod
    def _normalize_relative_path(cls, path: str) -> str:
        """
        统一相对路径分隔符。
        :param path: 原始路径
        :return: 规范化相对路径
        """
        return str(path or "").replace("\\", "/").lstrip("/")

    @classmethod
    def _normalize_error_summary(cls, content: str) -> str:
        """
        将异常命中行归一化为聚合键。
        :param content: 命中行内容
        :return: 聚合摘要
        """
        text = " ".join(str(content or "").strip().split())
        if not text:
            return ""
        return text[:200]

    @classmethod
    def _resolve_mode(cls, env_key: str, default: str = "auto") -> str:
        """
        从环境变量读取日志读取模式，非法值按默认值处理。
        :param env_key: 环境变量名称
        :param default: 默认模式
        :return: auto/native/python
        """
        value = str(os.getenv(env_key) or default or "auto").strip().lower()
        if value not in {"auto", "native", "python"}:
            logger.warning(f"日志读取模式配置非法，env_key={env_key}，value={value}，fallback={default}")
            return default
        return value

    @classmethod
    def _release_page_cache(
        cls,
        target_files: list[str],
        ticket_id: int,
        record_id: int | None = None,
    ) -> None:
        """
        rg 搜索完成后建议 OS 释放本次搜索读取文件的页缓存，避免多次搜索不同工单日志后内存持续增长。
        在 Linux 上使用 posix_fadvise(POSIX_FADV_DONTNEED)，Windows 上跳过。
        :param target_files: 本次搜索的日志文件相对路径列表
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :return: 无
        """
        if os.name != "posix":
            return
        try:
            import ctypes

            POSIX_FADV_DONTNEED = 4  # Linux 标准值
            released_count = 0
            for target_file in target_files:
                try:
                    target_path = cls._resolve_log_file(ticket_id, target_file, record_id)
                    fd = os.open(str(target_path), os.O_RDONLY)
                    try:
                        ctypes.CDLL("libc.so.6", use_errno=True).posix_fadvise(
                            fd, 0, 0, POSIX_FADV_DONTNEED
                        )
                        released_count += 1
                    except Exception:
                        pass
                    finally:
                        os.close(fd)
                except Exception:
                    pass
            if released_count > 0:
                logger.debug(
                    f"日志搜索后释放页缓存完成，ticket_id={ticket_id}，"
                    f"record_id={record_id}，released_files={released_count}/{len(target_files)}"
                )
        except Exception:
            pass

    @classmethod
    def _write_meta(cls, path: Path, payload: dict[str, Any]) -> None:
        """
        写入日志准备元数据。
        :param path: 元数据文件路径
        :param payload: 元数据内容
        :return: 无
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def _ticket_dir(cls, ticket_id: int, record_id: int | None = None) -> Path:
        """
        获取工单日志根目录。
        :param ticket_id: 工单ID
        :return: 根目录
        """
        ticket_dir = cls.BASE_DIR / f"ticket_{ticket_id}"
        return ticket_dir / f"record_{record_id}" if record_id else ticket_dir

    @classmethod
    def _extract_dir(cls, ticket_id: int, record_id: int | None = None) -> Path:
        """
        获取工单日志解压目录。
        :param ticket_id: 工单ID
        :return: 解压目录
        """
        return cls._ticket_dir(ticket_id, record_id) / "extract"

    @classmethod
    def read_line_content(
        cls, ticket_id: int, file_path: str, line_no: int, record_id: int | None = None
    ) -> str:
        """
        获取指定日志文件的单行完整原始内容，不做截断，用于前端展开超大行的完整内容。
        :param ticket_id: 工单ID
        :param file_path: 相对日志文件路径
        :param line_no: 行号
        :param record_id: 日志拉取记录ID
        :return: 完整原始行内容
        """
        normalized_file = cls._normalize_relative_path(file_path)
        target_path = cls._resolve_log_file(ticket_id, normalized_file, record_id)
        center = max(int(line_no or 1), 1)
        rows = cls._read_line_offsets(target_path, center, center)
        if not rows:
            raise ValueError(f"行号 {center} 在日志文件 {normalized_file} 中不存在")
        _, offset = rows[0]
        meta = cls._ensure_line_index(target_path)
        encoding = str(meta.get("encoding") or "utf-8")
        with target_path.open("rb") as source:
            source.seek(offset)
            content = source.readline().decode(encoding, errors="replace")
        return content.rstrip("\r\n")
