"""
AI 分析结果话题回帖（aiResultFollowUp）的单元测试。

覆盖：sendOn 四枚举匹配、手动三态覆盖、任务表列幂等、无锚点降级跳过（策略B）、
多群去重回帖、配置归一化、模板渲染。
2026-09 拆表：锚点改查 ticket_group_push_anchor 表、幂等改用
ticket_ai_analysis_task.result_replied_at 列，测试按 DAO 打桩。
"""
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.ticket.service.sync.ticket_ai_result_reply_card_service import TicketAiResultReplyCardService
from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService

GROUP_PUSH_MODULE = "modules.ticket.service.sync.ticket_sync_group_push_service"


def _make_anchor(message_id: str, chat_id: str, root_id: str = "", thread_id: str = "") -> SimpleNamespace:
    """构造锚点表 ORM 行的测试替身。"""
    return SimpleNamespace(
        message_id=message_id,
        root_id=root_id or message_id,
        thread_id=thread_id,
        chat_id=chat_id,
    )


def _make_db() -> SimpleNamespace:
    """构造带 commit/rollback 的数据库会话替身。"""
    return SimpleNamespace(commit=lambda: None, rollback=lambda: None)


class TestMatchAiResultSendOn(unittest.TestCase):
    """sendOn 四枚举与终态匹配矩阵。"""

    def test_send_on_matrix(self):
        """none 全不推；success 仅成功；failed 仅失败；always 成功失败都推；取消态永不推。"""
        matrix = [
            ("none", "success", False),
            ("none", "failed", False),
            ("none", "canceled", False),
            ("success", "success", True),
            ("success", "failed", False),
            ("success", "canceled", False),
            ("failed", "failed", True),
            ("failed", "success", False),
            ("failed", "canceled", False),
            ("always", "success", True),
            ("always", "failed", True),
            ("always", "canceled", False),
        ]
        for send_on, status, expected in matrix:
            with self.subTest(send_on=send_on, status=status):
                self.assertEqual(
                    TicketSyncGroupPushService._match_ai_result_send_on(send_on, status),
                    expected,
                )


class TestShouldSendAiResultFollowUp(unittest.TestCase):
    """回帖判定：全局开关 + sendOn + 手动三态覆盖。"""

    def _config(self, enabled=True, send_on="always"):
        return {"enabled": enabled, "sendOn": send_on, "replyInThread": True, "template": ""}

    def test_disabled_by_default(self):
        """总开关关闭时不回帖。"""
        ok, reason = TicketSyncGroupPushService.should_send_ai_result_follow_up(
            self._config(enabled=False), ai_task_status="success"
        )
        self.assertFalse(ok)
        self.assertIn("未启用", reason)

    def test_send_on_mismatch(self):
        """sendOn 与终态不匹配时不回帖。"""
        ok, reason = TicketSyncGroupPushService.should_send_ai_result_follow_up(
            self._config(send_on="success"), ai_task_status="failed"
        )
        self.assertFalse(ok)
        self.assertIn("不匹配", reason)

    def test_send_on_match(self):
        """sendOn 与终态匹配时回帖。"""
        ok, _ = TicketSyncGroupPushService.should_send_ai_result_follow_up(
            self._config(send_on="success"), ai_task_status="success"
        )
        self.assertTrue(ok)

    def test_manual_off_overrides(self):
        """手动 off 强制不回帖。"""
        ok, reason = TicketSyncGroupPushService.should_send_ai_result_follow_up(
            self._config(), ai_task_status="success", override="off"
        )
        self.assertFalse(ok)
        self.assertIn("不回帖", reason)

    def test_manual_on_skips_enabled_gate(self):
        """手动 on 跳过总开关，但仍受 sendOn 语义约束。"""
        ok, _ = TicketSyncGroupPushService.should_send_ai_result_follow_up(
            self._config(enabled=False, send_on="always"), ai_task_status="success", override="on"
        )
        self.assertTrue(ok)
        ok2, _ = TicketSyncGroupPushService.should_send_ai_result_follow_up(
            self._config(enabled=False, send_on="success"), ai_task_status="failed", override="on"
        )
        self.assertFalse(ok2)

    def test_manual_follow_uses_global(self):
        """follow（默认）跟随全局开关。"""
        ok, _ = TicketSyncGroupPushService.should_send_ai_result_follow_up(
            self._config(enabled=False), ai_task_status="success", override="follow"
        )
        self.assertFalse(ok)


