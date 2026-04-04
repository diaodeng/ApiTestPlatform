from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from loguru import logger

try:
    from playwright.async_api import Frame, FrameLocator, Locator, Page, async_playwright
except Exception:  # pragma: no cover - optional dependency
    Frame = FrameLocator = Locator = Page = Any
    async_playwright = None

EventSender = Callable[[dict[str, Any]], Awaitable[None]]

RECORDER_SCRIPT = """
(() => {
  if (window.__qtrRecorderInstalled__) return;
  window.__qtrRecorderInstalled__ = true;
  const cleanText = (value) => (value || "").replace(/\\s+/g, " ").trim().slice(0, 120);
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
  const cssPath = (el) => {
    if (!(el instanceof Element)) return "";
    const parts = [];
    let current = el;
    while (current && current.nodeType === 1 && parts.length < 5) {
      let part = current.tagName.toLowerCase();
      if (current.id) {
        part += "#" + current.id;
        parts.unshift(part);
        break;
      }
      const cls = Array.from(current.classList || []).slice(0, 2).join(".");
      if (cls) part += "." + cls;
      const siblings = current.parentElement ? Array.from(current.parentElement.children).filter((item) => item.tagName === current.tagName) : [];
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
      parts.unshift(part);
      current = current.parentElement;
    }
    return parts.join(" > ");
  };
  const buildLocators = (el) => {
    const locators = [];
    const role = inferRole(el);
    const text = cleanText(el.innerText || el.textContent || "");
    const label = cleanText(el.getAttribute("aria-label") || el.labels?.[0]?.innerText || "");
    const placeholder = cleanText(el.getAttribute("placeholder") || "");
    const testId = cleanText(el.getAttribute("data-testid") || el.getAttribute("data-test") || "");
    if (role) {
      const roleValue = { role };
      if (text) roleValue.name = text;
      else if (label) roleValue.name = label;
      locators.push({ locatorType: "role", locatorValue: roleValue, priority: 0, enabled: true });
    }
    if (label) locators.push({ locatorType: "label", locatorValue: { text: label, exact: true }, priority: 1, enabled: true });
    if (placeholder) locators.push({ locatorType: "placeholder", locatorValue: { text: placeholder, exact: true }, priority: 2, enabled: true });
    if (text) locators.push({ locatorType: "text", locatorValue: { text, exact: true }, priority: 3, enabled: true });
    if (testId) locators.push({ locatorType: "test_id", locatorValue: { testId }, priority: 4, enabled: true });
    const css = cssPath(el);
    if (css) locators.push({ locatorType: "css", locatorValue: { selector: css }, priority: 5, enabled: true });
    return locators;
  };
  const buildSnapshot = (el) => ({
    elementText: cleanText(el.innerText || el.textContent || ""),
    context: { pageUrl: window.location.href, frameUrl: window.location.href, frameChain: [], shadowChain: [] },
    locators: buildLocators(el)
  });
  const emit = (payload) => {
    if (typeof window.__qtrRecordEvent === "function") {
      window.__qtrRecordEvent(payload);
    }
  };
  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest("button, a, input, textarea, select, [role], [data-testid], [data-test], *") : null;
    if (!target) return;
    const text = cleanText(target.innerText || target.textContent || "");
    const assertions = text ? [{ assertType: "text_contains", expected: text, enabled: true }] : [];
    emit({
      stepName: text ? `点击 ${text}` : "点击元素",
      actionType: "click",
      params: {},
      assertions,
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


@dataclass
class RecorderSession:
    recording_id: int
    agent_code: str
    sender: EventSender
    browser_name: str
    headless: bool
    start_url: str
    options: dict[str, Any]
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    event_index: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    async def emit(self, payload: dict[str, Any], event_type: str = "record_event") -> None:
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

    async def close(self) -> None:
        if self.page is not None:
            await self.page.close()
        if self.context is not None:
            await self.context.close()
        if self.browser is not None:
            await self.browser.close()
        if self.playwright is not None:
            await self.playwright.stop()


class WebTestService:
    _recorders: dict[int, RecorderSession] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def handle_request(cls, req_data: dict[str, Any], event_sender: EventSender | None = None) -> dict[str, Any]:
        command = req_data.get("command") or "run_case"
        if command == "run_case":
            return await cls._run_case(req_data)
        if command == "start_recording":
            return await cls._start_recording(req_data, event_sender)
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
        if async_playwright is None:
            return {
                "request_type": 3,
                "command": "start_recording",
                "success": False,
                "status": "failed",
                "message": "playwright 未安装，无法录制",
            }
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
            )
            cls._recorders[recording_id] = session

        try:
            session.playwright = await async_playwright().start()
            launcher = getattr(session.playwright, session.browser_name, None)
            if launcher is None:
                raise RuntimeError(f"unsupported browser: {session.browser_name}")
            session.browser = await launcher.launch(headless=session.headless)
            session.context = await session.browser.new_context(ignore_https_errors=True)

            async def _event_binding(source: Any, payload: Any) -> None:
                payload_dict = _as_dict(payload)
                if not payload_dict:
                    return
                await session.emit(payload_dict)

            await session.context.expose_binding("__qtrRecordEvent", _event_binding)
            await session.context.add_init_script(RECORDER_SCRIPT)
            session.page = await session.context.new_page()
            session.page.on(
                "framenavigated",
                lambda frame: asyncio.create_task(cls._handle_navigation(frame, session)),
            )
            await session.page.goto(session.start_url)
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
            return {
                "request_type": 3,
                "command": "start_recording",
                "success": True,
                "status": "accepted",
                "recording_id": recording_id,
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
    async def _handle_navigation(cls, frame: Any, session: RecorderSession) -> None:
        if session.page is None or frame != session.page.main_frame:
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
        await session.sender(
            {
                "type": "record_finished",
                "recording_id": recording_id,
                "payload": {"eventCount": len(session.events), "lastUrl": session.page.url if session.page else ""},
            }
        )
        await session.close()
        return {
            "request_type": 3,
            "command": "stop_recording",
            "success": True,
            "status": "stopped",
            "recording_id": recording_id,
            "data": {"eventCount": len(session.events)},
        }

    @classmethod
    async def _run_case(cls, req_data: dict[str, Any]) -> dict[str, Any]:
        if async_playwright is None:
            return {
                "request_type": 3,
                "command": "run_case",
                "success": False,
                "status": "failed",
                "message": "playwright 未安装，无法执行 Web 用例",
            }
        case_data = _as_dict(req_data.get("caseData"))
        runtime_options = _as_dict(req_data.get("runtimeOptions"))
        browser_name = str(runtime_options.get("browserName") or case_data.get("browserName") or "chromium")
        headless = bool(runtime_options.get("headless", case_data.get("headless", True)))
        start_url = str(case_data.get("startUrl") or "")
        steps = case_data.get("steps") or []
        if not isinstance(steps, list):
            steps = []

        result_steps: list[dict[str, Any]] = []
        playwright = await async_playwright().start()
        browser = None
        context = None
        page = None
        try:
            launcher = getattr(playwright, browser_name, None)
            if launcher is None:
                raise RuntimeError(f"unsupported browser: {browser_name}")
            browser = await launcher.launch(headless=headless)
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            if start_url:
                await page.goto(start_url)
            overall_success = True
            for raw_step in steps:
                step = _as_dict(raw_step)
                step_result = await cls._run_single_step(page, step)
                result_steps.append(step_result)
                if step_result["status"] != "passed":
                    overall_success = False
                    if not bool(runtime_options.get("continueOnFailure", False)):
                        break
            return {
                "request_type": 3,
                "command": "run_case",
                "success": overall_success,
                "status": "success" if overall_success else "failed",
                "result": {"steps": result_steps, "pageUrl": page.url if page else start_url},
            }
        except Exception as exc:
            logger.exception(exc)
            return {
                "request_type": 3,
                "command": "run_case",
                "success": False,
                "status": "failed",
                "message": str(exc),
                "result": {"steps": result_steps, "pageUrl": page.url if page else start_url},
            }
        finally:
            if page is not None:
                await page.close()
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()
            await playwright.stop()

    @classmethod
    async def _run_single_step(cls, page: Any, step: dict[str, Any]) -> dict[str, Any]:
        action_type = str(step.get("actionType") or step.get("action_type") or "")
        step_id = step.get("stepId") or step.get("step_id")
        step_name = step.get("stepName") or step.get("step_name") or action_type or "step"
        params = _as_dict(step.get("params"))
        assertions = step.get("assertions") or []
        started_at = time.perf_counter()
        attempts: list[dict[str, Any]] = []
        try:
            locator = None
            if action_type != "goto":
                locator, attempts = await cls._resolve_locator(page, step)
            await cls._execute_action(page, locator, action_type, params)
            await cls._execute_assertions(page, locator, assertions)
            return {
                "stepId": step_id,
                "stepName": step_name,
                "status": "passed",
                "durationMs": int((time.perf_counter() - started_at) * 1000),
                "attempts": attempts,
                "pageUrl": page.url,
            }
        except Exception as exc:
            logger.exception(exc)
            return {
                "stepId": step_id,
                "stepName": step_name,
                "status": "failed",
                "durationMs": int((time.perf_counter() - started_at) * 1000),
                "attempts": attempts,
                "pageUrl": page.url,
                "error": str(exc),
            }

    @classmethod
    async def _resolve_locator(cls, page: Any, step: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
        target_snapshot = _as_dict(step.get("targetSnapshot"))
        locators = target_snapshot.get("locators") or []
        attempts: list[dict[str, Any]] = []
        for raw_locator in locators:
            locator_def = _as_dict(raw_locator)
            locator_type = str(locator_def.get("locatorType") or locator_def.get("locator_type") or "")
            locator_value = _as_dict(locator_def.get("locatorValue"))
            try:
                locator = cls._build_locator(page, locator_type, locator_value)
                count = await locator.count()
                attempts.append({"locatorType": locator_type, "locatorValue": locator_value, "count": count})
                if count > 0:
                    return locator.first, attempts
            except Exception as exc:
                attempts.append({"locatorType": locator_type, "locatorValue": locator_value, "error": str(exc)})
        raise RuntimeError(f"未定位到步骤元素: {json.dumps(attempts, ensure_ascii=False)}")

    @classmethod
    def _build_locator(cls, page: Any, locator_type: str, locator_value: dict[str, Any]) -> Any:
        if locator_type == "role":
            return page.get_by_role(locator_value.get("role", ""), name=locator_value.get("name"), exact=locator_value.get("exact", False))
        if locator_type == "label":
            return page.get_by_label(locator_value.get("text", ""), exact=locator_value.get("exact", False))
        if locator_type == "placeholder":
            return page.get_by_placeholder(locator_value.get("text", ""), exact=locator_value.get("exact", False))
        if locator_type == "text":
            return page.get_by_text(locator_value.get("text", ""), exact=locator_value.get("exact", False))
        if locator_type == "test_id":
            return page.get_by_test_id(locator_value.get("testId", ""))
        selector = locator_value.get("selector", "")
        if locator_type == "xpath":
            return page.locator(f"xpath={selector}")
        return page.locator(selector)

    @classmethod
    async def _execute_action(cls, page: Any, locator: Any, action_type: str, params: dict[str, Any]) -> None:
        if action_type == "goto":
            await page.goto(str(params.get("url") or ""))
            return
        if action_type == "click":
            await locator.click()
            return
        if action_type == "fill":
            await locator.fill(str(params.get("value") or ""))
            return
        if action_type == "press":
            await locator.press(str(params.get("key") or "Enter"))
            return
        if action_type == "check":
            await locator.check()
            return
        if action_type == "uncheck":
            await locator.uncheck()
            return
        if action_type == "select_option":
            values = params.get("values") or []
            if not isinstance(values, list):
                values = [values]
            await locator.select_option(values)
            return
        raise RuntimeError(f"unsupported action type: {action_type}")

    @classmethod
    async def _execute_assertions(cls, page: Any, locator: Any, assertions: list[Any]) -> None:
        for raw_assertion in assertions:
            assertion = _as_dict(raw_assertion)
            assert_type = str(assertion.get("assertType") or assertion.get("assert_type") or "")
            expected = assertion.get("expected")
            if assert_type == "text_contains":
                text = (await locator.text_content() or "").strip()
                if str(expected or "") not in text:
                    raise AssertionError(f"text_contains failed: expected={expected}, actual={text}")
            elif assert_type == "text_equals":
                text = (await locator.text_content() or "").strip()
                if text != str(expected or ""):
                    raise AssertionError(f"text_equals failed: expected={expected}, actual={text}")
            elif assert_type == "visible":
                if not await locator.is_visible():
                    raise AssertionError("visible assertion failed")
            elif assert_type == "url_contains":
                if str(expected or "") not in page.url:
                    raise AssertionError(f"url_contains failed: expected={expected}, actual={page.url}")
