"""
工单日志内存/资源指标解析工具。

从拉取回来的 pos 日志文本中提取 ``Process cpu:..% mem:..%/..Mb threads:../..``
格式的进程资源监控数据，用于日志查看器的内存分析图表。
本工具只做纯解析，不访问数据库、不访问网络、不做任何副作用操作。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# 匹配格式：
# 2026-05-31 23:59:42,527 ... Process cpu:0.00%, mem:4.65%/375.02Mb, threads:61/46
MEMORY_LOG_PATTERN = re.compile(
    r"(?P<time>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}).*?"
    r"Process cpu:(?P<cpu>[\d.]+)%.*?"
    r"mem:(?P<mem_pct>[\d.]+)%/(?P<mem_mb>[\d.]+)Mb.*?"
    r"threads:(?P<threads_active>\d+)/(?P<threads_max>\d+)"
)

# 监控行固定包含的 ASCII 字节锚点（"Process cpu"），用于正则匹配前快速过滤无关行；
# 监控格式与正则强相关，若正则调整必须同步更新此锚点，否则会导致漏解析
_MEMORY_LOG_ANCHOR = b"Process cpu"


@dataclass(frozen=True)
class TicketLogMemoryMetricPoint:
    """
    单条进程资源监控数据点。

    :param time: 日志时间戳
    :param cpu_percent: 进程 CPU 占用百分比
    :param mem_percent: 进程内存占用百分比
    :param mem_mb: 进程内存占用量（Mb）
    :param threads_active: 当前活跃线程数
    :param threads_max: 线程数上限
    :param source_file: 数据来源的相对日志文件路径
    """

    time: datetime
    cpu_percent: float
    mem_percent: float
    mem_mb: float
    threads_active: int
    threads_max: int
    source_file: str
    # 命中行号（1 开始），用于前端曲线点点击后直接跳转日志上下文
    line: int = 0
    # naive 本地时间的 epoch 秒（日志无时区信息，随服务器时区），供前端时间轴与联动匹配
    epoch: float = 0.0


class TicketLogMemoryMetricsUtil:
    """
    工单日志资源监控数据解析工具，纯函数实现，供内存分析服务调用。
    """

    @classmethod
    def iter_parse_file(
        cls, file_path: Path, relative_name: str, progress_interval_lines: int = 2000
    ) -> Iterator[tuple[str, object]]:
        """
        以生成器方式解析单个日志文件，支持流式产出数据点与进度信号。

        实现过程：
        1. 以二进制方式逐行读取，避免日志中混入非法字节导致解码失败；
        2. 用固定正则匹配 ``Process cpu/mem/threads`` 监控行；
        3. 每 progress_interval_lines 行对外产出一次 ``("progress", 已处理比例)`` 进度信号，
            并把攒下的数据点按 ``("points", 批次列表)`` 先行产出，
            让上层服务可以在大文件解析过程中持续向外推送进度。

        :param file_path: 日志文件绝对路径
        :param relative_name: 展示用的相对日志路径
        :param progress_interval_lines: 进度信号间隔行数
        :return: 迭代器，元素为 ("points", 批次数据点列表) 或 ("progress", 0~1 的处理比例)
        """
        file_size = file_path.stat().st_size
        batch: list[TicketLogMemoryMetricPoint] = []
        line_no = 0
        with file_path.open("rb") as source:
            for raw_line in source:
                line_no += 1
                # 快速预过滤：只有包含 ASCII 锚点的行才可能命中监控正则，
                # 其余行直接跳过解码与正则匹配，大幅降低大文件逐行扫描的 CPU 开销
                if _MEMORY_LOG_ANCHOR not in raw_line:
                    match = None
                else:
                    try:
                        line = raw_line.decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                    match = MEMORY_LOG_PATTERN.search(line)
                if match:
                    try:
                        log_time = datetime.strptime(match.group("time"), "%Y-%m-%d %H:%M:%S,%f")
                    except ValueError:
                        log_time = None
                    if log_time is not None:
                        batch.append(
                            TicketLogMemoryMetricPoint(
                                time=log_time,
                                cpu_percent=float(match.group("cpu")),
                                mem_percent=float(match.group("mem_pct")),
                                mem_mb=float(match.group("mem_mb")),
                                threads_active=int(match.group("threads_active")),
                                threads_max=int(match.group("threads_max")),
                                source_file=relative_name,
                                line=line_no,
                                epoch=log_time.timestamp(),
                            )
                        )
                if progress_interval_lines > 0 and line_no % progress_interval_lines == 0:
                    if batch:
                        yield "points", batch
                        batch = []
                    ratio = min(1.0, source.tell() / file_size) if file_size else 1.0
                    yield "progress", ratio
        if batch:
            yield "points", batch
        yield "progress", 1.0

    @classmethod
    def parse_hit_line(
        cls, content: str, relative_name: str, line_no: int = 0
    ) -> TicketLogMemoryMetricPoint | None:
        """
        解析单条搜索命中行，提取资源监控数据点。

        供基于日志搜索管道（rg/Python 降级）的链路复用：
        命中行已由搜索层过滤出包含监控关键字的行，这里再做结构化解析。

        解析策略：正则不匹配或时间戳非法时返回 None（由调用方计入 skipped），
        绝不抛异常中断整体分析流程。

        :param content: 命中行文本内容
        :param relative_name: 展示用的相对日志文件路径
        :param line_no: 命中行号（1 开始），用于前端曲线点点击跳转日志上下文
        :return: 解析成功返回数据点，失败返回 None
        """
        match = MEMORY_LOG_PATTERN.search(str(content or ""))
        if not match:
            return None
        try:
            log_time = datetime.strptime(match.group("time"), "%Y-%m-%d %H:%M:%S,%f")
        except ValueError:
            return None
        return TicketLogMemoryMetricPoint(
            time=log_time,
            cpu_percent=float(match.group("cpu")),
            mem_percent=float(match.group("mem_pct")),
            mem_mb=float(match.group("mem_mb")),
            threads_active=int(match.group("threads_active")),
            threads_max=int(match.group("threads_max")),
            source_file=relative_name,
            line=int(line_no or 0),
            epoch=log_time.timestamp(),
        )

    @classmethod
    def parse_file(cls, file_path: Path, relative_name: str) -> list[TicketLogMemoryMetricPoint]:
        """
        解析单个日志文件中的全部资源监控数据点。

        复用 :meth:`iter_parse_file` 的解析逻辑，一次性收集全部数据点，
        供非流式调用方使用。

        :param file_path: 日志文件绝对路径
        :param relative_name: 展示用的相对日志路径
        :return: 当前文件解析出的数据点列表（未排序）
        """
        points: list[TicketLogMemoryMetricPoint] = []
        for kind, payload in cls.iter_parse_file(file_path, relative_name):
            if kind == "points":
                points.extend(payload)  # type: ignore[arg-type]
        return points

    @classmethod
    def merge_points(
        cls, point_lists: list[list[TicketLogMemoryMetricPoint]], max_points: int
    ) -> list[TicketLogMemoryMetricPoint]:
        """
        合并多个文件的数据点，按时间排序、去重并做降采样。

        实现过程：
        1. 展平所有文件的数据点并按时间升序排序；
        2. 同一时间戳仅保留第一条，避免轮转文件重叠导致曲线抖动；
        3. 当总点数超过 max_points 时按等距步长抽样，保证首尾数据点始终保留，
            让图表可以覆盖完整时间范围。

        :param point_lists: 每个日志文件解析出的数据点列表
        :param max_points: 返回数据点上限
        :return: 排序去重并限流后的数据点列表
        """
        merged: list[TicketLogMemoryMetricPoint] = []
        seen_times: set[datetime] = set()
        for points in point_lists:
            for point in points:
                if point.time in seen_times:
                    continue
                seen_times.add(point.time)
                merged.append(point)
        merged.sort(key=lambda item: item.time)

        total = len(merged)
        if max_points <= 0 or total <= max_points:
            return merged
        # 等距抽样：按均匀索引取点，保证首尾数据点始终保留且不超过上限
        if max_points == 1:
            return [merged[0]]
        indices = sorted(
            {round(index * (total - 1) / (max_points - 1)) for index in range(max_points)}
        )
        return [merged[index] for index in indices]

    @classmethod
    def build_summary(cls, points: list[TicketLogMemoryMetricPoint]) -> dict[str, object]:
        """
        基于数据点构建汇总信息。

        :param points: 已排序去重的数据点
        :return: 包含时间范围、内存/CPU/线程极值的字典
        """
        if not points:
            return {}
        mem_values = [point.mem_mb for point in points]
        cpu_values = [point.cpu_percent for point in points]
        mem_pct_values = [point.mem_percent for point in points]
        threads_active_values = [point.threads_active for point in points]
        threads_max_values = [point.threads_max for point in points]
        return {
            "start_time": points[0].time,
            "end_time": points[-1].time,
            "mem_mb_min": min(mem_values),
            "mem_mb_max": max(mem_values),
            "mem_percent_min": min(mem_pct_values),
            "mem_percent_max": max(mem_pct_values),
            "cpu_percent_min": min(cpu_values),
            "cpu_percent_max": max(cpu_values),
            "threads_active_min": min(threads_active_values),
            "threads_active_max": max(threads_active_values),
            "threads_max_max": max(threads_max_values),
        }

