from __future__ import annotations

import bz2
import gzip
import json
import lzma
import re
import shutil
import subprocess
import tarfile
import zipfile
from collections import Counter
from datetime import datetime
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
from modules.ticket.service.ticket_log_pull_service import TicketLogPullService
from utils.log_util import logger


class LogService:
    """
    工单日志统一服务，负责把日志拉取归档准备为可搜索文件，并提供搜索、上下文和异常摘要能力。
    """

    BASE_DIR = Path(__file__).resolve().parents[4] / "data" / "logs"
    SOURCE_FILE_NAME = "log.zip"
    META_FILE_NAME = "meta.json"
    TEXT_EXTENSIONS = {".log", ".txt", ".out"}
    COMPRESSED_SUFFIXES = (".zip", ".rar", ".7z", ".tar", ".tar.gz", ".tgz", ".gz", ".bz2", ".xz")
    ERROR_KEYWORDS = ("ERROR", "Exception", "Traceback", "timeout", "failed")
    MAX_RECURSIVE_EXTRACT_ROUNDS = 20
    LINE_INDEX_SUFFIX = ".lineidx"

    @classmethod
    def prepare(cls, db: Session, ticket_id: int) -> TicketLogPrepareModel:
        """
        准备指定工单的日志目录：复用最新日志拉取归档，下载或复制到 source 后递归解压到 extract。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 准备结果
        """
        logger.info(f"开始准备工单日志查看目录，ticket_id={ticket_id}")
        ticket_dir = cls._ticket_dir(ticket_id)
        source_dir = ticket_dir / "source"
        extract_dir = ticket_dir / "extract"
        meta_path = ticket_dir / cls.META_FILE_NAME
        if extract_dir.exists() and any(extract_dir.iterdir()):
            files = cls.files(ticket_id)
            logger.info(f"工单日志已存在解压目录，跳过重复准备，ticket_id={ticket_id}，file_count={len(files)}")
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                prepared=True,
                source_path=str(cls._find_source_archive(source_dir) or source_dir / cls.SOURCE_FILE_NAME),
                extract_path=str(extract_dir),
                file_count=len(files),
                message="日志已准备完成",
            )

        record = cls._latest_record(db, ticket_id)
        if not record:
            logger.warning(f"未找到工单日志拉取记录，无法准备日志，ticket_id={ticket_id}")
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                prepared=False,
                file_count=0,
                message="未找到日志文件，且未配置下载地址",
            )

        archive_path, should_cleanup = TicketLogPullService._resolve_archive_source_for_view(record, db)
        if not archive_path:
            logger.warning(f"未解析到可用日志归档文件，ticket_id={ticket_id}，record_id={record.id}")
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                prepared=False,
                file_count=0,
                message="未找到日志文件，且未配置下载地址",
            )

        try:
            source_dir.mkdir(parents=True, exist_ok=True)
            extract_dir.mkdir(parents=True, exist_ok=True)
            source_path = source_dir / cls._build_source_file_name(archive_path)
            shutil.copy2(archive_path, source_path)
            if should_cleanup:
                archive_path.unlink(missing_ok=True)
            cls._extract_recursive(source_path, extract_dir)
            files = cls.files(ticket_id)
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
            logger.info(f"工单日志准备完成，ticket_id={ticket_id}，record_id={record.id}，file_count={len(files)}")
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                prepared=True,
                source_path=str(source_path),
                extract_path=str(extract_dir),
                file_count=len(files),
                message="日志准备完成",
            )
        except Exception as exc:
            logger.exception(exc)
            return TicketLogPrepareModel(
                ticket_id=ticket_id,
                prepared=False,
                source_path=str(cls._find_source_archive(source_dir) or source_dir / cls.SOURCE_FILE_NAME),
                extract_path=str(extract_dir),
                file_count=0,
                message=f"日志准备失败：{exc}",
            )

    @classmethod
    def files(cls, ticket_id: int) -> list[TicketLogFileModel]:
        """
        查询指定工单已准备目录中的可读日志文本文件。
        :param ticket_id: 工单ID
        :return: 日志文件列表
        """
        extract_dir = cls._extract_dir(ticket_id)
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
                    file=cls._relative_log_path(ticket_id, path),
                    size=path.stat().st_size,
                    modified_at=datetime.fromtimestamp(path.stat().st_mtime),
                )
            )
        return sorted(result, key=lambda item: item.file)

    @classmethod
    def search(
        cls,
        ticket_id: int,
        keyword: str,
        context_before: int = 20,
        context_after: int = 20,
        limit: int = 100,
        with_context: bool = True,
    ) -> list[TicketLogSearchHitModel]:
        """
        使用 ripgrep 搜索工单日志，并按需返回每个命中的上下文。
        :param ticket_id: 工单ID
        :param keyword: 搜索关键字
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :return: 搜索命中列表
        """
        keyword = str(keyword or "").strip()
        if not keyword:
            return []
        extract_dir = cls._extract_dir(ticket_id)
        if not extract_dir.exists():
            return []
        command = ["rg", "-n", "--no-heading", "--color", "never", "--fixed-strings", keyword, "."]
        try:
            process = subprocess.run(
                command,
                cwd=str(extract_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise RuntimeError("未找到 ripgrep(rg)，请先安装 rg 后再使用日志搜索") from exc
        if process.returncode not in (0, 1):
            raise RuntimeError(f"日志搜索执行失败：{process.stderr.strip() or process.stdout.strip()}")

        hits: list[TicketLogSearchHitModel] = []
        for raw_line in process.stdout.splitlines():
            if len(hits) >= limit:
                break
            hit = cls._parse_rg_line(raw_line)
            if not hit:
                continue
            if with_context:
                hit.context = cls.context(ticket_id, hit.file, hit.line, context_before, context_after)
            hits.append(hit)
        return hits

    @classmethod
    def context(cls, ticket_id: int, file_path: str, line_no: int, before: int, after: int) -> TicketLogContextModel:
        """
        按行号索引读取指定日志文件在某行附近的上下文，必要时跨轮转文件补足前后文。
        :param ticket_id: 工单ID
        :param file_path: 相对日志文件路径
        :param line_no: 中心行号
        :param before: 前置行数
        :param after: 后置行数
        :return: 上下文内容
        """
        normalized_file = cls._normalize_relative_path(file_path)
        target_path = cls._resolve_log_file(ticket_id, normalized_file)
        center = max(int(line_no or 1), 1)
        before_count = max(int(before or 0), 0)
        after_count = max(int(after or 0), 0)
        index_data = cls._ensure_line_index(target_path)
        total = int(index_data.get("line_count") or 0)
        bounded_center = min(center, max(total, 1))
        start = max(bounded_center - before_count, 1)
        end = min(bounded_center + after_count, total)

        context_parts: list[tuple[str, int, str]] = []
        missing_before = max(before_count - (bounded_center - start), 0)
        missing_after = max(after_count - (end - bounded_center), 0)
        previous_file = None
        next_file = None
        if missing_before > 0:
            previous_file = cls._adjacent_log_file(ticket_id, normalized_file, direction="previous")
            if previous_file:
                previous_path = cls._resolve_log_file(ticket_id, previous_file)
                previous_index = cls._ensure_line_index(previous_path)
                previous_total = int(previous_index.get("line_count") or 0)
                previous_start = max(previous_total - missing_before + 1, 1)
                context_parts.extend(
                    (previous_file, line, content)
                    for line, content in cls._read_lines_by_index(previous_path, previous_start, previous_total)
                )

        context_parts.extend(
            (normalized_file, line, content) for line, content in cls._read_lines_by_index(target_path, start, end)
        )

        if missing_after > 0:
            next_file = cls._adjacent_log_file(ticket_id, normalized_file, direction="next")
            if next_file:
                next_path = cls._resolve_log_file(ticket_id, next_file)
                context_parts.extend(
                    (next_file, line, content)
                    for line, content in cls._read_lines_by_index(next_path, 1, missing_after)
                )

        context_lines = [
            TicketLogContextLineModel(file=line_file, line=index, content=content.rstrip("\r\n"))
            for line_file, index, content in context_parts
        ]
        has_prev = start > 1 or cls._adjacent_log_file(ticket_id, normalized_file, direction="previous") is not None
        has_next = end < total or cls._adjacent_log_file(ticket_id, normalized_file, direction="next") is not None
        prev_file, prev_line = cls._build_context_page_pointer(
            ticket_id, normalized_file, start, end, total, direction="previous"
        )
        next_file, next_line = cls._build_context_page_pointer(
            ticket_id, normalized_file, start, end, total, direction="next"
        )
        return TicketLogContextModel(
            ticket_id=ticket_id,
            file=normalized_file,
            line=bounded_center,
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
    def search_time(
        cls,
        ticket_id: int,
        time_keyword: str,
        context_before: int = 20,
        context_after: int = 20,
        limit: int = 100,
        with_context: bool = True,
    ) -> list[TicketLogSearchHitModel]:
        """
        按时间文本搜索日志，典型输入为 14:32。
        :param ticket_id: 工单ID
        :param time_keyword: 时间关键字
        :param context_before: 前置上下文行数
        :param context_after: 后置上下文行数
        :param limit: 最大返回命中数
        :param with_context: 是否直接返回上下文
        :return: 搜索命中列表
        """
        return cls.search(ticket_id, time_keyword, context_before, context_after, limit, with_context)

    @classmethod
    def errors(cls, ticket_id: int, limit: int = 100) -> TicketLogErrorSummaryModel:
        """
        提取常见异常关键字并聚合计数。
        :param ticket_id: 工单ID
        :param limit: 最大样例数量
        :return: 异常摘要
        """
        samples: list[TicketLogSearchHitModel] = []
        counter: Counter[str] = Counter()
        for keyword in cls.ERROR_KEYWORDS:
            remain = max(limit - len(samples), 0)
            if remain <= 0:
                break
            for hit in cls.search(ticket_id, keyword, 0, 0, remain, with_context=False):
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
    def _extract_recursive(cls, archive_path: Path, target_dir: Path) -> None:
        """
        递归解压压缩包，直到目录内不再存在受支持的压缩文件或达到最大轮次。
        :param archive_path: 初始压缩包路径
        :param target_dir: 解压目标目录
        :return: 无
        """
        cls._extract_one(archive_path, target_dir)
        for round_index in range(cls.MAX_RECURSIVE_EXTRACT_ROUNDS):
            archives = [path for path in target_dir.rglob("*") if path.is_file() and cls._is_archive(path)]
            if not archives:
                logger.info(f"递归解压完成，target_dir={target_dir}，round={round_index}")
                return
            for archive in archives:
                extract_to = archive.parent / archive.stem
                extract_to.mkdir(parents=True, exist_ok=True)
                try:
                    cls._extract_one(archive, extract_to)
                    archive.unlink(missing_ok=True)
                    logger.info(f"完成一层日志压缩包解压，archive={archive}，extract_to={extract_to}")
                except Exception as exc:
                    logger.warning(f"日志压缩包解压失败，archive={archive}，reason={exc}")
        logger.warning(f"递归解压达到最大轮次后停止，target_dir={target_dir}，max_rounds={cls.MAX_RECURSIVE_EXTRACT_ROUNDS}")

    @classmethod
    def _extract_one(cls, archive_path: Path, target_dir: Path) -> None:
        """
        解压单个压缩文件，优先使用标准库，RAR/7z 交给系统 7z。
        :param archive_path: 压缩文件路径
        :param target_dir: 目标目录
        :return: 无
        """
        name = archive_path.name.lower()
        if name.endswith(".zip"):
            cls._extract_zip_safely(archive_path, target_dir)
            return
        if name.endswith((".tar", ".tar.gz", ".tgz", ".bz2", ".xz")) and tarfile.is_tarfile(archive_path):
            cls._extract_tar_safely(archive_path, target_dir)
            return
        if name.endswith(".gz") and not name.endswith(".tar.gz"):
            output_path = target_dir / archive_path.with_suffix("").name
            with gzip.open(archive_path, "rb") as source, output_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            return
        if name.endswith(".bz2"):
            output_path = target_dir / archive_path.with_suffix("").name
            with bz2.open(archive_path, "rb") as source, output_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            return
        if name.endswith(".xz"):
            output_path = target_dir / archive_path.with_suffix("").name
            with lzma.open(archive_path, "rb") as source, output_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            return
        cls._extract_by_7z(archive_path, target_dir)

    @classmethod
    def _extract_zip_safely(cls, archive_path: Path, target_dir: Path) -> None:
        """
        安全解压 ZIP 文件，避免压缩包内的相对路径写出目标目录。
        :param archive_path: ZIP 文件路径
        :param target_dir: 解压目标目录
        :return: 无
        """
        root = target_dir.resolve()
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                target_path = (target_dir / member.filename).resolve()
                if not cls._is_relative_to(target_path, root):
                    logger.warning(f"跳过非法 ZIP 条目，archive={archive_path}，member={member.filename}")
                    continue
                archive.extract(member, target_dir)

    @classmethod
    def _extract_tar_safely(cls, archive_path: Path, target_dir: Path) -> None:
        """
        安全解压 TAR 文件，避免压缩包内的相对路径写出目标目录。
        :param archive_path: TAR 文件路径
        :param target_dir: 解压目标目录
        :return: 无
        """
        root = target_dir.resolve()
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                target_path = (target_dir / member.name).resolve()
                if not cls._is_relative_to(target_path, root):
                    logger.warning(f"跳过非法 TAR 条目，archive={archive_path}，member={member.name}")
                    continue
                archive.extract(member, target_dir)

    @classmethod
    def _extract_by_7z(cls, archive_path: Path, target_dir: Path) -> None:
        """
        使用系统 7z 解压 Python 标准库不覆盖的格式。
        :param archive_path: 压缩文件路径
        :param target_dir: 目标目录
        :return: 无
        """
        executable = shutil.which("7z") or shutil.which("7z.exe")
        if not executable:
            raise RuntimeError("当前环境未找到 7z，无法解压 rar/7z 等格式")
        process = subprocess.run(
            [executable, "x", "-y", f"-o{target_dir}", str(archive_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "7z 解压失败")

    @classmethod
    def _is_archive(cls, path: Path) -> bool:
        """
        判断文件是否为支持递归处理的压缩文件。
        :param path: 文件路径
        :return: 是否压缩文件
        """
        name = path.name.lower()
        return any(name.endswith(suffix) for suffix in cls.COMPRESSED_SUFFIXES)

    @classmethod
    def _is_relative_to(cls, path: Path, root: Path) -> bool:
        """
        判断路径是否位于指定根目录内。
        :param path: 待判断路径
        :param root: 根目录
        :return: 是否位于根目录内
        """
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @classmethod
    def _build_source_file_name(cls, archive_path: Path) -> str:
        """
        按真实压缩格式生成 source 目录中的文件名，避免 rar/7z 被误当成 zip。
        :param archive_path: 原始压缩包路径
        :return: 缓存文件名
        """
        name = archive_path.name.lower()
        for suffix in (".tar.gz", ".tgz", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"):
            if name.endswith(suffix):
                return f"log{suffix}"
        return cls.SOURCE_FILE_NAME

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
        sample = path.read_bytes()[:8192]
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
        if index_path.exists():
            try:
                with index_path.open("r", encoding="utf-8") as file_obj:
                    meta = json.loads(file_obj.readline() or "{}")
                if meta.get("size") == stat.st_size and meta.get("mtime_ns") == stat.st_mtime_ns:
                    return meta
            except Exception as exc:
                logger.warning(f"读取日志行索引失败，将重建索引，path={path}，reason={exc}")

        logger.info(f"开始构建日志行索引，path={path}，size={stat.st_size}")
        encoding = cls._detect_file_encoding(path)
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
    def _read_lines_by_index(cls, path: Path, start: int, end: int) -> list[tuple[int, str]]:
        """
        基于行索引读取指定行范围，不扫描整份日志。
        :param path: 日志文件路径
        :param start: 起始行号
        :param end: 结束行号
        :return: 行号与文本内容列表
        """
        if end < start:
            return []
        meta = cls._ensure_line_index(path)
        total = int(meta.get("line_count") or 0)
        if total <= 0:
            return []
        normalized_start = max(int(start or 1), 1)
        normalized_end = min(int(end or total), total)
        offsets = cls._read_line_offsets(path, normalized_start, normalized_end)
        encoding = str(meta.get("encoding") or "utf-8")
        result: list[tuple[int, str]] = []
        with path.open("rb") as source:
            for line_no, offset in offsets:
                source.seek(offset)
                content = source.readline().decode(encoding, errors="replace")
                result.append((line_no, content))
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
        读取文件头部样本并探测编码。
        :param path: 文件路径
        :return: 编码名称
        """
        with path.open("rb") as file_obj:
            sample = file_obj.read(65536)
        detected = from_bytes(sample).best()
        return detected.encoding if detected and detected.encoding else "utf-8"

    @classmethod
    def _parse_rg_line(cls, raw_line: str) -> TicketLogSearchHitModel | None:
        """
        解析 rg 的 no-heading 输出行。搜索命令在 extract 目录内执行，因此这里拿到的是相对路径。
        :param raw_line: rg 输出原始行
        :return: 搜索命中
        """
        remain = raw_line.lstrip(".\\/")
        parts = remain.split(":", 2)
        if len(parts) < 3:
            return None
        try:
            line_no = int(parts[1])
        except ValueError:
            return None
        return TicketLogSearchHitModel(
            file=cls._normalize_relative_path(parts[0]),
            line=line_no,
            content=parts[2],
        )

    @classmethod
    def _adjacent_log_file(cls, ticket_id: int, file_path: str, direction: str) -> str | None:
        """
        按日志轮转顺序查找相邻文件。数字越大越旧，数字越小越靠近当前，无数字文件最新。
        :param ticket_id: 工单ID
        :param file_path: 当前相对日志路径
        :param direction: previous 查更旧文件，next 查更新文件
        :return: 相邻相对日志路径
        """
        current = cls._resolve_log_file(ticket_id, file_path)
        current_key = cls._rotation_key(current.name)
        candidates: list[tuple[int, str]] = []
        for item in cls.files(ticket_id):
            candidate_path = cls._resolve_log_file(ticket_id, item.file)
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
        direction: str,
    ) -> tuple[str | None, int | None]:
        """
        生成上下文翻页建议位置，当前文件不足时跳到相邻轮转文件。
        :param ticket_id: 工单ID
        :param file_path: 当前文件
        :param start: 当前上下文开始行
        :param end: 当前上下文结束行
        :param total: 当前文件总行数
        :param direction: previous/next
        :return: 建议文件和中心行
        """
        if direction == "previous":
            if start > 1:
                return file_path, max(start - 1, 1)
            previous_file = cls._adjacent_log_file(ticket_id, file_path, direction="previous")
            if previous_file:
                previous_path = cls._resolve_log_file(ticket_id, previous_file)
                previous_total = int(cls._ensure_line_index(previous_path).get("line_count") or 0)
                return previous_file, max(previous_total, 1)
            return None, None
        if end < total:
            return file_path, min(end + 1, total)
        next_file = cls._adjacent_log_file(ticket_id, file_path, direction="next")
        if next_file:
            return next_file, 1
        return None, None

    @classmethod
    def _resolve_log_file(cls, ticket_id: int, file_path: str) -> Path:
        """
        将前端传入的相对日志路径解析为解压目录内的安全绝对路径。
        :param ticket_id: 工单ID
        :param file_path: 相对路径
        :return: 绝对路径
        """
        extract_dir = cls._extract_dir(ticket_id).resolve()
        target_path = (extract_dir / cls._normalize_relative_path(file_path)).resolve()
        try:
            target_path.relative_to(extract_dir)
        except ValueError as exc:
            raise ValueError("日志文件路径非法") from exc
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError("日志文件不存在")
        return target_path

    @classmethod
    def _relative_log_path(cls, ticket_id: int, path: Path) -> str:
        """
        生成相对日志路径。
        :param ticket_id: 工单ID
        :param path: 绝对路径
        :return: 相对路径
        """
        return cls._normalize_relative_path(str(path.relative_to(cls._extract_dir(ticket_id))))

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
    def _ticket_dir(cls, ticket_id: int) -> Path:
        """
        获取工单日志根目录。
        :param ticket_id: 工单ID
        :return: 根目录
        """
        return cls.BASE_DIR / f"ticket_{ticket_id}"

    @classmethod
    def _extract_dir(cls, ticket_id: int) -> Path:
        """
        获取工单日志解压目录。
        :param ticket_id: 工单ID
        :return: 解压目录
        """
        return cls._ticket_dir(ticket_id) / "extract"
