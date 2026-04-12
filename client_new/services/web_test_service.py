from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from loguru import logger

try:
    from playwright.async_api import Frame, FrameLocator, Locator, Page
except Exception:  # pragma: no cover - optional dependency
    Frame = FrameLocator = Locator = Page = Any

from services.playwright_browser_runtime import start_playwright_browser

EventSender = Callable[[dict[str, Any]], Awaitable[None]]

RECORDER_SCRIPT = """
(() => {
  if (window.__qtrRecorderInstalled__) return;
  window.__qtrRecorderInstalled__ = true;
  window.__qtrRecordActive__ = window.__qtrRecordActive__ !== false;
  const cleanText = (value) => (value || "").replace(/\\s+/g, " ").trim().slice(0, 120);
  const attr = (el, name) => cleanText(el.getAttribute(name) || "");
  const options = window.__qtrRecordOptions__ && typeof window.__qtrRecordOptions__ === "object"
    ? window.__qtrRecordOptions__
    : {};
  const captureAssertions = options.captureAssertions !== false && options.capture_assertions !== false;
  const autoAssertTextOnClick = captureAssertions
    && (options.autoAssertTextOnClick === true || options.auto_assert_text_on_click === true);
  const assertionAttachMode = String(options.assertionAttachMode || options.assertion_attach_mode || "inside_step").toLowerCase();
  const attachAssertToPreviousStep = !["parallel_step", "parallel", "separate_step"].includes(assertionAttachMode);
  const quickAssertPickEnabled = captureAssertions;
  const isQuickAssertEvent = (event) => !!(event && event.altKey);
  const isStableToken = (value) => {
    const text = cleanText(value);
    if (!text || text.length < 2 || text.length > 80) return false;
    // uuid / hash / long timestamp-like token is usually unstable for replay
    if (/[0-9a-f]{10,}/i.test(text) || /\\d{6,}/.test(text)) return false;
    return true;
  };
  const cssEscape = (value) => {
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(value);
    }
    return String(value || "").replace(/([ !"#$%&'()*+,./:;<=>?@[\\\\\\]^`{|}~])/g, "\\\\$1");
  };
  const inferRole = (el) => {
    const explicit = el.getAttribute("role");
    if (explicit) return explicit;
    const tag = (el.tagName || "").toLowerCase();
    if (tag === "button") return "button";
    if (tag === "a") return "link";
    if (tag === "input") {
      const type = (el.getAttribute("type") || "text").toLowerCase();
      if (type === "checkbox") return "checkbox";
      if (type === "radio") return "radio";
      if (["submit", "button"].includes(type)) return "button";
      return "textbox";
    }
    if (tag === "select") return "combobox";
    if (tag === "textarea") return "textbox";
    return "";
  };
  const pushLocator = (locators, locatorType, locatorValue) => {
    const key = `${locatorType}::${JSON.stringify(locatorValue || {})}`;
    if (locators.some((item) => item.__key === key)) return;
    locators.push({ locatorType, locatorValue, enabled: true, __key: key });
  };
  const cssPath = (el) => {
    if (!(el instanceof Element)) return "";
    const id = attr(el, "id");
    if (isStableToken(id)) {
      return `#${cssEscape(id)}`;
    }
    const testId = attr(el, "data-testid") || attr(el, "data-test");
    if (isStableToken(testId)) {
      return `[data-testid="${cssEscape(testId)}"]`;
    }
    const name = attr(el, "name");
    if (isStableToken(name)) {
      return `${(el.tagName || "div").toLowerCase()}[name="${cssEscape(name)}"]`;
    }
    const parts = [];
    let current = el;
    while (current && current.nodeType === 1 && parts.length < 6) {
      let part = current.tagName.toLowerCase();
      const currentId = attr(current, "id");
      if (isStableToken(currentId)) {
        part += "#" + cssEscape(currentId);
        parts.unshift(part);
        break;
      }
      const stableClass = Array.from(current.classList || []).find((item) => isStableToken(item));
      if (stableClass) part += "." + cssEscape(stableClass);
      const currentName = attr(current, "name");
      if (isStableToken(currentName)) part += `[name="${cssEscape(currentName)}"]`;
      const siblings = current.parentElement ? Array.from(current.parentElement.children).filter((item) => item.tagName === current.tagName) : [];
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
      parts.unshift(part);
      current = current.parentElement;
    }
    return parts.join(" > ");
  };
  const buildLocators = (el, mode = {}) => {
    const preferStableLocators = mode && mode.preferStableLocators === true;
    const locators = [];
    const id = attr(el, "id");
    const nameAttr = attr(el, "name");
    const testId = attr(el, "data-testid") || attr(el, "data-test");
    const ariaLabel = cleanText(attr(el, "aria-label"));
    const role = inferRole(el);
    const text = cleanText(el.innerText || el.textContent || "");
    const labelText = cleanText(el.labels?.[0]?.innerText || "");
    const label = cleanText(ariaLabel || labelText || "");
    const placeholder = cleanText(el.getAttribute("placeholder") || "");
    if (isStableToken(testId)) pushLocator(locators, "test_id", { testId });
    if (isStableToken(id)) pushLocator(locators, "id", { id });
    if (isStableToken(nameAttr)) pushLocator(locators, "name", { name: nameAttr });
    if (role) {
      const roleValue = { role };
      if (preferStableLocators) {
        if (ariaLabel) roleValue.name = ariaLabel;
        else if (labelText && labelText !== text) roleValue.name = labelText;
      } else if (text) roleValue.name = text;
      else if (label) roleValue.name = label;
      pushLocator(locators, "role", roleValue);
    }
    if (label) pushLocator(locators, "label", { text: label, exact: true });
    if (placeholder) pushLocator(locators, "placeholder", { text: placeholder, exact: true });
    if (!preferStableLocators && text && text.length <= 80) pushLocator(locators, "text", { text, exact: true });
    const css = cssPath(el);
    if (css) pushLocator(locators, "css", { selector: css });
    if (preferStableLocators && !locators.length && text && text.length <= 80) {
      pushLocator(locators, "text", { text, exact: true });
    }
    return locators.map((item, index) => ({
      locatorType: item.locatorType,
      locatorValue: item.locatorValue,
      priority: index,
      enabled: true
    }));
  };
  const buildSnapshot = (el, mode = {}) => ({
    elementText: cleanText(el.innerText || el.textContent || ""),
    context: { pageUrl: window.location.href, frameUrl: window.location.href, frameChain: [], shadowChain: [] },
    locators: buildLocators(el, mode)
  });
  const emit = (payload) => {
    if (window.__qtrRecordActive__ === false) {
      return;
    }
    if (typeof window.__qtrRecordEvent === "function") {
      window.__qtrRecordEvent(payload);
    }
  };
  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest("button, a, input, textarea, select, [role], [data-testid], [data-test], *") : null;
    if (!target) return;
    const text = cleanText(target.innerText || target.textContent || "");
    if (quickAssertPickEnabled && isQuickAssertEvent(event)) {
      event.preventDefault();
      event.stopPropagation();
        emit({
          stepName: text
            ? (attachAssertToPreviousStep ? `为上一步追加断言 文本包含 ${text}` : `断言文本包含 ${text}`)
            : (attachAssertToPreviousStep ? "为上一步追加断言 元素可见" : "断言元素可见"),
        actionType: text ? "assert_text_contains" : "wait_visible",
        params: text ? { expected: text } : {},
        assertions: [],
        rawEvent: {
          eventType: attachAssertToPreviousStep ? "assert_pick_attach_prev" : "assert_pick",
          trigger: "alt_click",
          tagName: target.tagName,
          assertionAttachMode,
          attachToPreviousStep: attachAssertToPreviousStep
        },
        targetSnapshot: buildSnapshot(target, { preferStableLocators: true })
      });
      return;
    }
    if (autoAssertTextOnClick && text) {
      emit({
        stepName: `断言文本包含 ${text}`,
        actionType: "assert_text_contains",
        params: { expected: text },
        assertions: [],
        rawEvent: { eventType: "auto_assert_before_click", tagName: target.tagName },
        targetSnapshot: buildSnapshot(target)
      });
    }
    emit({
      stepName: text ? `点击 ${text}` : "点击元素",
      actionType: "click",
      params: {},
      assertions: [],
      rawEvent: { eventType: "click", tagName: target.tagName },
      targetSnapshot: buildSnapshot(target)
    });
  }, true);
  document.addEventListener("change", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const tag = (target.tagName || "").toLowerCase();
    if (tag === "input") {
      const type = (target.getAttribute("type") || "text").toLowerCase();
      if (["checkbox", "radio"].includes(type)) {
        emit({
          stepName: target.checked ? "勾选元素" : "取消勾选元素",
          actionType: target.checked ? "check" : "uncheck",
          params: {},
          assertions: [],
          rawEvent: { eventType: "change", tagName: target.tagName },
          targetSnapshot: buildSnapshot(target)
        });
        return;
      }
      emit({
        stepName: "填写输入框",
        actionType: "fill",
        params: { value: target.value || "" },
        assertions: [],
        rawEvent: { eventType: "change", tagName: target.tagName },
        targetSnapshot: buildSnapshot(target)
      });
      return;
    }
    if (tag === "textarea") {
      emit({
        stepName: "填写文本域",
        actionType: "fill",
        params: { value: target.value || "" },
        assertions: [],
        rawEvent: { eventType: "change", tagName: target.tagName },
        targetSnapshot: buildSnapshot(target)
      });
      return;
    }
    if (tag === "select") {
      const values = Array.from(target.selectedOptions || []).map((item) => item.value || item.label || "");
      emit({
        stepName: "选择下拉项",
        actionType: "select_option",
        params: { values },
        assertions: [],
        rawEvent: { eventType: "change", tagName: target.tagName },
        targetSnapshot: buildSnapshot(target)
      });
    }
  }, true);
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    emit({
      stepName: "键盘按下 Enter",
      actionType: "press",
      params: { key: "Enter" },
      assertions: [],
      rawEvent: { eventType: "keydown", key: "Enter" },
      targetSnapshot: buildSnapshot(target)
    });
  }, true);
})();
"""


def _as_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    return {}


