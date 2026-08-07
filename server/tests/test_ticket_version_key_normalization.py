from modules.ticket.service.log_pull.ticket_log_post_process_service import TicketLogPostProcessService
from modules.ticket.util.ticket_common_util import normalize_ticket_version_key


def test_normalize_ticket_version_key_filters_field_label():
    """版本号归一化应过滤字段名，避免把 version 当成有效版本。"""
    assert normalize_ticket_version_key("version") == ""
    assert normalize_ticket_version_key("版本号") == ""
    assert normalize_ticket_version_key("release/2.3.4") == "release/2.3.4"


def test_post_download_extract_ignores_plain_version_label(tmp_path):
    """日志版本提取应忽略普通 version 字段名并继续查找后续有效版本。"""
    log_file = tmp_path / "app.log"
    log_file.write_text("version: version\napp version: 3.4.5\n", encoding="utf-8")

    assert TicketLogPostProcessService.extract_version_key_from_files([log_file]) == "3.4.5"