class TestAiResultReplyIdempotency(unittest.TestCase):
    """任务表列幂等：TicketAiDao.is_result_replied / mark_result_replied（2026-09 拆表后）。"""

    def test_mark_and_check(self):
        """result_replied_at 非 NULL 即已回帖；无任务行或 task_id 为空视为未回帖。"""
        from modules.ticket.dao.ticket_ai_dao import TicketAiDao

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = (datetime.now(),)
        self.assertTrue(TicketAiDao.is_result_replied(db, 1))
        db.query.return_value.filter.return_value.first.return_value = (None,)
        self.assertFalse(TicketAiDao.is_result_replied(db, 1))
        db.query.return_value.filter.return_value.first.return_value = None
        self.assertFalse(TicketAiDao.is_result_replied(db, 1))
        self.assertFalse(TicketAiDao.is_result_replied(db, None))

    def test_mark_returns_updated_only_once(self):
        """条件更新（result_replied_at IS NULL）保证并发下只有第一个写者生效。"""
        from modules.ticket.dao.ticket_ai_dao import TicketAiDao

        db = MagicMock()
        db.query.return_value.filter.return_value.update.return_value = 1
        self.assertTrue(TicketAiDao.mark_result_replied(db, 100, chat_ids=["oc_1"]))
        db.query.return_value.filter.return_value.update.return_value = 0
        self.assertFalse(TicketAiDao.mark_result_replied(db, 100))
        self.assertFalse(TicketAiDao.mark_result_replied(db, None))


class TestCollectAiResultReplyTargets(unittest.TestCase):
    """回帖目标收集：空锚点过滤与按群去重（2026-09 拆表后查锚点表）。"""

    def test_dedup_by_chat_and_skip_empty(self):
        """同群多条锚点只回一次；空 messageId 锚点跳过。"""
        anchors = [
            _make_anchor("om_a", "oc_1"),
            _make_anchor("om_b", "oc_1"),
            _make_anchor("om_c", "oc_2"),
            _make_anchor("", "oc_3"),
        ]
        with patch(
            "modules.ticket.service.sync.ticket_sync_group_push_service.TicketGroupPushAnchorDao.list_anchors_by_ticket_id",
            return_value=anchors,
        ):
            targets = TicketSyncGroupPushService._collect_ai_result_reply_targets(MagicMock(), 1)
        self.assertEqual([t["messageId"] for t in targets], ["om_a", "om_c"])

    def test_no_refs_returns_empty(self):
        """无锚点返回空列表。"""
        with patch(
            "modules.ticket.service.sync.ticket_sync_group_push_service.TicketGroupPushAnchorDao.list_anchors_by_ticket_id",
            return_value=[],
        ):
            self.assertEqual(TicketSyncGroupPushService._collect_ai_result_reply_targets(MagicMock(), 1), [])


