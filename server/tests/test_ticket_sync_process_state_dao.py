"""
工单同步过程状态宽表 DAO（ticket_sync_process_state）的单元测试。

覆盖：发布域/推送域按域更新白名单、处理锁抢占（已发送/占用中/超时抢占）、
仅一次标记、行不存在默认态。
阶段 2b 存储地基的服务层切换尚未接入，本测试保证 DAO 行为契约先行稳定。
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from modules.ticket.dao.ticket_sync_process_state_dao import TicketSyncProcessStateDao


def _make_state_row(**overrides):
    """构造状态行 ORM 替身（默认态：可发布、未推送、无锁）。"""
    row = MagicMock()
    row.ticket_id = 1
    row.publish_ready = True
    row.publish_status = "ready"
    row.publish_reason = ""
    row.publish_updated_at = None
    row.ai_task_status = ""
    row.push_sent_once = False
    row.push_sent_at = None
    row.push_scene = ""
    row.push_revision = 0
    row.push_processing = False
    row.push_processing_at = None
    row.push_processing_scene = ""
    row.push_processing_revision = 0
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


class TestGetState(unittest.TestCase):
    """查询与默认态。"""

    def test_missing_row_returns_none(self):
        """行不存在返回 None（调用方按默认态处理）。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        self.assertIsNone(TicketSyncProcessStateDao.get_state(db, 1))
        self.assertIsNone(TicketSyncProcessStateDao.get_state(db, 0))

    def test_for_update_applies_row_lock(self):
        """for_update 走行级锁查询。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = _make_state_row()
        state = TicketSyncProcessStateDao.get_state(db, 1, for_update=True)
        self.assertIsNotNone(state)
        db.query.return_value.filter.return_value.with_for_update.assert_called_once()


class TestUpdatePublishState(unittest.TestCase):
    """发布域更新：仅触碰发布列。"""

    def test_update_creates_and_sets_publish_fields(self):
        """行不存在时创建并写入发布域字段。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
        with patch("modules.ticket.dao.ticket_sync_process_state_dao.TicketSyncProcessState") as state_cls:
            state_cls.return_value = _make_state_row()
            state = TicketSyncProcessStateDao.update_publish_state(
                db, 1, ready=False, status="processing_ai", reason="AI分析处理中", ai_task_status="running"
            )
        db.add.assert_called_once()
        self.assertFalse(state.publish_ready)
        self.assertEqual(state.publish_status, "processing_ai")
        self.assertEqual(state.ai_task_status, "running")
        self.assertIsNotNone(state.publish_updated_at)

    def test_ai_task_status_none_keeps_old_value(self):
        """ai_task_status=None 保持原值不变。"""
        db = MagicMock()
        row = _make_state_row(ai_task_status="success")
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = row
        state = TicketSyncProcessStateDao.update_publish_state(db, 1, ready=True, status="ready", reason="完成")
        self.assertEqual(state.ai_task_status, "success")


class TestUpdatePushFields(unittest.TestCase):
    """推送域更新：字段白名单。"""

    def test_rejects_non_push_fields(self):
        """非群推送域字段（如发布域）拒绝更新，防止跨域覆盖。"""
        db = MagicMock()
        with self.assertRaises(ValueError):
            TicketSyncProcessStateDao.update_push_fields(db, 1, {"publish_ready": False})

    def test_updates_allowed_fields(self):
        """白名单内字段正常更新。"""
        db = MagicMock()
        row = _make_state_row()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = row
        state = TicketSyncProcessStateDao.update_push_fields(
            db, 1, {"push_sent_once": True, "push_scene": "bitable_pull"}
        )
        self.assertTrue(state.push_sent_once)
        self.assertEqual(state.push_scene, "bitable_pull")


class TestPushProcessingLock(unittest.TestCase):
    """处理锁：抢占/占用/超时。"""

    def test_acquire_fails_when_sent_once(self):
        """已发送过群推送：抢锁直接失败（already_sent）。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = _make_state_row(
            push_sent_once=True
        )
        acquired, reason, _ = TicketSyncProcessStateDao.acquire_push_processing_lock(db, 1, scene="s", revision=1)
        self.assertFalse(acquired)
        self.assertEqual(reason, "already_sent")

    def test_acquire_fails_when_locked_recently(self):
        """锁被占用且未超时：失败。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = _make_state_row(
            push_processing=True, push_processing_at=datetime.now() - timedelta(seconds=10)
        )
        acquired, reason, _ = TicketSyncProcessStateDao.acquire_push_processing_lock(db, 1, scene="s", revision=1)
        self.assertFalse(acquired)
        self.assertEqual(reason, "group_push_processing")

    def test_acquire_steals_stale_lock(self):
        """锁超时视为残留：可抢占。"""
        db = MagicMock()
        row = _make_state_row(push_processing=True, push_processing_at=datetime.now() - timedelta(seconds=600))
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = row
        acquired, reason, state = TicketSyncProcessStateDao.acquire_push_processing_lock(
            db, 1, scene="bitable_pull", revision=3
        )
        self.assertTrue(acquired)
        self.assertTrue(state.push_processing)
        self.assertEqual(state.push_processing_scene, "bitable_pull")
        self.assertEqual(state.push_processing_revision, 3)

    def test_release_is_idempotent(self):
        """释放锁幂等：未持锁时无操作。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _make_state_row(push_processing=False)
        state = TicketSyncProcessStateDao.release_push_processing_lock(db, 1)
        self.assertFalse(state.push_processing)

    def test_mark_sent_once_clears_lock(self):
        """仅一次标记同时清掉处理锁。"""
        db = MagicMock()
        row = _make_state_row(push_processing=True, push_processing_at=datetime.now())
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = row
        state = TicketSyncProcessStateDao.mark_push_sent_once(db, 1, scene="external_sync", revision=2)
        self.assertTrue(state.push_sent_once)
        self.assertIsNotNone(state.push_sent_at)
        self.assertFalse(state.push_processing)
        self.assertIsNone(state.push_processing_at)


class TestListStatesForPull(unittest.TestCase):
    """批量查询（delivery 拉取链路）。"""

    def test_empty_ids_returns_empty(self):
        self.assertEqual(TicketSyncProcessStateDao.list_states_for_pull(MagicMock(), []), {})

    def test_maps_by_ticket_id(self):
        db = MagicMock()
        rows = [_make_state_row(), _make_state_row()]
        rows[0].ticket_id = 1
        rows[1].ticket_id = 2
        db.query.return_value.filter.return_value.all.return_value = rows
        mapping = TicketSyncProcessStateDao.list_states_for_pull(db, [1, 2, 3])
        self.assertEqual(set(mapping.keys()), {1, 2})


if __name__ == "__main__":
    unittest.main()
