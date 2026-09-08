from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.log_pull.ticket_log_post_process_service import TicketLogPostProcessService
from modules.ticket.util.ticket_log_version_extract_util import (
    DEFAULT_LOG_VERSION_PATTERNS,
    extract_version_key_by_patterns,
    parse_log_version_patterns,
)

# 真实日志样例：ms_h 特征行才是应用版本，launcher_version 与 OpenGL 行都不是。
MS_H_LINE = "2026-09-04 13:03:53,291 I 001720-Scheduler_0 : ms_h:1, ms_l:1, ls_h:6, ls_l:8, version:1.1.6.8"
LAUNCHER_LINE = "2026-09-04 14:23:19,105 -[I] MainThread: 从主进程环境参数获取到launcher_version:1.0.6.8"
OPENGL_LINE = "2026-09-04 13:47:18,129 I 008492-MainThread : GL: OpenGL parsed version: 4, 6"


def test_default_log_pattern_extracts_ms_h_version():
    """默认日志正则应只命中 ms_h 特征行的版本号。"""
    assert extract_version_key_by_patterns(MS_H_LINE, []) == "1.1.6.8"
    assert extract_version_key_by_patterns(LAUNCHER_LINE, []) == ""
    assert extract_version_key_by_patterns(OPENGL_LINE, []) == ""


def test_default_log_pattern_priority_in_mixed_log():
    """launcher_version 与 OpenGL 行先出现时也不得抢占 ms_h 行的提取结果。"""
    mixed_log = "\n".join([OPENGL_LINE, LAUNCHER_LINE, MS_H_LINE])
    assert extract_version_key_by_patterns(mixed_log, []) == "1.1.6.8"


def test_parse_log_version_patterns_filters_invalid():
    """解析配置时应过滤非法正则、空串与重复项。"""
    assert parse_log_version_patterns(None) == []
    assert parse_log_version_patterns("不是JSON") == []
    assert parse_log_version_patterns(["(bad", " ", r"(\d+\.\d+)"]) == [r"(\d+\.\d+)"]
    assert parse_log_version_patterns([r"(\d+)", r"(\d+)"]) == [r"(\d+)"]


def test_custom_pattern_overrides_default():
    """配置自定义正则后按配置提取，且非法配置回退默认正则。"""
    # 自定义正则允许命中 launcher 行（模拟运维显式改为提取启动器版本）。
    custom = [r"launcher_version\s*[:=]\s*(\d+(?:\.\d+){2,3})"]
    assert extract_version_key_by_patterns(LAUNCHER_LINE, custom) == "1.0.6.8"
    # 全部非法时回退默认正则。
    assert extract_version_key_by_patterns(MS_H_LINE, ["(bad"]) == "1.1.6.8"


def test_post_download_extract_from_files_with_patterns(tmp_path):
    """下载后处理链路应使用传入的正则配置逐行提取。"""
    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join([LAUNCHER_LINE, OPENGL_LINE, MS_H_LINE]) + "\n", encoding="utf-8")

    assert TicketLogPostProcessService.extract_version_key_from_files([log_file]) == "1.1.6.8"
    # 传入空列表同样回退默认正则。
    assert TicketLogPostProcessService.extract_version_key_from_files([log_file], []) == "1.1.6.8"
    # 传入自定义正则时按配置提取。
    custom = [r"launcher_version\s*[:=]\s*(\d+(?:\.\d+){2,3})"]
    assert TicketLogPostProcessService.extract_version_key_from_files([log_file], custom) == "1.0.6.8"


def test_text_pattern_filters_launcher_and_opengl():
    """工单标题/描述文本提取应排除带前缀字段与单数字片段。"""
    assert TicketLightAiService.extract_version_key_from_text("版本号: 1.2.3.4") == "1.2.3.4"
    assert TicketLightAiService.extract_version_key_from_text("app version: 2.3.4.5") == "2.3.4.5"
    assert TicketLightAiService.extract_version_key_from_text(LAUNCHER_LINE) == ""
    assert TicketLightAiService.extract_version_key_from_text(OPENGL_LINE) == ""


def test_default_log_patterns_compilable():
    """内置默认正则必须可编译，防止书写错误导致提取链路失效。"""
    import re

    for pattern in DEFAULT_LOG_VERSION_PATTERNS:
        re.compile(pattern)