class TestSendAiResultThreadReply(unittest.TestCase):
    """send_ai_result_thread_reply 主流程。"""

    def _ticket(self):
        return SimpleNamespace(
            ticket_id=1,
            ticket_no="INC-R-1",
            title="回帖测试",
            ticket_url="http://t",
            module_name="M",
            merchant_name="P",
            extra_data={"external_sync": {"sync_state": {}}},
        )

    def _run(self, ticket, follow_up_config, status="success", task_id=100, anchors=None, replied=False):
        anchors = anchors or []
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={"groupPush": {"appId": "app", "appSecret": "secret"}},
            ),
            patch.object(TicketSyncNotifyService, "resolve_feishu_auth", return_value=("app", "secret")),
            patch.object(TicketSyncNotifyService, "send_feishu_thread_reply") as send_reply,
            patch(f"{GROUP_PUSH_MODULE}.TicketGroupPushAnchorDao.list_anchors_by_ticket_id", return_value=anchors),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.is_result_replied", return_value=replied),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.mark_result_replied", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.update_result_replied_chat_ids", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.release_result_replied", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.has_any_result_replied", return_value=False),
        ):
            result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                _make_db(),
                ticket=ticket,
                meta={"sync_state": {}},
                follow_up_config=follow_up_config,
                ai_task_status=status,
                ai_task_id=task_id,
                ai_result_payload={"analysis_summary": "摘要"},
            )
        return result, send_reply

    def test_reply_skipped_when_send_on_none(self):
        """sendOn=none 时跳过且不发送。"""
        result, send_reply = self._run(
            self._ticket(),
            {"enabled": True, "sendOn": "none", "replyInThread": True, "template": ""},
            anchors=[_make_anchor("om_a", "oc_1")],
        )
        self.assertTrue(result["skipped"])
        send_reply.assert_not_called()

    def test_reply_skipped_when_no_anchor(self):
        """无锚点且策略为 skip（默认）：跳过，不新建话题。"""
        result, send_reply = self._run(
            self._ticket(),
            {"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
            anchors=[],
        )
        self.assertTrue(result["skipped"])
        self.assertIn("锚点", result["skipReason"])
        send_reply.assert_not_called()

    def test_reply_skipped_when_task_replied(self):
        """同 task_id 已回帖过（任务表 result_replied_at 非空）：幂等跳过。"""
        result, send_reply = self._run(
            self._ticket(),
            {"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
            anchors=[_make_anchor("om_a", "oc_1")],
            replied=True,
        )
        self.assertTrue(result["skipped"])
        self.assertIn("已回帖", result["skipReason"])
        send_reply.assert_not_called()

    def test_reply_sends_to_each_deduped_group(self):
        """正常回帖：按去重后的目标群逐个发送并标记任务表幂等列。"""
        result, send_reply = self._run(
            self._ticket(),
            {"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
            anchors=[
                _make_anchor("om_a", "oc_1"),
                _make_anchor("om_b", "oc_1"),
                _make_anchor("om_c", "oc_2"),
            ],
        )
        self.assertFalse(result["skipped"])
        self.assertEqual(result["targetCount"], 2)
        self.assertEqual(result["successCount"], 2)
        self.assertEqual(send_reply.call_count, 2)
        called_message_ids = [call.kwargs["message_id"] for call in send_reply.call_args_list]
        self.assertEqual(called_message_ids, ["om_a", "om_c"])

    def test_reply_skipped_when_once_per_ticket(self):
        """oncePerTicket 开启且该工单回帖过：工单级幂等跳过。"""
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={"groupPush": {"appId": "app", "appSecret": "secret"}},
            ),
            patch.object(TicketSyncNotifyService, "resolve_feishu_auth", return_value=("app", "secret")),
            patch.object(TicketSyncNotifyService, "send_feishu_thread_reply") as send_reply2,
            patch(f"{GROUP_PUSH_MODULE}.TicketGroupPushAnchorDao.list_anchors_by_ticket_id", return_value=[]),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.is_result_replied", return_value=False),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.has_any_result_replied", return_value=True),
        ):
            result2, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                _make_db(),
                ticket=self._ticket(),
                meta={"sync_state": {}},
                follow_up_config={"enabled": True, "sendOn": "always", "oncePerTicket": True},
                ai_task_status="success",
                ai_task_id=400,
            )
        self.assertTrue(result2["skipped"])
        self.assertIn("oncePerTicket", result2["skipReason"])
        send_reply2.assert_not_called()

    def test_reply_skipped_when_prewrite_fails(self):
        """抢占式占坑失败（并发已被处理）：跳过发送。"""
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={"groupPush": {"appId": "app", "appSecret": "secret"}},
            ),
            patch.object(TicketSyncNotifyService, "resolve_feishu_auth", return_value=("app", "secret")),
            patch.object(TicketSyncNotifyService, "send_feishu_thread_reply") as send_reply,
            patch(
                f"{GROUP_PUSH_MODULE}.TicketGroupPushAnchorDao.list_anchors_by_ticket_id",
                return_value=[_make_anchor("om_a", "oc_1")],
            ),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.is_result_replied", return_value=False),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.mark_result_replied", return_value=False),
        ):
            result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                _make_db(),
                ticket=self._ticket(),
                meta={"sync_state": {}},
                follow_up_config={"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
                ai_task_status="success",
                ai_task_id=500,
            )
        self.assertTrue(result["skipped"])
        self.assertIn("已回帖", result["skipReason"])
        send_reply.assert_not_called()

    def test_reply_continues_on_single_failure(self):
        """单个群回帖失败不中断其他群。"""
        reply_side_effect = [
            Exception("网络超时"),
            {"messageId": "om_r", "rootId": "om_a", "threadId": "omt_x", "chatId": "oc_2"},
        ]
        with patch.object(
            TicketSyncNotifyService,
            "send_feishu_thread_reply",
            side_effect=reply_side_effect,
        ):
            with (
                patch(
                    "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                    return_value={"groupPush": {"appId": "app", "appSecret": "secret"}},
                ),
                patch.object(TicketSyncNotifyService, "resolve_feishu_auth", return_value=("app", "secret")),
                patch(
                    f"{GROUP_PUSH_MODULE}.TicketGroupPushAnchorDao.list_anchors_by_ticket_id",
                    return_value=[_make_anchor("om_a", "oc_1"), _make_anchor("om_c", "oc_2")],
                ),
                patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.is_result_replied", return_value=False),
                patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.mark_result_replied", return_value=True),
                patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.update_result_replied_chat_ids", return_value=True),
                patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.release_result_replied", return_value=True),
                patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.has_any_result_replied", return_value=False),
            ):
                result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                    _make_db(),
                    ticket=self._ticket(),
                    meta={"sync_state": {}},
                    follow_up_config={"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
                    ai_task_status="success",
                    ai_task_id=200,
                    ai_result_payload={},
                )
        self.assertEqual(result["targetCount"], 2)
        self.assertEqual(result["successCount"], 1)


