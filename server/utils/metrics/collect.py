"""按固定低基数标签采集并推送进程、容器和任务指标。

采集线程支持多个推送通道（profile）：每个启用通道有独立的标签、间隔、
批次与扩展指标开关。通道配置由运行时服务（modules 层）周期注入，
线程本身不访问数据库；采集或推送的任何异常都被就地捕获，绝不影响主业务。
"""

from __future__ import annotations

import os
import threading
import time

import httpx
from loguru import logger


class CollectorProfileSnapshot:
    """单个推送通道的生效参数快照，由运行时服务从数据库配置构建。"""

    def __init__(
        self,
        profile_id: int,
        push_url: str,
        auth_user: str = "",
        auth_password: str = "",
        job_label: str = "QTR",
        instance_label: str = "TEST_ENV",
        machine_label: str = "",
        interval_seconds: int = 5,
        batch_size: int = 100,
        timeout_seconds: int = 10,
        extended_enabled: bool = False,
        revision: int = 0,
    ):
        self.profile_id = profile_id
        self.push_url = push_url
        self.auth_user = auth_user
        self.auth_password = auth_password
        self.job_label = job_label or "QTR"
        self.instance_label = instance_label or "TEST_ENV"
        self.machine_label = machine_label
        self.interval_seconds = max(1, int(interval_seconds or 5))
        self.batch_size = max(1, int(batch_size or 100))
        self.timeout_seconds = max(1, int(timeout_seconds or 10))
        self.extended_enabled = bool(extended_enabled)
        self.revision = revision

    def identity(self) -> tuple:
        """返回用于热生效比对的配置指纹。"""
        return (
            self.profile_id,
            self.push_url,
            self.auth_user,
            self.auth_password,
            self.job_label,
            self.instance_label,
            self.machine_label,
            self.interval_seconds,
            self.batch_size,
            self.timeout_seconds,
            self.extended_enabled,
            self.revision,
        )


