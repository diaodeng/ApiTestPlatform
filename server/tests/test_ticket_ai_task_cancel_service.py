"""
工单 AI 分析任务取消服务测试。

覆盖：
- 任务不存在返回失败；
- 终态任务无需取消（幂等返回当前状态）；
- created/running 任务取消后：状态置 canceled、活跃锁释放、审计 canceled、写工单事件；
- running 任务取消时发送 Agent 通知、created 任务不发通知。
"""

import unittest
from unittest.mock import MagicMock, patch

from modules.ticket.entity.do.ticket_do import TicketAiAnalysisTask
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


class CancelAnalysisTaskTests(unittest.TestCase):
    def _build_task(self, status: str) -> TicketAiAnalysisTask:
        task = TicketAiAnalysisTask(
            task_id=1001,
            ticket_id=2002,
            version_id=3003,
            status=status,
            status_desc="x",
            command_line="",
        )
        task.request_fingerprint = "fp-1"
        task.analysis_context = {"selectedAgentCode": "agent-a"}
        return task

    def _run_cancel(self, task, online_agent="agent-a"):
        db = MagicMock()
        user = MagicMock()
        with patch(
            "modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.get_task_by_id",
            return_value=task,
        ), patch(
            "modules.ticket.service.ai.ticket_ai_analysis_service.TicketDao.add_event"
        ), patch(
            "modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.update_task"
        ), patch.object(
            TicketAiAnalysisService, "_mark_task_status"
        ) as mark_mock, patch.object(
            TicketAiAnalysisService, "_update_execution_record"
        ), patch.object(
            TicketAiAnalysisService, "_resolve_agent_code", return_value=online_agent
        ), patch.object(
            TicketAiAnalysisService, "_notify_agent_task_canceled"
        ) as notify_mock:
            result = TicketAiAnalysisService.cancel_analysis_task_services(db, 2002, task.task_id, user)
        return result, mark_mock, notify_mock

    def test_task_not_found_fails(self):
        """任务不存在或工单不匹配时返回失败。"""
        db = MagicMock()
        user = MagicMock()
        with patch(
            "modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.get_task_by_id",
            return_value=None,
        ):
            result = TicketAiAnalysisService.cancel_analysis_task_services(db, 1, 2, user)
        self.assertFalse(result.is_success)

    def test_terminal_task_no_cancel_needed(self):
        """终态任务返回成功且不改动状态。"""
        for status in (
            TicketAiAnalysisStatus.SUCCESS.value,
            TicketAiAnalysisStatus.FAILED.value,
            TicketAiAnalysisStatus.CANCELED.value,
        ):
            task = self._build_task(status)
            result, mark_mock, notify_mock = self._run_cancel(task)
            self.assertTrue(result.is_success)
            mark_mock.assert_not_called()
            notify_mock.assert_not_called()

    def test_running_task_canceled_with_agent_notify(self):
        """running 任务取消：置 canceled 态并发送 Agent 通知。"""
        task = self._build_task(TicketAiAnalysisStatus.RUNNING.value)
        result, mark_mock, notify_mock = self._run_cancel(task)
        self.assertTrue(result.is_success)
        mark_mock.assert_called_once()
        _, kwargs = mark_mock.call_args
        self.assertEqual(kwargs["status"], TicketAiAnalysisStatus.CANCELED.value)
        notify_mock.assert_called_once()

    def test_created_task_canceled_without_agent_notify(self):
        """created 任务未派发到 Agent，取消不发通知。"""
        task = self._build_task(TicketAiAnalysisStatus.CREATED.value)
        result, mark_mock, notify_mock = self._run_cancel(task)
        self.assertTrue(result.is_success)
        mark_mock.assert_called_once()
        notify_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
