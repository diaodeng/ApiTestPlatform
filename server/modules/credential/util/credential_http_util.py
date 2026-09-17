import base64
import hashlib
import hmac
import re
import struct
import time
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx


def generate_totp(secret: str, digits: int = 6, period: int = 30) -> str:
    """使用标准 RFC 6238 算法生成 TOTP，不依赖第三方包。"""
    normalized = secret.replace(" ", "").replace("-", "").upper()
    key = base64.b32decode(normalized + "=" * (-len(normalized) % 8), casefold=True)
    counter = int(time.time() // period)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def secret_cookies(secret: dict[str, Any]) -> dict[str, str]:
    """合并结构化 Cookie、主 Cookie 字符串和 storageState 为请求 Cookie。"""
    result: dict[str, str] = {}
    storage = secret.get("storageState") or secret.get("storage_state")
    if isinstance(storage, dict) and storage:
        result.update(secret_cookies(storage))
    raw = secret.get("cookie") or secret.get("cookieHeader")
    if raw:
        parsed = SimpleCookie()
        parsed.load(str(raw))
        result.update({key: morsel.value for key, morsel in parsed.items()})
    cookies = secret.get("cookies")
    if isinstance(cookies, dict):
        result.update({str(key): str(value) for key, value in cookies.items() if str(key).strip()})
    elif isinstance(cookies, list):
        result.update(
            {
                str(item.get("name")): str(item.get("value", ""))
                for item in cookies
                if isinstance(item, dict) and item.get("name")
            }
        )
    return result


def response_cookies(response: httpx.Response) -> dict[str, str]:
    """解析响应中的全部标准 Set-Cookie 为键值对。"""
    result: dict[str, str] = {}
    for value in response.headers.get_list("set-cookie"):
        parsed = SimpleCookie()
        parsed.load(value)
        result.update({key: morsel.value for key, morsel in parsed.items()})
    return result


def read_response_value(payload: Any, response: httpx.Response, response_cookies: dict[str, str], source: Any):
    """按来源语法读取响应值，支持附加一次 transform 加工。

    来源语法：
    - `json:字段路径`：按点路径读取 JSON 字段；
    - `header:名称`：读取响应头；`header:set-cookie[n]` 读取第 n 条原始 Set-Cookie；
    - `cookie:名称`：读取标准 Set-Cookie 解析后的单个 Cookie 值；
    - `cookies`：全部 Set-Cookie 键值对。
    transform 语法（只能附加一个，追加在来源后，用 `|` 分隔）：
    - `url_query:参数名`：把来源值当作 URL，提取指定查询参数；
    - `regex:正则`：按正则提取，存在捕获组时返回第 1 组，否则返回整体匹配。
    """
    base_source, transform = _split_source_transform(source)
    value = _read_base_response_value(payload, response, response_cookies, base_source)
    if transform is not None:
        value = _apply_source_transform(value, transform)
    return value


def _split_source_transform(source: Any) -> tuple[str, str | None]:
    """把 `来源|transform` 拆成两部分；只允许一个 `|`，保证 regex 表达式自身可包含 `|`。"""
    text = str(source or "")
    if "|" not in text:
        return text, None
    base, transform = text.split("|", 1)
    return base.strip(), transform.strip()


def _read_base_response_value(payload: Any, response: httpx.Response, response_cookies: dict[str, str], source: str):
    """按原始来源语法读取响应值，不含 transform。"""
    text = str(source or "")
    if text == "cookies" or text == "cookie.*":
        # 未返回标准 Set-Cookie 时不把空对象视作已提取，避免整组覆盖误清空旧 Cookie。
        return response_cookies or None
    if text.startswith("header:"):
        header_name = text[7:].strip()
        raw_set_cookie_index = None
        if header_name.lower().startswith("set-cookie[") and header_name.endswith("]"):
            raw_set_cookie_index = header_name[len("set-cookie["):-1]
            if not raw_set_cookie_index.isdigit() or int(raw_set_cookie_index) < 1:
                raise ValueError("header:set-cookie[n] 中 n 必须是从 1 开始的响应 Set-Cookie 序号")
            header_name = "set-cookie"
        if header_name.lower() == "set-cookie":
            # Set-Cookie 允许出现多次，不能将多条值拼接后误写入单个 Cookie 字段。
            values = [value.strip() for value in response.headers.get_list("set-cookie") if value.strip()]
            if raw_set_cookie_index is not None:
                index = int(raw_set_cookie_index) - 1
                if index >= len(values):
                    raise ValueError(f"响应 Set-Cookie 序号超出范围，当前只有 {len(values)} 条")
                return values[index]
            if len(values) > 1:
                raise ValueError(
                    "响应包含多个 Set-Cookie，header:set-cookie 只能读取单条原始值；"
                    "请使用 header:set-cookie[n] 明确选择序号，或使用 cookie:<名称> 提取标准 Cookie"
                )
            return values[0] if values else None
        return response.headers.get(header_name)
    if text.startswith("cookie:"):
        return response_cookies.get(text[7:])
    if text.startswith("json:"):
        text = text[5:]
    value = payload
    for part in text.split(".") if text else []:
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _apply_source_transform(value: Any, transform: str):
    """对来源值执行一次加工；url_query 与 regex 失配时返回 None，由调用方决定是否视为提取失败。"""
    if transform.startswith("url_query:"):
        parameter_name = transform[len("url_query:"):].strip()
        if not parameter_name:
            raise ValueError("url_query transform 必须指定查询参数名，例如 json:result|url_query:ticket")
        return _apply_url_query_transform(value, parameter_name)
    if transform.startswith("regex:"):
        pattern = transform[len("regex:"):].strip()
        if not pattern:
            raise ValueError("regex transform 必须填写正则表达式，例如 json:result|regex:ticket=([0-9a-f-]+)")
        return _apply_regex_transform(value, pattern)
    raise ValueError(f"不支持的来源加工方式: {transform}，仅支持 url_query:参数名 或 regex:正则")


def _apply_url_query_transform(value: Any, parameter_name: str):
    """把来源值当作 URL（或纯查询串），提取指定查询参数的第一个值。"""
    if value is None:
        return None
    text = str(value)
    query = urlsplit(text).query or text
    parsed = parse_qs(query, keep_blank_values=True)
    values = parsed.get(parameter_name)
    return values[0] if values else None


def _apply_regex_transform(value: Any, pattern: str):
    """按正则提取来源值；存在捕获组时返回第 1 组，否则返回整体匹配。"""
    if value is None:
        return None
    try:
        match = re.search(pattern, str(value))
    except re.error as exc:
        raise ValueError(f"来源加工的正则表达式无效: {pattern}，原因：{exc}") from exc
    if not match:
        return None
    return match.group(1) if match.groups() else match.group(0)


def write_response_value(secret: dict[str, Any], target: str, value: Any) -> None:
    """按显式目标路径写入提取值，禁止未配置规则时隐式更新 Cookie。"""
    normalized_target = target.strip()
    if normalized_target == "header.cookie":
        _assert_cookie_header(secret)
        if isinstance(value, (dict, list)):
            raise ValueError("header.cookie 只能写入单个 Cookie Header 字符串")
        # 覆盖整个 Cookie Header，用户需明确接受未包含的 Cookie 会丢失。
        secret["headerValue"] = str(value)
        return

    if normalized_target.startswith("header.cookie."):
        cookie_name = normalized_target[len("header.cookie."):].strip()
        if not cookie_name:
            raise ValueError("header.cookie.<名称> 必须填写要更新的 Cookie 名称")
        _assert_cookie_header(secret)
        if isinstance(value, (dict, list)):
            raise ValueError("header.cookie.<名称> 只能写入单个 Cookie 值")
        existing = str(secret.get("headerValue") or secret.get("header_value") or "")
        # 同名项替换；原 Header 中没有该项时按配置约定静默追加。
        secret["headerValue"] = merge_cookies_into_string(existing, {cookie_name: str(value)})
        return

    if normalized_target == "cookies":
        _assert_structured_cookie_target_allowed(secret)
        if not isinstance(value, dict):
            raise ValueError("目标字段 cookies 只能接收对象值，例如来源 cookies 或 JSON 对象")
        # 显式配置 cookies ← cookies 表示以本次响应 Cookie 集合整体覆盖旧集合。
        secret["cookies"] = {str(key): str(item) for key, item in value.items() if str(key).strip()}
        return

    if normalized_target.startswith("cookies."):
        cookie_name = normalized_target[len("cookies."):].strip()
        if not cookie_name:
            raise ValueError("cookies.<名称> 必须填写要更新的 Cookie 名称")
        _assert_structured_cookie_target_allowed(secret)
        if isinstance(value, (dict, list)):
            raise ValueError("cookies.<名称> 只能写入单个 Cookie 值")
        cookies = secret_cookies(secret)
        cookies[cookie_name] = str(value)
        secret["cookies"] = cookies
        return

    # 普通字段仍按显式字段名整体写入，例如 token、headerValue、headers。
    secret[normalized_target] = value


def _assert_cookie_header(secret: dict[str, Any]) -> None:
    """确认 header.cookie 目标仅用于 Header 名称为 Cookie 的凭证。"""
    header_name = str(secret.get("headerName") or secret.get("header_name") or "").strip()
    if header_name.lower() != "cookie":
        raise ValueError("header.cookie 目标仅适用于 Header 名称为 Cookie 的凭证")


def _assert_structured_cookie_target_allowed(secret: dict[str, Any]) -> None:
    """避免主 Cookie Header 与结构化 Cookie 同时写回，防止下次编辑出现冲突。"""
    header_name = str(secret.get("headerName") or secret.get("header_name") or "").strip()
    if header_name.lower() == "cookie":
        raise ValueError(
            "主 Header 为 Cookie 时不能写入 cookies 或 cookies.<名称>；"
            "请使用 header.cookie 或 header.cookie.<名称> 更新 Cookie Header"
        )


def extract_response_secret(
    old_secret: dict[str, Any], response: httpx.Response, mapping: Any
) -> tuple[dict[str, Any], bool]:
    """从 JSON、响应头和 Set-Cookie 提取新凭证，并保留未变化的旧字段。

    返回值: (新的 secret 字典, 是否实际提取到了新内容)。
    """
    result = dict(old_secret)
    extracted_any = False
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    cookies = response_cookies(response)
    if isinstance(mapping, dict):
        for secret_key, source in mapping.items():
            value = read_response_value(payload, response, cookies, source)
            if value is not None:
                write_response_value(result, str(secret_key), value)
                extracted_any = True
    return result, extracted_any


def validate_response_success_assertions(response: httpx.Response, assertions: list[Any]) -> None:
    """校验业务成功断言，任何一条不通过都抛出异常终止流程。"""
    if not assertions:
        return
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    cookies = response_cookies(response)
    for index, raw_assertion in enumerate(assertions, start=1):
        assertion = raw_assertion.model_dump() if hasattr(raw_assertion, "model_dump") else raw_assertion
        if not isinstance(assertion, dict):
            raise ValueError(f"响应成功断言第 {index} 条格式错误")
        source = str(assertion.get("source") or "").strip()
        operator = str(assertion.get("operator") or "equals")
        expected = assertion.get("expected")
        actual = response.status_code if source == "status" else read_response_value(payload, response, cookies, source)
        if matches_response_assertion(actual, operator, expected):
            continue
        message = str(assertion.get("message") or "").strip()
        detail = message or f"来源 {source} 的实际值 {actual!r} 不满足 {operator} {expected!r}"
        raise ValueError(f"响应成功断言第 {index} 条未通过：{detail}")


def matches_response_assertion(actual: Any, operator: str, expected: Any) -> bool:
    """使用固定操作符比较响应值，避免在凭证刷新中执行任意代码。"""
    if operator == "exists":
        return actual is not None
    if operator == "not_empty":
        if actual is None:
            return False
        if isinstance(actual, str):
            return bool(actual.strip())
        if isinstance(actual, (dict, list, tuple, set)):
            return bool(actual)
        return True
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, (dict, list, tuple, set)):
            return expected in actual
        return False
    if operator == "in":
        return isinstance(expected, list) and actual in expected
    raise ValueError(f"不支持的响应成功断言操作符: {operator}")