def _as_list(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    return []


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def _resolve_manual_login_gate(runtime_options: dict[str, Any]) -> tuple[bool, int]:
    """解析手动登录闸门配置，统一支持驼峰/下划线命名。"""
    enabled_candidates = [
        runtime_options.get("manualLoginEnabled"),
        runtime_options.get("manual_login_enabled"),
        runtime_options.get("manualLoginGate"),
        runtime_options.get("manual_login_gate"),
        runtime_options.get("waitForManualLogin"),
        runtime_options.get("wait_for_manual_login"),
    ]
    enabled = False
    for candidate in enabled_candidates:
        if candidate not in (None, ""):
            enabled = _as_bool(candidate, False)
            break

    wait_candidates = [
        runtime_options.get("manualLoginWaitSec"),
        runtime_options.get("manual_login_wait_sec"),
        runtime_options.get("manualLoginTimeoutSec"),
        runtime_options.get("manual_login_timeout_sec"),
        runtime_options.get("manualLoginWaitSeconds"),
        runtime_options.get("manual_login_wait_seconds"),
    ]
    wait_sec = 120
    for candidate in wait_candidates:
        if candidate not in (None, ""):
            wait_sec = _as_int(candidate, 120)
            break
    wait_sec = max(0, min(wait_sec, 3600))
    return enabled, wait_sec


def _resolve_manual_login_require_confirm(runtime_options: dict[str, Any]) -> bool:
    """解析手动登录是否需要显式确认继续。"""
    candidates = [
        runtime_options.get("manualLoginRequireConfirm"),
        runtime_options.get("manual_login_require_confirm"),
        runtime_options.get("manualLoginNeedConfirm"),
        runtime_options.get("manual_login_need_confirm"),
    ]
    for candidate in candidates:
        if candidate not in (None, ""):
            return _as_bool(candidate, False)
    return False


async def _wait_manual_login_if_needed(
    page: Any,
    runtime_options: dict[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    """在执行/录制前为手动登录预留等待窗口。"""
    enabled, wait_sec = _resolve_manual_login_gate(runtime_options)
    gate_result: dict[str, Any] = {
        "enabled": enabled,
        "waitSec": wait_sec,
        "stage": stage,
        "waitedSec": 0,
    }
    try:
        gate_result["pageUrl"] = str(getattr(page, "url", "") or "")
    except Exception:
        gate_result["pageUrl"] = ""
    if not enabled or wait_sec <= 0:
        return gate_result

    logger.info(f"[manual-login-gate] stage={stage}, wait_sec={wait_sec}, page={gate_result.get('pageUrl')}")
    started_at = time.time()
    await asyncio.sleep(wait_sec)
    gate_result["waitedSec"] = max(0, int(round(time.time() - started_at)))
    return gate_result


def _resolve_runtime_settings(case_data: dict[str, Any], runtime_options: dict[str, Any]) -> dict[str, Any]:
    runtime_overrides = _as_dict(runtime_options.get("runtimeOverrides") or runtime_options.get("runtime_overrides"))
    case_runtime_settings = _as_dict(case_data.get("runtimeSettings") or case_data.get("runtime_settings"))
    return {
        **case_runtime_settings,
        **runtime_overrides,
        **runtime_options,
    }


def _resolve_persist_context_settings(runtime_options: dict[str, Any]) -> tuple[bool, str]:
    """解析是否启用浏览器状态保留，以及状态作用域键。"""
    enabled_candidates = [
        runtime_options.get("persistContextEnabled"),
        runtime_options.get("persist_context_enabled"),
        runtime_options.get("preserveBrowserContext"),
        runtime_options.get("preserve_browser_context"),
        runtime_options.get("keepBrowserCache"),
        runtime_options.get("keep_browser_cache"),
    ]
    enabled = False
    for candidate in enabled_candidates:
        if candidate not in (None, ""):
            enabled = _as_bool(candidate, False)
            break

    key_candidates = [
        runtime_options.get("persistContextKey"),
        runtime_options.get("persist_context_key"),
        runtime_options.get("preserveContextKey"),
        runtime_options.get("preserve_context_key"),
    ]
    scope_key = ""
    for candidate in key_candidates:
        text = str(candidate or "").strip()
        if text:
            scope_key = text
            break
    return enabled, scope_key


def _resolve_reuse_retained_session_id(runtime_options: dict[str, Any]) -> str:
    """解析跨用例复用浏览器会话ID。"""
    candidates = [
        runtime_options.get("reuseRetainedSessionId"),
        runtime_options.get("reuse_retained_session_id"),
        runtime_options.get("retainedSessionId"),
        runtime_options.get("retained_session_id"),
    ]
    for candidate in candidates:
        session_id = str(candidate or "").strip()
        if session_id:
            return session_id
    return ""


def _build_context_state_path(
    runtime_options: dict[str, Any],
    *,
    browser_name: str,
    start_url: str,
    default_scope: str = "",
) -> Path | None:
    """生成上下文状态文件路径，用于跨次执行保留 Cookie/LocalStorage。"""
    persist_enabled, scope_key = _resolve_persist_context_settings(runtime_options)
    if not persist_enabled:
        return None

    runtime_profile_id = str(
        runtime_options.get("runtimeProfileId")
        or runtime_options.get("runtime_profile_id")
        or ""
    ).strip()
    target_host = _host_from_url(start_url)
    raw_scope = scope_key or runtime_profile_id or default_scope or target_host or "default"
    safe_scope = re.sub(r"[^a-zA-Z0-9_.-]+", "_", raw_scope).strip("._-")
    if not safe_scope:
        safe_scope = "default"

    safe_browser = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(browser_name or "chromium")).strip("._-") or "chromium"
    storage_dir = Path(__file__).resolve().parents[1] / "storage" / "runtime" / "web-context-state"
    return storage_dir / f"{safe_scope}.{safe_browser}.json"


async def _create_browser_context(
    browser: Any,
    *,
    runtime_options: dict[str, Any],
    browser_name: str,
    start_url: str,
    default_scope: str = "",
) -> tuple[Any, Path | None]:
    """根据运行配置创建 BrowserContext（可选恢复历史状态）。"""
    state_path = _build_context_state_path(
        runtime_options,
        browser_name=browser_name,
        start_url=start_url,
        default_scope=default_scope,
    )
    context_kwargs: dict[str, Any] = {"ignore_https_errors": True}
    if state_path is not None and state_path.exists():
        context_kwargs["storage_state"] = str(state_path)
    context = await browser.new_context(**context_kwargs)
    return context, state_path


async def _save_context_state_if_needed(context: Any, state_path: Path | None) -> None:
    """在关闭上下文前落盘状态，便于下次恢复登录态。"""
    if context is None or state_path is None:
        return
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(state_path))
    except Exception as exc:
        logger.debug(f"保存浏览器上下文状态失败: {exc}")


def _step_timeout_ms(step: dict[str, Any], runtime_options: dict[str, Any], case_data: dict[str, Any]) -> int:
    params = _as_dict(step.get("params"))
    case_runtime = _as_dict(case_data.get("runtimeSettings") or case_data.get("runtime_settings"))
    candidates = [
        step.get("timeoutMs"),
        step.get("timeout_ms"),
        params.get("timeoutMs"),
        params.get("timeout_ms"),
        runtime_options.get("stepTimeoutMs"),
        runtime_options.get("step_timeout_ms"),
        runtime_options.get("timeoutMs"),
        runtime_options.get("timeout_ms"),
        case_runtime.get("stepTimeoutMs"),
        case_runtime.get("step_timeout_ms"),
        case_runtime.get("timeoutMs"),
        case_runtime.get("timeout_ms"),
        10000,
    ]
    for candidate in candidates:
        if candidate not in (None, ""):
            return max(_as_int(candidate, 10000), 500)
    return 10000


def _step_think_time_ms(step: dict[str, Any], runtime_options: dict[str, Any], case_data: dict[str, Any]) -> int:
    params = _as_dict(step.get("params"))
    case_runtime = _as_dict(case_data.get("runtimeSettings") or case_data.get("runtime_settings"))
    candidates = [
        step.get("thinkTimeMs"),
        step.get("think_time_ms"),
        params.get("thinkTimeMs"),
        params.get("think_time_ms"),
        runtime_options.get("stepThinkTimeMs"),
        runtime_options.get("step_think_time_ms"),
        runtime_options.get("thinkTimeMs"),
        runtime_options.get("think_time_ms"),
        case_runtime.get("stepThinkTimeMs"),
        case_runtime.get("step_think_time_ms"),
        case_runtime.get("thinkTimeMs"),
        case_runtime.get("think_time_ms"),
        0,
    ]
    for candidate in candidates:
        if candidate not in (None, ""):
            return max(_as_int(candidate, 0), 0)
    return 0


def _continue_on_failure(step: dict[str, Any], runtime_options: dict[str, Any]) -> bool:
    if step.get("continueOnFailure") is not None:
        return bool(step.get("continueOnFailure"))
    if step.get("continue_on_failure") is not None:
        return bool(step.get("continue_on_failure"))
    return bool(runtime_options.get("continueOnFailure", False))


def _has_following_enabled_step(steps: list[Any], current_index: int) -> bool:
    for idx in range(current_index + 1, len(steps)):
        candidate = _as_dict(steps[idx])
        if bool(candidate.get("enabled", True)):
            return True
    return False


_TEXT_SPACE_PATTERN = re.compile(r"\s+")


def _normalize_assert_text(value: Any) -> str:
    return _TEXT_SPACE_PATTERN.sub(" ", str(value or "")).strip()


def _compact_assert_text(value: str) -> str:
    return _TEXT_SPACE_PATTERN.sub("", value or "")


def _text_contains(actual: str, expected: str) -> bool:
    if expected in actual:
        return True
    expected_compact = _compact_assert_text(expected)
    if not expected_compact:
        return False
    return expected_compact in _compact_assert_text(actual)


def _text_equals(actual: str, expected: str) -> bool:
    if actual == expected:
        return True
    expected_compact = _compact_assert_text(expected)
    if not expected_compact:
        return False
    return _compact_assert_text(actual) == expected_compact


async def _read_locator_text(locator: Any, *, timeout_ms: int | None = None) -> str:
    kwargs: dict[str, Any] = {}
    if timeout_ms and timeout_ms > 0:
        kwargs["timeout"] = timeout_ms
    try:
        text = await locator.inner_text(**kwargs)
    except Exception:
        text = await locator.text_content(**kwargs)
    return _normalize_assert_text(text)


_ACTIONS_WITHOUT_TARGET = {
    "goto",
    "sleep",
    "wait",
    "assert_page_contains",
    "assert_page_not_contains",
    "assert_title_contains",
    "assert_url_contains",
}

_LOCATOR_TYPE_WEIGHT = {
    "test_id": 0,
    "id": 1,
    "name": 2,
    "role": 3,
    "label": 4,
    "placeholder": 5,
    "text": 6,
    "css": 7,
    "xpath": 8,
}


def _action_requires_locator(action_type: str) -> bool:
    return str(action_type or "").strip().lower() not in _ACTIONS_WITHOUT_TARGET


_VAR_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_.-]+)\}|\{\{([a-zA-Z0-9_.-]+)\}\}")


