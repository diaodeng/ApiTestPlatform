"""
工单日志内存分析子服务。

负责从已准备完成的日志解压目录中提取 ``Process cpu/mem/threads`` 资源监控数据，
供日志查看器的内存分析图表使用。文件解析逻辑下沉到
:mod:`modules.ticket.util.ticket_log_memory_metrics_util`，本服务只做目录定位、
文件筛选与业务编排。
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.entity.vo.ticket_log_pull_vo import (
    TicketLogMemoryMetricPointModel,
    TicketLogMemoryMetricsModel,
    TicketLogMemoryMetricsRequestModel,
)
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.util.ticket_log_memory_metrics_util import (
    TicketLogMemoryMetricPoint,
    TicketLogMemoryMetricsUtil,
)
from utils.log_util import logger

# 与 LogService.BASE_DIR 保持一致的日志根目录
_LOG_BASE_DIR = Path(__file__).resolve().parents[4] / "data" / "logs"

# 判定为归档/索引的文件后缀，这些文件不参与内存指标解析
_SKIP_SUFFIXES = {".zip", ".gz", ".tgz", ".tar", ".7z", ".rar", ".lineidx", ".png", ".jpg", ".pdf"}

# 内存分析默认最多解析的日志文件数量，防止误开超大目录导致扫描过久
_DEFAULT_MAX_FILE_COUNT = 200


class TicketLogMemoryMetricsService:
    """
    工单日志内存分析服务，提供资源监控数据提取与汇总能力。
    """

    @classmethod
    def collect_metrics(
        cls, request: TicketLogMemoryMetricsRequestModel, db: Session | None = None
    ) -> TicketLogMemoryMetricsModel:
        """
        提取指定日志拉取记录的资源监控数据点（非流式入口）。

        内部复用 :meth:`iter_collect_metrics_events` 的事件流，取最终结果返回，
        保证流式与非流式两条链路的解析逻辑完全一致。

        :param request: 内存分析请求参数
        :param db: 数据库会话，用于读取日志搜索资源保护配置
        :return: 资源监控数据与汇总信息
        """
        for event in cls.iter_collect_metrics_events(request, db):
            if event.get("type") == "result":
                return event.get("data")  # type: ignore[return-value]
            if event.get("type") == "error":
                raise RuntimeError(str(event.get("message") or "内存分析失败"))
        return cls._build_empty_model(int(request.ticket_id or 0), request.record_id, "内存分析未返回结果")

    @classmethod
    def iter_collect_metrics_events(
        cls, request: TicketLogMemoryMetricsRequestModel, db: Session | None = None
    ) -> Iterator[dict[str, Any]]:
        """
        以事件流方式提取资源监控数据，供流式接口边扫描边推送进度。

        事件格式：
        - ``{"type": "start", "fileCount": n, "totalBytes": b}``：开始扫描，声明文件数与总字节；
        - ``{"type": "progress", "file": 名称, "fileIndex": i, "fileCount": n,
          "percent": 整体百分比, "filePercent": 单文件百分比, "points": 已提取点数,
          "skippedFileCount": 跳过数}``：扫描进度；
        - ``{"type": "result", "data": 结果模型}``：最终结果；
        - ``{"type": "error", "message": 文案}``：失败原因。

        实现过程：
        1. 定位日志解压目录并筛选参与解析的日志文件（含数量保护）；
        2. 逐文件调用解析工具的生成器接口，边解析边换算整体百分比并产出进度事件；
        3. 全部文件解析完成后合并去重、降采样并构建汇总结果。

        :param request: 内存分析请求参数
        :param db: 数据库会话，用于读取日志搜索资源保护配置
        :return: 事件字典迭代器
        """
        started_at = time.monotonic()
        ticket_id = int(request.ticket_id or 0)
        record_id = request.record_id
        max_points = int(request.max_points or 2000)
        extract_dir = cls._extract_dir(ticket_id, record_id)
        logger.info(
            f"工单日志内存分析开始，ticket_id={ticket_id}，record_id={record_id}，"
            f"extract_dir={extract_dir}，max_points={max_points}"
        )
        if not extract_dir.exists() or not any(extract_dir.rglob("*")):
            logger.warning(
                f"工单日志内存分析未找到解压目录或目录为空，ticket_id={ticket_id}，"
                f"record_id={record_id}，extract_dir={extract_dir}"
            )
            yield {
                "type": "result",
                "data": cls._build_empty_model(
                    ticket_id, record_id, "日志尚未准备完成或目录为空，请先打开日志查看器完成准备"
                ),
            }
            return

        try:
            log_files = cls._collect_log_files(extract_dir, request, db)
        except RuntimeError as exc:
            logger.warning(
                f"工单日志内存分析文件数量超过保护阈值，ticket_id={ticket_id}，record_id={record_id}，错误：{exc}"
            )
            yield {"type": "error", "message": str(exc)}
            return

        total_bytes = sum(path.stat().st_size for path, _ in log_files)
        yield {
            "type": "start",
            "fileCount": len(log_files),
            "totalBytes": total_bytes,
            "maxPoints": max_points,
        }
        if not log_files:
            yield {
                "type": "result",
                "data": cls._build_empty_model(ticket_id, record_id, "日志目录中未找到可解析的日志文件"),
            }
            return

        point_lists: list[list[TicketLogMemoryMetricPoint]] = []
        skipped_files = 0
        processed_bytes = 0

        def build_progress_event(
            file_index: int, file_name: str, file_percent: float
        ) -> dict[str, Any]:
            """
            构建进度事件，换算整体百分比并汇总已提取的数据点数量。

            :param file_index: 当前文件序号（从 1 开始）
            :param file_name: 当前文件相对路径
            :param file_percent: 当前文件处理百分比（0~100）
            :return: 进度事件字典
            """
            percent = round(processed_bytes * 100 / total_bytes, 1) if total_bytes else 100.0
            return {
                "type": "progress",
                "file": file_name,
                "fileIndex": file_index,
                "fileCount": len(log_files),
                "percent": percent,
                "filePercent": file_percent,
                "points": sum(len(item) for item in point_lists),
                "skippedFileCount": skipped_files,
            }

        for index, (absolute_path, relative_name) in enumerate(log_files):
            file_size = absolute_path.stat().st_size
            file_points: list[TicketLogMemoryMetricPoint] = []
            try:
                for kind, payload in TicketLogMemoryMetricsUtil.iter_parse_file(absolute_path, relative_name):
                    if kind == "points":
                        file_points.extend(payload)  # type: ignore[arg-type]
                    else:
                        ratio = min(1.0, max(0.0, float(payload)))
                        yield build_progress_event(
                            index + 1, relative_name, round(ratio * 100, 1)
                        )
            except OSError as exc:
                skipped_files += 1
                logger.warning(f"内存分析跳过不可读日志文件，file={relative_name}，错误：{exc}")
            if file_points:
                point_lists.append(file_points)
            processed_bytes += file_size
            yield build_progress_event(index + 1, relative_name, 100.0)

        merged_points = TicketLogMemoryMetricsUtil.merge_points(point_lists, max_points)
        summary = TicketLogMemoryMetricsUtil.build_summary(merged_points)
        total_points = sum(len(item) for item in point_lists)
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            f"工单日志内存分析完成，ticket_id={ticket_id}，record_id={record_id}，"
            f"scan_file_count={len(log_files)}，skipped_file_count={skipped_files}，"
            f"total_points={total_points}，returned_points={len(merged_points)}，"
            f"truncated={total_points != len(merged_points)}，elapsed_ms={elapsed_ms}"
        )
        if not merged_points:
            yield {
                "type": "result",
                "data": cls._build_empty_model(
                    ticket_id, record_id, "日志中未找到 Process 资源监控数据（cpu/mem/threads）"
                ),
            }
            return

        yield {
            "type": "result",
            "data": TicketLogMemoryMetricsModel(
                ticket_id=ticket_id,
                record_id=record_id,
                total=len(merged_points),
                scan_file_count=len(log_files),
                skipped_file_count=skipped_files,
                truncated=total_points != len(merged_points),
                message=None,
                elapsed_ms=elapsed_ms,
                start_time=summary.get("start_time"),  # type: ignore[arg-type]
                end_time=summary.get("end_time"),  # type: ignore[arg-type]
                mem_mb_min=summary.get("mem_mb_min"),  # type: ignore[arg-type]
                mem_mb_max=summary.get("mem_mb_max"),  # type: ignore[arg-type]
                mem_percent_min=summary.get("mem_percent_min"),  # type: ignore[arg-type]
                mem_percent_max=summary.get("mem_percent_max"),  # type: ignore[arg-type]
                cpu_percent_min=summary.get("cpu_percent_min"),  # type: ignore[arg-type]
                cpu_percent_max=summary.get("cpu_percent_max"),  # type: ignore[arg-type]
                threads_active_min=summary.get("threads_active_min"),  # type: ignore[arg-type]
                threads_active_max=summary.get("threads_active_max"),  # type: ignore[arg-type]
                threads_max_max=summary.get("threads_max_max"),  # type: ignore[arg-type]
                points=[
                    TicketLogMemoryMetricPointModel(
                        time=point.time,
                        cpu_percent=point.cpu_percent,
                        mem_percent=point.mem_percent,
                        mem_mb=point.mem_mb,
                        threads_active=point.threads_active,
                        threads_max=point.threads_max,
                        source_file=point.source_file,
                    )
                    for point in merged_points
                ],
            ),
        }

    @classmethod
    def _build_empty_model(
        cls, ticket_id: int, record_id: int | None, message: str
    ) -> TicketLogMemoryMetricsModel:
        """
        构建空结果模型，用于目录不存在或没有可解析数据时的统一返回。

        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :param message: 提示信息
        :return: 空的内存分析结果模型
        """
        return TicketLogMemoryMetricsModel(
            ticket_id=ticket_id,
            record_id=record_id,
            total=0,
            scan_file_count=0,
            skipped_file_count=0,
            truncated=False,
            message=message,
        )

    @classmethod
    def _extract_dir(cls, ticket_id: int, record_id: int | None = None) -> Path:
        """
        获取工单日志解压目录，目录规则与日志查看器（LogService）保持一致。

        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID，为空时使用工单根目录
        :return: 解压目录路径
        """
        ticket_dir = _LOG_BASE_DIR / f"ticket_{ticket_id}"
        base_dir = ticket_dir / f"record_{record_id}" if record_id else ticket_dir
        return base_dir / "extract"

    @classmethod
    def _collect_log_files(
        cls, extract_dir: Path, request: TicketLogMemoryMetricsRequestModel, db: Session | None
    ) -> list[tuple[Path, str]]:
        """
        收集参与内存分析的日志文件，并按配置做数量保护。

        实现过程：
        1. 递归遍历解压目录，跳过归档、图片和索引文件；
        2. 指定文件范围时仅解析所选文件，未指定时解析全部候选文件；
        3. 候选文件数量超过保护阈值时直接报错，提示用户指定文件范围。

        :param extract_dir: 日志解压目录
        :param request: 内存分析请求参数
        :param db: 数据库会话，用于读取搜索资源保护配置
        :return: (绝对路径, 相对展示路径) 列表
        """
        max_file_count = cls._resolve_max_file_count(db)
        selected_files = [str(item or "").strip().replace("\\", "/").lstrip("/") for item in (request.files or [])]
        selected_files = [item for item in selected_files if item]

        candidates: list[tuple[Path, str]] = []
        for path in extract_dir.rglob("*"):
            if not path.is_file() or path.stat().st_size <= 0:
                continue
            if path.suffix.lower() in _SKIP_SUFFIXES:
                continue
            relative_name = path.relative_to(extract_dir).as_posix()
            if selected_files and relative_name not in selected_files:
                continue
            candidates.append((path, relative_name))

        # 未指定文件范围时限制解析文件数量，避免超大目录扫描过久
        if not selected_files and len(candidates) > max_file_count:
            raise RuntimeError(
                f"日志文件数量（{len(candidates)}）超过内存分析保护阈值（{max_file_count}），请指定文件范围后重试"
            )
        return sorted(candidates, key=lambda item: item[1])

    @classmethod
    def _resolve_max_file_count(cls, db: Session | None) -> int:
        """
        解析内存分析允许扫描的最大文件数量。

        优先使用日志拉取存储配置中的 ``maxSearchFileCount``，配置不可用时使用内置默认值。

        :param db: 数据库会话
        :return: 最大扫描文件数量
        """
        if db is None:
            return _DEFAULT_MAX_FILE_COUNT
        try:
            config = TicketLogPullService.get_storage_config_dict(db)
        except Exception as exc:
            logger.warning(f"读取日志搜索资源保护配置失败，使用内置默认值，错误：{exc}")
            return _DEFAULT_MAX_FILE_COUNT
        try:
            return max(1, int(config.get("maxSearchFileCount") or _DEFAULT_MAX_FILE_COUNT))
        except (TypeError, ValueError):
            return _DEFAULT_MAX_FILE_COUNT
