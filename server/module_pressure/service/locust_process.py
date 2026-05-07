from __future__ import annotations

import csv
import errno
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


class LocustProcessError(RuntimeError):
    """Locust 子进程启动、控制或报告采集失败时抛出。"""


class LocustProcessController:
    """通过子进程和 Locust Web API 控制任务级 master 生命周期。"""

    def __init__(self, host: str = "127.0.0.1"):
        self.host = host

    def allocate_port(self) -> int:
        """申请一个当前机器空闲端口，用作 Locust Web 或 master 通信端口。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.host, 0))
            return int(sock.getsockname()[1])

    def discover_master_host(self) -> str:
        """获取 Worker 可连接的本机地址，失败时回退到 127.0.0.1。"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return str(sock.getsockname()[0])
        except Exception:
            return self.host

    def start_master(
        self,
        *,
        script_path: str,
        artifact_dir: str,
        master_web_port: int,
        master_bind_port: int,
        expect_workers: int = 0,
        finish_callback_urls: str | None = None,
    ) -> subprocess.Popen:
        """启动任务级 Locust master 子进程，返回 Popen 对象。"""
        command = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            script_path,
            "--master",
            "--web-host",
            "0.0.0.0",
            "--web-port",
            str(master_web_port),
            "--master-bind-host",
            "0.0.0.0",
            "--master-bind-port",
            str(master_bind_port),
            "--csv",
            str(Path(artifact_dir) / "stats"),
            "--html",
            str(Path(artifact_dir) / "report.html"),
        ]
        if expect_workers > 0:
            command.extend(["--expect-workers", str(expect_workers)])

        log_file = Path(artifact_dir) / "locust-master.log"
        log_handle = log_file.open("a", encoding="utf-8")
        env = os.environ.copy()
        if finish_callback_urls:
            env["QTR_PRESSURE_FINISH_CALLBACK_URLS"] = finish_callback_urls
        return subprocess.Popen(
            command,
            cwd=str(Path(script_path).parent),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            env=env,
        )

    def start_standalone(
        self,
        *,
        script_path: str,
        artifact_dir: str,
        web_port: int,
        finish_callback_urls: str | None = None,
    ) -> subprocess.Popen:
        """启动单机 Locust 子进程，便于没有 Worker 时本机执行和调试。"""
        command = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            script_path,
            "--web-host",
            "0.0.0.0",
            "--web-port",
            str(web_port),
            "--csv",
            str(Path(artifact_dir) / "stats"),
            "--html",
            str(Path(artifact_dir) / "report.html"),
        ]
        log_file = Path(artifact_dir) / "locust-master.log"
        log_handle = log_file.open("a", encoding="utf-8")
        env = os.environ.copy()
        if finish_callback_urls:
            env["QTR_PRESSURE_FINISH_CALLBACK_URLS"] = finish_callback_urls
        return subprocess.Popen(
            command,
            cwd=str(Path(script_path).parent),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            env=env,
        )

    def wait_web_ready(self, port: int, timeout_seconds: int = 30) -> None:
        """等待 Locust Web API 就绪，超时抛出异常。"""
        deadline = time.time() + timeout_seconds
        last_error = None
        while time.time() < deadline:
            try:
                response = requests.get(f"http://{self.host}:{port}/stats/requests", timeout=2)
                if response.status_code < 500:
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(1)
        raise LocustProcessError(f"Locust Web API 未就绪: {last_error}")

    def start_test(self, *, port: int, users: int, spawn_rate: float, run_time: str | None = None) -> dict:
        """调用 Locust /swarm 接口开始压测。"""
        payload: dict[str, Any] = {
            "user_count": str(users),
            "spawn_rate": str(spawn_rate),
        }
        if run_time:
            payload["run_time"] = run_time
        response = requests.post(f"http://{self.host}:{port}/swarm", data=payload, timeout=10)
        if response.status_code >= 400:
            raise LocustProcessError(f"启动压测失败: {response.status_code} {response.text}")
        return response.json() if response.text else {"success": True}

    def stop_test(self, *, port: int) -> None:
        """调用 Locust /stop 接口停止压测。"""
        try:
            requests.get(f"http://{self.host}:{port}/stop", timeout=5)
        except Exception:
            pass

    def stats(self, *, port: int) -> dict:
        """读取 Locust 当前统计数据。"""
        response = requests.get(f"http://{self.host}:{port}/stats/requests", timeout=5)
        if response.status_code >= 400:
            raise LocustProcessError(f"读取压测状态失败: {response.status_code} {response.text}")
        return response.json()

    def terminate(self, pid: int | None) -> None:
        """终止 Locust master 子进程。"""
        if not pid:
            return
        try:
            if os.name == "nt":
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

    def is_process_alive(self, pid: int | None) -> bool:
        """判断指定进程是否仍存活。

        方法作用:
            在 Locust API 不可达时，提供基于 PID 的进程存活兜底判断。
        参数作用:
            pid: 进程 ID。
        响应值:
            True 表示进程存在；False 表示进程不存在或不可访问。
        """
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError as exc:
            # EPERM 表示进程存在但当前进程无权限信号操作。
            return getattr(exc, "errno", None) == errno.EPERM
        except Exception:
            return False

    def collect_summary(self, artifact_dir: str) -> dict:
        """从 Locust CSV 产物聚合报告摘要，供历史对比使用。"""
        stats_path = Path(artifact_dir) / "stats_stats.csv"
        failures_path = Path(artifact_dir) / "stats_failures.csv"
        summary = {
            "requests": 0,
            "failures": 0,
            "avg_rt_ms": 0,
            "p50_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "rps": 0,
            "fail_rate": 0,
            "rows": [],
            "failures_detail": [],
        }
        if stats_path.exists():
            with stats_path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            summary["rows"] = rows
            total = next((row for row in rows if row.get("Name") == "Aggregated"), rows[-1] if rows else None)
            if total:
                requests_count = int(float(total.get("Request Count") or 0))
                failures_count = int(float(total.get("Failure Count") or 0))
                summary.update(
                    {
                        "requests": requests_count,
                        "failures": failures_count,
                        "avg_rt_ms": float(total.get("Average Response Time") or 0),
                        "p50_ms": float(total.get("50%") or 0),
                        "p95_ms": float(total.get("95%") or 0),
                        "p99_ms": float(total.get("99%") or 0),
                        "rps": float(total.get("Requests/s") or 0),
                        "fail_rate": failures_count / requests_count if requests_count else 0,
                    }
                )

        if failures_path.exists():
            with failures_path.open(encoding="utf-8-sig", newline="") as file:
                summary["failures_detail"] = list(csv.DictReader(file))
        return summary
