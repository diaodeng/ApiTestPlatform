"""JSON 文本修复工具：挽救模型输出中常见形态的非法 JSON。

背景：工单 AI 分析链路中，部分模型（如 deepseek-v4-flash）即使传入
--output-schema 也可能在字符串值内部输出未转义英文双引号，例如把
请求体示例 {"yuuId": "934..."} 原样嵌进 analysis_summary 值里，
导致整体 JSON 非法（生产场景 INC00002000624N）。

本模块只做“挽救”不做“猜测”：每一处修复都必须让整体文本重新通过
json.loads 且解析为 dict 才算成功，否则保持失败语义（返回 None），
交由上层补救重试处理。
"""

from __future__ import annotations

import json
import re
from typing import Any

# 单个文本修复的最大长度，超长输入直接放弃（结果 JSON 正常在几十 KB 量级）
_MAX_REPAIR_INPUT_LENGTH = 2_000_000
# 歧义引号决策次数上限（每次决策是“该引号是结束符还是值内字符”）。
# 每次决策只是一次局部扫描（不重建文本、不解析），代价很低；长文本中
# “结束符”分支深入探索失败是常态，需要累计计数，实测 10KB 样本约需
# 数百次决策，48 会提前耗尽导致正确路径没机会执行。
_MAX_DECISIONS = 1024


def repair_json_text(text: str) -> dict[str, Any] | None:
    """
    尝试把可能损坏的 JSON 文本修复为 dict。

    依次尝试（任一成功即返回）：
    1. 直接 json.loads；
    2. 剥离 Markdown 代码块围栏后解析；
    3. 截取花括号主体后做回溯式未转义引号修复。

    :param text: 原始文本（可能是非法 JSON）
    :return: 修复后的 dict；无法挽救时返回 None
    """
    if not isinstance(text, str) or not text.strip():
        return None
    if len(text) > _MAX_REPAIR_INPUT_LENGTH:
        return None
    stripped = text.strip()
    # 1. 直接解析
    try:
        payload = json.loads(stripped)
        return payload if isinstance(payload, dict) else None
    except Exception:
        pass
    # 2. 剥离围栏后解析（```json ... ``` / ``` ... ```）
    inner = _strip_markdown_fence(stripped)
    if inner is not None:
        try:
            payload = json.loads(inner)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
    # 3. 截取花括号主体后做回溯式引号修复
    source = inner if inner is not None else stripped
    start = source.find("{")
    end = source.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = source[start : end + 1]
    return _repair_by_backtracking(candidate)


def _strip_markdown_fence(text: str) -> str | None:
    """剥离 Markdown 代码块围栏，返回内层文本；无围栏返回 None。"""
    match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", text)
    if match:
        return match.group(1)
    # 容错首尾不完整的围栏（截断场景）：开头 ```json 无闭合
    match = re.match(r"^```(?:json)?\s*\n([\s\S]+)$", text)
    if match:
        return match.group(1)
    return None


def _build_with_escapes(text: str, escapes: list[int]) -> str:
    """按给定的“需转义引号位置列表”重建文本。"""
    parts: list[str] = []
    prev = 0
    for pos in sorted(escapes):
        parts.append(text[prev:pos])
        parts.append('\\"')
        prev = pos + 1
    parts.append(text[prev:])
    return "".join(parts)


