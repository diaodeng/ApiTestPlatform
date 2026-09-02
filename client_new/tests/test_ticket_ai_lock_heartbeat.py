"""
Agent 工作区锁心跳续租测试。

覆盖：
- 有心跳字段的锁按心跳判活（新鲜=有效、超窗=过期）；
- 无心跳字段的旧版锁回退时间窗判定（兼容）；
- 心跳刷新写入 lastHeartbeatAt。
"""

import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from services.ticket_ai_analysis_service import TicketAiAnalysisService


class LockHeartbeatTests(unittest.TestCase):
    def _write_lock(self, workspace: Path, payload: dict) -> Path:
        lock_file = workspace / "analysis.lock"
        lock_file.write_text(json.dumps(payload), encoding="utf-8")
        return lock_file

    def test_fresh_heartbeat_keeps_lock_alive(self):
        """心跳在窗口内（<60s）时锁有效，即使启动时间已超过旧时间窗。"""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            lock_payload = {
                "startedAt": (datetime.now() - timedelta(hours=2)).isoformat(),
                "lastHeartbeatAt": datetime.now().isoformat(),
            }
            lock_file = self._write_lock(workspace, lock_payload)
            self.assertFalse(
                TicketAiAnalysisService._is_stale_lock(
                    json.loads(lock_file.read_text(encoding="utf-8")), 120
                )
            )

    def test_stopped_heartbeat_expires_lock(self):
        """心跳停止超过 60 秒视为 Worker 已死，锁过期可接管。"""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            lock_payload = {
                "startedAt": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "lastHeartbeatAt": (datetime.now() - timedelta(seconds=90)).isoformat(),
            }
            lock_file = self._write_lock(workspace, lock_payload)
            self.assertTrue(
                TicketAiAnalysisService._is_stale_lock(
                    json.loads(lock_file.read_text(encoding="utf-8")), 120
                )
            )

    def test_legacy_lock_falls_back_to_time_window(self):
        """无心跳字段的旧锁按启动时间+超时×2 判定，行为与旧版一致。"""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            # 启动 2 分钟、超时 120s（窗口 240s）：未过期。
            fresh_payload = {"startedAt": (datetime.now() - timedelta(minutes=2)).isoformat()}
            self.assertFalse(TicketAiAnalysisService._is_stale_lock(fresh_payload, 120))
            # 启动 10 分钟、超时 120s（窗口 240s）已过：过期。
            stale_payload = {"startedAt": (datetime.now() - timedelta(minutes=10)).isoformat()}
            self.assertTrue(TicketAiAnalysisService._is_stale_lock(stale_payload, 120))


class HeartbeatRefreshTests(unittest.TestCase):
    def test_refresh_writes_last_heartbeat(self):
        """心跳刷新应更新锁文件中的 lastHeartbeatAt 且保留其他字段。"""
        with tempfile.TemporaryDirectory() as tmp:
            lock_file = Path(tmp) / "analysis.lock"
            lock_file.write_text(json.dumps({"taskId": 1, "startedAt": "2026-01-01T00:00:00"}), encoding="utf-8")
            TicketAiAnalysisService._refresh_task_lock_heartbeat(lock_file)
            payload = json.loads(lock_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["taskId"], 1)
            self.assertIn("lastHeartbeatAt", payload)


if __name__ == "__main__":
    unittest.main()
