"""资源采集服务运行时管理：桥接采集线程与数据库配置。

职责边界：
- 周期从数据库加载启用的采集服务配置，转换为线程可用的参数快照注入采集线程；
- 把采集线程的推送结果回写回配置表（独立数据库会话，异常隔离）；
- 汇总各进程角色（api/celery_worker/celery_beat）的运行状态供接口查询。

采集线程（utils/metrics/collect.py）本身不访问数据库，依赖本服务注入配置。
"""

from __future__ import annotations

import os
import threading
import time

from loguru import logger
from sqlalchemy.orm import Session

from config.database import SessionLocal
from modules.metrics.entity.do.metrics_do import MetricsCollectorProfile
from modules.metrics.service.metrics_collector_config_service import MetricsCollectorConfigService
from utils.metrics.collect import CollectorProfileSnapshot, PushDataToServer

# 各进程角色对应的采集线程引用，键为进程角色名。
_threads: dict[str, PushDataToServer] = {}
_threads_lock = threading.Lock()


class MetricsCollectorRuntimeService:
    """采集线程运行时管理，进程内单例使用。"""

    # 轮询数据库配置的间隔秒数：配置启停与修改最迟在此时间内热生效。
    PROFILE_POLL_SECONDS = 5

    @classmethod
    def start(cls, role: str) -> PushDataToServer | None:
        """为当前进程启动采集线程；已有线程时直接复用，返回 None 表示跳过。

        启动时注入配置加载回调，采集线程主循环按固定间隔（PROFILE_REFRESH_SECONDS）
        自行轮询数据库配置并热生效，不再依赖外部周期任务驱动。
        """
        with _threads_lock:
            existing = _threads.get(role)
            if existing and existing.is_alive():
                return None
            thread = PushDataToServer(role=role)
            thread.result_listener = cls._on_push_result
            thread.profile_provider = lambda: cls.load_active_profiles(role)
            _threads[role] = thread
            thread.start()
        logger.info(f"指标采集线程已启动: role={role}")
        return thread

    @classmethod
    def stop_all(cls):
        """停止当前进程的全部采集线程，供应用关闭钩子调用。"""
        with _threads_lock:
            threads = list(_threads.values())
            _threads.clear()
        for thread in threads:
            try:
                thread.stop()
            except Exception as exc:
                logger.warning(f"停止指标采集线程失败: role={thread.role}, error={exc}")

    @classmethod
    def get_thread(cls, role: str) -> PushDataToServer | None:
        """返回指定角色的采集线程（可能不存在）。"""
        with _threads_lock:
            return _threads.get(role)

    # ------------------------------------------------------------------
    # 配置轮询与线程注入
    # ------------------------------------------------------------------

    @classmethod
    def load_active_profiles(cls, role: str, db: Session | None = None) -> list[CollectorProfileSnapshot]:
        """加载启用的采集服务配置并转换为线程参数快照。

        默认使用独立数据库会话；传入 db 时使用该会话（测试或调用方已持有
        会话的场景）。数据库异常时向上抛出，由调用方决定保留或清空通道：
        采集线程捕获异常后保留现有通道继续推送，不会误把加载失败当作无通道。

        轮询顺带把内存诊断快照的可视化配置热注入当前线程（同一会话，
        失败只记日志，不影响通道加载）。
        """
        try:
            if db is not None:
                cls._refresh_memory_snapshot_config(db)
                return [cls._to_snapshot(row) for row in MetricsCollectorConfigService.load_push_profiles(db)]
            with SessionLocal() as session:
                cls._refresh_memory_snapshot_config(session)
                return [cls._to_snapshot(row) for row in MetricsCollectorConfigService.load_push_profiles(session)]
        except Exception as exc:
            logger.warning(f"加载采集服务配置失败: role={role}, error={exc}")
            raise

    @staticmethod
    def _refresh_memory_snapshot_config(db: Session) -> None:
        """把数据库中的诊断快照配置热注入当前进程的采集线程。

        异常只记日志，绝不影响采集通道加载与主业务。
        """
        try:
            from modules.metrics.service.memory_snapshot_config_service import MemorySnapshotConfigService

            thread = cls.get_thread_any()
            if thread is None:
                return
            config = MemorySnapshotConfigService.load_runtime_config(db)
            thread.memory_snapshot_watcher.apply_config(config)
        except Exception as exc:
            logger.debug(f"刷新内存诊断快照配置失败: error={exc}")

    @classmethod
    def get_thread_any(cls) -> PushDataToServer | None:
        """返回当前进程任意一个采集线程（单进程只启动一个角色）。"""
        with _threads_lock:
            for thread in _threads.values():
                if thread.is_alive():
                    return thread
            return None

    @classmethod
    def poll_and_apply(cls, role: str):
        """手动触发一次配置轮询并注入线程，供测试或管理接口使用。"""
        thread = cls.get_thread(role)
        if not thread:
            return
        profiles = cls.load_active_profiles(role)
        thread.replace_profiles(profiles)

    @staticmethod
    def _to_snapshot(row: MetricsCollectorProfile) -> CollectorProfileSnapshot:
        """把配置 ORM 实体转换为线程参数快照，认证密码在此处解密。"""
        from modules.metrics.util.metrics_secret_util import decrypt_password

        return CollectorProfileSnapshot(
            profile_id=int(row.profile_id),
            push_url=row.push_url,
            auth_user=row.auth_user,
            auth_password=decrypt_password(row.auth_password_cipher),
            job_label=row.job_label,
            instance_label=row.instance_label,
            machine_label=row.machine_label,
            interval_seconds=row.interval_seconds,
            batch_size=row.batch_size,
            timeout_seconds=row.timeout_seconds,
            extended_enabled=row.extended_enabled,
            revision=row.revision,
        )

    # ------------------------------------------------------------------
    # 推送结果回写
    # ------------------------------------------------------------------

    @staticmethod
    def _on_push_result(profile_id: int, success: bool, message: str):
        """采集线程推送结果回调：用独立会话回写配置表，异常隔离。

        回调运行在采集线程内，使用短事务避免长时间占用连接。
        """
        try:
            with SessionLocal() as db:
                MetricsCollectorConfigService.record_push_result(db, profile_id, success, message)
        except Exception as exc:
            logger.debug(f"推送结果回写失败: profileId={profile_id}, error={exc}")

    # ------------------------------------------------------------------
    # 运行状态查询
    # ------------------------------------------------------------------

    @classmethod
    def describe_runtime(cls) -> dict:
        """汇总当前进程的采集线程运行状态，供状态接口返回。"""
        with _threads_lock:
            threads = dict(_threads)
        processes = []
        for role, thread in threads.items():
            processes.append(
                {
                    "role": role,
                    "pid": os.getpid(),
                    "running": bool(thread.is_alive() and not thread.stopped),
                    "activeProfileIds": [profile.profile_id for profile in thread.get_profiles()],
                    "lastPollTime": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "lastError": "",
                }
            )
        return {"processes": processes}

    @classmethod
    def thread_summary(cls, role: str) -> dict:
        """返回指定角色线程的简要状态，用于日志与调试。"""
        thread = cls.get_thread(role)
        if not thread:
            return {"role": role, "running": False}
        return {
            "role": role,
            "running": bool(thread.is_alive() and not thread.stopped),
            "pushFailures": thread.push_failures,
            "activeProfileIds": [profile.profile_id for profile in thread.get_profiles()],
        }