def _interpolate_string(value: str, variables: dict[str, Any]) -> str:
    if not value:
        return value

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2) or ""
        if key in variables:
            return str(variables.get(key) or "")
        return match.group(0)

    return _VAR_PATTERN.sub(_replace, str(value))


def _resolve_runtime_variables(runtime_options: dict[str, Any]) -> dict[str, Any]:
    variables: dict[str, Any] = {}
    for key in ("variables", "runtimeVariables", "runtime_variables", "cookieVariables", "cookie_variables"):
        value = runtime_options.get(key)
        if isinstance(value, dict):
            variables.update(value)
    return variables


def _normalize_cookie_rules(runtime_options: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for key in ("cookieRules", "cookie_rules", "cookieScopes", "cookie_scopes", "cookieProfiles", "cookie_profiles"):
        for item in _as_list(runtime_options.get(key)):
            if not isinstance(item, dict):
                continue
            cookies = _as_list(item.get("cookies"))
            if not cookies:
                continue
            match = _as_dict(item.get("match"))
            for match_key in ("host", "domain", "urlContains", "url_contains", "urlRegex", "url_regex"):
                if item.get(match_key) not in (None, "") and match_key not in match:
                    match[match_key] = item.get(match_key)
            apply_on = _as_list(item.get("applyOn") or item.get("apply_on"))
            normalized_apply_on = {
                str(entry).strip().lower()
                for entry in apply_on
                if str(entry).strip()
            }
            if not normalized_apply_on:
                normalized_apply_on = {"before_start", "before_step", "before_goto"}
            rules.append(
                {
                    "name": str(item.get("name") or f"rule_{len(rules) + 1}"),
                    "match": match,
                    "applyOn": normalized_apply_on,
                    "cookies": cookies,
                }
            )
    global_cookies = _as_list(runtime_options.get("cookies"))
    if global_cookies:
        rules.append(
            {
                "name": "global_cookies",
                "match": {},
                "applyOn": {"before_start", "before_step", "before_goto"},
                "cookies": global_cookies,
            }
        )
    return rules


def _host_from_url(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value)]


def _rule_matches_url(rule: dict[str, Any], *, url: str, host: str, variables: dict[str, Any]) -> bool:
    match = _as_dict(rule.get("match"))
    if not match:
        return True

    host_values = _ensure_list(match.get("host")) + _ensure_list(match.get("domain"))
    if host_values:
        normalized = [_interpolate_string(item.lower(), variables) for item in host_values]
        if not host:
            return False
        if not any(host == item or host.endswith(f".{item}") for item in normalized if item):
            return False

    contains_values = _ensure_list(match.get("urlContains") or match.get("url_contains"))
    if contains_values:
        normalized = [_interpolate_string(item, variables) for item in contains_values]
        if not any(item and item in url for item in normalized):
            return False

    regex_values = _ensure_list(match.get("urlRegex") or match.get("url_regex"))
    if regex_values:
        matched = False
        for item in regex_values:
            pattern = _interpolate_string(item, variables)
            if not pattern:
                continue
            try:
                if re.search(pattern, url):
                    matched = True
                    break
            except re.error:
                continue
        if not matched:
            return False

    return True


def _normalize_cookie_item(
    cookie_item: dict[str, Any],
    *,
    variables: dict[str, Any],
    target_url: str,
    target_host: str,
    default_domain: str = "",
) -> dict[str, Any] | None:
    name = _interpolate_string(str(cookie_item.get("name") or ""), variables).strip()
    if not name:
        return None
    value = _interpolate_string(str(cookie_item.get("value") or ""), variables)
    if value == "":
        return None

    cookie_payload: dict[str, Any] = {"name": name, "value": value}

    explicit_url = cookie_item.get("url")
    explicit_domain = cookie_item.get("domain")
    explicit_path = cookie_item.get("path")
    default_domain_value = _interpolate_string(str(default_domain or ""), variables).strip().lstrip(".")

    if explicit_url:
        cookie_payload["url"] = _interpolate_string(str(explicit_url), variables)
    elif explicit_domain:
        cookie_payload["domain"] = _interpolate_string(str(explicit_domain), variables)
        cookie_payload["path"] = _interpolate_string(str(explicit_path or "/"), variables)
    elif default_domain_value:
        cookie_payload["domain"] = default_domain_value
        cookie_payload["path"] = _interpolate_string(str(explicit_path or "/"), variables)
    elif target_url:
        cookie_payload["url"] = target_url
    elif target_host:
        cookie_payload["domain"] = target_host
        cookie_payload["path"] = "/"
    else:
        return None

    if cookie_item.get("httpOnly") is not None:
        cookie_payload["httpOnly"] = bool(cookie_item.get("httpOnly"))
    if cookie_item.get("secure") is not None:
        cookie_payload["secure"] = bool(cookie_item.get("secure"))
    if cookie_item.get("sameSite") is not None:
        same_site = str(cookie_item.get("sameSite") or "").strip().lower()
        if same_site in {"lax", "strict", "none"}:
            cookie_payload["sameSite"] = same_site.capitalize()
    if cookie_item.get("expires") not in (None, ""):
        cookie_payload["expires"] = _as_int(cookie_item.get("expires"))
    return cookie_payload


def _summarize_cookie_for_debug(cookie_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(cookie_item.get("name") or ""),
        "domain": cookie_item.get("domain"),
        "path": cookie_item.get("path"),
        "url": cookie_item.get("url"),
        "httpOnly": bool(cookie_item.get("httpOnly")) if cookie_item.get("httpOnly") is not None else None,
        "secure": bool(cookie_item.get("secure")) if cookie_item.get("secure") is not None else None,
        "sameSite": cookie_item.get("sameSite"),
        "expires": cookie_item.get("expires"),
    }


async def _capture_context_cookies_for_debug(context: Any, *, target_url: str) -> list[dict[str, Any]]:
    if context is None:
        return []
    try:
        if target_url:
            cookies = await context.cookies([target_url])
        else:
            cookies = await context.cookies()
    except Exception:
        return []
    result: list[dict[str, Any]] = []
    for item in _as_list(cookies):
        cookie_item = _as_dict(item)
        if not cookie_item:
            continue
        result.append(
            {
                "name": str(cookie_item.get("name") or ""),
                "domain": cookie_item.get("domain"),
                "path": cookie_item.get("path"),
                "httpOnly": bool(cookie_item.get("httpOnly")) if cookie_item.get("httpOnly") is not None else None,
                "secure": bool(cookie_item.get("secure")) if cookie_item.get("secure") is not None else None,
                "sameSite": cookie_item.get("sameSite"),
                "expires": cookie_item.get("expires"),
            }
        )
    return result


async def _apply_cookie_rules(
    context: Any,
    *,
    target_url: str,
    stage: str,
    cookie_rules: list[dict[str, Any]],
    variables: dict[str, Any],
) -> dict[str, Any] | None:
    if context is None or not cookie_rules:
        return None

    stage_name = str(stage or "").strip().lower()
    host = _host_from_url(target_url)
    cookies_to_apply: list[dict[str, Any]] = []
    applied_rule_names: list[str] = []

    for rule in cookie_rules:
        apply_on = set(rule.get("applyOn") or set())
        if stage_name and apply_on and stage_name not in apply_on:
            continue
        if not _rule_matches_url(rule, url=target_url, host=host, variables=variables):
            continue

        rule_match = _as_dict(rule.get("match"))
        default_domain_candidates = _ensure_list(rule_match.get("domain")) + _ensure_list(rule_match.get("host"))
        default_domain = ""
        for candidate in default_domain_candidates:
            normalized_candidate = _interpolate_string(str(candidate or ""), variables).strip().lstrip(".").lower()
            if normalized_candidate:
                default_domain = normalized_candidate
                break

        applied_rule_names.append(str(rule.get("name") or "rule"))
        for raw_cookie in _as_list(rule.get("cookies")):
            cookie_def = _as_dict(raw_cookie)
            if not cookie_def:
                continue
            normalized_cookie = _normalize_cookie_item(
                cookie_def,
                variables=variables,
                target_url=target_url,
                target_host=host,
                default_domain=default_domain,
            )
            if normalized_cookie is not None:
                cookies_to_apply.append(normalized_cookie)

    if not cookies_to_apply:
        return None

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in cookies_to_apply:
        domain_or_url = str(item.get("domain") or item.get("url") or "")
        path = str(item.get("path") or "/")
        deduped[(str(item.get("name")), domain_or_url, path)] = item

    final_payload = list(deduped.values())
    if not final_payload:
        return None
    await context.add_cookies(final_payload)
    return {
        "stage": stage_name,
        "targetUrl": target_url,
        "targetHost": host,
        "appliedCount": len(final_payload),
        "rules": applied_rule_names,
        "appliedCookies": [_summarize_cookie_for_debug(item) for item in final_payload],
    }


async def _close_playwright_objects(
    page: Any,
    context: Any,
    browser: Any,
    playwright: Any,
) -> None:
    if page is not None:
        try:
            await page.close()
        except Exception as exc:
            logger.debug(f"关闭 page 失败: {exc}")
    if context is not None:
        try:
            await context.close()
        except Exception as exc:
            logger.debug(f"关闭 context 失败: {exc}")
    if browser is not None:
        try:
            await browser.close()
        except Exception as exc:
            logger.debug(f"关闭 browser 失败: {exc}")
    if playwright is not None:
        try:
            await playwright.stop()
        except Exception as exc:
            logger.debug(f"关闭 playwright 失败: {exc}")


@dataclass
class RecorderSession:
    recording_id: int
    agent_code: str
    sender: EventSender
    browser_name: str
    headless: bool
    start_url: str
    options: dict[str, Any]
    runtime_options: dict[str, Any] = field(default_factory=dict)
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    context_state_path: Path | None = None
    event_index: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    active: bool = True
    capture_enabled: bool = False
    manual_login_pending: bool = False

    async def emit(self, payload: dict[str, Any], event_type: str = "record_event") -> None:
        if not self.active:
            return
        self.event_index += 1
        self.events.append(payload)
        await self.sender(
            {
                "type": event_type,
                "recording_id": self.recording_id,
                "event_index": self.event_index,
                "payload": payload,
            }
        )

    async def disable_recording(self) -> None:
        self.active = False
        if self.context is not None:
            try:
                await self.context.add_init_script(
                    "window.__qtrRecordActive__ = false;"
                )
            except Exception as exc:
                logger.debug(f"禁用后续页面录制脚本失败: {exc}")
        if self.page is not None:
            try:
                await self.page.evaluate("() => { window.__qtrRecordActive__ = false; }")
            except Exception as exc:
                logger.debug(f"禁用当前页面录制脚本失败: {exc}")

    async def close(self) -> None:
        self.active = False
        page = self.page
        context = self.context
        browser = self.browser
        playwright = self.playwright
        context_state_path = self.context_state_path
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self.context_state_path = None
        await _save_context_state_if_needed(context, context_state_path)
        await _close_playwright_objects(page, context, browser, playwright)


