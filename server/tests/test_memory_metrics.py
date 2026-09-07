from __future__ import annotations

import threading
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from utils.metrics.collect import CollectorProfileSnapshot, PushDataToServer
from utils.metrics.process import ProcessCollector, ProcessSnapshot
from utils.metrics.task_memory import TaskMemoryObserver


@dataclass
class _FakeProcessCollector:
    snapshots: list[ProcessSnapshot]

    def snapshot(self) -> ProcessSnapshot:
        return self.snapshots.pop(0)


def _snapshot(rss: int, uss: int, threads: int = 2, children: int = 0) -> ProcessSnapshot:
    return ProcessSnapshot(
        pid=123,
        rss_bytes=rss,
        vms_bytes=rss * 2,
        uss_bytes=uss,
        threads=threads,
        children=children,
        cpu_seconds_total=1.0,
        start_time_seconds=100.0,
        uptime_seconds=10.0,
        open_files=3,
        connections=4,
    )


def test_task_memory_observer_tracks_active_and_low_cardinality_labels():
    collector = _FakeProcessCollector([_snapshot(100, 80), _snapshot(140, 100), _snapshot(130, 90)])
    observer = TaskMemoryObserver(role="celery_worker", process_collector=collector)
    context = {
        "task_id": 999,
        "celery_task_id": "celery-uuid",
        "trace_id": "trace-uuid",
        "task_key": "jobs.case.run",
        "task_family": "case_execution",
        "queue_name": "case-execution",
        "owner_type": "hrm",
        "trigger_type": "background",
    }

    observation = observer.start(context)
    assert any(name == "qtr_task_active" and value == 1 for name, _, value in observer.metrics())

    values = observer.finish(context, observation, "success")
    assert values["memory_delta_bytes"] == 40
    assert values["uss_delta_bytes"] == 20
    metrics = observer.metrics()
    completed = [item for item in metrics if item[0] == "qtr_task_completed_total"]
    assert completed[0][1]["role"] == "celery_worker"
    assert completed[0][1]["status"] == "success"
    assert "task_id" not in completed[0][1]
    assert any(name == "qtr_task_active" and value == 0 for name, _, value in metrics)


def test_process_collector_falls_back_to_legacy_connections_api():
    class LegacyProcess:
        pid = 123

        def memory_info(self):
            return SimpleNamespace(rss=100, vms=200)

        def memory_full_info(self):
            return SimpleNamespace(uss=80)

        def open_files(self):
            return []

        def connections(self):
            return [object(), object()]

        def create_time(self):
            return 100.0

        def cpu_times(self):
            return SimpleNamespace(user=1.0, system=0.5)

        def children(self, recursive=True):
            return []

        def num_threads(self):
            return 2

    snapshot = ProcessCollector(process=LegacyProcess()).snapshot()
    assert snapshot.connections == 2


def test_prometheus_labels_are_escaped():
    with patch.object(PushDataToServer, "__init__", lambda self: None):
        collector = PushDataToServer()
    collector.role = 'worker"\\\\\nrole'
    collector.extended_enabled = True
    labels = collector._labels("sensor", {"task_family": 'case"\\\\\nrun'})
    assert 'role="worker\\"\\\\\\\\\\nrole"' in labels
    assert 'task_family="case\\"\\\\\\\\\\nrun"' in labels


def test_push_payload_keeps_legacy_batch_boundary():
    """推送体保持纯样本行拼接语义：整批内容一次性作为请求体发送。"""
    with patch.object(PushDataToServer, "__init__", lambda self: None):
        collector = PushDataToServer()
    profile = CollectorProfileSnapshot(profile_id=1, push_url="https://metrics.example.test/import")
    data_lines = ['qtr_test{job="QTR"} 1 1000']
    collector.push_failures = 0
    response = SimpleNamespace(status_code=204, text="")
    with patch("utils.metrics.collect.httpx.post", return_value=response) as post:
        collector._push(profile, data_lines)
    assert post.call_args.kwargs["content"] == data_lines[0]
    assert post.call_args.args[0] == profile.push_url


def test_machine_level_metrics_do_not_carry_role_label():
    """机器/容器级指标不带 role 标签，进程/任务级指标必须带 role。

    cpu、memory、cgroup 数据在同一台机器上所有进程采集结果相同：带 role 会
    把一份数据拆成多条序列，导致面板聚合翻倍；rss、任务数据是进程独有数据，
    不带 role 则三个进程互相覆盖同一条序列（历史缺陷）。
    """
    with patch.object(PushDataToServer, "__init__", lambda self: None):
        collector = PushDataToServer()
    collector.role = "celery_worker"
    profile = CollectorProfileSnapshot(profile_id=1, push_url="https://x", extended_enabled=True)
    raw = {
        "machine": [("cpu_usage_percent", 1.5), ("memory_used_mb", 100)],
        "cgroup": {"qtr_cgroup_memory_current_bytes": 2048},
        "process": {"rss_bytes": 815, "threads": 10},
        "task": [("qtr_task_active", {"role": "celery_worker", "task_family": "case"}, 1)],
    }
    lines = collector._format_samples(raw, profile)
    machine_lines = [line for line in lines if line.startswith(("cpu_", "memory_", "qtr_cgroup_"))]
    process_lines = [line for line in lines if line.startswith("qtr_process_")]
    task_lines = [line for line in lines if line.startswith("qtr_task_")]
    assert machine_lines and all("role=" not in line for line in machine_lines)
    assert process_lines and all('role="celery_worker"' in line for line in process_lines)
    assert task_lines and all('role="celery_worker"' in line for line in task_lines)


