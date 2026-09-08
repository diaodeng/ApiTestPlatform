#!/usr/bin/env python
"""服务端故障自动取证脚本：拉取部署平台实例信息 + 容器内日志 + VM 指标。

用途：服务端发生重启/OOM/异常后，一键收集现场证据，替代人工开 xterm 终端逐条敲命令。
取证产物写入 scripts/output/incident_<时间戳>/ 目录，供事后复盘。

数据来源（均为只读操作）：
1. 部署平台 API：getAppInstances 列出实例（版本/commit/启动时间/podIP），
   getAppOperations 解析 bash 终端地址（页面 JS 揭示了真实 WS 协议：
   /api/cluster/<cluster>/terminal?...&cmd=sh&cmd=-c&cmd=<命令>，首帧须发 '___'+resize JSON）；
2. xterm WebSocket：在容器内执行只读命令，抓取应用日志尾部、supervisor 状态、
   cgroup 内存文件、dmesg OOM 记录等；
3. VictoriaMetrics：按启动时间窗口查询进程 RSS、容器 anon/file 内存、
   oom_kill 计数、重启前后任务指标。

用法：
    cd server
    uv run python scripts/incident_capture.py                      # 默认 qtr/blue/test 全量取证
    uv run python scripts/incident_capture.py --memory-hours 26    # VM 查询窗口拉长
    uv run python scripts/incident_capture.py --skip-vm            # 只拉终端日志

前置条件：
- .env.prod 已配置 VM_URL / VM_USER / VM_PASSWORD（VM 查询用）；
- 环境变量 DEPLOY_LOGIN_TOKEN（或 .env.prod 中 DEPLOY_LOGIN_TOKEN）为部署平台
  的 login_token（浏览器 Cookie 里 login_token 的值，URL 解码后的 Bearer JWT）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import dotenv_values  # noqa: E402

# ---------------------------------------------------------------------------
# 常量配置
# ---------------------------------------------------------------------------

DEPLOY_API_BASE = "https://dmall-cloud-api.dmall.com/deploy/v1/apps"
XTERM_HOST = "testapi2-symphony.rta-os.com"
XTERM_ORIGIN = "https://rdms.dmall.com"

# 取证时在容器内执行的只读命令清单（名称, 命令）。
# 日志尾部取 2000 行覆盖重启窗口；cgroup 与 dmesg 用于确认 OOM Kill。
TERMINAL_COMMANDS: list[tuple[str, str]] = [
    ("pods", "echo '--- supervisor 进程状态 ---'; supervisorctl status 2>&1 || true"),
    ("cgroup", (
        "echo '--- cgroup 内存 ---'; "
        "cat /sys/fs/cgroup/memory.max 2>/dev/null || cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null; "
        "cat /sys/fs/cgroup/memory.current 2>/dev/null || cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null; "
        "echo '--- oom events ---'; "
        "cat /sys/fs/cgroup/memory.events 2>/dev/null || cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null"
    )),
    (
        "dmesg_oom",
        "echo '--- 内核 OOM 记录 ---'; dmesg 2>/dev/null | grep -iE 'oom|killed process' | tail -20"
        " || echo 'dmesg 不可用或无 OOM 记录'",
    ),
    # 注意：外层用 sh -c 且命令经 URL 编码传输，$() 嵌套会被转义破坏，因此用 find 定位最新日期目录。
    (
        "app_log_tail",
        "L=$(find /app/logs -maxdepth 2 -name app.log -newer /etc/hostname | sort | tail -1); "
        'echo "--- 应用日志尾部2000行: $L ---"; tail -n 2000 "$L" 2>/dev/null || ls /app/logs/ | tail -5',
    ),
    (
        "error_log_tail",
        "L=$(find /app/logs -maxdepth 2 -name error.log -newer /etc/hostname | sort | tail -1); "
        'echo "--- 错误日志尾部300行: $L ---"; tail -n 300 "$L" 2>/dev/null || true',
    ),
    (
        "supervisord_log",
        "echo '--- supervisord 日志尾部100行 ---'; tail -n 100 /var/log/supervisord.log 2>/dev/null || true",
    ),
]

# VM 查询清单（PromQL, 说明）；窗口按最近一次进程启动时间动态计算。
VM_QUERIES: list[tuple[str, str]] = [
    ('qtr_process_rss_bytes{machine="test"}', '各进程RSS'),
    ('qtr_process_uss_bytes{machine="test"}', '各进程USS'),
    ('qtr_cgroup_memory_current_bytes{machine="test"}', '容器内存用量'),
    ('qtr_cgroup_memory_anon_bytes{machine="test"}', '容器匿名内存'),
    ('qtr_cgroup_memory_file_bytes{machine="test"}', '容器页缓存'),
    ('qtr_cgroup_memory_max_bytes{machine="test"}', '容器内存上限'),
    ('qtr_cgroup_memory_events_oom_total{machine="test"}', 'OOM事件计数'),
    ('qtr_cgroup_memory_events_oom_kill_total{machine="test"}', 'OOM Kill计数'),
    ('qtr_process_threads{machine="test",role="api"}', 'API线程数'),
]


def load_env() -> dict:
    """加载 .env.prod 配置（脚本独立运行时无法依赖应用配置模块）。"""
    env_file = BASE_DIR / ".env.prod"
    if env_file.exists():
        return {k: v for k, v in dotenv_values(env_file).items() if v}
    return {}


def utc_iso(local_dt: datetime) -> str:
    """本地时间转 UTC ISO 串（VM API 用 UTC）。"""
    return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 部署平台 API
# ---------------------------------------------------------------------------

def build_deploy_headers(login_token: str) -> dict:
    """构造部署平台请求头：Cookie 里的 login_token 是单次 URL 编码的 JWT。"""
    return {
        "Accept": "application/json, text/plain, */*",
        "Origin": XTERM_ORIGIN,
        "Referer": f"{XTERM_ORIGIN}/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152.0.0.0"
        ),
        "Cookie": f"login_token={urllib.parse.quote(login_token)}",
    }


def get_pod_info(client: httpx.Client, headers: dict, login_token: str) -> dict:
    """查询 qtr 应用 blue 组的运行实例，返回首个 Running 实例的关键字段。"""
    params = {
        "versionType": "RTA",
        "currentPage": 1,
        "pageSize": 10,
        "env": "test",
        "symZone": "",
        "code": "qtr",
        "group": "blue",
        # 部署平台 loginToken 参数是二次 URL 编码
        "loginToken": urllib.parse.quote(urllib.parse.quote(login_token)),
    }
    r = client.get(
        f"{DEPLOY_API_BASE}/getAppInstances", params=params, headers=headers, timeout=30
    )
    r.raise_for_status()
    data = r.json()
    if data.get("flag") != 20000:
        raise RuntimeError(f"getAppInstances 失败: flag={data.get('flag')}, msg={data.get('msg')}")
    pods = (data.get("data") or {}).get("result") or []
    running = next((p for p in pods if p.get("phase") == "Running"), None)
    if not running:
        raise RuntimeError(f"无 Running 实例: {[p.get('phase') for p in pods]}")
    return {
        "name": running["name"],
        "podIP": running["podIP"],
        "clusterCode": running["clusterCode"],
        "namespace": running["namespace"],
        "container": (running.get("containers") or [{}])[0].get("name", ""),
        "imageVersion": running.get("imageVersion", ""),
        "commitId": running.get("commitId", ""),
        "startTime": running.get("startTime", ""),
        "hostIP": running.get("hostIP", ""),
    }


# ---------------------------------------------------------------------------
# xterm WebSocket 终端执行
# ---------------------------------------------------------------------------

def _clean_ansi(text: str) -> str:
    """去掉终端转义序列，只留可读文本。"""
    return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[=>]|\r", "", text)


async def _run_ws_command(pod: dict, command: str, login_token: str, timeout_s: float) -> str:
    """通过 xterm WebSocket 在容器内执行一条命令并收集输出。

    协议（从终端页面 JS 逆向确认）：
    - WS 地址: ws://<host>/api/cluster/<cluster>/terminal?namespace=&pod=&container=&cmd=sh&cmd=-c&cmd=<url命令>
    - 连接后第一帧必须发 '___' + JSON(cols/rows/type=resize)，否则被服务端关闭；
    - 后续字节流即命令输出（终端转义序列需清洗）。
    """
    import websockets

    cmd_encoded = urllib.parse.quote(command, safe="")
    ws_url = (
        f"ws://{XTERM_HOST}/api/cluster/{pod['clusterCode']}/terminal"
        f"?namespace={pod['namespace']}&pod={pod['name']}&container={pod['container']}"
        f"&cmd=sh&cmd=-c&cmd={cmd_encoded}"
    )
    headers = {
        "Origin": f"https://{XTERM_HOST}",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152.0.0.0"
        ),
        "Cookie": f"login_token={urllib.parse.quote(login_token)}",
    }
    async with websockets.connect(ws_url, additional_headers=headers, open_timeout=20, max_size=32 * 1024 * 1024) as ws:
        await ws.send("___" + json.dumps({"cols": 240, "rows": 60, "type": "resize"}))
        chunks: list[str] = []
        try:
            while True:
                message = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                chunks.append(message if isinstance(message, str) else message.decode("utf-8", "ignore"))
        except asyncio.TimeoutError:
            pass
    return _clean_ansi("".join(chunks))


def run_terminal_commands(pod: dict, login_token: str, out_dir: Path, timeout_s: float = 30.0) -> None:
    """依次执行取证命令清单，输出分别写入独立文件。"""
    for name, command in TERMINAL_COMMANDS:
        output_file = out_dir / f"terminal_{name}.txt"
        try:
            output = asyncio.run(_run_ws_command(pod, command, login_token, timeout_s))
            output_file.write_text(output, encoding="utf-8")
            print(f"  [terminal] {name}: {len(output)} 字节 -> {output_file.name}")
        except Exception as exc:
            output_file.write_text(f"执行失败: {type(exc).__name__}: {exc}\n命令: {command}\n", encoding="utf-8")
            print(f"  [terminal] {name}: 失败 {exc}")


# ---------------------------------------------------------------------------
# VM 指标取证
# ---------------------------------------------------------------------------

def capture_vm(client: httpx.Client, env: dict, pod: dict, memory_hours: int, out_dir: Path) -> None:
    """按最近一次进程启动时间窗口查询 VM 指标，写入 JSON 与摘要。"""
    vm_query_url = (env.get("VM_URL") or "").replace("/api/v1/import/prometheus", "")
    if not vm_query_url:
        print("  [vm] 未配置 VM_URL，跳过")
        return
    auth = (env.get("VM_USER", ""), env.get("VM_PASSWORD", ""))

    start_time = _parse_start_time(pod.get("startTime", ""))
    window_start = start_time - timedelta(minutes=30)
    end_time = datetime.now()
    summary_lines = [f"# 取证时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", f"# Pod 启动: {pod['startTime']}", ""]

    for index, (query, label) in enumerate(VM_QUERIES):
        params = {"query": query, "start": utc_iso(window_start), "end": utc_iso(end_time), "step": "120"}
        try:
            r = client.get(f"{vm_query_url}/api/v1/query_range", params=params, auth=auth, timeout=30)
            payload = r.json().get("data", {}).get("result", [])
            (out_dir / f"vm_{index:02d}_{re.sub(r'[^a-zA-Z0-9]', '_', query)[:60]}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            summary_lines.append(f"## {label}: {query}")
            for series in payload:
                role = series["metric"].get("role", "")
                values = series["values"]
                first, last = values[0], values[-1]
                first_dt = datetime.fromtimestamp(first[0], timezone(timedelta(hours=8))).strftime("%m-%d %H:%M")
                last_dt = datetime.fromtimestamp(last[0], timezone(timedelta(hours=8))).strftime("%m-%d %H:%M")
                def fmt(v: str) -> str:
                    return f"{float(v)/1024/1024:.0f}MB" if float(v) > 10 * 1024 * 1024 else str(v)
                summary_lines.append(
                    f"  {role or '-'}: {first_dt}={fmt(first[1])} -> {last_dt}={fmt(last[1])} ({len(values)}点)"
                )
            print(f"  [vm] {label}: {len(payload)} 序列")
        except Exception as exc:
            summary_lines.append(f"## {label}: 查询失败 {exc}")
            print(f"  [vm] {label}: 失败 {exc}")

    # 额外：memory_hours 窗口的容器内存整点趋势（看发布前基线）
    params = {
        "query": 'qtr_cgroup_memory_anon_bytes{machine="test"}',
        "start": utc_iso(end_time - timedelta(hours=memory_hours)),
        "end": utc_iso(end_time),
        "step": "1800",
    }
    try:
        r = client.get(f"{vm_query_url}/api/v1/query_range", params=params, auth=auth, timeout=30)
        payload = r.json().get("data", {}).get("result", [])
        (out_dir / "vm_anon_history.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        summary_lines.append(f"\n## 近 {memory_hours} 小时容器 anon 内存（每30分钟）")
        for series in payload:
            for ts, value in series["values"]:
                dt = datetime.fromtimestamp(ts, timezone(timedelta(hours=8))).strftime("%m-%d %H:%M")
                summary_lines.append(f"  {dt} {float(value)/1024/1024:.0f}MB")
        print(f"  [vm] anon 历史: {sum(len(s['values']) for s in payload)} 点")
    except Exception as exc:
        summary_lines.append(f"\n## anon 历史: 查询失败 {exc}")

    (out_dir / "vm_summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")


def _parse_start_time(text: str) -> datetime:
    """解析部署平台 startTime（'2026-09-07 19:15:39'，本地时区）。"""
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.now() - timedelta(hours=1)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="服务端故障自动取证")
    parser.add_argument("--memory-hours", type=int, default=26, help="VM anon 历史窗口小时数")
    parser.add_argument("--skip-vm", action="store_true", help="跳过 VM 查询，只拉终端日志")
    parser.add_argument("--skip-terminal", action="store_true", help="跳过终端命令，只查 VM")
    parser.add_argument("--out", type=str, default="", help="自定义输出目录")
    args = parser.parse_args()

    env = load_env()
    login_token = env.get("DEPLOY_LOGIN_TOKEN") or os.environ.get("DEPLOY_LOGIN_TOKEN", "")
    if not login_token:
        # 兼容直接粘贴 URL 编码形式（Bearer%20...）
        login_token = urllib.parse.unquote(env.get("DEPLOY_LOGIN_TOKEN_RAW", "") or "")
    if not login_token:
        print("错误: 未配置 DEPLOY_LOGIN_TOKEN（.env.prod 或环境变量，值为浏览器 Cookie login_token 的解码值）")
        sys.exit(1)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else BASE_DIR / "scripts" / "output" / f"incident_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    headers = build_deploy_headers(login_token)

    print(f"取证输出目录: {out_dir}")
    # VM 是自签证书站点需关闭校验；部署平台接口正常校验。
    with httpx.Client(verify=False) as vm_client, httpx.Client() as deploy_client:
        # 1. 实例信息
        print("[1/3] 查询部署平台实例...")
        pod = get_pod_info(deploy_client, headers, login_token)
        (out_dir / "pod_info.json").write_text(json.dumps(pod, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  pod={pod['name']} image={pod['imageVersion']} startTime={pod['startTime']}")
        print(f"  commitId={pod['commitId']}")

        # 2. 终端取证
        if not args.skip_terminal:
            print("[2/3] 终端命令取证...")
            run_terminal_commands(pod, login_token, out_dir)

        # 3. VM 指标取证
        if not args.skip_vm:
            print("[3/3] VM 指标取证...")
            capture_vm(vm_client, env, pod, args.memory_hours, out_dir)

    print(f"完成。取证文件见: {out_dir}")


if __name__ == "__main__":
    main()
