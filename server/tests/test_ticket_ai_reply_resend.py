"""
AI 结果回帖手动补发服务（resend_result_reply_services）的单元测试。

覆盖：任务/工单校验、状态限制、已回帖拒绝、补发成功与发送失败路径。
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService

AI_SERVICE_MODULE = "modules.ticket.service.ai.ticket_ai_analysis_service"
GROUP_PUSH_SERVICE_MODULE = "modules.ticket.service.sync.ticket_sync_group_push_service"
SYNC_CONFIG_SERVICE_MODULE = "modules.ticket.service.sync.ticket_sync_config_service"


def _make_task(status="success", replied=False):
    return SimpleNamespace(
        task_id=2048452915620864,
        ticket_id=1,
        status=status,
        analysis_result={"analysis_summary": "摘要"},
        error_message="",
    )


def _make_ticket():
    return SimpleNamespace(ticket_id=1, ticket_no="INC-RES-1", extra_data={"external_sync": {"sync_state": {}}})


class TestResendResultReplyServices(unittest.TestCase):
    """补发服务的校验与结果分支。"""

    _UNSET = object()

    def _run(self, task, ticket=_UNSET, is_replied=False, reply_result=None):
        current_user = SimpleNamespace(
            user=SimpleNamespace(user_name="tester", user_id=10001)
        )
        if ticket is self._UNSET:
            ticket = _make_ticket()
        with (
            patch(f"{AI_SERVICE_MODULE}.TicketAiDao.get_task_by_id", return_value=task),
            patch(f"{AI_SERVICE_MODULE}.TicketDao.get_ticket_by_id", return_value=ticket),
            patch(f"{AI_SERVICE_MODULE}.TicketAiDao.is_result_replied", return_value=is_replied),
            patch(f"{AI_SERVICE_MODULE}.TicketDao.add_event"),
            patch(f"{SYNC_CONFIG_SERVICE_MODULE}.TicketSyncConfigService.load_sync_config", return_value={}),
            patch(
                f"{GROUP_PUSH_SERVICE_MODULE}.TicketSyncGroupPushService.build_meta",
                return_value={"sync_state": {}},
            ),
            patch(
                f"{GROUP_PUSH_SERVICE_MODULE}.TicketSyncGroupPushService.resolve_sync_scene_from_meta",
                return_value="bitable_pull",
            ),
            patch(
                f"{GROUP_PUSH_SERVICE_MODULE}.TicketSyncGroupPushService.send_ai_result_thread_reply",
                return_value=(reply_result or {"skipped": False, "successCount": 1}, None, {}),
            ) as send_reply,
        ):
            result = TicketAiAnalysisService.resend_result_reply_services(
                MagicMock(), 1, 2048452915620864, current_user
            )
        return result, send_reply

    def test_task_not_found(self):
        """任务不存在或与工单不匹配：拒绝。"""
        result, _ = self._run(None)
        self.assertFalse(result.is_success)
        self.assertIn("不存在", result.message)

    def test_ticket_not_found(self):
        """工单不存在：拒绝。"""
        result, _ = self._run(_make_task(), ticket=None)
        self.assertFalse(result.is_success)

    def test_task_status_not_allowed(self):
        """非成功/失败终态（如运行中、已取消）：拒绝补发。"""
        result, _ = self._run(_make_task(status="running"))
        self.assertFalse(result.is_success)
        self.assertIn("仅分析成功或失败", result.message)

    def test_already_replied_rejected(self):
        """已回帖过的任务：拒绝重复补发。"""
        result, _ = self._run(_make_task(), is_replied=True)
        self.assertFalse(result.is_success)
        self.assertIn("已回帖过", result.message)

    def test_resend_success(self):
        """未回帖的成功任务：以手动意图（enabled+sendOn=always、override=on）发送。"""
        result, send_reply = self._run(_make_task())
        self.assertTrue(result.is_success)
        send_reply.assert_called_once()
        kwargs = send_reply.call_args.kwargs
        self.assertEqual(kwargs["ai_task_id"], 2048452915620864)
        self.assertEqual(kwargs["override"], "on")
        self.assertEqual(kwargs["follow_up_config"]["sendOn"], "always")
        self.assertTrue(kwargs["follow_up_config"]["enabled"])

    def test_resend_skipped_returns_failure(self):
        """回帖被跳过（如无锚点）：返回失败并带原因。"""
        result, _ = self._run(_make_task(), reply_result={"skipped": True, "skipReason": "工单无群消息锚点"})
        self.assertFalse(result.is_success)
        self.assertIn("无群消息锚点", result.message)

    def test_resend_all_failed_returns_failure(self):
        """全部群发送失败：返回失败。"""
        result, _ = self._run(_make_task(), reply_result={"skipped": False, "successCount": 0})
        self.assertFalse(result.is_success)


if __name__ == "__main__":
    unittest.main()
