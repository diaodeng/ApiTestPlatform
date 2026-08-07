from __future__ import annotations

import bz2
import gzip
import io
import lzma
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any

import py7zr

from utils.log_util import logger

# -------------------------------------------------------
# 支持的压缩格式及递归解压配置
# -------------------------------------------------------
COMPRESSED_SUFFIXES: tuple[str, ...] = (".zip", ".rar", ".7z", ".tar", ".tar.gz", ".tgz", ".gz", ".bz2", ".xz")
MAX_RECURSIVE_EXTRACT_ROUNDS = 20


class TicketLogArchiveUtil:
    """日志压缩包解压工具类 — 供 LogService 和 TicketLogPostProcessService 共用。"""

    DEFAULT_SOURCE_NAME = "log.zip"

    # ---------------- 入口方法 ----------------

    @staticmethod
    def extract_recursive(
        archive_path: Path,
        target_dir: Path,
        runtime_config: dict[str, Any],
        started_at: float,
        *,
        context: str = "日志",
    ) -> None:
        """
        递归解压压缩包，直到目录内不再存在受支持的压缩文件或达到最大轮次。
        :param archive_path: 初始压缩包路径
        :param target_dir: 解压目标目录
        :param runtime_config: 运行保护配置
        :param started_at: 开始时间戳
        :param context: 日志消息前缀，区分业务场景
        """
        TicketLogArchiveUtil.ensure_prepare_budget(started_at, runtime_config, context=context)
        TicketLogArchiveUtil.extract_one(archive_path, target_dir)
        TicketLogArchiveUtil.validate_extracted_resource_usage(target_dir, runtime_config, context=context)
        for round_index in range(MAX_RECURSIVE_EXTRACT_ROUNDS):
            TicketLogArchiveUtil.ensure_prepare_budget(started_at, runtime_config, context=context)
            archives = [
                path for path in target_dir.rglob("*") if path.is_file() and TicketLogArchiveUtil.is_archive(path)
            ]
            if not archives:
                logger.info(f"{context}递归解压完成，target_dir={target_dir}，round={round_index}")
                return
            for archive in archives:
                TicketLogArchiveUtil.ensure_prepare_budget(started_at, runtime_config, context=context)
                extract_to = archive.parent / archive.stem
                extract_to.mkdir(parents=True, exist_ok=True)
                try:
                    TicketLogArchiveUtil.extract_one(archive, extract_to)
                    archive.unlink(missing_ok=True)
                    TicketLogArchiveUtil.validate_extracted_resource_usage(
                        target_dir, runtime_config, context=context
                    )
                except Exception as exc:
                    logger.warning(f"{context}压缩包解压失败，archive={archive}，reason={exc}")
        logger.warning(
            f"{context}递归解压达到最大轮次后停止，target_dir={target_dir}，max_rounds={MAX_RECURSIVE_EXTRACT_ROUNDS}"
        )

    # ---------------- 单文件解压 ----------------

    @staticmethod
    def extract_one(archive_path: Path, target_dir: Path) -> None:
        """
        解压单个压缩文件，优先使用标准库，.7z 先尝试 py7zr 失败后 fallback 到系统 7z，其他未知格式走系统 7z 兜底。
        :param archive_path: 压缩文件路径
        :param target_dir: 解压目录
        """
        name = archive_path.name.lower()
        if name.endswith(".zip"):
            TicketLogArchiveUtil.extract_zip_safely(archive_path, target_dir)
            return
        if name.endswith((".tar", ".tar.gz", ".tgz", ".bz2", ".xz")) and tarfile.is_tarfile(archive_path):
            TicketLogArchiveUtil.extract_tar_safely(archive_path, target_dir)
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
        if name.endswith(".7z"):
            try:
                TicketLogArchiveUtil.extract_7z(archive_path, target_dir)
            except Exception as exc:
                logger.warning(f"py7zr 解压失败，fallback 到系统 7z，archive={archive_path}，reason={exc}")
                TicketLogArchiveUtil.extract_by_7z(archive_path, target_dir)
            return
        TicketLogArchiveUtil.extract_by_7z(archive_path, target_dir, context="")

    # ---------------- 安全解压（路径穿越保护） ----------------

    @staticmethod
    def extract_zip_safely(archive_path: Path, target_dir: Path) -> None:
        """
        安全解压 ZIP 文件，避免压缩包内的相对路径写出目标目录。
        :param archive_path: ZIP 文件路径
        :param target_dir: 解压目标目录
        """
        root = target_dir.resolve()
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                target_path = (target_dir / member.filename).resolve()
                if not TicketLogArchiveUtil.is_relative_to(target_path, root):
                    logger.warning(f"跳过非法 ZIP 条目，archive={archive_path}，member={member.filename}")
                    continue
                archive.extract(member, target_dir)

    @staticmethod
    def extract_tar_safely(archive_path: Path, target_dir: Path) -> None:
        """
        安全解压 TAR 文件，避免压缩包内的相对路径写出目标目录。
        :param archive_path: TAR 文件路径
        :param target_dir: 解压目标目录
        """
        root = target_dir.resolve()
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                target_path = (target_dir / member.name).resolve()
                if not TicketLogArchiveUtil.is_relative_to(target_path, root):
                    logger.warning(f"跳过非法 TAR 条目，archive={archive_path}，member={member.name}")
                    continue
                archive.extract(member, target_dir)

    # ---------------- 7z 解压 ----------------

    @staticmethod
    def extract_7z(archive_path: Path, target_dir: Path) -> None:
        """
        使用 py7zr 解压 .7z 文件，py7zr 内部已含路径穿越保护。
        :param archive_path: .7z 压缩包路径
        :param target_dir: 解压目标目录
        """
        with py7zr.SevenZipFile(archive_path, "r") as archive:
            archive.extractall(path=target_dir)

    @staticmethod
    def extract_by_7z(archive_path: Path, target_dir: Path, *, context: str = "日志") -> None:
        """
        使用系统 7z 命令解压 Python 标准库不覆盖的格式（兜底）。
        :param archive_path: 压缩文件路径
        :param target_dir: 目标目录
        :param context: 日志消息前缀
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

    # ---------------- 压缩包读取适配器 ----------------

    class _ArchiveReader:
        """统一 ZIP / 7z 压缩包读取接口，提供 namelist() + open() 兼容 zipfile.ZipFile。"""

        def __init__(self, path: Path) -> None:
            name = path.name.lower()
            if name.endswith(".7z"):
                self._backend: Any = py7zr.SevenZipFile(path, "r")
                self._is_7z = True
            else:
                self._backend: Any = zipfile.ZipFile(path)
                self._is_7z = False

        def namelist(self) -> list[str]:
            """返回压缩包内所有条目名称（不含目录）。"""
            if self._is_7z:
                return self._backend.getnames()
            return self._backend.namelist()

        def open(self, name: str, mode: str = "r") -> io.BytesIO:
            """读取压缩包内指定条目内容，返回 BytesIO。"""
            if self._is_7z:
                data = self._backend.read(targets=[name])
                if name in data:
                    return data[name]
                raise KeyError(f"Entry '{name}' not found in 7z archive")
            return self._backend.open(name, mode)

        def __enter__(self):
            return self

        def __exit__(self, *args: Any) -> None:
            self._backend.close()

    @staticmethod
    def open_archive_reader(archive_path: Path) -> _ArchiveReader:
        """
        根据文件后缀返回 ZIP 或 7z 的统一读取器，供日志文本截取流程使用。
        :param archive_path: 压缩包路径
        :return: 读取器实例，支持上下文管理
        """
        return TicketLogArchiveUtil._ArchiveReader(archive_path)

    # ---------------- 保护检查 ----------------

    @staticmethod
    def ensure_prepare_budget(
        started_at: float,
        runtime_config: dict[str, Any],
        *,
        context: str = "日志",
    ) -> None:
        """
        检查解压阶段是否超过配置的最大耗时。
        :param started_at: 开始时间戳
        :param runtime_config: 运行保护配置
        :param context: 日志消息前缀
        """
        max_seconds = TicketLogArchiveUtil.config_int(runtime_config, "maxExtractSeconds", 300)
        if time.monotonic() - started_at > max_seconds:
            raise RuntimeError(f"{context}解压准备超过当前保护超时，请缩小日志包或调整日志拉取存储配置")

    @staticmethod
    def validate_extracted_resource_usage(
        target_dir: Path,
        runtime_config: dict[str, Any],
        *,
        context: str = "日志",
    ) -> None:
        """
        检查解压目录资源占用，避免异常日志包拖垮服务。
        :param target_dir: 解压目标目录
        :param runtime_config: 运行保护配置
        :param context: 日志消息前缀
        """
        max_file_count = TicketLogArchiveUtil.config_int(runtime_config, "maxExtractFileCount", 2000)
        max_total_bytes = TicketLogArchiveUtil.config_int(runtime_config, "maxExtractTotalBytes", 2147483648)
        file_count = 0
        total_bytes = 0
        for path in target_dir.rglob("*"):
            if not path.is_file():
                continue
            file_count += 1
            total_bytes += path.stat().st_size
            if file_count > max_file_count:
                raise RuntimeError(f"{context}解压文件数量超过当前保护阈值，请缩小日志包或调整日志拉取存储配置")
            if total_bytes > max_total_bytes:
                raise RuntimeError(f"{context}解压总大小超过当前保护阈值，请缩小日志包或调整日志拉取存储配置")

    # ---------------- 工具方法 ----------------

    @staticmethod
    def is_archive(path: Path) -> bool:
        """
        判断文件是否为支持递归处理的压缩文件。
        :param path: 文件路径
        """
        name = path.name.lower()
        return any(name.endswith(suffix) for suffix in COMPRESSED_SUFFIXES)

    @staticmethod
    def is_relative_to(path: Path, root: Path) -> bool:
        """
        判断路径是否位于指定根目录内。
        :param path: 待判断路径
        :param root: 根目录
        """
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def config_int(config: dict[str, Any], key: str, default: int) -> int:
        """
        从运行配置中安全读取正整数。
        :param config: 运行配置字典
        :param key: 配置键名
        :param default: 默认值
        """
        try:
            value = int(float(str(config.get(key, default)).strip()))
            return value if value > 0 else default
        except Exception:
            return default

    @staticmethod
    def config_bool(config: dict[str, Any], key: str, default: bool) -> bool:
        """
        从运行配置中安全读取布尔值。
        :param config: 运行配置字典
        :param key: 配置键名
        :param default: 默认值
        """
        value = config.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def build_source_file_name(archive_path: Path, default_name: str = "log.zip") -> str:
        """
        按真实压缩格式生成 source 目录中的文件名，避免 rar/7z 被误当成 zip。
        :param archive_path: 原始压缩包路径
        :param default_name: 没有匹配到已知后缀时的默认文件名
        """
        name = archive_path.name.lower()
        for suffix in (".tar.gz", ".tgz", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"):
            if name.endswith(suffix):
                return f"log{suffix}"
        return default_name