class PushDataToServer(threading.Thread):
    """将当前进程资源指标按通道批量推送到 VictoriaMetrics/vmagent。

    线程每秒采集一次本机指标，按每个启用通道攒批推送。通道列表由
    MetricsCollectorRuntimeService 通过 replace_profiles 周期刷新，
    配置变化即热生效；推送结果通过 result_listener 回调交给运行时服务落库。
    """

    # 采集循环的固定节拍：每秒采集一次本机指标。
    TICK_SECONDS = 1

    def __init__(self, role: str | None = None):
        super().__init__(daemon=True)
        self.role = role or os.environ.get("QTR_METRICS_ROLE", "api")
        self.stopped = False
        self.group = os.environ.get("SYM_GROUP", "stable")
        self.push_failures = 0
        # 测试兼容：直接设置 extended_enabled 时按旧语义附加 role 标签。
        self.extended_enabled = False
        # 推送结果回调：签名 (profile_id, success, message)，由运行时服务注入。
        self.result_listener = None

        # 平台相关采集器延迟构建，构建失败时对应指标跳过采集。
        self._collectors_ready = False
        self.cpu_info = None
        self.mem_info = None
        self.process_info = None
        self.cgroup_memory_info = None
        self.task_observer = None

        # 按通道（profile_id）持有各自的待推送样本与上次推送时间。
        self._profiles: list[CollectorProfileSnapshot] = []
        self._profiles_lock = threading.Lock()
        self._channel_buffers: dict[int, list[str]] = {}
        self._channel_last_push: dict[int, float] = {}

    # ------------------------------------------------------------------
    # 采集器构建
    # ------------------------------------------------------------------

    def _ensure_collectors(self):
        """延迟构建平台相关采集器，失败只跳过采集，不影响线程存活。"""
        if self._collectors_ready:
            return
        try:
            from .container import CgroupCPU, MemoryCollector
            from .process import CgroupMemoryCollector, ProcessCollector
            from .task_memory import get_task_memory_observer

            self.cpu_info = CgroupCPU()
            self.mem_info = MemoryCollector()
            self.process_info = ProcessCollector()
            self.cgroup_memory_info = CgroupMemoryCollector()
            self.task_observer = get_task_memory_observer(self.role)
            self._collectors_ready = True
            logger.info(f"指标采集器初始化成功: role={self.role}")
        except Exception as exc:
            logger.warning(f"指标采集器初始化失败，本轮跳过采集: role={self.role}, error={exc}")

    # ------------------------------------------------------------------
    # 通道配置热生效
    # ------------------------------------------------------------------

    def replace_profiles(self, profiles: list[CollectorProfileSnapshot]):
        """用最新通道配置替换当前列表，并清理已消失通道的缓冲。"""
        with self._profiles_lock:
            new_ids = {profile.profile_id for profile in profiles}
            old_ids = set(self._channel_buffers)
            previous = {profile.profile_id: profile for profile in self._profiles}
            self._profiles = list(profiles)
            for stale_id in old_ids - new_ids:
                self._channel_buffers.pop(stale_id, None)
                self._channel_last_push.pop(stale_id, None)
        for profile in profiles:
            old = previous.get(profile.profile_id)
            if old is None:
                logger.info(
                    f"采集通道启动: role={self.role}, profileId={profile.profile_id}, "
                    f"url={profile.push_url}, interval={profile.interval_seconds}s"
                )
            elif old.identity() != profile.identity():
                logger.info(
                    f"采集通道配置热生效: role={self.role}, profileId={profile.profile_id}, "
                    f"revision={old.revision}->{profile.revision}"
                )

    def get_profiles(self) -> list[CollectorProfileSnapshot]:
        """返回当前生效的通道配置快照。"""
        with self._profiles_lock:
            return list(self._profiles)

    # ------------------------------------------------------------------
    # 线程主循环
    # ------------------------------------------------------------------

    def run(self):
        """主循环：每秒采集一次，异常就地捕获，退出前尽力推送剩余样本。"""
        logger.info(f"开始采集信息: role={self.role}")
        while not self.stopped:
            try:
                self._collect_tick()
            except Exception as exc:
                self.push_failures += 1
                logger.exception(f"指标采集失败: role={self.role}, failures={self.push_failures}, error={exc}")
            self._interruptible_sleep(self.TICK_SECONDS)
        self._flush_remaining()

    def _interruptible_sleep(self, seconds: float):
        """可被 stop 及时打断的休眠。"""
        deadline = time.time() + seconds
        while not self.stopped and time.time() < deadline:
            time.sleep(min(0.2, max(0.0, deadline - time.time())))

    def stop(self):
        """请求停止采集线程，剩余样本由主循环退出前尽力推送。"""
        self.stopped = True

    def _flush_remaining(self):
        """退出前把各通道剩余样本尽力推完，异常只记日志。"""
        for profile in self.get_profiles():
            buffer = self._channel_buffers.get(profile.profile_id)
            if not buffer:
                continue
            try:
                self._push(profile, buffer)
                self._channel_buffers[profile.profile_id] = []
            except Exception as exc:
                logger.warning(f"退出前推送剩余指标失败: role={self.role}, profileId={profile.profile_id}, error={exc}")

    # ------------------------------------------------------------------
    # 指标采集与按通道分发
    # ------------------------------------------------------------------

    def _collect_tick(self):
        """采集一次本机指标，并为每个启用通道格式化、攒批、按需推送。"""
        self._ensure_collectors()
        profiles = self.get_profiles()
        if not profiles:
            return
        raw = self._collect_raw(profiles)
        if not raw:
            return
        for profile in profiles:
            lines = self._format_samples(raw, profile)
            if not lines:
                continue
            buffer = self._channel_buffers.setdefault(profile.profile_id, [])
            buffer.extend(lines)
            self._maybe_push(profile)

    def _collect_raw(self, profiles: list[CollectorProfileSnapshot]) -> dict:
        """采集原始指标数据；只有存在开启扩展指标的通道时才采集扩展数据。

        指标按归属层级分为两类：
        - machine/cgroup 是宿主机或容器级数据，同一台机器上所有进程读到同一份，
          样本不允许携带 role 标签，避免同一数据被拆成 N 条序列或聚合翻倍；
        - process/task 是当前进程独有数据，必须携带 role 区分不同进程。
        """
        if self.cpu_info is None or self.mem_info is None:
            return {}
        machine_data = {}
        machine_data.update(self.cpu_info.cpu_status())
        machine_data.update(self.mem_info.snapshot())
        raw: dict = {"machine": [(key, value) for key, value in machine_data.items() if key != "mode"]}

        raw["process"] = None
        raw["cgroup"] = None
        raw["task"] = []
        if not any(profile.extended_enabled for profile in profiles):
            return raw
        try:
            if self.process_info is not None:
                raw["process"] = self.process_info.snapshot().as_dict()
            if self.cgroup_memory_info is not None:
                raw["cgroup"] = self.cgroup_memory_info.snapshot()
            if self.task_observer is not None:
                raw["task"] = self.task_observer.metrics()
        except Exception as exc:
            # 扩展指标失败不影响基础机器指标推送。
            logger.warning(f"扩展指标采集失败: role={self.role}, error={exc}")
        return raw

    def _format_samples(self, raw: dict, profile: CollectorProfileSnapshot) -> list[str]:
        """按通道的标签配置与扩展开关把原始数据格式化为样本行。

        machine 与 cgroup 指标是机器/容器级共享数据，不带 role 标签；
        process 与 task 指标是进程级数据，带 role 标签区分进程。
        """
        lines: list[str] = []
        for key, value in raw.get("machine") or []:
            lines.append(self._append_metric(key, value, profile, with_role=False))
        if not profile.extended_enabled:
            return lines
        for key, value in (raw.get("cgroup") or {}).items():
            lines.append(self._append_metric(key, value, profile, with_role=False))
        for key, value in (raw.get("process") or {}).items():
            lines.append(self._append_metric(f"qtr_process_{key}", value, profile, with_role=True))
        for name, extra, value in raw.get("task") or []:
            lines.append(self._append_metric(name, value, profile, extra, with_role=True))
        return lines

    # ------------------------------------------------------------------
    # 推送
    # ------------------------------------------------------------------

    def _maybe_push(self, profile: CollectorProfileSnapshot):
        """按通道的批次与间隔边界决定是否推送。"""
        buffer = self._channel_buffers.get(profile.profile_id, [])
        now = time.time()
        if profile.profile_id not in self._channel_last_push:
            self._channel_last_push[profile.profile_id] = now
        last = self._channel_last_push[profile.profile_id]
        if len(buffer) >= profile.batch_size or now - last >= profile.interval_seconds:
            self._push(profile, buffer)
            self._channel_buffers[profile.profile_id] = []
            self._channel_last_push[profile.profile_id] = now

    def _push(self, profile: CollectorProfileSnapshot, data_lines: list[str]):
        """按通道配置推送一批样本，失败记录日志并回写状态。"""
        if not profile.push_url or not data_lines:
            return
        headers = {"Content-Type": "text/plain"}
        metrics_data = "\n".join(data_lines)
        try:
            response = httpx.post(
                profile.push_url,
                content=metrics_data,
                auth=(profile.auth_user, profile.auth_password) if profile.auth_user else None,
                headers=headers,
                timeout=profile.timeout_seconds,
                verify=False,
            )
            if response.status_code != 204:
                self.push_failures += 1
                logger.warning(
                    f"指标推送失败: role={self.role}, profileId={profile.profile_id}, "
                    f"status={response.status_code}, samples={len(data_lines)}, "
                    f"bytes={len(metrics_data.encode('utf-8'))}, failures={self.push_failures}, "
                    f"response={response.text[:200]!r}"
                )
                self._notify_push_result(profile.profile_id, False, f"HTTP {response.status_code}")
            else:
                self._notify_push_result(profile.profile_id, True)
        except Exception as exc:
            self.push_failures += 1
            logger.exception(
                f"指标推送异常: role={self.role}, profileId={profile.profile_id}, "
                f"failures={self.push_failures}, error={exc}"
            )
            self._notify_push_result(profile.profile_id, False, str(exc)[:200])

    def _notify_push_result(self, profile_id: int, success: bool, message: str = ""):
        """通过回调把推送结果交给运行时服务落库，回调异常不影响采集循环。"""
        listener = getattr(self, "result_listener", None)
        if listener is None:
            return
        try:
            listener(profile_id, success, message)
        except Exception as exc:
            logger.debug(f"推送结果回调异常: profileId={profile_id}, error={exc}")

    # ------------------------------------------------------------------
    # 样本格式化
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_label_value(value: object) -> str:
        """按 Prometheus 文本协议转义标签值。"""
        return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

    def _labels(
        self,
        sensor: str,
        extra: dict[str, str] | None = None,
        profile: CollectorProfileSnapshot | None = None,
        with_role: bool = True,
    ) -> str:
        """构造单个通道的固定低基数标签串。

        通道未指定时回退到历史默认标签，保持旧行为兼容。
        with_role=False 用于机器/容器级指标（cpu、memory、cgroup）：这些数据
        同一台机器上所有进程采集结果相同，附加 role 会把一份数据拆成多条
        序列，导致面板聚合翻倍；进程级指标（rss、任务）必须带 role 区分。
        """
        if profile is not None:
            labels = {
                "job": profile.job_label,
                "instance": profile.instance_label,
                "machine": profile.machine_label or getattr(self, "group", "stable"),
            }
            if profile.extended_enabled and with_role:
                labels["role"] = self.role
        else:
            labels = {
                "job": "QTR",
                "instance": "TEST_ENV",
                "machine": getattr(self, "group", "stable"),
            }
            if self.extended_enabled and with_role:
                labels["role"] = self.role
        labels["sensor"] = sensor
        if extra:
            labels.update(extra)
        return ",".join(f'{key}="{self._escape_label_value(value)}"' for key, value in labels.items())

    def _append_metric(
        self,
        name: str,
        value: int | float,
        profile: CollectorProfileSnapshot | None = None,
        extra: dict[str, str] | None = None,
        with_role: bool = True,
    ) -> str:
        """格式化一个纯数值 Prometheus 样本行。"""
        timestamp = int(time.time() * 1000)
        label_str = self._labels(name, extra, profile, with_role)
        return f"{name}{{{label_str}}} {value} {timestamp}"