class TestSendAiResultReplyNoAnchorStrategy(unittest.TestCase):
    """无锚点策略：skip 跳过 / send_then_reply 先补发再回帖。"""

    def _ticket(self):
        return SimpleNamespace(
            ticket_id=1,
            ticket_no="INC-NA-1",
            title="无锚点策略测试",
            ticket_url="http://t",
            module_name="M",
            merchant_name="P",
            extra_data={"external_sync": {"sync_state": {}}},
        )

    def _config(self, strategy):
        return {
            "enabled": True,
            "sendOn": "always",
            "replyInThread": True,
            "template": "",
            "noAnchorStrategy": strategy,
        }

    def _run_with_push(self, ticket, meta, follow_up_config, push_result=None, anchors_after_push=None):
        """打桩补发方法与回帖发送，执行回帖主流程。

        anchors_after_push：补发成功后锚点表应返回的行（send_then_reply 分支二次收集目标）；
        默认无补发场景下锚点表恒返回空。
        """
        anchor_calls = [[], anchors_after_push] if anchors_after_push is not None else [[]]
        with (
            patch.object(
                TicketSyncGroupPushService,
                "send_group_message_for_ai_reply",
                return_value=(push_result or (True, ticket, meta, "")),
            ) as send_push,
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={"groupPush": {"appId": "app", "appSecret": "secret"}},
            ),
            patch.object(TicketSyncNotifyService, "resolve_feishu_auth", return_value=("app", "secret")),
            patch.object(TicketSyncNotifyService, "send_feishu_thread_reply") as send_reply,
            patch(
                f"{GROUP_PUSH_MODULE}.TicketGroupPushAnchorDao.list_anchors_by_ticket_id",
                side_effect=anchor_calls,
            ),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.is_result_replied", return_value=False),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.mark_result_replied", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.update_result_replied_chat_ids", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.release_result_replied", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.has_any_result_replied", return_value=False),
        ):
            result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                _make_db(),
                ticket=ticket,
                meta=meta,
                follow_up_config=follow_up_config,
                ai_task_status="success",
                ai_task_id=300,
                ai_result_payload={"analysis_summary": "摘要"},
                sync_scene="bitable_pull",
            )
        return result, send_push, send_reply

    def test_skip_strategy_skips_without_push(self):
        """策略 skip：不调用补发，直接跳过。"""
        ticket = self._ticket()
        meta = {"sync_state": {}}
        result, send_push, send_reply = self._run_with_push(ticket, meta, self._config("skip"))
        self.assertTrue(result["skipped"])
        self.assertIn("锚点", result["skipReason"])
        send_push.assert_not_called()
        send_reply.assert_not_called()

    def test_send_then_reply_pushes_and_replies(self):
        """策略 send_then_reply：补发成功（锚点表出现新锚点）后继续回帖。"""
        ticket = self._ticket()
        meta = {"sync_state": {}}
        result, send_push, send_reply = self._run_with_push(
            ticket,
            meta,
            self._config("send_then_reply"),
            push_result=(True, ticket, {"sync_state": {}}, ""),
            anchors_after_push=[_make_anchor("om_new", "oc_new")],
        )
        send_push.assert_called_once()
        self.assertFalse(result["skipped"])
        self.assertEqual(result["successCount"], 1)
        send_reply.assert_called_once()
        self.assertEqual(send_reply.call_args.kwargs["message_id"], "om_new")

    def test_send_then_reply_skips_when_push_blocked(self):
        """策略 send_then_reply：补发被拦截（范围/条件/已发送过）时跳过回帖。"""
        ticket = self._ticket()
        meta = {"sync_state": {}}
        result, send_push, send_reply = self._run_with_push(
            ticket,
            meta,
            self._config("send_then_reply"),
            push_result=(False, ticket, meta, "群推送未对场景 bitable_pull 启用"),
        )
        send_push.assert_called_once()
        self.assertTrue(result["skipped"])
        self.assertIn("补发工单信息未成功", result["skipReason"])
        send_reply.assert_not_called()

    def test_send_then_reply_skips_when_no_anchor_after_push(self):
        """策略 send_then_reply：补发返回成功但锚点表仍无锚点时跳过（防御分支）。"""
        ticket = self._ticket()
        meta = {"sync_state": {}}
        result, send_push, send_reply = self._run_with_push(
            ticket,
            meta,
            self._config("send_then_reply"),
            push_result=(True, ticket, {"sync_state": {}}, ""),
            anchors_after_push=[],
        )
        send_push.assert_called_once()
        self.assertTrue(result["skipped"])
        self.assertIn("仍未取得话题锚点", result["skipReason"])
        send_reply.assert_not_called()


