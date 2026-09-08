import json
import re
from typing import Any

from modules.ticket.util.ticket_common_util import normalize_ticket_version_key

# 日志版本提取默认正则：锚定 POS 应用版本行的 ms_h/ms_l/ls_h/ls_l 特征（如
# "ms_h:1, ms_l:1, ls_h:6, ls_l:8, version:1.1.6.8"），
# 避免误命中 "launcher_version:1.0.6.8"（启动器版本）和
# "OpenGL parsed version: 4, 6"（显卡解析版本）等非应用版本信息。
DEFAULT_LOG_VERSION_PATTERNS: list[str] = [
    r"ms_h\s*:\s*\d+\s*,\s*ms_l\s*:\s*\d+\s*,\s*ls_h\s*:\s*\d+\s*,\s*ls_l\s*:\s*\d+"
    r"\s*,\s*version\s*[:=]\s*(\d+(?:\.\d+){2,3})",
]

# 工单标题/描述文本提取版本号的兜底正则：要求 version 前没有字母/下划线
# （排除 launcher_version 等带前缀字段），捕获组为标准 x.y.z 起步的版本形态
# （排除 "OpenGL parsed version: 4, 6" 这类单数字片段）。
DEFAULT_TEXT_VERSION_PATTERNS: list[str] = [
    r"(?:版本号|版本)\s*[:：=]\s*([0-9]+(?:\.[0-9]+){2,3})",
    r"(?<![A-Za-z_])(?:app[_\s-]*)?version\s*[:=]\s*([0-9]+(?:\.[0-9]+){2,3})",
]

# 可配置正则数量上限，防止误粘贴大段内容拖慢日志扫描。
MAX_LOG_VERSION_PATTERNS = 20


def parse_log_version_patterns(raw_value: Any) -> list[str]:
    """
    解析并校验日志版本提取正则配置。
    :param raw_value: 配置中的正则列表（通常来自日志拉取存储配置 versionExtractPatterns）
    :return: 合法编译的正则列表；入参为空或全部非法时返回空列表（调用方回退默认正则）
    """
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return []
        try:
            raw_value = json.loads(stripped)
        except ValueError:
            return []
    if not isinstance(raw_value, list):
        return []
    patterns: list[str] = []
    for item in raw_value[:MAX_LOG_VERSION_PATTERNS]:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            re.compile(text)
        except re.error:
            continue
        if text not in patterns:
            patterns.append(text)
    return patterns


def extract_version_key_by_patterns(
    text: str | None,
    patterns: Any,
) -> str:
    """
    按配置的正则列表从文本中提取版本号，取第一个命中且归一化有效的值。
    :param text: 待匹配文本（单行或多行日志正文）
    :param patterns: 正则表达式列表；为空列表时使用默认日志正则，None 时使用默认文本正则
    :return: 版本号；未命中返回空字符串
    """
    if not text:
        return ""
    if patterns is None:
        candidates = DEFAULT_TEXT_VERSION_PATTERNS
    else:
        candidates = parse_log_version_patterns(patterns) or DEFAULT_LOG_VERSION_PATTERNS
    for pattern in candidates:
        try:
            match = re.search(pattern, text, flags=re.IGNORECASE)
        except re.error:
            continue
        if not match:
            continue
        captured = match.group(1) if match.groups() else match.group(0)
        version_key = normalize_ticket_version_key(captured)
        if version_key:
            return version_key
    return ""
