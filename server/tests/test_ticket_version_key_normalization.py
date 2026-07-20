from types import SimpleNamespace
from unittest.mock import patch

from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.log_pull.ticket_log_post_process_service import TicketLogPostProcessService
from modules.ticket.util.ticket_common_util import normalize_ticket_version_key, resolve_ticket_current_version_key


def test_normalize_ticket_version_key_filters_field_label():
    """版本号归一化应过滤字段名，避免把 version 当成有效版本。"""
    assert normalize_ticket_version_key("version") == ""
    assert normalize_ticket_version_key("版本号") == ""
    assert normalize_ticket_version_key("release/2.3.4") == "release/2.3.4"


def test_resolve_ticket_current_version_key_prefers_affected_version():
    """工单当前版本应优先读取主表发生版本，扩展字段仅作为兼容兜底。"""
    ticket = SimpleNamespace(affected_version="2.0.0", extra_data={"version_key": "1.0.0"})

    assert resolve_ticket_current_version_key(ticket) == "2.0.0"


def test_post_download_extract_skips_when_ticket_has_affected_version(tmp_path):
    """日志下载后版本提取发现工单已有发生版本时，不应继续扫描日志文件。"""
    log_file = tmp_path / "app.log"
    log_file.write_text("version: 9.9.9\n", encoding="utf-8")
    ticket = SimpleNamespace(affected_version="1.2.3", extra_data={})

    with (
        patch(
            "modules.ticket.service.log_pull.ticket_log_post_process_service.TicketDao.get_ticket_by_id",
            return_value=ticket,
        ),
        patch.object(TicketLogPostProcessService, "extract_version_key_from_files") as extract_mock,
        patch("modules.ticket.service.log_pull.ticket_log_post_process_service.TicketDao.update_ticket") as update_mock,
    ):
        version_key = TicketLogPostProcessService.extract_and_update_version_key(
            SimpleNamespace(),
            ticket_id=1001,
            record_id=2001,
            log_files=[log_file],
        )

    assert version_key == "1.2.3"
    extract_mock.assert_not_called()
    update_mock.assert_not_called()


def test_post_download_extract_writes_affected_version_and_compat_extra(tmp_path):
    """日志下载后提取成功时，应写主表发生版本并保留兼容 extra_data.version_key。"""
    log_file = tmp_path / "app.log"
    log_file.write_text("version: release/2.3.4\n", encoding="utf-8")
    ticket = SimpleNamespace(affected_version="", extra_data={})

    with (
        patch(
            "modules.ticket.service.log_pull.ticket_log_post_process_service.TicketDao.get_ticket_by_id",
            return_value=ticket,
        ),
        patch("modules.ticket.service.log_pull.ticket_log_post_process_service.TicketDao.update_ticket") as update_mock,
    ):
        version_key = TicketLogPostProcessService.extract_and_update_version_key(
            SimpleNamespace(),
            ticket_id=1001,
            record_id=2001,
            log_files=[log_file],
        )

    assert version_key == "release/2.3.4"
    update_payload = update_mock.call_args.args[2]
    assert update_payload["affected_version"] == "release/2.3.4"
    assert update_payload["extra_data"]["version_key"] == "release/2.3.4"


def test_post_download_extract_ignores_plain_version_label(tmp_path):
    """日志版本提取应忽略普通 version 字段名并继续查找后续有效版本。"""
    log_file = tmp_path / "app.log"
    log_file.write_text("version: version\napp version: 3.4.5\n", encoding="utf-8")

    assert TicketLogPostProcessService.extract_version_key_from_files([log_file]) == "3.4.5"


def test_ticket_decorate_preserves_affected_version_field():
    """工单列表装饰时应保留主表发生版本，不再被历史 versionKey 覆盖。"""
    item = {
        "projectName": "",
        "merchantName": "",
        "versionKey": "1.0.0",
        "affectedVersion": "2.0.0",
        "extraData": {},
    }

    TicketService._decorate_ticket_item(item)

    assert item["affectedVersion"] == "2.0.0"
    assert item["versionKey"] == "1.0.0"