def test_legacy_mode_samples_exclude_extended_metrics():
    """扩展指标关闭的通道只发送机器级样本，且保持无 role 的历史格式。"""
    with patch.object(PushDataToServer, "__init__", lambda self: None):
        collector = PushDataToServer()
    collector.role = "api"
    profile = CollectorProfileSnapshot(profile_id=1, push_url="https://x", extended_enabled=False)
    raw = {
        "machine": [("cpu_usage_percent", 1.5)],
        "cgroup": {"qtr_cgroup_memory_current_bytes": 2048},
        "process": {"rss_bytes": 815},
        "task": [("qtr_task_active", {"role": "api"}, 1)],
    }
    lines = collector._format_samples(raw, profile)
    assert len(lines) == 1
    assert lines[0].startswith("cpu_usage_percent")
    assert "role=" not in lines[0]


def test_thread_polls_profile_provider_and_applies_config():
    """采集线程主循环按固定间隔调用配置回调并热生效。

    回归背景：此前 replace_profiles 无任何周期调用方，通道配置从未注入，
    线程因无通道而跳过所有采集推送，导致 Grafana 查不到 memory_pressure 等指标。
    """
    with patch.object(PushDataToServer, "__init__", lambda self: None):
        collector = PushDataToServer()
    collector.role = "api"
    collector._profiles = []
    collector._profiles_lock = threading.Lock()
    collector._channel_buffers = {}
    collector._channel_last_push = {}
    calls = []

    def provider():
        calls.append(1)
        return [CollectorProfileSnapshot(profile_id=7, push_url="https://x", machine_label="home")]

    collector.profile_provider = provider
    # 时间戳归零保证首轮立即刷新；之后 3 秒内不应重复刷新。
    collector._last_profile_refresh = 0.0
    collector._refresh_profiles_if_due()
    first = collector.get_profiles()
    assert [profile.profile_id for profile in first] == [7]
    assert len(calls) == 1

    collector._refresh_profiles_if_due()
    assert len(calls) == 1

    # 超过刷新间隔后再次刷新；回调抛异常时保留现有通道。
    collector._last_profile_refresh -= collector.PROFILE_REFRESH_SECONDS + 1
    collector._refresh_profiles_if_due()
    assert len(calls) == 2

    def broken_provider():
        raise RuntimeError("db down")

    collector.profile_provider = broken_provider
    collector._last_profile_refresh -= collector.PROFILE_REFRESH_SECONDS + 1
    collector._refresh_profiles_if_due()
    assert [profile.profile_id for profile in collector.get_profiles()] == [7]


def test_thread_without_provider_keeps_empty_channels():
    """未注入配置回调且无外部注入时，线程保持空通道、不采集推送。"""
    with patch.object(PushDataToServer, "__init__", lambda self: None):
        collector = PushDataToServer()
    collector._profiles = []
    collector._profiles_lock = threading.Lock()
    collector.profile_provider = None
    collector._refresh_profiles_if_due()
    assert collector.get_profiles() == []


def test_process_snapshot_as_dict_contains_only_numeric_fields():
    values = _snapshot(100, 80).as_dict()
    assert values["rss_bytes"] == 100
    assert values["uptime_seconds"] == 10.0
    assert all(isinstance(value, (int, float)) for value in values.values())


def test_runtime_service_injects_profile_provider():
    """运行时服务启动线程时必须注入配置加载回调，保证线程能自行拿到通道配置。"""
    from modules.metrics.service import metrics_collector_runtime_service as runtime

    captured = {}

    class FakeThread:
        def __init__(self, role=None):
            self.role = role
            self.result_listener = None
            self.profile_provider = None

        def start(self):
            captured["started"] = True

    original = runtime._threads.copy()
    try:
        runtime._threads.clear()
        with patch.object(runtime, "PushDataToServer", FakeThread):
            thread = runtime.MetricsCollectorRuntimeService.start(role="api")
        assert captured.get("started") is True
        assert callable(thread.profile_provider)
        with patch.object(
            runtime.MetricsCollectorRuntimeService,
            "load_active_profiles",
            classmethod(lambda cls, role: [CollectorProfileSnapshot(profile_id=3, push_url="https://x")]),
        ):
            profiles = thread.profile_provider()
        assert [profile.profile_id for profile in profiles] == [3]
    finally:
        runtime._threads.clear()
        runtime._threads.update(original)

