"""
AI 分析结果话题回帖（aiResultFollowUp）的单元测试。

覆盖：sendOn 四枚举匹配、手动三态覆盖、task_id 幂等、无锚点降级跳过（策略B）、
多群去重回帖、配置归一化、模板渲染。
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService


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
    """task_id 幂等标记。"""

    def test_mark_and_check(self):
        """标记后同 task_id 命中、不同 task_id 不命中。"""
        meta = {"sync_state": {}}
        self.assertFalse(TicketSyncGroupPushService.is_ai_result_replied(meta, task_id=1))
        meta = TicketSyncGroupPushService.mark_ai_result_replied(meta, task_id=1)
        self.assertTrue(TicketSyncGroupPushService.is_ai_result_replied(meta, task_id=1))
        self.assertFalse(TicketSyncGroupPushService.is_ai_result_replied(meta, task_id=2))
        self.assertIsNone(TicketSyncGroupPushService.is_ai_result_replied({}, task_id=None) is not None and None)

    def test_mark_keeps_recent_50(self):
        """幂等列表保留最近 50 条防止元数据无限增长。"""
        meta = {"sync_state": {}}
        for task_id in range(1, 61):
            meta = TicketSyncGroupPushService.mark_ai_result_replied(meta, task_id=task_id)
        replied = meta["sync_state"]["ai_result_reply_task_ids"]
        self.assertEqual(len(replied), 50)
        self.assertFalse(TicketSyncGroupPushService.is_ai_result_replied(meta, task_id=1))
        self.assertTrue(TicketSyncGroupPushService.is_ai_result_replied(meta, task_id=60))


class TestCollectAiResultReplyTargets(unittest.TestCase):
    """回帖目标收集：空锚点过滤与按群去重。"""

    def test_dedup_by_chat_and_skip_empty(self):
        """同群多条锚点只回一次；空 messageId 锚点跳过。"""
        meta = {
            "sync_state": {
                "group_push_message_refs": [
                    {"messageId": "om_a", "rootId": "om_a", "chatId": "oc_1"},
                    {"messageId": "om_b", "rootId": "om_b", "chatId": "oc_1"},
                    {"messageId": "om_c", "rootId": "om_c", "chatId": "oc_2"},
                    {"messageId": "", "rootId": "", "chatId": "oc_3"},
                ]
            }
        }
        targets = TicketSyncGroupPushService._collect_ai_result_reply_targets(meta)
        self.assertEqual([t["messageId"] for t in targets], ["om_a", "om_c"])

    def test_no_refs_returns_empty(self):
        """无锚点返回空列表。"""
        self.assertEqual(TicketSyncGroupPushService._collect_ai_result_reply_targets({"sync_state": {}}), [])


class TestSendAiResultThreadReply(unittest.TestCase):
    """send_ai_result_thread_reply 主流程。"""

    def _ticket(self, refs=None, replied_ids=None):
        sync_state = {}
        if refs is not None:
            sync_state["group_push_message_refs"] = refs
        if replied_ids is not None:
            sync_state["ai_result_reply_task_ids"] = replied_ids
        return SimpleNamespace(
            ticket_id=1,
            ticket_no="INC-R-1",
            title="回帖测试",
            ticket_url="http://t",
            module_name="M",
            merchant_name="P",
            extra_data={"external_sync": {"sync_state": sync_state}},
        )

    def _run(self, ticket, follow_up_config, status="success", task_id=100):
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={"groupPush": {"appId": "app", "appSecret": "secret"}},
            ),
            patch.object(TicketSyncNotifyService, "resolve_feishu_auth", return_value=("app", "secret")),
            patch.object(TicketSyncNotifyService, "send_feishu_thread_reply") as send_reply,
            patch.object(TicketSyncGroupPushService, "persist_sync_meta", side_effect=lambda db, **kw: kw["ticket"]),
        ):
            result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                SimpleNamespace(),
                ticket=ticket,
                meta={"sync_state": ticket.extra_data["external_sync"]["sync_state"]},
                follow_up_config=follow_up_config,
                ai_task_status=status,
                ai_task_id=task_id,
                ai_result_payload={"analysis_summary": "摘要"},
            )
        return result, send_reply

    def test_reply_skipped_when_send_on_none(self):
        """sendOn=none 时跳过且不发送。"""
        result, send_reply = self._run(
            self._ticket(refs=[{"messageId": "om_a", "rootId": "om_a", "chatId": "oc_1"}]),
            {"enabled": True, "sendOn": "none", "replyInThread": True, "template": ""},
        )
        self.assertTrue(result["skipped"])
        send_reply.assert_not_called()

    def test_reply_skipped_when_no_anchor(self):
        """无锚点且策略为 skip（默认）：跳过，不新建话题。"""
        result, send_reply = self._run(
            self._ticket(refs=[]),
            {"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
        )
        self.assertTrue(result["skipped"])
        self.assertIn("锚点", result["skipReason"])
        send_reply.assert_not_called()

    def test_reply_skipped_when_task_replied(self):
        """同 task_id 已回帖过：幂等跳过。"""
        result, send_reply = self._run(
            self._ticket(refs=[{"messageId": "om_a", "rootId": "om_a", "chatId": "oc_1"}], replied_ids=["100"]),
            {"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
        )
        self.assertTrue(result["skipped"])
        self.assertIn("已回帖", result["skipReason"])
        send_reply.assert_not_called()

    def test_reply_sends_to_each_deduped_group(self):
        """正常回帖：按去重后的目标群逐个发送并标记 task_id。"""
        ticket = self._ticket(
            refs=[
                {"messageId": "om_a", "rootId": "om_a", "chatId": "oc_1"},
                {"messageId": "om_b", "rootId": "om_b", "chatId": "oc_1"},
                {"messageId": "om_c", "rootId": "om_c", "chatId": "oc_2"},
            ]
        )
        result, send_reply = self._run(
            ticket,
            {"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
        )
        self.assertFalse(result["skipped"])
        self.assertEqual(result["targetCount"], 2)
        self.assertEqual(result["successCount"], 2)
        self.assertEqual(send_reply.call_count, 2)
        called_message_ids = [call.kwargs["message_id"] for call in send_reply.call_args_list]
        self.assertEqual(called_message_ids, ["om_a", "om_c"])

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
                patch.object(
                    TicketSyncGroupPushService, "persist_sync_meta", side_effect=lambda db, **kw: kw["ticket"]
                ),
            ):
                result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                    SimpleNamespace(),
                    ticket=self._ticket(
                        refs=[
                            {"messageId": "om_a", "rootId": "om_a", "chatId": "oc_1"},
                            {"messageId": "om_c", "rootId": "om_c", "chatId": "oc_2"},
                        ]
                    ),
                    meta={
                        "sync_state": {
                            "group_push_message_refs": [
                                {"messageId": "om_a", "rootId": "om_a", "chatId": "oc_1"},
                                {"messageId": "om_c", "rootId": "om_c", "chatId": "oc_2"},
                            ]
                        }
                    },
                    follow_up_config={"enabled": True, "sendOn": "always", "replyInThread": True, "template": ""},
                    ai_task_status="success",
                    ai_task_id=200,
                    ai_result_payload={},
                )
        self.assertEqual(result["targetCount"], 2)
        self.assertEqual(result["successCount"], 1)


class TestSendAiResultReplyNoAnchorStrategy(unittest.TestCase):
    """无锚点策略：skip 跳过 / send_then_reply 先补发再回帖。"""

    def _ticket(self, refs=None):
        sync_state = {}
        if refs is not None:
            sync_state["group_push_message_refs"] = refs
        return SimpleNamespace(
            ticket_id=1,
            ticket_no="INC-NA-1",
            title="无锚点策略测试",
            ticket_url="http://t",
            module_name="M",
            merchant_name="P",
            extra_data={"external_sync": {"sync_state": sync_state}},
        )

    def _config(self, strategy):
        return {
            "enabled": True,
            "sendOn": "always",
            "replyInThread": True,
            "template": "",
            "noAnchorStrategy": strategy,
        }

    def _run_with_push(self, ticket, meta, follow_up_config, push_result=None):
        """打桩补发方法与回帖发送，执行回帖主流程。"""
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
            patch.object(
                TicketSyncGroupPushService, "persist_sync_meta", side_effect=lambda db, **kw: kw["ticket"]
            ),
        ):
            result, _, _ = TicketSyncGroupPushService.send_ai_result_thread_reply(
                SimpleNamespace(),
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
        ticket = self._ticket(refs=[])
        meta = {"sync_state": {}}
        result, send_push, send_reply = self._run_with_push(ticket, meta, self._config("skip"))
        self.assertTrue(result["skipped"])
        self.assertIn("锚点", result["skipReason"])
        send_push.assert_not_called()
        send_reply.assert_not_called()

    def test_send_then_reply_pushes_and_replies(self):
        """策略 send_then_reply：补发成功（返回带锚点的 meta）后继续回帖。"""
        ticket = self._ticket(refs=[])
        meta = {"sync_state": {}}
        pushed_meta = {
            "sync_state": {
                "group_push_message_refs": [
                    {"messageId": "om_new", "rootId": "om_new", "chatId": "oc_new"}
                ]
            }
        }
        result, send_push, send_reply = self._run_with_push(
            ticket,
            meta,
            self._config("send_then_reply"),
            push_result=(True, ticket, pushed_meta, ""),
        )
        send_push.assert_called_once()
        self.assertFalse(result["skipped"])
        self.assertEqual(result["successCount"], 1)
        send_reply.assert_called_once()
        self.assertEqual(send_reply.call_args.kwargs["message_id"], "om_new")

    def test_send_then_reply_skips_when_push_blocked(self):
        """策略 send_then_reply：补发被拦截（范围/条件/已发送过）时跳过回帖。"""
        ticket = self._ticket(refs=[])
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
        """策略 send_then_reply：补发返回成功但元数据仍无锚点时跳过（防御分支）。"""
        ticket = self._ticket(refs=[])
        meta = {"sync_state": {}}
        result, send_push, send_reply = self._run_with_push(
            ticket,
            meta,
            self._config("send_then_reply"),
            push_result=(True, ticket, {"sync_state": {}}, ""),
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


if __name__ == "__main__":
    unittest.main()