def merge_cookies_into_string(existing: str, new_cookies: dict[str, str]) -> str:
    """将 Set-Cookie 键值对合并到现有 cookie 字符串中，同名 key 替换值，新 key 追加到末尾。"""
    if not new_cookies:
        return existing
    # 解析现有 cookie 字符串，保持顺序
    pairs: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for part in existing.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        if key and key not in seen_keys:
            pairs.append((key, value.strip()))
            seen_keys.add(key)
    # 合并新 cookie：同名替换，新 key 追加
    for key, value in new_cookies.items():
        key = key.strip()
        if not key:
            continue
        if key in seen_keys:
            for i, (k, _) in enumerate(pairs):
                if k == key:
                    pairs[i] = (key, value.strip())
                    break
        else:
            pairs.append((key, value.strip()))
            seen_keys.add(key)
    return "; ".join(f"{k}={v}" for k, v in pairs)


def mask_request_for_log(kwargs: dict[str, Any]) -> dict[str, Any]:
    """脱敏刷新/登录请求日志，避免 Cookie、Token、密码、验证码、ticket 等凭证内容写入日志。"""
    sensitive_names = {
        "authorization", "cookie", "set_cookie", "proxy_authorization", "password",
        "passwd", "secret", "token", "api_key", "apikey", "otp", "google_code", "ticket",
    }
    sensitive_fragments = ("token", "secret", "password", "cookie", "api_key", "otp", "ticket")

    def mask(value: Any, key: str = "") -> Any:
        normalized_key = key.lower().replace("-", "_")
        if normalized_key in sensitive_names or any(name in normalized_key for name in sensitive_fragments):
            return "******"
        if normalized_key == "headers" and isinstance(value, dict):
            # 请求模板可把任意 secret 字段注入自定义 Header，日志中不再按 Header 名称猜测敏感性。
            return {str(item_key): "******" for item_key in value}
        if isinstance(value, dict):
            return {str(item_key): mask(item_value, str(item_key)) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [mask(item) for item in value]
        return value

    return mask(kwargs)
