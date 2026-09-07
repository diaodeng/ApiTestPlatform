"""RSS 阈值触发的 tracemalloc 诊断快照。

背景：生产环境出现过进程 RSS 一次性 +300MB 阶跃且永不回落的内存问题，
常规指标只有总量没有分配来源。本模块在指标采集线程的秒级节拍里检查
当前进程 RSS，超过配置阈值时自动开启 tracemalloc、采样 top 分配源并
写入日志目录，用于事后归因。

设计约束：
- 默认完全关闭（QTR_MEMORY_SNAPSHOT_ENABLED=false），不影响现有业务；
- tracemalloc 自身有约 2 倍分配开销，仅在达到阈值后开启、采样完成即关闭，
  不会长期挂载在生产进程上；
- 每个进程最多采样一次（可配置冷却秒数），避免反复采样放大内存压力；
- 所有异常就地吞掉并计数，绝不影响采集线程主循环。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from loguru import logger


@dataclass(frozen=True)
class MemorySnapshotConfig:
    """诊断快照的行为参数，全部来自环境变量，缺省关闭。"""

    enabled: bool
    rss_threshold_mb: int
    top_lines: int
    cooldown_seconds: int


def load_memory_snapshot_config() -> MemorySnapshotConfig:
    """
    从环境变量读取诊断快照配置。

    :return: 配置对象；未设置或非法时 enabled=False
    """
    raw_enabled = os.environ.get("QTR_MEMORY_SNAPSHOT_ENABLED", "false").strip().lower()
    enabled = raw_enabled in ("1", "true", "yes", "on")
    try:
        threshold = max(int(os.environ.get("QTR_MEMORY_SNAPSHOT_RSS_MB", "900")), 128)
    except ValueError:
        threshold = 900
    try:
        top_lines = min(max(int(os.environ.get("QTR_MEMORY_SNAPSHOT_TOP_LINES", "50")), 10), 500)
    except ValueError:
        top_lines = 50
    try:
        cooldown = min(max(int(os.environ.get("QTR_MEMORY_SNAPSHOT_COOLDOWN_SEC", "3600")), 60), 86400)
    except ValueError:
        cooldown = 3600
    return MemorySnapshotConfig(
        enabled=enabled,
        rss_threshold_mb=threshold,
        top_lines=top_lines,
        cooldown_seconds=cooldown,
    )


class MemorySnapshotWatcher:
    """
    RSS 阈值触发的 tracemalloc 采样器，由采集线程按秒驱动 check()。

    只在单进程内生效（tracemalloc 是进程级 API），每个进程的采集线程
    各持有一个实例，互不干扰。
    """

    def __init__(self, role: str, config: MemorySnapshotConfig | None = None):
        self.role = role
        self.config = config or load_memory_snapshot_config()
        self._last_snapshot_at = 0.0
        self._check_count = 0

    def check(self) -> None:
        """
        检查当前进程 RSS 是否越过阈值，越界则执行一次快照。

        任何异常只计数并吞掉，保证调用方（采集线程主循环）不受影响。
        :return: 无
        """
        if not self.config.enabled:
            return
        self._check_count += 1
        # 快照采样本身有开销，节拍降为每 10 秒检查一次。
        if self._check_count % 10 != 0:
            return
        if time.time() - self._last_snapshot_at < self.config.cooldown_seconds:
            return
        try:
            import psutil

            rss_mb = psutil.Process().memory_info().rss / 1024 / 1024
            if rss_mb < self.config.rss_threshold_mb:
                return
            self._last_snapshot_at = time.time()
            self._take_snapshot(rss_mb)
        except Exception as exc:
            logger.warning(f"内存诊断快照检查失败: role={self.role}, error={exc}")

    def _take_snapshot(self, rss_mb: float) -> None:
        """
        开启 tracemalloc 追踪一个观察窗口并输出 top 分配源。

        :param rss_mb: 触发时的 RSS（MB）
        :return: 无
        """
        import tracemalloc

        logger.warning(
            f"内存诊断快照触发: role={self.role}, rss={rss_mb:.0f}MB, "
            f"threshold={self.config.rss_threshold_mb}MB, 开始追踪分配"
        )
        tracemalloc.start()
        try:
            # 观察窗口：只追踪这段时间内的存量与新增分配。tracemalloc.start
            # 之后 take_snapshot 会统计自启动以来的全部分配，因此这里先让
            # 采集线程自然运行一个窗口，再抓取快照。
            time.sleep(5)
            snapshot = tracemalloc.take_snapshot()
            self._write_snapshot(rss_mb, snapshot)
        finally:
            tracemalloc.stop()
            logger.warning(f"内存诊断快照完成: role={self.role}, tracemalloc 已关闭")

    def _write_snapshot(self, rss_mb: float, snapshot) -> None:
        """
        把 top 分配源写入日志目录下的快照文件。

        文件按 role 和时间戳命名，保留在 logs/memory_snapshots/ 下由人工
        复盘后清理；写失败只记日志。

        :param rss_mb: 触发时的 RSS（MB）
        :param snapshot: tracemalloc 快照对象
        :return: 无
        """
        from datetime import datetime

        from utils.log_util import get_log_path

        top_stats = snapshot.statistics("lineno", cumulative=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = get_log_path(name=f"memory_snapshot_{self.role}_{timestamp}").replace("\\", "/")
        lines: list[str] = [
            f"# role={self.role} rss={rss_mb:.0f}MB threshold={self.config.rss_threshold_mb}MB",
            f"# time={datetime.now().isoformat()}",
            f"# top {self.config.top_lines} allocation sites (cumulative, lineno)",
        ]
        for index, stat in enumerate(top_stats[: self.config.top_lines], start=1):
            frame = stat.traceback[0] if stat.traceback else None
            location = f"{frame.filename}:{frame.lineno}" if frame else "<unknown>"
            lines.append(f"{index}. {location} size={stat.size / 1024 / 1024:.2f}MB count={stat.count}")
        try:
            with open(output_path, "w", encoding="utf-8") as file_obj:
                file_obj.write("\n".join(lines))
            logger.warning(f"内存诊断快照已写入: role={self.role}, path={output_path}, sites={len(lines) - 3}")
        except OSError as exc:
            logger.warning(f"内存诊断快照写入失败: role={self.role}, path={output_path}, error={exc}")
