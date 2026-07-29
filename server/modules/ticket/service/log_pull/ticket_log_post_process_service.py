from __future__ import annotations

import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from charset_normalizer import from_bytes
from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullRecord
from modules.ticket.service.core.ticket_version_service import TicketVersionService
from modules.ticket.util.ticket_common_util import normalize_ticket_version_key
from modules.ticket.util.ticket_log_archive_util import TicketLogArchiveUtil
from utils.log_util import logger


class TicketLogPostProcessService:
    """
    工单日志拉取完成后的本地后处理服务。

    负责在日志压缩包下载完成后，按配置把归档准备到日志查看目录，并可选执行版本号提取和行索引生成。
    """

    BASE_DIR = Path(__file__).resolve().parents[4] / "data" / "logs"
    META_FILE_NAME = "meta.json"
    LINE_INDEX_SUFFIX = ".lineidx"
    LINE_INDEX_ENCODING_VERSION = 2
    TEXT_EXTENSIONS = {".log", ".txt", ".out"}
    VERSION_PATTERN = re.compile(
        r"(?:版本号|版本|version|app[_\s-]*version)\s*[:：=]\s*([A-Za-z0-9._/-]+)",
        re.IGNORECASE,
    )

    @classmethod
    def run_after_download(
        cls,
        db: Session,
        record: TicketLogPullRecord,
        archive_path: Path,
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        根据日志存储配置执行下载完成后的后处理。
        :param db: 数据库会话
        :param record: 日志拉取记录
        :param archive_path: 已下载到本地临时文件的压缩包路径
        :param runtime_config: 日志拉取存储配置
        :return: 后处理摘要
        """
        if not cls._config_bool(runtime_config, "postDownloadExtractEnabled", False):
            return {"enabled": False, "message": "下载完成后自动解压未启用"}
        if not record.ticket_id:
            return {"enabled": True, "prepared": False, "message": "记录未关联工单，跳过解压"}
        if not archive_path.exists():
            return {"enabled": True, "prepared": False, "message": "压缩包文件不存在，跳过解压"}

        started_at = time.monotonic()
        ticket_dir = cls._ticket_dir(record.ticket_id, record.id)
        source_dir = ticket_dir / "source"
        extract_dir = ticket_dir / "extract"
        source_dir.mkdir(parents=True, exist_ok=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        source_path = source_dir / cls._build_source_file_name(archive_path)
        shutil.copy2(archive_path, source_path)
        cls._extract_recursive(source_path, extract_dir, runtime_config, started_at)
        log_files = cls._list_log_files(extract_dir)
        version_key = ""
        if cls._config_bool(runtime_config, "postDownloadVersionExtractEnabled", False):
            version_key = cls.extract_and_update_version_key(db, record.ticket_id, record.id, log_files)
        indexed_count = 0
        if cls._config_bool(runtime_config, "postDownloadIndexEnabled", False):
            indexed_count = cls.build_line_indexes(log_files)
        cls._write_meta(
            ticket_dir / cls.META_FILE_NAME,
            {
                "ticket_id": record.ticket_id,
                "record_id": record.id,
                "source_path": str(source_path),
                "extract_path": str(extract_dir),
                "prepared_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "file_count": len(log_files),
                "post_download": True,
                "version_key": version_key,
                "indexed_count": indexed_count,
            },
        )
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            f"日志下载完成后处理完成，ticket_id={record.ticket_id}，record_id={record.id}，"
            f"source_path={source_path}，extract_path={extract_dir}，file_count={len(log_files)}，"
            f"version_key={version_key}，indexed_count={indexed_count}，elapsed_ms={elapsed_ms}"
        )
        return {
            "enabled": True,
            "prepared": True,
            "sourcePath": str(source_path),
            "extractPath": str(extract_dir),
            "fileCount": len(log_files),
            "versionKey": version_key,
            "indexedCount": indexed_count,
            "elapsedMs": elapsed_ms,
        }

    @classmethod
    def extract_and_update_version_key(
        cls,
        db: Session,
        ticket_id: int,
        record_id: int,
        log_files: list[Path],
    ) -> str:
        """
        从已解压日志文件中流式提取版本号，并在工单缺失版本时写入发生版本。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :param log_files: 已解压日志文件列表
        :return: 提取到的版本号，未命中返回空字符串
        """
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            return ""
        if ticket.affected_version_id:
            current_version_key = TicketVersionService.get_version_name_map(db, {ticket.affected_version_id}).get(
                ticket.affected_version_id, ""
            )
            logger.info(
                f"日志下载完成后版本提取跳过，ticket_id={ticket_id}，record_id={record_id}，"
                f"reason=工单已有发生版本，version_key={current_version_key}"
            )
            return current_version_key

        version_key = cls.extract_version_key_from_files(log_files)
        if not version_key:
            logger.info(f"日志下载完成后版本提取未命中，ticket_id={ticket_id}，record_id={record_id}")
            return ""
        ticket.update_by = "system"
        ticket.update_time = datetime.now()
        TicketVersionService.assign_detected_ticket_version(
            db,
            ticket,
            version_type="affected",
            version_key=version_key,
            source="log_extract",
        )
        logger.info(
            f"日志下载完成后版本提取成功，ticket_id={ticket_id}，record_id={record_id}，version_key={version_key}"
        )
        return version_key

    @classmethod
    def extract_version_key_from_files(cls, log_files: list[Path]) -> str:
        """
        从日志文件中按行流式提取版本号，命中后立即返回。
        :param log_files: 日志文件列表
        :return: 提取到的版本号
        """
        for path in log_files:
            encoding = cls._detect_file_encoding(path)
            try:
                with path.open("r", encoding=encoding, errors="replace") as file_obj:
                    for line in file_obj:
                        match = cls.VERSION_PATTERN.search(line)
                        if match:
                            version_key = normalize_ticket_version_key(match.group(1))
                            if version_key:
                                return version_key
            except Exception as exc:
                logger.warning(f"日志版本提取读取文件失败，path={path}，reason={exc}")
        return ""

    @classmethod
    def build_line_indexes(cls, log_files: list[Path]) -> int:
        """
        为已解压日志文件生成行索引。
        :param log_files: 日志文件列表
        :return: 成功生成或复用的索引数量
        """
        indexed_count = 0
        for path in log_files:
            try:
                cls._ensure_line_index(path)
                indexed_count += 1
            except Exception as exc:
                logger.warning(f"日志下载完成后生成行索引失败，path={path}，reason={exc}")
        return indexed_count

    @classmethod
    def _extract_recursive(
        cls,
        archive_path: Path,
        target_dir: Path,
        runtime_config: dict[str, Any],
        started_at: float,
    ) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.extract_recursive(
            archive_path, target_dir, runtime_config, started_at, context="日志下载完成后"
        )

    @classmethod
    def _ensure_prepare_budget(cls, started_at: float, runtime_config: dict[str, Any]) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.ensure_prepare_budget(started_at, runtime_config, context="日志下载完成后自动")

    @classmethod
    def _validate_extracted_resource_usage(cls, target_dir: Path, runtime_config: dict[str, Any]) -> None:
        """委托到 TicketLogArchiveUtil。"""
        TicketLogArchiveUtil.validate_extracted_resource_usage(target_dir, runtime_config, context="日志下载完成后自动")

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
    def _list_log_files(cls, extract_dir: Path) -> list[Path]:
        """
        列出已解压目录中的可搜索日志文本文件。
        :param extract_dir: 解压目录
        :return: 日志文件列表
        """
        result: list[Path] = []
        for path in extract_dir.rglob("*"):
            if not path.is_file() or path.stat().st_size <= 0:
                continue
            if path.name.endswith(cls.LINE_INDEX_SUFFIX):
                continue
            if cls._is_archive(path):
                continue
            if cls._is_text_file(path):
                result.append(path)
        return sorted(result, key=lambda item: str(item))

    @classmethod
    def _ensure_line_index(cls, path: Path) -> dict[str, Any]:
        """
        确保指定日志文件存在行号索引。
        :param path: 日志文件路径
        :return: 索引元数据
        """
        index_path = path.with_name(f"{path.name}{cls.LINE_INDEX_SUFFIX}")
        stat = path.stat()
        if index_path.exists():
            try:
                with index_path.open("r", encoding="utf-8") as file_obj:
                    meta = json.loads(file_obj.readline() or "{}")
                if (
                    meta.get("size") == stat.st_size
                    and meta.get("mtime_ns") == stat.st_mtime_ns
                    and meta.get("encoding_version") == cls.LINE_INDEX_ENCODING_VERSION
                ):
                    return meta
            except Exception as exc:
                logger.warning(f"读取日志行索引失败，将重建索引，path={path}，reason={exc}")

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
            "encoding_version": cls.LINE_INDEX_ENCODING_VERSION,
            "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
        }
        with index_path.open("w", encoding="utf-8", newline="\n") as index_file:
            index_file.write(json.dumps(meta, ensure_ascii=False) + "\n")
            with temp_index_path.open("r", encoding="utf-8") as temp_index_file:
                shutil.copyfileobj(temp_index_file, index_file)
        temp_index_path.unlink(missing_ok=True)
        return meta

    @classmethod
    def _detect_file_encoding(cls, path: Path) -> str:
        """
        探测日志文件编码。
        :param path: 文件路径
        :return: 编码名称
        """
        with path.open("rb") as file_obj:
            sample = file_obj.read(65536)
        if not sample:
            return "utf-8"
        if sample.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        try:
            sample.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass
        for fallback_encoding in ("gb18030", "gbk", "big5"):
            try:
                sample.decode(fallback_encoding)
                return fallback_encoding
            except UnicodeDecodeError:
                continue
        detected = from_bytes(sample).best()
        detected_encoding = str(detected.encoding or "").strip() if detected else ""
        return detected_encoding or "utf-8"

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
    def _write_meta(cls, path: Path, payload: dict[str, Any]) -> None:
        """
        写入日志查看目录元数据。
        :param path: 元数据文件路径
        :param payload: 元数据内容
        :return: 无
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def _build_source_file_name(cls, archive_path: Path) -> str:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.build_source_file_name(archive_path, TicketLogArchiveUtil.DEFAULT_SOURCE_NAME)

    @classmethod
    def _ticket_dir(cls, ticket_id: int, record_id: int | None = None) -> Path:
        """
        获取日志查看根目录。
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :return: 根目录
        """
        ticket_dir = cls.BASE_DIR / f"ticket_{ticket_id}"
        return ticket_dir / f"record_{record_id}" if record_id else ticket_dir

    @classmethod
    def _is_archive(cls, path: Path) -> bool:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.is_archive(path)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.is_relative_to(path, root)

    @staticmethod
    def _config_int(config: dict[str, Any], key: str, default: int) -> int:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.config_int(config, key, default)

    @staticmethod
    def _config_bool(config: dict[str, Any], key: str, default: bool) -> bool:
        """委托到 TicketLogArchiveUtil。"""
        return TicketLogArchiveUtil.config_bool(config, key, default)