class TestSendGroupMessageForAiReply(unittest.TestCase):
    """补发方法的判定链：范围、场景开关、去重标记。"""

    def _ticket(self, sent_once=False):
        return SimpleNamespace(
            ticket_id=1,
            ticket_no="INC-PUSH-1",
            title="补发判定测试",
            ticket_url="http://t",
            module_name="POS-客户端",
            merchant_name="P",
            extra_data={},
        )

    def _run(self, ticket, meta, *, scope_eligible=True, scene_enabled=True, auto_result=None):
        config = {
            "groupPush": {"enabled": True, "sendAfterBitablePull": scene_enabled},
            "automationScope": {"enabled": True, "moduleNameIncludes": ["POS"]},
        }
        scope = SimpleNamespace(
            eligible=scope_eligible,
            reason="" if scope_eligible else "当前模块未命中自动化关注范围",
            module_id=None,
            module_name="POS-客户端",
        )
        auto_result = auto_result or {"skipped": False, "pushSuccessCount": 1, "chatSuccessCount": 1}
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value=config,
            ),
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketAutomationScopeService.evaluate_ticket",
                return_value=scope,
            ),
            patch.object(
                TicketSyncGroupPushService,
                "send_auto_group_message_once",
                return_value=(auto_result, ticket, meta),
            ) as send_auto,
        ):
            pushed, ticket_out, meta_out, reason = TicketSyncGroupPushService.send_group_message_for_ai_reply(
                SimpleNamespace(),
                ticket=ticket,
                meta=meta,
                sync_scene="bitable_pull",
            )
        return pushed, reason, send_auto

    def test_push_success(self):
        """判定全通过时调用自动群推送并返回成功。"""
        pushed, reason, send_auto = self._run(self._ticket(), {"sync_state": {}})
        self.assertTrue(pushed)
        self.assertEqual(reason, "")
        send_auto.assert_called_once()

    def test_push_skipped_by_scope(self):
        """自动化范围不匹配时不补发。"""
        pushed, reason, _ = self._run(self._ticket(), {"sync_state": {}}, scope_eligible=False)
        self.assertFalse(pushed)
        self.assertIn("自动化范围", reason)

    def test_push_skipped_by_scene_switch(self):
        """场景开关未启用时不补发。"""
        pushed, reason, _ = self._run(self._ticket(), {"sync_state": {}}, scene_enabled=False)
        self.assertFalse(pushed)
        self.assertIn("未对场景", reason)

    def test_push_skipped_when_sent_once(self):
        """工单已发送过群推送（历史已有群消息）时不重复发送。"""
        meta = {"sync_state": {"group_push_sent_once": True}}
        pushed, reason, _ = self._run(self._ticket(), meta)
        self.assertFalse(pushed)
        self.assertIn("已发送过", reason)

    def test_push_skipped_when_auto_push_blocked(self):
        """自动推送被条件拦截（如推送条件不满足）时不补发。"""
        auto_result = {"skipped": True, "skipReason": "工单未满足自定义推送条件"}
        pushed, reason, _ = self._run(
            self._ticket(), {"sync_state": {}}, auto_result=auto_result
        )
        self.assertFalse(pushed)
        self.assertIn("推送条件", reason)

    def test_push_skipped_when_send_failed(self):
        """推送执行但无成功计数时视为失败。"""
        auto_result = {"skipped": False, "pushSuccessCount": 0, "chatSuccessCount": 0}
        pushed, reason, _ = self._run(
            self._ticket(), {"sync_state": {}}, auto_result=auto_result
        )
        self.assertFalse(pushed)
        self.assertIn("未产生成功发送", reason)


