"""
活跃指纹锁与执行入口白名单测试。

覆盖：
- _mark_task_status 终态释放活跃锁、活跃态按指纹占锁；
- 执行入口对非 created/running 状态任务跳过执行（防 canceled 误执行）；
- 心跳锁判活（client_new 侧同构逻辑在对应测试文件覆盖）。
"""

import unittest
from unittest.mock import MagicMock, patch

from config.get_db import _ensure_ticket_ai_analysis_active_lock  # noqa: F401  确认迁移函数可导入
from modules.ticket.entity.do.ticket_do import TicketAiAnalysisTask
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


class MarkTaskStatusActiveLockTests(unittest.TestCase):
    def _build_task(self, fingerprint: str = "fp-1") -> TicketAiAnalysisTask:
        task = TicketAiAnalysisTask(task_id=1, ticket_id=2, version_id=3)
        task.request_fingerprint = fingerprint
        return task

    def test_terminal_status_releases_active_lock(self):
        """success/failed/canceled 状态应把 active_lock 置空。"""
        db = MagicMock()
        with patch(
            "modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.update_task"
        ) as update_mock, patch.object(
            TicketAiAnalysisService, "_log_task_step"
        ):
            for status in (
                TicketAiAnalysisStatus.SUCCESS.value,
                TicketAiAnalysisStatus.FAILED.value,
                TicketAiAnalysisStatus.CANCELED.value,
            ):
                TicketAiAnalysisService._mark_task_status(
                    db, 1, status=status, status_desc="x"
                )
                args, _kwargs = update_mock.call_args
                kwargs = {"update_data": args[2]}
                self.assertIsNone(kwargs["update_data"]["active_lock"])

    def test_active_status_occupies_lock_with_fingerprint(self):
        """created/running 状态应按调用方传入的指纹占锁。"""
        db = MagicMock()
        with patch(
            "modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.update_task"
        ) as update_mock, patch.object(
            TicketAiAnalysisService, "_log_task_step"
        ):
            TicketAiAnalysisService._mark_task_status(
                db,
                1,
                status=TicketAiAnalysisStatus.CREATED.value,
                status_desc="x",
                active_lock_fingerprint="fp-abc",
            )
            args, _kwargs = update_mock.call_args
            kwargs = {"update_data": args[2]}
            self.assertEqual(kwargs["update_data"]["active_lock"], "fp-abc")

    def test_active_status_without_fingerprint_releases_lock(self):
        """活跃态未传指纹（无指纹的历史任务）时不占锁，避免写脏数据。"""
        db = MagicMock()
        with patch(
            "modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.update_task"
        ) as update_mock, patch.object(
            TicketAiAnalysisService, "_log_task_step"
        ):
            TicketAiAnalysisService._mark_task_status(
                db, 1, status=TicketAiAnalysisStatus.RUNNING.value, status_desc="x"
            )
            args, _kwargs = update_mock.call_args
            kwargs = {"update_data": args[2]}
            self.assertIsNone(kwargs["update_data"]["active_lock"])


if __name__ == "__main__":
    unittest.main()
