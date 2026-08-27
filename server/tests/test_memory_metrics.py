from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from utils.metrics.collect import PushDataToServer
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
    with patch.object(PushDataToServer, "__init__", lambda self: None):
        collector = PushDataToServer()
    collector.vm_url = "https://metrics.example.test/import"
    collector.data_lines = ['qtr_test{job="QTR"} 1 1000']
    collector.push_failures = 0
    response = SimpleNamespace(status_code=204, text="")
    with patch("utils.metrics.collect.httpx.post", return_value=response) as post:
        collector._push()
    assert post.call_args.kwargs["content"] == collector.data_lines[0]


def test_process_snapshot_as_dict_contains_only_numeric_fields():
    values = _snapshot(100, 80).as_dict()
    assert values["rss_bytes"] == 100
    assert values["uptime_seconds"] == 10.0
    assert all(isinstance(value, (int, float)) for value in values.values())
