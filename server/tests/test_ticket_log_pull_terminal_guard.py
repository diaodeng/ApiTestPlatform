"""日志拉取终态写入防护测试。

验证 _update_status / _update_record_if_not_terminal 的条件更新语义：
- 记录已被人工停止（cancelled）后，非终态更新与重复终态覆盖应被拦截；
- 活动状态记录正常流转不受影响。
"""

from __future__ import annotations

from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService


class FakeQuery:
    """模拟 ORM 查询链，按预设记录状态决定条件更新是否命中。"""

    def __init__(self, current_status: str, updated: dict):
        self.current_status = current_status
        self.updated = updated

    def options(self, *args, **kwargs):
        """忽略延迟列配置。"""
        return self

    def filter(self, *args, **kwargs):
        """记录过滤条件，不做真实判断（状态判断由服务层语义测试覆盖）。"""
        return self

    def update(self, data):
        """仅当记录当前不是终态时模拟写入成功。"""
        terminal = {"success", "failed", "exception", "cancelled"}
        if self.current_status in terminal:
            return 0
        self.updated.update(data)
        return 1


class FakeDb:
    """模拟仅具备 update 用法的最小数据库会话。"""

    def __init__(self, current_status: str):
        self.current_status = current_status
        self.updated: dict = {}
        self.commit_count = 0

    def query(self, *args, **kwargs):
        """返回预设状态的查询链。"""
        return FakeQuery(self.current_status, self.updated)

    def commit(self):
        """记录 commit 次数。"""
        self.commit_count += 1


def test_update_status_blocked_after_manual_cancel():
    """人工停止（cancelled）后，后台线程的轮询字段更新应被条件更新拦截。"""
    db = FakeDb("cancelled")
    TicketLogPullService._update_status(
        db,
        123,
        status_desc="已提交申请，轮询外部平台处理中",
        last_polled_at="2026-09-09 10:00:00",
    )
    assert db.updated == {}


def test_update_status_blocked_success_overwrite_after_cancel():
    """人工停止后，下载线程把状态覆盖为 success 的写入应被拦截。"""
    db = FakeDb("cancelled")
    written = TicketLogPullService._update_record_if_not_terminal(
        db,
        123,
        {"status": "success", "status_desc": "日志拉取完成"},
    )
    assert written is False
    assert db.updated == {}


def test_update_status_allows_normal_active_transition():
    """活动状态记录的正常状态流转应正常写入。"""
    db = FakeDb("polling")
    TicketLogPullService._update_status(
        db,
        124,
        status="downloading",
        status_desc="正在下载日志压缩包",
    )
    assert db.updated.get("status") == "downloading"


def test_update_status_terminal_write_passes_unconditionally():
    """失败处理等终态写入应无条件执行（由调用链保证语义）。"""
    db = FakeDb("cancelled")
    db.query = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("终态写入不应走条件更新"))
    updated: dict = {}

    def fake_dao_update(db2, record_id, data):
        updated.update(data)

    from modules.ticket.dao import ticket_log_pull_dao

    original = ticket_log_pull_dao.TicketLogPullDao.update_record
    ticket_log_pull_dao.TicketLogPullDao.update_record = staticmethod(fake_dao_update)
    try:
        TicketLogPullService._update_status(db, 125, status="failed", status_desc="外部平台日志拉取失败")
    finally:
        ticket_log_pull_dao.TicketLogPullDao.update_record = original
    assert updated.get("status") == "failed"
