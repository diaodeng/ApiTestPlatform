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


def build_secret_headers(secret: dict[str, Any], include_cookie_header: bool = False) -> dict[str, str]:
    """组装凭证默认携带的请求 Header：附加 Header + 主 Header（含 valuePrefix 拼接）。

    include_cookie_header=False（多步链默认）时排除 Cookie 类 Header：
    显式 Cookie 请求头会覆盖 httpx Cookie Jar，破坏步骤间会话延续，
    Cookie 内容应改由 additional_header_cookies + secret_cookies 并入 Jar 携带。
    """
    result: dict[str, str] = {}
    for key, value in (secret.get("headers") or {}).items():
        name = str(key).strip()
        if not name:
            continue
        if name.lower() == "cookie" and not include_cookie_header:
            continue
        result[name] = str(value)
    header_name = str(secret.get("headerName") or secret.get("header_name") or "").strip()
    header_value = str(
        secret.get("headerValue") or secret.get("header_value") or secret.get("token") or secret.get("apiKey") or ""
    ).strip()
    value_prefix = str(secret.get("valuePrefix") or secret.get("value_prefix") or "")
    if value_prefix and secret.get("token") and not header_value.startswith(value_prefix):
        header_value = f"{value_prefix}{header_value}"
    if header_name and header_value and (include_cookie_header or header_name.lower() != "cookie"):
        result.setdefault(header_name, header_value)
    return result


def additional_header_cookies(secret: dict[str, Any]) -> dict[str, str]:
    """解析附加 Header 中配置的 Cookie 项为键值对；多步链将其并入初始 Cookie Jar 而非显式 Header。"""
    result: dict[str, str] = {}
    for key, value in (secret.get("headers") or {}).items():
        if str(key).strip().lower() != "cookie":
            continue
        parsed = SimpleCookie()
        parsed.load(str(value))
        result.update({name: morsel.value for name, morsel in parsed.items()})
    return result


# 部分掩码强度分级：全遮（密码/密钥/验证码类，部分泄露存在助记猜测风险）与
# 首尾保留（Cookie/Token/ticket 类，保留首尾可判断"值是否为空/是否旧值残留/格式是否正确"）。
MASK_FULL_FIELDS = {"password", "passwd", "pwd", "secret", "otp", "google_code", "otpsecret", "otp_secret", "api_key", "apikey"}
MASK_PARTIAL_FIELDS = {"ticket", "cookie", "token", "authorization", "session", "set_cookie"}
MASK_PARTIAL_FRAGMENTS = ("ticket", "token", "session")
MASK_KEEP_HEAD = 6
MASK_KEEP_TAIL = 6


def partial_mask(value: str, keep_head: int = MASK_KEEP_HEAD, keep_tail: int = MASK_KEEP_TAIL) -> str:
    """保留首尾字符的部分掩码；过短值（<= keep_head+keep_tail）整体遮蔽，避免泄露大半内容。"""
    text = str(value)
    if len(text) <= keep_head + keep_tail:
        return "******"
    return f"{text[:keep_head]}****{text[-keep_tail:]}"


def describe_response_cookies(response: httpx.Response) -> str:
    """响应 Cookie 的可排查描述：保留 Cookie 名与部分值，替代 httpx 默认对象输出。"""
    cookies = response_cookies(response)
    if not cookies:
        return "[]"
    return "; ".join(f"{name}={partial_mask(value)}" for name, value in cookies.items())


