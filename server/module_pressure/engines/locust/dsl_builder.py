from __future__ import annotations

import json
import re
from pathlib import Path


def _safe_name(value: str, fallback: str) -> str:
    """把用例名称转换为合法 Python 方法名，避免动态脚本语法错误。"""
    name = re.sub(r"\W+", "_", value or "").strip("_")
    if not name or name[0].isdigit():
        return fallback
    return name


def _normalize_task(task: dict, index: int) -> dict:
    """补齐任务默认值，生成 Locust 脚本时使用统一结构。"""
    request = task.get("request") or {}
    return {
        "name": task.get("name") or request.get("name") or f"task_{index}",
        "method_name": _safe_name(task.get("name") or f"task_{index}", f"task_{index}"),
        "weight": int(task.get("weight") or 1),
        "request": {
            "method": (request.get("method") or "GET").upper(),
            "url": request.get("url") or request.get("path") or "/",
            "headers": request.get("headers") or {},
            "params": request.get("params") or {},
            "json": request.get("json", request.get("body")),
            "data": request.get("data"),
            "name": request.get("name") or task.get("name"),
        },
        "assertions": task.get("assertions") or task.get("assert") or [],
    }


def normalize_dsl(dsl: dict, base_url: str | None = None) -> dict:
    """规范化平台 DSL，支持 tasks 或 flow 两种入口字段。"""
    target = dsl.get("target") or {}
    raw_tasks = dsl.get("tasks") or dsl.get("flow") or []
    if not raw_tasks and dsl.get("request"):
        raw_tasks = [dsl]
    return {
        "base_url": base_url or target.get("base_url") or dsl.get("base_url") or "",
        "wait_time": dsl.get("wait_time") or {"min": 0.1, "max": 0.5},
        "tasks": [_normalize_task(task, index) for index, task in enumerate(raw_tasks, start=1)],
    }