class TestAiResultReplyContent(unittest.TestCase):
    """AI 结果回帖模板渲染。"""

    def _ticket(self):
        return SimpleNamespace(
            ticket_no="INC-T-1",
            title="模板测试",
            ticket_url="http://t",
            module_name="POS",
            merchant_name="商家",
        )

    def test_success_default_template(self):
        """成功终态使用成功默认模板并渲染 AI 变量。"""
        content = TicketSyncNotifyService.build_ai_result_reply_content(
            ticket=self._ticket(),
            follow_up_config={"template": ""},
            ai_task_status="success",
            ai_result_payload={
                "analysis_summary": "SCO白屏为客户端渲染异常",
                "root_cause": "前端脚本加载失败",
                "fix_suggestion": "升级客户端补丁",
                "confidence": 0.85,
            },
        )
        self.assertIn("AI 分析成功", content)
        self.assertIn("SCO白屏为客户端渲染异常", content)
        self.assertIn("前端脚本加载失败", content)
        self.assertIn("0.85", content)

    def test_failed_default_template(self):
        """失败终态使用失败默认模板并渲染失败原因。"""
        content = TicketSyncNotifyService.build_ai_result_reply_content(
            ticket=self._ticket(),
            follow_up_config={"template": ""},
            ai_task_status="failed",
            ai_result_payload={},
            ai_error_message="Agent 连接超时",
        )
        self.assertIn("AI 分析失败", content)
        self.assertIn("Agent 连接超时", content)

    def test_custom_template_overrides(self):
        """自定义模板优先生效。"""
        content = TicketSyncNotifyService.build_ai_result_reply_content(
            ticket=self._ticket(),
            follow_up_config={"template": "结果[${ticket_no}]: ${analysis_summary}"},
            ai_task_status="success",
            ai_result_payload={"analysis_summary": "结论X"},
        )
        self.assertEqual(content, "结果[INC-T-1]: 结论X")

    def test_list_fields_joined(self):
        """列表字段转为分行文本。"""
        content = TicketSyncNotifyService.build_ai_result_reply_content(
            ticket=self._ticket(),
            follow_up_config={"template": "${next_steps}"},
            ai_task_status="success",
            ai_result_payload={"next_steps": ["步骤一", "步骤二"]},
        )
        self.assertEqual(content, "- 步骤一\n- 步骤二")