def mask_request_for_log(kwargs: dict[str, Any]) -> dict[str, Any]:
    """脱敏刷新/登录请求日志：敏感值按分级部分掩码，便于日志排查（确认值是否为空/旧值残留/格式正确）。

    分级规则见 MASK_FULL_FIELDS / MASK_PARTIAL_FIELDS：
    - 密码、密钥、验证码类全遮 ******；
    - Cookie、Token、ticket 保留首尾各 6 字符；
    - 值为 ${secret.*}/${step.*} 占位符（引用声明，不含密文）时原样显示；
    - multipart 的 files 为 (字段名, 值) 元组，按字段名分级脱敏值；
    - headers 的值按 Header 名称分级脱敏。
    """
    sensitive_names = set(MASK_FULL_FIELDS) | set(MASK_PARTIAL_FIELDS)
    sensitive_fragments = MASK_PARTIAL_FRAGMENTS + ("password", "secret", "cookie", "api_key", "otp")

    placeholder = re.compile(r"\$\{(?:secret|step\.[A-Za-z0-9]+)\.[A-Za-z_][A-Za-z0-9_]*\}")

    def mask_value_by_key(value: Any, key: str) -> Any:
        """按字段名分级脱敏单个值；multipart 的 (filename, value) 元组解包后对值掩码。"""
        normalized = key.lower().replace("-", "_")
        if isinstance(value, str) and placeholder.fullmatch(value.strip()):
            return value
        target = value[1] if isinstance(value, tuple) and len(value) >= 2 else value
        if normalized in MASK_FULL_FIELDS or any(f in normalized for f in ("password", "secret", "api_key", "apikey", "otp")):
            return "******"
        if normalized in MASK_PARTIAL_FIELDS or any(f in normalized for f in MASK_PARTIAL_FRAGMENTS):
            return partial_mask(str(target))
        return "******"

    def mask(value: Any, key: str = "") -> Any:
        normalized_key = key.lower().replace("-", "_")
        if normalized_key in {"headers", "files", "cookies"} and isinstance(value, dict):
            # headers 值按 Header 名称分级；files/cookies 同理，占位符原样。
            return {str(item_key): mask_value_by_key(item_value, str(item_key)) for item_key, item_value in value.items()}
        if isinstance(value, dict):
            return {str(item_key): mask(item_value, str(item_key)) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [mask(item) for item in value]
        if normalized_key in sensitive_names or any(name in normalized_key for name in sensitive_fragments):
            return mask_value_by_key(value, key)
        return value

    return mask(kwargs)


def mask_response_for_log(content: bytes | str) -> str:
    """脱敏响应体日志：JSON 字符串值按部分掩码处理，键名与结构保持原样以便排查。

    仅对形如 `键=值`/`"键":"值"` 的字符串值做部分掩码（键名命中敏感名单）；
    非敏感键的值（如 code、msg、result）原样保留，保证"用户未登录"等业务信息可读。
    """
    import json as _json

    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
    try:
        payload = _json.loads(text)
    except ValueError:
        # 非 JSON 响应（如 text/plain）：只处理 key=value 形态，其余原样。
        return re.sub(
            r"(" + "|".join(sorted(MASK_PARTIAL_FIELDS | MASK_FULL_FIELDS)) + r")=([^\s&;]{7,})",
            lambda m: f"{m.group(1)}={partial_mask(m.group(2))}",
            text,
            flags=re.IGNORECASE,
        )

    sensitive = set(MASK_FULL_FIELDS) | set(MASK_PARTIAL_FIELDS)

    def redact(node: Any, key: str = "") -> Any:
        normalized = key.lower().replace("-", "_").split(".")[-1]
        if isinstance(node, dict):
            return {k: redact(v, str(k)) for k, v in node.items()}
        if isinstance(node, list):
            return [redact(item, key) for item in node]
        if isinstance(node, str) and (normalized in sensitive or any(f in normalized for f in MASK_PARTIAL_FRAGMENTS + ("password", "secret", "api_key"))):
            if node in (None, ""):
                return node
            if normalized in MASK_FULL_FIELDS or any(f in normalized for f in ("password", "secret", "api_key", "otp")):
                return "******"
            return partial_mask(node)
        return node

    try:
        return _json.dumps(redact(payload), ensure_ascii=False)
    except (TypeError, ValueError):
        return text
