"""
AI 终态群推送场景解析与同步元数据场景持久化的单元测试。

背景：bitable_pull 场景工单的 AI 任务完成后，群推送回调曾硬编码 external_sync 场景，
被 sendAfterExternalSync=false 配置静默拦截（日志无工单号，无法定位）。
修复后场景随入库持久化到 sync_state.sync_scene，AI 终态回调按真实场景推送。
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService


class TestResolveSyncSceneFromMeta(unittest.TestCase):
    """resolve_sync_scene_from_meta 的场景解析测试。"""

    def test_persisted_scene_takes_priority(self):
        """入库时持久化的 sync_scene 优先于任何推断。"""
        meta = {
            "sourceSystem": "external",
            "sync_state": {"sync_scene": "bitable_pull"},
        }
        self.assertEqual(TicketSyncGroupPushService.resolve_sync_scene_from_meta(meta), "bitable_pull")

    def test_invalid_persisted_scene_falls_back_to_source_system(self):
        """持久化场景不是合法枚举时回退按来源系统推断。"""
        meta = {
            "sourceSystem": "feishu_bitable_pull",
            "sync_state": {"sync_scene": "unknown_scene"},
        }
        self.assertEqual(TicketSyncGroupPushService.resolve_sync_scene_from_meta(meta), "bitable_pull")

    def test_bitable_pull_source_system_inferred(self):
        """历史工单无 sync_scene 时，feishu_bitable_pull 来源推断为 bitable_pull。"""
        meta = {
            "sourceSystem": "feishu_bitable_pull",
            "sync_state": {},
        }
        self.assertEqual(TicketSyncGroupPushService.resolve_sync_scene_from_meta(meta), "bitable_pull")

    def test_manual_create_source_system_inferred(self):
        """历史工单无 sync_scene 时，manual_create 来源推断为 manual_create。"""
        meta = {
            "source": {"system": "manual_create"},
            "sync_state": {},
        }
        self.assertEqual(TicketSyncGroupPushService.resolve_sync_scene_from_meta(meta), "manual_create")

    def test_external_source_defaults_to_external_sync(self):
        """无法区分的外部来源默认 external_sync，与历史行为一致。"""
        meta = {
            "sourceSystem": "external",
            "sync_state": {},
        }
        self.assertEqual(TicketSyncGroupPushService.resolve_sync_scene_from_meta(meta), "external_sync")

    def test_empty_meta_defaults_to_external_sync(self):
        """空元数据默认 external_sync，不抛异常。"""
        self.assertEqual(TicketSyncGroupPushService.resolve_sync_scene_from_meta({}), "external_sync")


class TestBuildMetaSyncScenePassthrough(unittest.TestCase):
    """两处 build_meta 白名单重建后必须保留 sync_scene 字段。"""

    def test_payload_build_meta_keeps_sync_scene(self):
        """TicketSyncPayloadService.build_meta 保留已有 sync_scene。"""
        extra_data = {
            "external_sync": {
                "sync_state": {
                    "sync_scene": "bitable_pull",
                    "publish_ready": True,
                }
            }
        }
        meta = TicketSyncPayloadService.build_meta(extra_data)
        self.assertEqual(meta["sync_state"]["sync_scene"], "bitable_pull")

    def test_group_push_build_meta_keeps_sync_scene(self):
        """TicketSyncGroupPushService.build_meta 保留已有 sync_scene。"""
        extra_data = {
            "external_sync": {
                "sync_state": {
                    "sync_scene": "remote_pull",
                    "group_push_sent_once": True,
                }
            }
        }
        meta = TicketSyncGroupPushService.build_meta(extra_data)
        self.assertEqual(meta["sync_state"]["sync_scene"], "remote_pull")

    def test_group_push_build_meta_defaults_empty_sync_scene(self):
        """历史元数据没有 sync_scene 时补空字符串，不抛异常。"""
        extra_data = {"external_sync": {"sync_state": {}}}
        meta = TicketSyncGroupPushService.build_meta(extra_data)
        self.assertEqual(meta["sync_state"]["sync_scene"], "")


class TestFinalizeSyncAfterAiSceneResolution(unittest.TestCase):
    """finalize_sync_after_ai 必须用工单元数据里的真实场景触发群推送。"""

    def _build_ticket(self, sync_scene: str | None):
        """构造带同步元数据的最小工单对象。"""
        sync_state = {"sync_scene": sync_scene} if sync_scene else {}
        extra_data = {
            "external_sync": {
                "revision": 3,
                "sourceSystem": "feishu_bitable_pull",
                "sync_state": {
                    **sync_state,
                    "publish_ready": False,
                    "publish_status": "processing_ai",
                    "automation": {
                        "steps": {
                            "ai_analysis": {"status": "queued", "detail": {"via": "log_pull_auto_ai"}},
                        },
                    },
                },
            }
        }
        return SimpleNamespace(
            ticket_id=2047632318114816,
            ticket_no="INC00001929286",
            module_id=None,
            module_name="POS-客户端",
            extra_data=extra_data,
        )

    def test_finalize_after_ai_uses_persisted_scene(self):
        """AI 成功后按持久化的 bitable_pull 场景触发群推送，而不是 external_sync。"""
        ticket = self._build_ticket("bitable_pull")
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketDao.get_ticket_by_id",
                return_value=ticket,
            ),
            patch.object(TicketSyncGroupPushService, "persist_sync_meta", return_value=ticket),
            patch.object(TicketSyncGroupPushService, "resolve_ai_pending_state", return_value=(False, "success")),
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={
                    "automationScope": {"enabled": True, "moduleNameIncludes": ["POS"]},
                    "groupPush": {
                        "enabled": True,
                        "sendAfterExternalSync": False,
                        "sendAfterBitablePull": True,
                    },
                },
            ),
            patch.object(
                TicketSyncGroupPushService,
                "send_auto_group_message_once",
                return_value=({"skipped": False, "pushSuccessCount": 1}, ticket, {}),
            ) as send_auto_push,
        ):
            TicketSyncGroupPushService.finalize_sync_after_ai(
                SimpleNamespace(),
                ticket_id=ticket.ticket_id,
                ai_task_status="success",
            )

        send_auto_push.assert_called_once()
        self.assertEqual(send_auto_push.call_args.kwargs["scene"], "bitable_pull")

    def test_finalize_after_ai_infers_scene_from_source_system(self):
        """历史工单没有持久化场景时，按来源系统推断 bitable_pull。"""
        ticket = self._build_ticket(None)
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketDao.get_ticket_by_id",
                return_value=ticket,
            ),
            patch.object(TicketSyncGroupPushService, "persist_sync_meta", return_value=ticket),
            patch.object(TicketSyncGroupPushService, "resolve_ai_pending_state", return_value=(False, "success")),
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={
                    "automationScope": {"enabled": True, "moduleNameIncludes": ["POS"]},
                    "groupPush": {
                        "enabled": True,
                        "sendAfterExternalSync": False,
                        "sendAfterBitablePull": True,
                    },
                },
            ),
            patch.object(
                TicketSyncGroupPushService,
                "send_auto_group_message_once",
                return_value=({"skipped": False, "pushSuccessCount": 1}, ticket, {}),
            ) as send_auto_push,
        ):
            TicketSyncGroupPushService.finalize_sync_after_ai(
                SimpleNamespace(),
                ticket_id=ticket.ticket_id,
                ai_task_status="success",
            )

        send_auto_push.assert_called_once()
        self.assertEqual(send_auto_push.call_args.kwargs["scene"], "bitable_pull")

    def test_finalize_after_ai_explicit_scene_overrides_meta(self):
        """显式传入 sync_scene 时优先使用，不读元数据。"""
        ticket = self._build_ticket("bitable_pull")
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketDao.get_ticket_by_id",
                return_value=ticket,
            ),
            patch.object(TicketSyncGroupPushService, "persist_sync_meta", return_value=ticket),
            patch.object(TicketSyncGroupPushService, "resolve_ai_pending_state", return_value=(False, "success")),
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={
                    "automationScope": {"enabled": True, "moduleNameIncludes": ["POS"]},
                    "groupPush": {"enabled": True, "sendAfterExternalSync": True},
                },
            ),
            patch.object(
                TicketSyncGroupPushService,
                "send_auto_group_message_once",
                return_value=({"skipped": False, "pushSuccessCount": 1}, ticket, {}),
            ) as send_auto_push,
        ):
            TicketSyncGroupPushService.finalize_sync_after_ai(
                SimpleNamespace(),
                ticket_id=ticket.ticket_id,
                ai_task_status="success",
                sync_scene="remote_pull",
            )

        send_auto_push.assert_called_once()
        self.assertEqual(send_auto_push.call_args.kwargs["scene"], "remote_pull")


class TestApplyAiTerminalStatusToAutomationStep(unittest.TestCase):
    """AI 终态回写 automation.steps.ai_analysis 的测试。"""

    def test_queued_step_updated_to_success(self):
        """AI 成功终态把 queued 步骤更新为 success，自动化整体收敛 completed。"""
        meta = {
            "sync_state": {
                "automation": {
                    "steps": {
                        "identify": {"status": "success"},
                        "ai_analysis": {"status": "queued", "detail": {"via": "log_pull_auto_ai"}},
                    },
                },
            }
        }
        updated = TicketSyncGroupPushService._apply_ai_terminal_status_to_automation_step(meta, "success")
        ai_step = updated["sync_state"]["automation"]["steps"]["ai_analysis"]
        self.assertEqual(ai_step["status"], "success")
        self.assertEqual(updated["sync_state"]["automation"]["status"], "completed")

    def test_failed_step_marks_automation_failed(self):
        """AI 失败终态把步骤更新为 failed，自动化整体标记 failed。"""
        meta = {
            "sync_state": {
                "automation": {
                    "steps": {
                        "identify": {"status": "success"},
                        "ai_analysis": {"status": "running"},
                    },
                },
            }
        }
        updated = TicketSyncGroupPushService._apply_ai_terminal_status_to_automation_step(meta, "failed")
        self.assertEqual(updated["sync_state"]["automation"]["steps"]["ai_analysis"]["status"], "failed")
        self.assertEqual(updated["sync_state"]["automation"]["status"], "failed")

    def test_other_running_steps_keep_automation_running(self):
        """其他步骤仍在运行时，AI 终态不把自动化整体置为 completed。"""
        meta = {
            "sync_state": {
                "automation": {
                    "steps": {
                        "identify": {"status": "success"},
                        "log_pull": {"status": "running"},
                        "ai_analysis": {"status": "queued"},
                    },
                },
            }
        }
        updated = TicketSyncGroupPushService._apply_ai_terminal_status_to_automation_step(meta, "canceled")
        self.assertEqual(updated["sync_state"]["automation"]["steps"]["ai_analysis"]["status"], "canceled")
        self.assertNotEqual(updated["sync_state"]["automation"]["status"], "completed")

    def test_missing_ai_step_is_noop(self):
        """元数据没有 ai_analysis 步骤时原样返回。"""
        meta = {"sync_state": {"automation": {"steps": {"identify": {"status": "success"}}}}}
        updated = TicketSyncGroupPushService._apply_ai_terminal_status_to_automation_step(meta, "success")
        self.assertEqual(updated, meta)

    def test_pending_status_is_noop(self):
        """非终态状态不回写步骤。"""
        meta = {
            "sync_state": {
                "automation": {
                    "steps": {"ai_analysis": {"status": "queued"}},
                },
            }
        }
        updated = TicketSyncGroupPushService._apply_ai_terminal_status_to_automation_step(meta, "running")
        self.assertEqual(updated["sync_state"]["automation"]["steps"]["ai_analysis"]["status"], "queued")