def _repair_by_backtracking(text: str) -> dict[str, Any] | None:
    """
    回溯式修复字符串值内部未转义的英文双引号。

    与旧版单遍贪心扫描的区别：旧版把“引号后紧跟 , } ] :”一律判为字符串
    结束符，遇到字符串值内嵌套的 JSON 示例（如 {"yuuId": "934..."}，
    其 "键": 形态与真实结构无法区分）时状态机错乱导致整体失败。

    新版利用 JSON 语法约束把决策点压缩到极少数：
    - 字符串分为“键字符串”与“值字符串”（由打开它的结构位置决定）；
    - 键字符串内的引号后跟 ```:``` → 必为键结束（合法 JSON 中键后必然是冒号）；
    - 值字符串内的引号后跟 ```:``` → 必为值内字符（合法 JSON 中值之后
      只能是 , 或 } / ]，不可能是冒号）；
    - 仅“值字符串内的引号后跟 , } ]”才是二义点。剪枝：统计当前值字符串
      内未配对的 `{` 数量——大于 0 说明正处于嵌入的 JSON 对象中，该引号
      几乎必然是值内字符（先转义）；否则优先按真实结束符处理；
    - 其余形态（引号后跟其他字符）一律视为值内字符直接转义。

    每个分支都使用独立的上下文拷贝（depth_stack 可变列表），避免探索
    过程互相污染。任一分支重建文本通过 json.loads 且为 dict 即成功；
    全部路径失败或决策次数超限返回 None。
    """
    if len(text) > _MAX_REPAIR_INPUT_LENGTH or '"' not in text:
        return None
    decisions = 0

    def dfs(
        index: int,
        in_string: bool,
        string_is_value: bool,
        escapes: list[int],
        depth_stack: list[str],
        expect_value: bool,
        value_start: int,
    ) -> dict[str, Any] | None:
        """
        从 index 开始扫描。
        :param in_string: 当前是否处于字符串内部
        :param string_is_value: 当前字符串是否为值字符串（True=值，False=键）
        :param escapes: 已决定转义的引号位置列表
        :param depth_stack: 结构上下文栈（'o'=对象等待键，'a'=数组）
        :param expect_value: 对象内是否正处于“等待值”状态
        :param value_start: 当前值字符串的起始引号位置（统计嵌入花括号用）
        :return: 修复成功的 dict；分支穷尽返回 None
        """
        nonlocal decisions
        if decisions > _MAX_DECISIONS:
            return None
        while index < len(text):
            ch = text[index]
            if not in_string:
                if ch == '"':
                    # 数组元素或对象值位置的字符串都是值字符串；对象键位置是键字符串
                    string_is_value = expect_value or bool(depth_stack and depth_stack[-1] == "a")
                    value_start = index + 1
                    in_string = True
                    index += 1
                    continue
                if ch == "{":
                    depth_stack.append("o")
                    expect_value = False
                    index += 1
                    continue
                if ch == "[":
                    depth_stack.append("a")
                    expect_value = False
                    index += 1
                    continue
                if ch in "}]":
                    if depth_stack:
                        depth_stack.pop()
                    expect_value = False
                    index += 1
                    continue
                if ch == ":":
                    expect_value = True
                    index += 1
                    continue
                if ch == ",":
                    # 对象中逗号后等键；数组中逗号后仍是值
                    expect_value = bool(depth_stack and depth_stack[-1] == "a")
                    index += 1
                    continue
                index += 1
                continue
            # 字符串内部
            if ch == "\\" and index + 1 < len(text):
                index += 2
                continue
            if ch == '"':
                after = text[index + 1 :].lstrip()
                if string_is_value:
                    if after.startswith(":"):
                        # 值字符串内 quote+冒号：合法 JSON 中值后不可能是冒号，
                        # 必为值内字符，直接转义（无分支）
                        escapes.append(index)
                        index += 1
                        continue
                    if after.startswith((",", "}", "]")) or after == "":
                        # 二义点：先统计值字符串内未配对花括号，
                        # 处于嵌入 JSON 对象内时优先按值内字符转义
                        segment = text[value_start:index]
                        opens = segment.count("{") - segment.count("}")
                        decisions += 1
                        if decisions > _MAX_DECISIONS:
                            return None
                        if opens > 0:
                            # 嵌入 JSON 上下文：先按值内字符转义
                            escapes.append(index)
                            payload = dfs(
                                index + 1,
                                True,
                                True,
                                escapes,
                                list(depth_stack),
                                expect_value,
                                value_start,
                            )
                            escapes.pop()
                            if payload is not None:
                                return payload
                            # 回退：按真实结束符处理
                            payload = dfs(
                                index + 1,
                                False,
                                False,
                                list(escapes),
                                list(depth_stack),
                                expect_value,
                                value_start,
                            )
                            return payload
                        # 常规上下文：先按“真实结束符”处理（多数情况）
                        payload = dfs(
                            index + 1,
                            False,
                            False,
                            list(escapes),
                            list(depth_stack),
                            expect_value,
                            value_start,
                        )
                        if payload is not None:
                            return payload
                        # 回退：该引号按值内字符转义，继续扫描
                        escapes.append(index)
                        payload = dfs(
                            index + 1,
                            True,
                            True,
                            escapes,
                            list(depth_stack),
                            expect_value,
                            value_start,
                        )
                        escapes.pop()
                        return payload
                    # 引号后跟其他字符：必为值内字符
                    escapes.append(index)
                    index += 1
                    continue
                # 键字符串内：quote+冒号 → 键结束（合法 JSON 键后必然是冒号）
                if after.startswith(":"):
                    in_string = False
                    expect_value = True
                    index += 1
                    continue
                # 键字符串内其他引号：键名中出现未转义引号，转义处理
                escapes.append(index)
                index += 1
                continue
            index += 1
        # 扫描结束：按当前转义集重建解析（覆盖收尾场景）
        try:
            payload = json.loads(_build_with_escapes(text, escapes))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    return dfs(0, False, False, [], [], False, 0)