@dataclass
class RetainedRunSession:
    session_id: str
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    context_state_path: Path | None = None

    async def close(self) -> None:
        page = self.page
        context = self.context
        browser = self.browser
        playwright = self.playwright
        context_state_path = self.context_state_path
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self.context_state_path = None
        await _save_context_state_if_needed(context, context_state_path)
        await _close_playwright_objects(page, context, browser, playwright)


@dataclass
class PreparedRunSession:
    run_id: int
    case_data: dict[str, Any]
    runtime_options: dict[str, Any]
    effective_runtime: dict[str, Any]
    steps: list[dict[str, Any]]
    start_url: str
    close_browser_on_finish: bool
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    context_state_path: Path | None = None
    cookie_variables: dict[str, Any] = field(default_factory=dict)
    cookie_rules: list[dict[str, Any]] = field(default_factory=list)
    runtime_debug: dict[str, Any] = field(default_factory=dict)

    async def close(self) -> None:
        page = self.page
        context = self.context
        browser = self.browser
        playwright = self.playwright
        context_state_path = self.context_state_path
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self.context_state_path = None
        await _save_context_state_if_needed(context, context_state_path)
        await _close_playwright_objects(page, context, browser, playwright)


@dataclass
class ActiveRunSession:
    run_id: int
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    page: Any = None
    context: Any = None
    browser: Any = None
    playwright: Any = None
    context_state_path: Path | None = None

    async def request_cancel(self) -> None:
        self.cancel_event.set()
        page = self.page
        context = self.context
        browser = self.browser
        playwright = self.playwright
        context_state_path = self.context_state_path
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self.context_state_path = None
        await _save_context_state_if_needed(context, context_state_path)
        await _close_playwright_objects(page, context, browser, playwright)

    async def close(self) -> None:
        await self.request_cancel()