class TestAiResultReplyMessageStyle(unittest.TestCase):
    """消息形态开关：模板留空时按 messageStyle 决定卡片/纯文本，配置模板时始终纯文本。"""

    def _ticket(self):
        return SimpleNamespace(
            ticket_id=9001,
            ticket_no="INC-STYLE-1",
            title="形态开关测试",
            ticket_url="http://t",
            module_name="M",
            merchant_name="P",
            extra_data={"external_sync": {"sync_state": {}}},
        )

    def _run(self, follow_up_config):
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={"groupPush": {"appId": "app", "appSecret": "secret"}},
            ),
            patch.object(TicketSyncNotifyService, "resolve_feishu_auth", return_value=("app", "secret")),
            patch.object(TicketSyncNotifyService, "send_feishu_thread_reply") as send_reply,
            patch(
                f"{GROUP_PUSH_MODULE}.TicketGroupPushAnchorDao.list_anchors_by_ticket_id",
                return_value=[_make_anchor("om_a", "oc_1")],
            ),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.is_result_replied", return_value=False),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.mark_result_replied", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.update_result_replied_chat_ids", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.release_result_replied", return_value=True),
            patch(f"{GROUP_PUSH_MODULE}.TicketAiDao.has_any_result_replied", return_value=False),
        ):
            result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                _make_db(),
                ticket=self._ticket(),
                meta={"sync_state": {}},
                follow_up_config=follow_up_config,
                ai_task_status="success",
                ai_task_id=500,
                ai_result_payload={"analysis_summary": "结论A", "root_cause": "根因B"},
            )
        self.assertFalse(result["skipped"])
        return send_reply

    def test_default_style_is_card(self):
        """模板留空且未配置 messageStyle：默认发卡片（card 参数为卡片字典）。"""
        send_reply = self._run({"enabled": True, "sendOn": "always", "template": ""})
        self.assertEqual(send_reply.call_count, 1)
        self.assertIsInstance(send_reply.call_args.kwargs["card"], dict)

    def test_message_style_text_sends_plain_text(self):
        """模板留空且 messageStyle=text：发纯文本（card 参数为 None）。"""
        send_reply = self._run({"enabled": True, "sendOn": "always", "template": "", "messageStyle": "text"})
        self.assertEqual(send_reply.call_count, 1)
        self.assertIsNone(send_reply.call_args.kwargs["card"])
        self.assertIn("AI 分析成功", send_reply.call_args.kwargs["content"])

    def test_custom_template_forces_plain_text(self):
        """配置了自定义回帖模板：即使 messageStyle=card 也按模板发纯文本。"""
        send_reply = self._run(
            {"enabled": True, "sendOn": "always", "template": "T:${analysis_summary}", "messageStyle": "card"}
        )
        self.assertEqual(send_reply.call_count, 1)
        self.assertIsNone(send_reply.call_args.kwargs["card"])
        self.assertEqual(send_reply.call_args.kwargs["content"], "T:结论A")

    def test_card_fields_passed_to_builder(self):
        """卡片模式下 cardFields 白名单透传给卡片构造，未配置区块不渲染。"""
        send_reply = self._run(
            {
                "enabled": True, "sendOn": "always", "template": "",
                "messageStyle": "card", "cardFields": ["analysis_summary"],
            }
        )
        card = send_reply.call_args.kwargs["card"]
        # 提取文本时包含 fields 两列字段，确保"工单号"等区块确实未渲染。
        parts = []
        for element in card["elements"]:
            text = element.get("text")
            if isinstance(text, dict):
                parts.append(str(text.get("content", "")))
            for field in element.get("fields") or []:
                field_text = field.get("text") if isinstance(field, dict) else None
                if isinstance(field_text, dict):
                    parts.append(str(field_text.get("content", "")))
        joined = "\n".join(parts)
        self.assertIn("结论", joined)
        self.assertNotIn("工单号", joined)
        self.assertNotIn("置信度", joined)
        self.assertFalse(any(element.get("tag") == "action" for element in card["elements"]))