def build_locustfile_content(scenario: dict, csv_file_name: str = "cases.csv") -> str:
    """生成通用 Locust 脚本，运行时动态读取 scenario.json 和 CSV 数据。"""
    del scenario
    return f'''from __future__ import annotations

import csv
import json
import os
import re
import random
from itertools import cycle
from pathlib import Path
from string import Template

import jmespath
import requests
from locust import HttpUser, between, events, task


SCENARIO_FILE = Path(__file__).parent / "scenario.json"
CSV_FILE = Path(__file__).parent / "data" / "{csv_file_name}"


def load_scenario():
    """从运行目录加载场景 DSL，使脚本本身可以在不同运行间复用。"""
    with SCENARIO_FILE.open(encoding="utf-8") as file:
        return json.load(file)


SCENARIO = load_scenario()
CALLBACK_URLS = [item.strip() for item in os.getenv("QTR_PRESSURE_FINISH_CALLBACK_URLS", "").split(",") if item.strip()]


def notify_platform_finish():
    """压测结束时主动通知平台回收资源并更新运行状态。"""
    if not CALLBACK_URLS:
        return
    for callback_url in CALLBACK_URLS:
        try:
            response = requests.post(callback_url, timeout=3)
            if response.status_code < 400:
                return
        except Exception:
            continue


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Locust 生命周期回调：测试停止后触发平台自动收尾。"""
    del environment, kwargs
    notify_platform_finish()


class CSVDataSource:
    """CSV 参数化数据源，每一行支持一个 JSON case 或普通 CSV 字段。"""

    def __init__(self, path: Path):
        self.rows = self._load_rows(path)
        self.iter = cycle(self.rows or [{{}}])

    def _load_rows(self, path: Path) -> list[dict]:
        if not path.exists() or path.stat().st_size == 0:
            return []
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            rows = []
            for row in reader:
                if "case" in row and row["case"]:
                    rows.append(json.loads(row["case"]))
                    continue
                rows.append({{key: parse_cell(value) for key, value in row.items()}})
            return rows

    def next(self) -> dict:
        return next(self.iter)


def parse_cell(value):
    """把 CSV 单元格尽量解析为 JSON，否则保留原字符串。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except Exception:
        return value


def deep_merge(base, override):
    """递归合并请求配置，CSV 行可以覆盖任务默认请求。"""
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override if override is not None else base
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged


def render_value(value, context):
    """渲染 ${{name}} 模板变量，支持嵌套 dict/list。"""
    if isinstance(value, str):
        return Template(value).safe_substitute(context)
    if isinstance(value, list):
        return [render_value(item, context) for item in value]
    if isinstance(value, dict):
        return {{key: render_value(item, context) for key, item in value.items()}}
    return value


def normalize_assertions(raw_assertions):
    """统一断言 DSL，兼容 dict 简写和 list 完整写法。"""
    if not raw_assertions:
        return []
    if isinstance(raw_assertions, list):
        return raw_assertions
    normalized = []
    for key, expected in raw_assertions.items():
        if key == "status_code":
            normalized.append({{"source": "status_code", "op": "==", "expected": expected}})
        else:
            source = key[5:] if key.startswith("jmes:") else key
            normalized.append({{"source": source, "op": "==", "expected": expected}})
    return normalized


def pick_actual(resp, resp_json, source):
    """根据断言 source 从响应中取值。"""
    if source in ("status", "status_code"):
        return resp.status_code
    if source == "text":
        return resp.text
    if source.startswith("headers."):
        return resp.headers.get(source.replace("headers.", "", 1))
    return jmespath.search(source, resp_json)


def assert_value(actual, assertion):
    """执行 ==、!=、in、contains、regex、range 断言。"""
    op = assertion.get("op") or assertion.get("operator") or "=="
    expected = assertion.get("expected")
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "contains":
        return expected in actual
    if op == "regex":
        return re.search(str(expected), str(actual or "")) is not None
    if op == "range":
        low, high = expected
        return low <= actual <= high
    raise AssertionError(f"unsupported assertion op: {{op}}")


DATA_SOURCE = CSVDataSource(CSV_FILE)
TASK_POOL = [
    task_def
    for task_def in SCENARIO.get("tasks", [])
    for _ in range(max(int(task_def.get("weight") or 1), 1))
]


def pick_task():
    """按权重选择本次要执行的任务。"""
    if not TASK_POOL:
        raise RuntimeError("scenario has no tasks")
    return random.choice(TASK_POOL)


def run_task(user, task_def):
    """从 CSV 循环取数，组装请求，执行断言并上报 Locust 统计。"""
    row = DATA_SOURCE.next()
    context = dict(row)
    request_override = row.get("request") if isinstance(row.get("request"), dict) else row
    request = deep_merge(task_def.get("request") or {{}}, request_override)

    method = str(request.get("method") or "GET").upper()
    url = render_value(request.get("url") or request.get("path") or "/", context)
    headers = render_value(request.get("headers") or {{}}, context)
    params = render_value(request.get("params") or {{}}, context)
    json_body = render_value(request.get("json", request.get("body")), context)
    data_body = render_value(request.get("data"), context)
    name = request.get("name") or row.get("name") or task_def.get("name") or url
    raw_assertions = row.get("assertions", row.get("assert", task_def.get("assertions")))
    assertions = normalize_assertions(raw_assertions)

    with user.client.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_body,
        data=data_body,
        name=name,
        catch_response=True,
    ) as resp:
        resp_json = None
        for assertion in assertions:
            source = assertion.get("source") or assertion.get("expr")
            if source not in ("status", "status_code", "text") and not str(source).startswith("headers."):
                if resp_json is None:
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp.failure("response is not valid JSON")
                        return
            actual = pick_actual(resp, resp_json, source)
            try:
                matched = assert_value(actual, assertion)
            except Exception as exc:
                resp.failure(f"assertion error: {{exc}}")
                return
            if not matched:
                op = assertion.get("op") or assertion.get("operator") or "=="
                resp.failure(f"assert {{source}} {{op}} {{assertion.get('expected')}} failed, actual={{actual}}")
                return
        resp.success()


class PlatformUser(HttpUser):
    host = SCENARIO.get("base_url") or None
    wait_time = between(
        float(SCENARIO.get("wait_time", {{}}).get("min", 0.1)),
        float(SCENARIO.get("wait_time", {{}}).get("max", 0.5)),
    )

    @task
    def run_dynamic_task(self):
        run_task(self, pick_task())
'''


def compile_locust(dsl: dict, run_id: int, base_url: str | None = None, csv_text: str | None = None) -> dict:
    """把场景 DSL 编译为运行目录，返回脚本和 CSV 产物路径。"""
    run_dir = (Path.cwd() / "storage" / "pressure" / "runs" / f"run_{run_id}").resolve()
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    scenario = normalize_dsl(dsl, base_url)
    script_path = run_dir / "locustfile.py"
    csv_path = data_dir / "cases.csv"

    script_path.write_text(build_locustfile_content(scenario), encoding="utf-8")
    csv_path.write_text(csv_text or "case\n", encoding="utf-8")
    (run_dir / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "artifact_dir": str(run_dir),
        "script_path": str(script_path),
        "csv_path": str(csv_path),
        "scenario": scenario,
    }
