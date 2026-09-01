"""日志拉取提示快照（log_pull_hints）回填测试。"""
import unittest
from types import SimpleNamespace

from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService


class _EmptyQuery:
    """空查询桩，避免 build_upsert_payload 内部查询数据库。"""

    def filter(self, *args, **kwargs):
        return self

    def first(self, *args, **kwargs):
        return None


class RefreshLogPullHintsTests(unittest.TestCase):
    """refresh_log_pull_hints 提示快照刷新测试。"""

    def _build_sync_object(self, log_pull_config: dict) -> TicketExternalSyncUpsertModel:
        return TicketExternalSyncUpsertModel.model_validate(
            {
                "ticketNo": "INC-TEST-HINTS",
                "source": {"system": "test"},
                "description": "描述",
                "rawPayload": {"fields": {"(IT)StoreCode": [{"text": "215376", "type": "text"}]}},
                "logPullConfig": log_pull_config,
            }
        )

    def test_refresh_hints_includes_ai_extracted_pos_and_modify_time(self):
        """AI 回填后的 log_pull_config（含 posNo/modifyTime）应完整进入提示快照。

        对应 INC00001904725 问题：延后处理执行 AI 提取后未重建 log_pull_hints，
        详情页手动拉日志弹窗读不到提取出的机台和日期。
        """
        sync_object = self._build_sync_object(
            {
                "sourceStoreCode": "215376",
                "storeId": "188",
                "vendorId": 5,
                "posNo": 63,
                "modifyTime": "2026-08-29",
            }
        )
        extra_data = {"log_pull_hints": {"vendorId": 5, "storeId": "188", "sourceStoreCode": "215376"}}

        hints = TicketSyncPayloadService.refresh_log_pull_hints(
            extra_data=extra_data,
            sync_object=sync_object,
            detected={"vendorId": 5, "storeId": "188"},
            incoming_project_value=False,
        )

        self.assertEqual(hints["posNo"], 63)
        self.assertEqual(hints["modifyTime"], "2026-08-29")
        self.assertEqual(hints["storeId"], "188")
        self.assertEqual(hints["vendorId"], 5)
        self.assertEqual(hints["sourceStoreCode"], "215376")

    def test_refresh_hints_falls_back_to_sco_no(self):
        """log_pull_config 只有 scoNo 时，提示快照 posNo 使用 scoNo 的值。"""
        sync_object = self._build_sync_object(
            {
                "storeId": "188",
                "scoNo": 64,
                "modifyTime": "2026-08-29",
            }
        )

        hints = TicketSyncPayloadService.refresh_log_pull_hints(
            extra_data={},
            sync_object=sync_object,
            detected={"storeId": "188"},
            incoming_project_value=False,
        )

        self.assertEqual(hints["posNo"], 64)
        self.assertEqual(hints["modifyTime"], "2026-08-29")

    def test_refresh_hints_keeps_existing_hints_when_no_new_values(self):
        """AI 未提取到机台时应保留已有提示快照，不覆盖或清空。"""
        sync_object = self._build_sync_object({"storeId": "188"})
        extra_data = {"log_pull_hints": {"vendorId": 5, "storeId": "188", "posNo": 7, "modifyTime": "2026-08-01"}}

        hints = TicketSyncPayloadService.refresh_log_pull_hints(
            extra_data=extra_data,
            sync_object=sync_object,
            detected={"vendorId": 5, "storeId": "188"},
            incoming_project_value=False,
        )

        self.assertEqual(hints["posNo"], 7)
        self.assertEqual(hints["modifyTime"], "2026-08-01")

    def test_build_upsert_payload_writes_refreshed_hints_to_extra_data(self):
        """主入库路径的 payload.extra_data 应包含刷新后的提示快照。"""
        sync_object = self._build_sync_object(
            {
                "sourceStoreCode": "215376",
                "storeId": "188",
                "posNo": 63,
                "modifyTime": "2026-08-29",
            }
        )
        current_user = SimpleNamespace(user=SimpleNamespace(user_id=1, user_name="tester", nick_name=""))

        payload, _meta, _revision = TicketSyncPayloadService.build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=None,
            sync_object=sync_object,
            detected={"vendorId": 5, "storeId": "188"},
            current_user=current_user,
            sync_scene="bitable_pull",
        )

        hints = payload["extra_data"].get("log_pull_hints")
        self.assertIsNotNone(hints)
        self.assertEqual(hints["posNo"], 63)
        self.assertEqual(hints["modifyTime"], "2026-08-29")


if __name__ == "__main__":
    unittest.main()
