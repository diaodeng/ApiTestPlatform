"""
工单日志内存/资源指标解析工具。

从拉取回来的 pos 日志文本中提取 ``Process cpu:..% mem:..%/..Mb threads:../..``
格式的进程资源监控数据，用于日志查看器的内存分析图表。
本工具只做纯解析，不访问数据库、不访问网络、不做任何副作用操作。
"""

from __future__ import annotations

import re
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


class TicketLogMemoryMetricsUtil:
    """
    工单日志资源监控数据解析工具，纯函数实现，供内存分析服务调用。
    """

    @classmethod
    def parse_file(cls, file_path: Path, relative_name: str) -> list[TicketLogMemoryMetricPoint]:
        """
        解析单个日志文件中的全部资源监控数据点。

        实现过程：
        1. 以二进制方式逐行读取，避免日志中混入非法字节导致解码失败；
        2. 用固定正则匹配 ``Process cpu/mem/threads`` 监控行；
        3. 时间解析失败的行直接跳过，不影响其他数据。

        :param file_path: 日志文件绝对路径
        :param relative_name: 展示用的相对日志路径
        :return: 当前文件解析出的数据点列表（未排序）
        """
        points: list[TicketLogMemoryMetricPoint] = []
        try:
            with file_path.open("rb") as source:
                for raw_line in source:
                    try:
                        line = raw_line.decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                    match = MEMORY_LOG_PATTERN.search(line)
                    if not match:
                        continue
                    try:
                        log_time = datetime.strptime(match.group("time"), "%Y-%m-%d %H:%M:%S,%f")
                    except ValueError:
                        continue
                    points.append(
                        TicketLogMemoryMetricPoint(
                            time=log_time,
                            cpu_percent=float(match.group("cpu")),
                            mem_percent=float(match.group("mem_pct")),
                            mem_mb=float(match.group("mem_mb")),
                            threads_active=int(match.group("threads_active")),
                            threads_max=int(match.group("threads_max")),
                            source_file=relative_name,
                        )
                    )
        except OSError:
            # 读取失败直接抛给上层服务，由服务统一记录日志并决定是否跳过
            raise
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