class WebTestService:
    _recorders: dict[int, RecorderSession] = {}
    _retained_sessions: dict[int, RecorderSession] = {}
    _retained_runs: dict[str, RetainedRunSession] = {}
    _prepared_runs: dict[int, PreparedRunSession] = {}
    _active_runs: dict[int, ActiveRunSession] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def handle_request(cls, req_data: dict[str, Any], event_sender: EventSender | None = None) -> dict[str, Any]:
        command = req_data.get("command") or "run_case"
        if command == "run_case":
            return await cls._run_case(req_data)
        if command == "prepare_run_case":
            return await cls._prepare_run_case(req_data)
        if command == "continue_run_case":
            return await cls._continue_run_case(req_data)
        if command == "stop_run_case":
            return await cls._stop_run_case(req_data)
        if command == "cancel_run_case":
            return await cls._cancel_run_case(req_data)
        if command == "start_recording":
            return await cls._start_recording(req_data, event_sender)
        if command == "continue_recording":
            return await cls._continue_recording(req_data)
        if command == "cancel_recording_prepare":
            return await cls._cancel_recording_prepare(req_data)
        if command == "stop_recording":
            return await cls._stop_recording(req_data)
        return {
            "request_type": 3,
            "command": command,
            "success": False,
            "status": "failed",
            "message": f"unsupported webui command: {command}",
        }

    @classmethod
    async def _start_recording(cls, req_data: dict[str, Any], event_sender: EventSender | None) -> dict[str, Any]:
        if event_sender is None:
            return {
                "request_type": 3,
                "command": "start_recording",
                "success": False,
                "status": "failed",
                "message": "缺少事件发送器，无法实时推送录制结果",
            }
        recording_id = int(req_data.get("recordingId") or 0)
        if not recording_id:
            return {
                "request_type": 3,
                "command": "start_recording",
                "success": False,
                "status": "failed",
                "message": "recordingId 不能为空",
            }

        async with cls._lock:
            if recording_id in cls._recorders:
                return {
                    "request_type": 3,
                    "command": "start_recording",
                    "success": True,
                    "status": "accepted",
                    "recording_id": recording_id,
                    "message": "录制已在进行中",
                }

            session = RecorderSession(
                recording_id=recording_id,
                agent_code=str(req_data.get("agentCode") or ""),
                sender=event_sender,
                browser_name=str(req_data.get("browserName") or "chromium"),
                headless=bool(req_data.get("headless", False)),
                start_url=str(req_data.get("startUrl") or ""),
                options=_as_dict(req_data.get("recordingOptions")),
                runtime_options=_as_dict(req_data.get("runtimeOptions")),
            )
            cls._recorders[recording_id] = session

        try:
            runtime_overrides = _as_dict(session.runtime_options.get("runtimeOverrides") or session.runtime_options.get("runtime_overrides"))
            effective_runtime = {
                **runtime_overrides,
                **session.runtime_options,
            }
            browser_request_options = {
                **session.options,
                **effective_runtime,
            }
            session.playwright, session.browser = await start_playwright_browser(
                session.browser_name,
                headless=session.headless,
                request_options=browser_request_options,
            )
            session.context, session.context_state_path = await _create_browser_context(
                session.browser,
                runtime_options=effective_runtime,
                browser_name=session.browser_name,
                start_url=session.start_url,
                default_scope=f"recording-{recording_id}",
            )
            session.page = await session.context.new_page()
            cookie_variables = _resolve_runtime_variables(effective_runtime)
            cookie_rules = _normalize_cookie_rules(effective_runtime)
            if session.start_url:
                await _apply_cookie_rules(
                    session.context,
                    target_url=session.start_url,
                    stage="before_start",
                    cookie_rules=cookie_rules,
                    variables=cookie_variables,
                )
            if session.start_url:
                await session.page.goto(session.start_url)

            manual_login_enabled, manual_login_wait_sec = _resolve_manual_login_gate(effective_runtime)
            manual_login_require_confirm = _resolve_manual_login_require_confirm(effective_runtime)
            manual_gate_result: dict[str, Any] = {
                "enabled": manual_login_enabled,
                "waitSec": manual_login_wait_sec,
                "requireConfirm": manual_login_require_confirm,
                "waitingConfirm": False,
                "stage": "before_recording",
                "pageUrl": session.page.url if session.page else session.start_url,
            }
            if manual_login_enabled and manual_login_require_confirm:
                session.manual_login_pending = True
                manual_gate_result["waitingConfirm"] = True
                await session.sender(
                    {
                        "type": "record_status",
                        "recording_id": recording_id,
                        "payload": {
                            "status": "waiting_manual_login",
                            "message": "浏览器已启动，请手动登录后点击继续录制",
                            "manualLoginGate": manual_gate_result,
                        },
                    }
                )
            else:
                manual_gate_result = await _wait_manual_login_if_needed(
                    session.page,
                    effective_runtime,
                    stage="before_recording",
                )
                manual_gate_result["requireConfirm"] = False
                if manual_gate_result.get("enabled"):
                    await session.sender(
                        {
                            "type": "record_status",
                            "recording_id": recording_id,
                            "payload": {
                                "status": "manual_login_ready",
                                "message": "手动登录等待结束，开始录制",
                                "manualLoginGate": manual_gate_result,
                            },
                        }
                    )
                await cls._enable_recording_capture(session)
            return {
                "request_type": 3,
                "command": "start_recording",
                "success": True,
                "status": "accepted",
                "recording_id": recording_id,
                "data": {
                    "manualLoginGate": manual_gate_result,
                },
            }
        except Exception as exc:
            logger.exception(exc)
            async with cls._lock:
                cls._recorders.pop(recording_id, None)
            try:
                await session.sender(
                    {
                        "type": "record_error",
                        "recording_id": recording_id,
                        "message": str(exc),
                        "payload": {"message": str(exc)},
                    }
                )
                await session.close()
            except Exception:
                pass
            return {
                "request_type": 3,
                "command": "start_recording",
                "success": False,
                "status": "failed",
                "message": str(exc),
            }

    @classmethod
    async def _enable_recording_capture(cls, session: RecorderSession) -> None:
        """给录制会话注入录制脚本并开始捕获事件。"""
        if session.capture_enabled:
            return
        if session.context is None:
            raise RuntimeError("录制上下文不存在，无法继续录制")
        if session.page is None:
            raise RuntimeError("录制页面不存在，无法继续录制")

        async def _event_binding(source: Any, payload: Any) -> None:
            payload_dict = _as_dict(payload)
            if not payload_dict:
                return
            await session.emit(payload_dict)

        await session.context.expose_binding("__qtrRecordEvent", _event_binding)
        options_json = json.dumps(session.options, ensure_ascii=False)
        await session.context.add_init_script(f"window.__qtrRecordOptions__ = {options_json};")
        await session.context.add_init_script(RECORDER_SCRIPT)
        try:
            await session.page.evaluate("opts => { window.__qtrRecordOptions__ = opts; }", session.options)
            await session.page.evaluate(RECORDER_SCRIPT)
        except Exception as exc:
            logger.debug(f"注入当前页面录制脚本失败: {exc}")
        session.page.on(
            "framenavigated",
            lambda frame: asyncio.create_task(cls._handle_navigation(frame, session)),
        )
        await session.emit(
            {
                "stepName": "打开页面",
                "actionType": "goto",
                "params": {"url": session.start_url},
                "assertions": [],
                "rawEvent": {"eventType": "goto"},
                "targetSnapshot": None,
            }
        )
        session.capture_enabled = True

    @classmethod
    async def _continue_recording(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        recording_id = int(req_data.get("recordingId") or 0)
        if not recording_id:
            return {
                "request_type": 3,
                "command": "continue_recording",
                "success": False,
                "status": "failed",
                "message": "recordingId 不能为空",
            }
        async with cls._lock:
            session = cls._recorders.get(recording_id)
        if session is None:
            return {
                "request_type": 3,
                "command": "continue_recording",
                "success": False,
                "status": "failed",
                "message": "录制会话不存在",
            }
        if not session.manual_login_pending:
            return {
                "request_type": 3,
                "command": "continue_recording",
                "success": True,
                "status": "accepted",
                "recording_id": recording_id,
                "message": "当前录制无需继续确认",
            }
        try:
            session.manual_login_pending = False
            await cls._enable_recording_capture(session)
            await session.sender(
                {
                    "type": "record_status",
                    "recording_id": recording_id,
                    "payload": {
                        "status": "manual_login_ready",
                        "message": "已确认继续，开始录制",
                        "manualLoginGate": {
                            "enabled": True,
                            "requireConfirm": True,
                            "waitingConfirm": False,
                            "stage": "before_recording",
                            "pageUrl": session.page.url if session.page else session.start_url,
                        },
                    },
                }
            )
            return {
                "request_type": 3,
                "command": "continue_recording",
                "success": True,
                "status": "accepted",
                "recording_id": recording_id,
            }
        except Exception as exc:
            logger.exception(exc)
            return {
                "request_type": 3,
                "command": "continue_recording",
                "success": False,
                "status": "failed",
                "recording_id": recording_id,
                "message": str(exc),
            }

    @classmethod
    async def _handle_navigation(cls, frame: Any, session: RecorderSession) -> None:
        if not session.active or session.page is None or frame != session.page.main_frame:
            return
        await session.emit(
            {
                "stepName": "页面跳转",
                "actionType": "goto",
                "params": {"url": frame.url},
                "assertions": [],
                "rawEvent": {"eventType": "framenavigated"},
                "targetSnapshot": None,
            },
            event_type="record_status",
        )

    @classmethod
    async def _stop_recording(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        recording_id = int(req_data.get("recordingId") or 0)
        async with cls._lock:
            session = cls._recorders.pop(recording_id, None)
        if session is None:
            return {
                "request_type": 3,
                "command": "stop_recording",
                "success": False,
                "status": "failed",
                "message": "录制会话不存在",
            }
        close_browser_on_stop = req_data.get("closeBrowserOnStop")
        if close_browser_on_stop is None:
            close_browser_on_stop = session.options.get("closeBrowserOnStop")
        if close_browser_on_stop is None:
            close_browser_on_stop = session.headless
        else:
            close_browser_on_stop = bool(close_browser_on_stop)

        await session.disable_recording()
        await session.sender(
            {
                "type": "record_finished",
                "recording_id": recording_id,
                "payload": {"eventCount": len(session.events), "lastUrl": session.page.url if session.page else ""},
            }
        )
        if close_browser_on_stop:
            await session.close()
        else:
            async with cls._lock:
                cls._retained_sessions[recording_id] = session
        return {
            "request_type": 3,
            "command": "stop_recording",
            "success": True,
            "status": "stopped",
            "recording_id": recording_id,
            "data": {
                "eventCount": len(session.events),
                "browserRetained": not close_browser_on_stop,
            },
        }

    @classmethod
    async def shutdown_all_sessions(cls) -> None:
        async with cls._lock:
            sessions = (
                list(cls._recorders.values())
                + list(cls._retained_sessions.values())
                + list(cls._retained_runs.values())
                + list(cls._prepared_runs.values())
                + list(cls._active_runs.values())
            )
            cls._recorders.clear()
            cls._retained_sessions.clear()
            cls._retained_runs.clear()
            cls._prepared_runs.clear()
            cls._active_runs.clear()

        for session in sessions:
            try:
                await session.close()
            except Exception as exc:
                logger.exception(exc)

    @classmethod
    async def _prepare_run_case(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        run_id = _as_int(req_data.get("webCaseRunId") or req_data.get("web_case_run_id"), 0)
        if run_id <= 0:
            return {
                "request_type": 3,
                "command": "prepare_run_case",
                "success": False,
                "status": "failed",
                "message": "webCaseRunId 不能为空",
            }

        async with cls._lock:
            existing = cls._prepared_runs.get(run_id)
        if existing is not None:
            return {
                "request_type": 3,
                "command": "prepare_run_case",
                "success": True,
                "status": "waiting_manual_login",
                "result": {
                    "webCaseRunId": run_id,
                    "pageUrl": existing.page.url if existing.page else existing.start_url,
                    "runtimeDebug": existing.runtime_debug or {},
                    "awaitingManualConfirm": True,
                },
            }

        case_data = _as_dict(req_data.get("caseData"))
        runtime_options = _as_dict(req_data.get("runtimeOptions"))
        effective_runtime = _resolve_runtime_settings(case_data, runtime_options)
        browser_name = str(effective_runtime.get("browserName") or case_data.get("browserName") or "chromium")
        headless = bool(effective_runtime.get("headless", case_data.get("headless", True)))
        close_browser_on_finish = effective_runtime.get("closeBrowserOnFinish")
        if close_browser_on_finish is None:
            close_browser_on_finish = True
        else:
            close_browser_on_finish = bool(close_browser_on_finish)
        start_url = str(effective_runtime.get("startUrl") or case_data.get("startUrl") or "")
        steps = case_data.get("steps") or []
        if not isinstance(steps, list):
            steps = []

        prepared = PreparedRunSession(
            run_id=run_id,
            case_data=case_data,
            runtime_options=runtime_options,
            effective_runtime=effective_runtime,
            steps=[_as_dict(step) for step in steps],
            start_url=start_url,
            close_browser_on_finish=close_browser_on_finish,
        )
        try:
            prepared.playwright, prepared.browser = await start_playwright_browser(
                browser_name,
                headless=headless,
                request_options=effective_runtime,
            )
            prepared.context, prepared.context_state_path = await _create_browser_context(
                prepared.browser,
                runtime_options=effective_runtime,
                browser_name=browser_name,
                start_url=start_url,
                default_scope=f"run-{run_id}",
            )
            prepared.page = await prepared.context.new_page()
            prepared.cookie_variables = _resolve_runtime_variables(effective_runtime)
            prepared.cookie_rules = _normalize_cookie_rules(effective_runtime)
            prepared.runtime_debug = {
                "runtimeProfileId": runtime_options.get("runtimeProfileId") or runtime_options.get("runtime_profile_id"),
                "cookieRuleCount": len(prepared.cookie_rules),
                "cookieVariableKeys": sorted(prepared.cookie_variables.keys()),
                "persistContextEnabled": prepared.context_state_path is not None,
                "persistContextPath": str(prepared.context_state_path) if prepared.context_state_path is not None else "",
            }
            if start_url:
                before_start_cookie_apply = await _apply_cookie_rules(
                    prepared.context,
                    target_url=start_url,
                    stage="before_start",
                    cookie_rules=prepared.cookie_rules,
                    variables=prepared.cookie_variables,
                )
                prepared.runtime_debug["beforeStartCookieApply"] = before_start_cookie_apply or {
                    "stage": "before_start",
                    "targetUrl": start_url,
                    "targetHost": _host_from_url(start_url),
                    "appliedCount": 0,
                    "rules": [],
                    "appliedCookies": [],
                }
                prepared.runtime_debug["contextCookiesBeforeGoto"] = await _capture_context_cookies_for_debug(
                    prepared.context,
                    target_url=start_url,
                )
                await prepared.page.goto(start_url, timeout=_step_timeout_ms({}, effective_runtime, case_data))
                prepared.runtime_debug["contextCookiesAfterGoto"] = await _capture_context_cookies_for_debug(
                    prepared.context,
                    target_url=start_url,
                )
            manual_login_enabled, manual_login_wait_sec = _resolve_manual_login_gate(effective_runtime)
            prepared.runtime_debug["manualLoginGate"] = {
                "enabled": manual_login_enabled,
                "waitSec": manual_login_wait_sec,
                "requireConfirm": True,
                "waitingConfirm": True,
                "stage": "before_case_steps",
                "pageUrl": prepared.page.url if prepared.page else start_url,
            }
            prepared.runtime_debug.setdefault(
                "beforeStartCookieApply",
                {
                    "stage": "before_start",
                    "targetUrl": start_url,
                    "targetHost": _host_from_url(start_url),
                    "appliedCount": 0,
                    "rules": [],
                    "appliedCookies": [],
                },
            )
            async with cls._lock:
                cls._prepared_runs[run_id] = prepared
            return {
                "request_type": 3,
                "command": "prepare_run_case",
                "success": True,
                "status": "waiting_manual_login",
                "result": {
                    "webCaseRunId": run_id,
                    "pageUrl": prepared.page.url if prepared.page else start_url,
                    "runtimeDebug": prepared.runtime_debug,
                    "awaitingManualConfirm": True,
                },
                "message": "浏览器已就绪，请手动登录后继续执行",
            }
        except Exception as exc:
            logger.exception(exc)
            async with cls._lock:
                cls._prepared_runs.pop(run_id, None)
            await prepared.close()
            return {
                "request_type": 3,
                "command": "prepare_run_case",
                "success": False,
                "status": "failed",
                "message": str(exc),
            }

    @classmethod
    async def _continue_run_case(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        run_id = _as_int(req_data.get("webCaseRunId") or req_data.get("web_case_run_id"), 0)
        if run_id <= 0:
            return {
                "request_type": 3,
                "command": "continue_run_case",
                "success": False,
                "status": "failed",
                "message": "webCaseRunId 不能为空",
            }
        async with cls._lock:
            prepared = cls._prepared_runs.pop(run_id, None)
        if prepared is None:
            return {
                "request_type": 3,
                "command": "continue_run_case",
                "success": False,
                "status": "failed",
                "message": "未找到等待继续的执行会话",
                "result": {"webCaseRunId": run_id},
            }

        page = prepared.page
        context = prepared.context
        browser = prepared.browser
        playwright = prepared.playwright
        context_state_path = prepared.context_state_path
        case_data = prepared.case_data
        effective_runtime = prepared.effective_runtime
        steps = prepared.steps
        start_url = prepared.start_url
        cookie_rules = prepared.cookie_rules
        cookie_variables = prepared.cookie_variables
        runtime_debug = prepared.runtime_debug if isinstance(prepared.runtime_debug, dict) else {}
        runtime_debug.setdefault(
            "manualLoginGate",
            {
                "enabled": True,
                "requireConfirm": True,
                "waitingConfirm": False,
                "stage": "before_case_steps",
            },
        )
        runtime_debug["manualLoginGate"]["waitingConfirm"] = False
        runtime_debug["manualLoginGate"]["confirmed"] = True
        runtime_debug["manualLoginGate"]["confirmedAt"] = int(time.time())
        runtime_debug.setdefault("persistContextEnabled", context_state_path is not None)
        runtime_debug.setdefault("persistContextPath", str(context_state_path) if context_state_path is not None else "")

        active_session = ActiveRunSession(
            run_id=run_id,
            page=page,
            context=context,
            browser=browser,
            playwright=playwright,
            context_state_path=context_state_path,
        )
        async with cls._lock:
            cls._active_runs[run_id] = active_session

        result_steps: list[dict[str, Any]] = []
        response_payload: dict[str, Any]
        retained_session_id: str | None = None
        try:
            overall_success = True
            for step_index, raw_step in enumerate(steps):
                if active_session.cancel_event.is_set():
                    raise RuntimeError("执行已取消")
                step = _as_dict(raw_step)
                if not bool(step.get("enabled", True)):
                    result_steps.append(
                        {
                            "stepId": step.get("stepId") or step.get("step_id"),
                            "stepName": step.get("stepName") or step.get("step_name") or "step",
                            "status": "skipped",
                            "durationMs": 0,
                            "message": "步骤已禁用",
                            "pageUrl": page.url if page else start_url,
                        }
                    )
                    continue

                step_result = await cls._run_single_step(
                    page,
                    context,
                    step,
                    runtime_options=effective_runtime,
                    case_data=case_data,
                    cookie_rules=cookie_rules,
                    cookie_variables=cookie_variables,
                )
                result_steps.append(step_result)
                if active_session.cancel_event.is_set():
                    step_result["message"] = "执行已取消"
                    step_result["error"] = "执行已取消"
                    step_result["errorMessage"] = "执行已取消"
                    overall_success = False
                    break
                if step_result["status"] != "passed":
                    overall_success = False
                    if not _continue_on_failure(step, effective_runtime):
                        break
                think_time_ms = _step_think_time_ms(step, effective_runtime, case_data)
                if think_time_ms > 0 and _has_following_enabled_step(steps, step_index):
                    await asyncio.sleep(think_time_ms / 1000.0)
                    step_result["thinkTimeMs"] = think_time_ms

            runtime_debug.setdefault(
                "beforeStartCookieApply",
                {
                    "stage": "before_start",
                    "targetUrl": start_url,
                    "targetHost": _host_from_url(start_url),
                    "appliedCount": 0,
                    "rules": [],
                    "appliedCookies": [],
                },
            )
            response_payload = {
                "request_type": 3,
                "command": "continue_run_case",
                "success": overall_success,
                "status": "success" if overall_success else "failed",
                "result": {
                    "steps": result_steps,
                    "pageUrl": page.url if page else start_url,
                    "runtimeDebug": runtime_debug,
                },
            }
        except Exception as exc:
            logger.exception(exc)
            runtime_debug.setdefault(
                "beforeStartCookieApply",
                {
                    "stage": "before_start",
                    "targetUrl": start_url,
                    "targetHost": _host_from_url(start_url),
                    "appliedCount": 0,
                    "rules": [],
                    "appliedCookies": [],
                },
            )
            response_payload = {
                "request_type": 3,
                "command": "continue_run_case",
                "success": False,
                "status": "failed",
                "message": "执行已取消" if active_session.cancel_event.is_set() else str(exc),
                "result": {
                    "steps": result_steps,
                    "pageUrl": page.url if page else start_url,
                    "runtimeDebug": runtime_debug,
                },
            }
        finally:
            async with cls._lock:
                cls._active_runs.pop(run_id, None)
            cancelled = active_session.cancel_event.is_set()
            if cancelled or prepared.close_browser_on_finish or browser is None or playwright is None:
                await _save_context_state_if_needed(context, context_state_path)
                await _close_playwright_objects(page, context, browser, playwright)
            else:
                retained_session_id = uuid.uuid4().hex
                retained_session = RetainedRunSession(
                    session_id=retained_session_id,
                    playwright=playwright,
                    browser=browser,
                    context=context,
                    page=page,
                    context_state_path=context_state_path,
                )
                async with cls._lock:
                    cls._retained_runs[retained_session_id] = retained_session

        if isinstance(response_payload.get("result"), dict):
            response_payload["result"]["browserRetained"] = retained_session_id is not None
            if retained_session_id is not None:
                response_payload["result"]["retainedSessionId"] = retained_session_id
        return response_payload

    @classmethod
    async def _stop_run_case(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        run_id = _as_int(req_data.get("webCaseRunId") or req_data.get("web_case_run_id"), 0)
        if run_id <= 0:
            return {
                "request_type": 3,
                "command": "stop_run_case",
                "success": False,
                "status": "failed",
                "message": "webCaseRunId 不能为空",
            }
        reason = str(req_data.get("reason") or "已手动停止执行").strip() or "已手动停止执行"

        async with cls._lock:
            active_session = cls._active_runs.pop(run_id, None)
            prepared_session = cls._prepared_runs.pop(run_id, None)

        released = False
        if active_session is not None:
            released = True
            try:
                await active_session.request_cancel()
            except Exception as exc:
                logger.exception(exc)
        if prepared_session is not None:
            released = True
            try:
                await prepared_session.close()
            except Exception as exc:
                logger.exception(exc)

        return {
            "request_type": 3,
            "command": "stop_run_case",
            "success": True,
            "status": "stopped",
            "message": reason if released else "执行会话已结束，无需停止",
            "result": {
                "webCaseRunId": run_id,
                "released": released,
                "reason": reason,
            },
        }

    @classmethod
    async def _cancel_run_case(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        run_id = _as_int(req_data.get("webCaseRunId") or req_data.get("web_case_run_id"), 0)
        if run_id <= 0:
            return {
                "request_type": 3,
                "command": "cancel_run_case",
                "success": False,
                "status": "failed",
                "message": "webCaseRunId 不能为空",
            }
        reason = str(req_data.get("reason") or "已取消执行准备").strip() or "已取消执行准备"

        async with cls._lock:
            prepared_session = cls._prepared_runs.pop(run_id, None)
            active_session = cls._active_runs.pop(run_id, None)

        released = False
        if prepared_session is not None:
            released = True
            try:
                await prepared_session.close()
            except Exception as exc:
                logger.exception(exc)
        elif active_session is not None:
            # 并发场景下可能已经从“准备态”切到“执行中”，这里兜底中断，避免资源泄漏。
            released = True
            try:
                await active_session.request_cancel()
            except Exception as exc:
                logger.exception(exc)

        return {
            "request_type": 3,
            "command": "cancel_run_case",
            "success": True,
            "status": "cancelled",
            "message": reason if released else "执行准备会话已结束",
            "result": {
                "webCaseRunId": run_id,
                "released": released,
                "reason": reason,
            },
        }

    @classmethod
    async def _cancel_recording_prepare(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        recording_id = _as_int(req_data.get("recordingId"), 0)
        if recording_id <= 0:
            return {
                "request_type": 3,
                "command": "cancel_recording_prepare",
                "success": False,
                "status": "failed",
                "message": "recordingId 不能为空",
            }
        reason = str(req_data.get("reason") or "已取消录制准备").strip() or "已取消录制准备"

        async with cls._lock:
            session = cls._recorders.pop(recording_id, None)
            retained_session = cls._retained_sessions.pop(recording_id, None)

        released = False
        if session is not None:
            released = True
            try:
                await session.disable_recording()
            except Exception as exc:
                logger.debug(f"取消录制准备时停用录制失败: {exc}")
            try:
                await session.close()
            except Exception as exc:
                logger.exception(exc)
        if retained_session is not None:
            released = True
            try:
                await retained_session.close()
            except Exception as exc:
                logger.exception(exc)

        return {
            "request_type": 3,
            "command": "cancel_recording_prepare",
            "success": True,
            "status": "cancelled",
            "message": reason if released else "录制准备会话已结束",
            "result": {
                "recordingId": recording_id,
                "released": released,
                "reason": reason,
            },
        }

    @classmethod
    async def _run_case(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        run_id = _as_int(req_data.get("webCaseRunId") or req_data.get("web_case_run_id"), 0)
        case_data = _as_dict(req_data.get("caseData"))
        runtime_options = _as_dict(req_data.get("runtimeOptions"))
        effective_runtime = _resolve_runtime_settings(case_data, runtime_options)
        browser_name = str(effective_runtime.get("browserName") or case_data.get("browserName") or "chromium")
        headless = bool(effective_runtime.get("headless", case_data.get("headless", True)))
        close_browser_on_finish = effective_runtime.get("closeBrowserOnFinish")
        if close_browser_on_finish is None:
            close_browser_on_finish = True
        else:
            close_browser_on_finish = bool(close_browser_on_finish)
        start_url = str(effective_runtime.get("startUrl") or case_data.get("startUrl") or "")
        reuse_retained_session_id = _resolve_reuse_retained_session_id(effective_runtime)
        steps = case_data.get("steps") or []
        if not isinstance(steps, list):
            steps = []

        result_steps: list[dict[str, Any]] = []
        playwright = None
        browser = None
        context = None
        page = None
        response_payload: dict[str, Any]
        retained_session_id: str | None = None
        context_state_path: Path | None = None
        cookie_variables: dict[str, Any] = {}
        cookie_rules: list[dict[str, Any]] = []
        runtime_debug: dict[str, Any] = {}
        active_session = ActiveRunSession(run_id=run_id) if run_id > 0 else None
        try:
            reused_session: RetainedRunSession | None = None
            if reuse_retained_session_id:
                async with cls._lock:
                    reused_session = cls._retained_runs.pop(reuse_retained_session_id, None)
            if (
                reused_session is not None
                and reused_session.playwright is not None
                and reused_session.browser is not None
                and reused_session.context is not None
                and reused_session.page is not None
            ):
                playwright = reused_session.playwright
                browser = reused_session.browser
                context = reused_session.context
                page = reused_session.page
                context_state_path = reused_session.context_state_path
                runtime_debug["reusedRetainedSession"] = True
                runtime_debug["reuseRetainedSessionId"] = reuse_retained_session_id
            else:
                if reused_session is not None:
                    await reused_session.close()
                playwright, browser = await start_playwright_browser(
                    browser_name,
                    headless=headless,
                    request_options=effective_runtime,
                )
                context, context_state_path = await _create_browser_context(
                    browser,
                    runtime_options=effective_runtime,
                    browser_name=browser_name,
                    start_url=start_url,
                    default_scope=f"run-{run_id}" if run_id > 0 else "run-default",
                )
                page = await context.new_page()
                runtime_debug["reusedRetainedSession"] = False
                if reuse_retained_session_id:
                    runtime_debug["reuseRetainedSessionId"] = reuse_retained_session_id
                    runtime_debug["reuseRetainedSessionMiss"] = True

            if active_session is not None:
                active_session.page = page
                active_session.context = context
                active_session.browser = browser
                active_session.playwright = playwright
                active_session.context_state_path = context_state_path
                async with cls._lock:
                    cls._active_runs[run_id] = active_session

            cookie_variables = _resolve_runtime_variables(effective_runtime)
            cookie_rules = _normalize_cookie_rules(effective_runtime)
            runtime_debug = {
                **runtime_debug,
                "runtimeProfileId": runtime_options.get("runtimeProfileId") or runtime_options.get("runtime_profile_id"),
                "cookieRuleCount": len(cookie_rules),
                "cookieVariableKeys": sorted(cookie_variables.keys()),
                "persistContextEnabled": context_state_path is not None,
                "persistContextPath": str(context_state_path) if context_state_path is not None else "",
            }
            if start_url:
                before_start_cookie_apply = await _apply_cookie_rules(
                    context,
                    target_url=start_url,
                    stage="before_start",
                    cookie_rules=cookie_rules,
                    variables=cookie_variables,
                )
                runtime_debug["beforeStartCookieApply"] = before_start_cookie_apply or {
                    "stage": "before_start",
                    "targetUrl": start_url,
                    "targetHost": _host_from_url(start_url),
                    "appliedCount": 0,
                    "rules": [],
                    "appliedCookies": [],
                }
                runtime_debug["contextCookiesBeforeGoto"] = await _capture_context_cookies_for_debug(
                    context,
                    target_url=start_url,
                )
            if start_url:
                await page.goto(start_url, timeout=_step_timeout_ms({}, effective_runtime, case_data))
                runtime_debug["contextCookiesAfterGoto"] = await _capture_context_cookies_for_debug(
                    context,
                    target_url=start_url,
                )
            runtime_debug["manualLoginGate"] = await _wait_manual_login_if_needed(
                page,
                effective_runtime,
                stage="before_case_steps",
            )
            overall_success = True
            for step_index, raw_step in enumerate(steps):
                if active_session is not None and active_session.cancel_event.is_set():
                    raise RuntimeError("执行已取消")
                step = _as_dict(raw_step)
                if not bool(step.get("enabled", True)):
                    result_steps.append(
                        {
                            "stepId": step.get("stepId") or step.get("step_id"),
                            "stepName": step.get("stepName") or step.get("step_name") or "step",
                            "status": "skipped",
                            "durationMs": 0,
                            "message": "步骤已禁用",
                            "pageUrl": page.url if page else start_url,
                        }
                    )
                    continue

                step_result = await cls._run_single_step(
                    page,
                    context,
                    step,
                    runtime_options=effective_runtime,
                    case_data=case_data,
                    cookie_rules=cookie_rules,
                    cookie_variables=cookie_variables,
                )
                result_steps.append(step_result)
                if active_session is not None and active_session.cancel_event.is_set():
                    step_result["message"] = "执行已取消"
                    step_result["error"] = "执行已取消"
                    step_result["errorMessage"] = "执行已取消"
                    overall_success = False
                    break
                if step_result["status"] != "passed":
                    overall_success = False
                    if not _continue_on_failure(step, effective_runtime):
                        break
                think_time_ms = _step_think_time_ms(step, effective_runtime, case_data)
                if think_time_ms > 0 and _has_following_enabled_step(steps, step_index):
                    await asyncio.sleep(think_time_ms / 1000.0)
                    step_result["thinkTimeMs"] = think_time_ms
            runtime_debug.setdefault(
                "beforeStartCookieApply",
                {
                    "stage": "before_start",
                    "targetUrl": start_url,
                    "targetHost": _host_from_url(start_url),
                    "appliedCount": 0,
                    "rules": [],
                    "appliedCookies": [],
                },
            )
            runtime_debug.setdefault(
                "manualLoginGate",
                {
                    "enabled": False,
                    "waitSec": 0,
                    "waitedSec": 0,
                    "stage": "before_case_steps",
                },
            )
            response_payload = {
                "request_type": 3,
                "command": "run_case",
                "success": overall_success,
                "status": "success" if overall_success else "failed",
                "result": {
                    "steps": result_steps,
                    "pageUrl": page.url if page else start_url,
                    "runtimeDebug": runtime_debug,
                },
            }
        except Exception as exc:
            logger.exception(exc)
            runtime_debug.setdefault(
                "beforeStartCookieApply",
                {
                    "stage": "before_start",
                    "targetUrl": start_url,
                    "targetHost": _host_from_url(start_url),
                    "appliedCount": 0,
                    "rules": [],
                    "appliedCookies": [],
                },
            )
            runtime_debug.setdefault(
                "manualLoginGate",
                {
                    "enabled": False,
                    "waitSec": 0,
                    "waitedSec": 0,
                    "stage": "before_case_steps",
                },
            )
            response_payload = {
                "request_type": 3,
                "command": "run_case",
                "success": False,
                "status": "failed",
                "message": "执行已取消" if active_session is not None and active_session.cancel_event.is_set() else str(exc),
                "result": {
                    "steps": result_steps,
                    "pageUrl": page.url if page else start_url,
                    "runtimeDebug": runtime_debug,
                },
            }
        finally:
            cancelled = active_session.cancel_event.is_set() if active_session is not None else False
            if run_id > 0:
                async with cls._lock:
                    cls._active_runs.pop(run_id, None)
            if cancelled or close_browser_on_finish or browser is None or playwright is None:
                await _save_context_state_if_needed(context, context_state_path)
                await _close_playwright_objects(page, context, browser, playwright)
            else:
                retained_session_id = uuid.uuid4().hex
                retained_session = RetainedRunSession(
                    session_id=retained_session_id,
                    playwright=playwright,
                    browser=browser,
                    context=context,
                    page=page,
                    context_state_path=context_state_path,
                )
                page = None
                context = None
                browser = None
                playwright = None
                async with cls._lock:
                    cls._retained_runs[retained_session_id] = retained_session

        if isinstance(response_payload.get("result"), dict):
            response_payload["result"]["browserRetained"] = retained_session_id is not None
            if retained_session_id is not None:
                response_payload["result"]["retainedSessionId"] = retained_session_id
        return response_payload

    @classmethod
    async def _run_single_step(
        cls,
        page: Any,
        context: Any,
        step: dict[str, Any],
        *,
        runtime_options: dict[str, Any],
        case_data: dict[str, Any],
        cookie_rules: list[dict[str, Any]],
        cookie_variables: dict[str, Any],
    ) -> dict[str, Any]:
        action_type = str(step.get("actionType") or step.get("action_type") or "").strip().lower()
        step_id = step.get("stepId") or step.get("step_id")
        step_name = step.get("stepName") or step.get("step_name") or action_type or "step"
        params = _as_dict(step.get("params"))
        assertions = step.get("assertions") or []
        timeout_ms = _step_timeout_ms(step, runtime_options, case_data)
        started_at = time.perf_counter()
        attempts: list[dict[str, Any]] = []
        cookie_apply: dict[str, Any] | None = None
        try:
            if action_type == "goto":
                cookie_apply = await _apply_cookie_rules(
                    context,
                    target_url=str(params.get("url") or ""),
                    stage="before_goto",
                    cookie_rules=cookie_rules,
                    variables=cookie_variables,
                )
            else:
                cookie_apply = await _apply_cookie_rules(
                    context,
                    target_url=str(page.url or ""),
                    stage="before_step",
                    cookie_rules=cookie_rules,
                    variables=cookie_variables,
                )
            locator = None
            if _action_requires_locator(action_type):
                locator, attempts = await cls._resolve_locator(page, step, timeout_ms)
            await asyncio.wait_for(
                cls._execute_action(
                    page,
                    locator,
                    action_type,
                    params,
                    timeout_ms=timeout_ms,
                ),
                timeout=timeout_ms / 1000.0,
            )
            await asyncio.wait_for(
                cls._execute_assertions(page, locator, assertions, timeout_ms=timeout_ms),
                timeout=timeout_ms / 1000.0,
            )
            return {
                "stepId": step_id,
                "stepName": step_name,
                "status": "passed",
                "durationMs": int((time.perf_counter() - started_at) * 1000),
                "attempts": attempts,
                "cookieApply": cookie_apply,
                "pageUrl": page.url,
            }
        except Exception as exc:
            logger.exception(exc)
            error_message = str(exc or "").strip()
            if not error_message:
                if isinstance(exc, asyncio.TimeoutError):
                    error_message = f"步骤执行超时（>{timeout_ms}ms）"
                else:
                    error_message = f"{exc.__class__.__name__}"
            return {
                "stepId": step_id,
                "stepName": step_name,
                "status": "failed",
                "durationMs": int((time.perf_counter() - started_at) * 1000),
                "attempts": attempts,
                "cookieApply": cookie_apply,
                "pageUrl": page.url,
                "error": error_message,
                "errorMessage": error_message,
                "message": error_message,
                "errorType": exc.__class__.__name__,
            }

    @classmethod
    async def _resolve_locator(cls, page: Any, step: dict[str, Any], timeout_ms: int) -> tuple[Any, list[dict[str, Any]]]:
        target_snapshot = _as_dict(step.get("targetSnapshot") or step.get("target_snapshot"))
        raw_locators = target_snapshot.get("locators") or []
        if not raw_locators:
            raise RuntimeError("当前步骤缺少定位器配置")

        normalized_candidates: list[dict[str, Any]] = []
        for index, raw_locator in enumerate(raw_locators):
            locator_def = _as_dict(raw_locator)
            if locator_def.get("enabled") is False:
                continue
            locator_type = str(locator_def.get("locatorType") or locator_def.get("locator_type") or "").strip().lower()
            if not locator_type:
                continue
            locator_value_source = locator_def.get("locatorValue")
            if locator_value_source is None:
                locator_value_source = locator_def.get("locator_value")
            if isinstance(locator_value_source, dict):
                locator_value = _as_dict(locator_value_source)
            elif locator_type in {"css", "xpath"} and locator_value_source not in (None, ""):
                locator_value = {"selector": str(locator_value_source)}
            else:
                locator_value = {}
            normalized_candidates.append(
                {
                    "locatorType": locator_type,
                    "locatorValue": locator_value,
                    "priority": _as_int(locator_def.get("priority"), index),
                    "index": index,
                }
            )

        if not normalized_candidates:
            raise RuntimeError("当前步骤没有可用(启用)定位器")

        normalized_candidates.sort(
            key=lambda item: (
                _as_int(item.get("priority"), 999),
                _LOCATOR_TYPE_WEIGHT.get(str(item.get("locatorType") or ""), 99),
                _as_int(item.get("index"), 0),
            )
        )

        attempts: list[dict[str, Any]] = [
            {
                "locatorType": item.get("locatorType"),
                "locatorValue": item.get("locatorValue"),
                "priority": item.get("priority"),
                "tries": 0,
            }
            for item in normalized_candidates
        ]

        started_at = time.perf_counter()
        deadline = started_at + (max(timeout_ms, 500) / 1000.0)
        while time.perf_counter() < deadline:
            for attempt in attempts:
                locator_type = str(attempt.get("locatorType") or "")
                locator_value = _as_dict(attempt.get("locatorValue"))
                attempt["tries"] = _as_int(attempt.get("tries"), 0) + 1
                remaining_ms = int((deadline - time.perf_counter()) * 1000)
                if remaining_ms <= 0:
                    break
                probe_timeout = max(min(remaining_ms, 350), 50)
                try:
                    locator = cls._build_locator(page, locator_type, locator_value)
                    candidate = locator.first
                    await candidate.wait_for(state="attached", timeout=probe_timeout)
                    count = await locator.count()
                    attempt["count"] = count
                    if count > 0:
                        return candidate, attempts
                    attempt["message"] = "未匹配到元素"
                except Exception as exc:
                    attempt["error"] = str(exc)
            await asyncio.sleep(0.05)

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        raise RuntimeError(f"未在 {elapsed_ms}ms 内定位到步骤元素: {json.dumps(attempts, ensure_ascii=False)}")

    @classmethod
    def _build_locator(cls, page: Any, locator_type: str, locator_value: dict[str, Any]) -> Any:
        if locator_type == "role":
            return page.get_by_role(
                locator_value.get("role", ""),
                name=locator_value.get("name"),
                exact=locator_value.get("exact", False),
            )
        if locator_type == "label":
            return page.get_by_label(locator_value.get("text", ""), exact=locator_value.get("exact", False))
        if locator_type == "placeholder":
            return page.get_by_placeholder(locator_value.get("text", ""), exact=locator_value.get("exact", False))
        if locator_type == "text":
            return page.get_by_text(locator_value.get("text", ""), exact=locator_value.get("exact", False))
        if locator_type == "test_id":
            return page.get_by_test_id(locator_value.get("testId", ""))
        if locator_type == "id":
            element_id = str(locator_value.get("id") or "").strip()
            if not element_id:
                raise RuntimeError("id 定位器缺少 id 参数")
            safe_id = element_id.replace('"', '\\"')
            return page.locator(f'[id="{safe_id}"]')
        if locator_type == "name":
            element_name = str(locator_value.get("name") or "").strip()
            if not element_name:
                raise RuntimeError("name 定位器缺少 name 参数")
            safe_name = element_name.replace('"', '\\"')
            return page.locator(f'[name="{safe_name}"]')
        selector = locator_value.get("selector", "")
        selector = str(selector or "").strip()
        if not selector:
            raise RuntimeError(f"{locator_type} 定位器缺少 selector 参数")
        if locator_type == "xpath":
            return page.locator(f"xpath={selector}")
        return page.locator(selector)

    @classmethod
    async def _execute_action(
        cls,
        page: Any,
        locator: Any,
        action_type: str,
        params: dict[str, Any],
        *,
        timeout_ms: int,
    ) -> None:
        if action_type == "goto":
            await page.goto(str(params.get("url") or ""), timeout=timeout_ms)
            return
        if action_type in {"sleep", "wait"}:
            wait_ms = _as_int(params.get("waitMs") or params.get("wait_ms") or params.get("durationMs") or params.get("duration_ms"), 0)
            if wait_ms > 0:
                await asyncio.sleep(wait_ms / 1000.0)
            return
        if action_type in {"assert_page_contains", "assert_page_not_contains"}:
            expected = str(params.get("text") or params.get("expected") or "").strip()
            if not expected:
                raise AssertionError(f"{action_type} 需要 text/expected 参数")
            page_text = (await page.locator("body").inner_text(timeout=timeout_ms) or "").strip()
            if action_type == "assert_page_contains" and expected not in page_text:
                raise AssertionError(f"assert_page_contains failed: expected={expected}")
            if action_type == "assert_page_not_contains" and expected in page_text:
                raise AssertionError(f"assert_page_not_contains failed: expected_not_contains={expected}")
            return
        if action_type == "assert_title_contains":
            expected = str(params.get("title") or params.get("text") or params.get("expected") or "").strip()
            if not expected:
                raise AssertionError("assert_title_contains 需要 title/text/expected 参数")
            actual_title = await page.title()
            if expected not in str(actual_title or ""):
                raise AssertionError(f"assert_title_contains failed: expected={expected}, actual={actual_title}")
            return
        if action_type == "assert_url_contains":
            expected = str(params.get("urlPart") or params.get("url_part") or params.get("text") or params.get("expected") or "").strip()
            if not expected:
                raise AssertionError("assert_url_contains 需要 urlPart/text/expected 参数")
            if expected not in str(page.url or ""):
                raise AssertionError(f"assert_url_contains failed: expected={expected}, actual={page.url}")
            return

        if locator is None:
            raise RuntimeError(f"动作 {action_type} 需要有效定位器")
        if action_type == "click":
            await locator.click(timeout=timeout_ms)
            return
        if action_type == "double_click":
            await locator.dblclick(timeout=timeout_ms)
            return
        if action_type == "hover":
            await locator.hover(timeout=timeout_ms)
            return
        if action_type == "clear":
            await locator.fill("", timeout=timeout_ms)
            return
        if action_type == "fill":
            await locator.fill(str(params.get("value") or ""), timeout=timeout_ms)
            return
        if action_type == "press":
            await locator.press(str(params.get("key") or "Enter"), timeout=timeout_ms)
            return
        if action_type == "check":
            await locator.check(timeout=timeout_ms)
            return
        if action_type == "uncheck":
            await locator.uncheck(timeout=timeout_ms)
            return
        if action_type == "select_option":
            values = params.get("values") or []
            if not isinstance(values, list):
                values = [values]
            await locator.select_option(values, timeout=timeout_ms)
            return
        if action_type == "wait_visible":
            await locator.wait_for(state="visible", timeout=timeout_ms)
            return
        if action_type == "wait_hidden":
            await locator.wait_for(state="hidden", timeout=timeout_ms)
            return
        if action_type == "assert_text_equals":
            text = await _read_locator_text(locator, timeout_ms=timeout_ms)
            expected = _normalize_assert_text(params.get("expected") or params.get("text") or "")
            if not _text_equals(text, expected):
                raise AssertionError(f"assert_text_equals failed: expected={expected}, actual={text}")
            return
        if action_type == "assert_text_contains":
            text = await _read_locator_text(locator, timeout_ms=timeout_ms)
            expected = _normalize_assert_text(params.get("expected") or params.get("text") or "")
            if not _text_contains(text, expected):
                raise AssertionError(f"assert_text_contains failed: expected={expected}, actual={text}")
            return
        raise RuntimeError(f"unsupported action type: {action_type}")

    @classmethod
    def _assertion_wait_ms(cls, assertion: dict[str, Any], step_timeout_ms: int) -> int:
        candidates = [
            assertion.get("waitMs"),
            assertion.get("wait_ms"),
            assertion.get("timeoutMs"),
            assertion.get("timeout_ms"),
        ]
        for candidate in candidates:
            if candidate not in (None, ""):
                configured = _as_int(candidate, 0)
                if configured > 0:
                    return max(configured, 500)
        return max(_as_int(step_timeout_ms, 10000), 500)

    @classmethod
    async def _resolve_assertion_locator(
        cls,
        page: Any,
        step_locator: Any,
        assertion: dict[str, Any],
        timeout_ms: int,
    ) -> Any:
        target_snapshot = _as_dict(assertion.get("targetSnapshot") or assertion.get("target_snapshot"))
        if target_snapshot.get("locators"):
            resolved_locator, _ = await cls._resolve_locator(
                page,
                {"targetSnapshot": target_snapshot},
                timeout_ms=max(timeout_ms, 500),
            )
            return resolved_locator
        return step_locator

    @classmethod
    async def _check_assertion_once(
        cls,
        page: Any,
        step_locator: Any,
        assertion: dict[str, Any],
        *,
        assert_type: str,
        expected: Any,
        timeout_ms: int,
    ) -> None:
        current_locator = step_locator
        if assert_type in {"text_contains", "text_equals", "visible"}:
            current_locator = await cls._resolve_assertion_locator(page, step_locator, assertion, timeout_ms)
            if current_locator is None:
                raise AssertionError(f"{assert_type} 断言需要有效定位器")

        if assert_type == "text_contains":
            text = await _read_locator_text(current_locator, timeout_ms=max(min(timeout_ms, 1200), 120))
            expected_text = _normalize_assert_text(expected)
            if not _text_contains(text, expected_text):
                raise AssertionError(f"text_contains failed: expected={expected}, actual={text}")
            return
        if assert_type == "text_equals":
            text = await _read_locator_text(current_locator, timeout_ms=max(min(timeout_ms, 1200), 120))
            expected_text = _normalize_assert_text(expected)
            if not _text_equals(text, expected_text):
                raise AssertionError(f"text_equals failed: expected={expected}, actual={text}")
            return
        if assert_type == "visible":
            await current_locator.wait_for(state="visible", timeout=max(min(timeout_ms, 1500), 120))
            return
        if assert_type == "url_contains":
            if str(expected or "") not in page.url:
                raise AssertionError(f"url_contains failed: expected={expected}, actual={page.url}")
            return
        if assert_type == "page_contains":
            page_text = (await page.locator("body").inner_text(timeout=max(min(timeout_ms, 1200), 120)) or "").strip()
            if str(expected or "") not in page_text:
                raise AssertionError(f"page_contains failed: expected={expected}")
            return
        if assert_type == "title_contains":
            title = await page.title()
            if str(expected or "") not in str(title or ""):
                raise AssertionError(f"title_contains failed: expected={expected}, actual={title}")
            return
        if assert_type == "url_equals":
            if str(page.url or "") != str(expected or ""):
                raise AssertionError(f"url_equals failed: expected={expected}, actual={page.url}")
            return
        raise AssertionError(f"unsupported assertion type: {assert_type}")

    @classmethod
    async def _execute_assertions(cls, page: Any, locator: Any, assertions: list[Any], *, timeout_ms: int) -> None:
        supported_types = {
            "text_contains",
            "text_equals",
            "visible",
            "url_contains",
            "page_contains",
            "title_contains",
            "url_equals",
        }
        for index, raw_assertion in enumerate(assertions, start=1):
            assertion = _as_dict(raw_assertion)
            if assertion.get("enabled") is False:
                continue
            assert_type = str(assertion.get("assertType") or assertion.get("assert_type") or "").strip().lower()
            if not assert_type:
                continue
            if assert_type not in supported_types:
                raise AssertionError(f"unsupported assertion type: {assert_type}")

            expected = assertion.get("expected")
            assertion_wait_ms = cls._assertion_wait_ms(assertion, timeout_ms)
            deadline = time.perf_counter() + (assertion_wait_ms / 1000.0)
            last_error: Exception | None = None
            while time.perf_counter() < deadline:
                remaining_ms = int((deadline - time.perf_counter()) * 1000)
                probe_timeout = max(min(remaining_ms, 1200), 120)
                try:
                    await cls._check_assertion_once(
                        page,
                        locator,
                        assertion,
                        assert_type=assert_type,
                        expected=expected,
                        timeout_ms=probe_timeout,
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                await asyncio.sleep(0.1)

            if last_error is not None:
                error_message = str(last_error or "").strip() or f"{assert_type} assertion failed"
                raise AssertionError(f"断言#{index}失败: {error_message}") from last_error