class TestAiResultReplyCardService(unittest.TestCase):
    """AI 结果回帖卡片构造与字段白名单。"""

    def _ticket(self):
        return SimpleNamespace(
            ticket_no="INC-CARD-1",
            title="卡片测试",
            ticket_url="http://t",
            module_name="POS",
            merchant_name="商家",
        )

    _PAYLOAD = {
        "analysis_summary": "结论A",
        "root_cause": "根因B",
        "fix_suggestion": "建议C",
        "evidence": ["证据1"],
        "risk_items": ["风险1"],
        "next_steps": ["步骤1"],
        "confidence": 0.8,
    }

    @staticmethod
    def _card_text(card) -> str:
        """把卡片 elements 的文本内容（含 fields 两列字段）拼成一段便于断言的文本。"""
        parts: list[str] = []
        for element in card["elements"]:
            text = element.get("text")
            if isinstance(text, dict):
                parts.append(str(text.get("content", "")))
            for field in element.get("fields") or []:
                field_text = field.get("text") if isinstance(field, dict) else None
                if isinstance(field_text, dict):
                    parts.append(str(field_text.get("content", "")))
        return "\n".join(parts)

    def test_normalize_card_fields(self):
        """字段白名单归一化：剔除未知字段、去重、留空返回空列表。"""
        service = TicketAiResultReplyCardService
        self.assertEqual(service.normalize_card_fields(None), [])
        self.assertEqual(service.normalize_card_fields(""), [])
        self.assertEqual(
            service.normalize_card_fields(["analysis_summary", "bad_key", "analysis_summary"]),
            ["analysis_summary"],
        )
        self.assertEqual(service.normalize_card_fields("root_cause, fix_suggestion"), ["root_cause", "fix_suggestion"])

    def test_default_card_contains_all_sections(self):
        """未配置字段时默认全量展示：工单信息/结论/根因/建议/依据/风险/后续/置信度/按钮。"""
        card = TicketAiResultReplyCardService.build_ai_result_reply_card(
            ticket=self._ticket(),
            ai_task_status="success",
            ai_result_payload=self._PAYLOAD,
        )
        joined = self._card_text(card)
        for keyword in ("工单号", "结论", "根因分析", "修复建议", "依据", "风险项", "后续动作"):
            self.assertIn(keyword, joined)
        self.assertTrue(any(element.get("tag") == "note" for element in card["elements"]))
        self.assertTrue(any(element.get("tag") == "action" for element in card["elements"]))

    def test_card_fields_subset_only_renders_selected(self):
        """配置字段白名单后只渲染对应区块，未配置区块不出现。"""
        card = TicketAiResultReplyCardService.build_ai_result_reply_card(
            ticket=self._ticket(),
            ai_task_status="success",
            ai_result_payload=self._PAYLOAD,
            card_fields=["root_cause", "ticket_link"],
        )
        joined = self._card_text(card)
        self.assertIn("根因分析", joined)
        for keyword in ("工单号", "结论", "修复建议", "依据", "风险项", "后续动作", "置信度"):
            self.assertNotIn(keyword, joined)
        self.assertTrue(any(element.get("tag") == "action" for element in card["elements"]))

    def test_invalid_card_fields_fallback_to_all(self):
        """字段配置全部无效时回退全量展示。"""
        card = TicketAiResultReplyCardService.build_ai_result_reply_card(
            ticket=self._ticket(),
            ai_task_status="success",
            ai_result_payload=self._PAYLOAD,
            card_fields=["bad_key"],
        )
        joined = self._card_text(card)
        self.assertIn("工单号", joined)
        self.assertIn("结论", joined)

    def test_failed_card_keeps_error_section(self):
        """失败卡片始终展示失败原因区块。"""
        card = TicketAiResultReplyCardService.build_ai_result_reply_card(
            ticket=self._ticket(),
            ai_task_status="failed",
            ai_error_message="超时",
            card_fields=["analysis_summary"],
        )
        joined = self._card_text(card)
        self.assertIn("失败原因", joined)
        self.assertIn("超时", joined)

    def test_config_normalization_message_style(self):
        """配置归一化：messageStyle 合法值校验、cardFields 剔除无效字段。"""
        from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService

        normalized = TicketSyncConfigService._normalize_ai_result_follow_up_config(
            {"messageStyle": "TEXT", "cardFields": ["ticket_info", "bad"]}
        )
        self.assertEqual(normalized["messageStyle"], "text")
        self.assertEqual(normalized["cardFields"], ["ticket_info"])
        normalized_default = TicketSyncConfigService._normalize_ai_result_follow_up_config(
            {"messageStyle": "unknown"}
        )
        self.assertEqual(normalized_default["messageStyle"], "card")
        self.assertEqual(normalized_default["cardFields"], [])


if __name__ == "__main__":
    unittest.main()
