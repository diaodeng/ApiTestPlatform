from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

try:
    import psutil
except Exception:  # pragma: no cover - psutil is optional for the agent.
    psutil = None


class WorkerAgent:
    """Standalone pressure worker agent.

    The agent does not import project modules. It registers itself to the
    platform, polls assignment, prepares locust artifacts, starts locust worker,
    and reports ready status before the platform starts the test.
    """

    def __init__(self):
        self.server = self._env("QTR_SERVER").rstrip("/")
        self.worker_id = self._env("WORKER_ID", socket.gethostname())
        self.worker_host = self._env("WORKER_HOST", self._detect_host())
        self.api_key = self._env("QTR_API_KEY", "")
        self.jwt_token = self._env("QTR_TOKEN", "")
        self.work_dir = Path(self._env("WORKER_WORK_DIR", "./pressure_worker_runs")).resolve()
        self.max_users = int(self._env("MAX_USERS", "100"))
        self.cpu_cores = int(self._env("CPU_CORES", str(os.cpu_count() or 1)))
        self.memory_mb = int(self._env("MEMORY_MB", str(self._detect_memory_mb())))
        self.poll_interval = float(self._env("POLL_INTERVAL", "3"))
        self.remote_prefix = self._env("RUNS_REMOTE_PREFIX", "")
        self.local_prefix = self._env("RUNS_LOCAL_PREFIX", "")
        self.process: subprocess.Popen | None = None
        self.current_run_id: int | None = None

    def _env(self, key: str, default: str | None = None) -> str:
        value = os.getenv(key, default)
        if value is None or value == "":
            raise RuntimeError(f"Missing required environment variable: {key}")
        return value

    def _headers(self) -> dict[str, str]:
        if self.api_key:
            return {"X-API-Key": self.api_key}
        if self.jwt_token:
            return {"Authorization": f"Bearer {self.jwt_token}"}
        return {}

    def _detect_host(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return str(sock.getsockname()[0])
        except Exception:
            return "127.0.0.1"

    def _detect_memory_mb(self) -> int:
        if psutil is None:
            return 1024
        return int(psutil.virtual_memory().total / 1024 / 1024)

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = f"{self.server}{path}"
        response = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            raise RuntimeError(payload.get("msg") or f"request failed: {path}")
        return payload.get("data")

    def register(self) -> None:
        payload = {
            "worker_id": self.worker_id,
            "host": self.worker_host,
            "hostname": socket.gethostname(),
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "max_users": self.max_users,
            "engine_types": ["locust"],
            "labels": [item for item in self._env("WORKER_LABELS", "default").split(",") if item],
        }
        self._request("POST", "/pressure/workers/register", json=payload)

    def heartbeat(self, status: str | None = None) -> None:
        cpu_usage = psutil.cpu_percent(interval=None) / 100 if psutil else 0
        memory_usage = psutil.virtual_memory().percent / 100 if psutil else 0
        running = self.process is not None and self.process.poll() is None
        payload = {
            "worker_id": self.worker_id,
            "run_id": self.current_run_id if running else None,
            "current_users": 0,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "rps": 0,
            "fail_rate": 0,
            "latency_ms": 0,
            "status": status or ("busy" if running else "idle"),
        }
        self._request("POST", "/pressure/workers/heartbeat", json=payload)

    def poll_assignment(self) -> dict[str, Any]:
        return self._request("GET", f"/pressure/workers/{self.worker_id}/assignment")

    def report_ready(self, run_id: int, status: str, message: str = "") -> None:
        self._request(
            "POST",
            f"/pressure/workers/{self.worker_id}/ready",
            json={"run_id": run_id, "status": status, "message": message},
        )

    def translate_shared_path(self, path: str) -> str:
        if self.remote_prefix and self.local_prefix and path.startswith(self.remote_prefix):
            return self.local_prefix + path[len(self.remote_prefix):]
        return path

    def prepare_artifacts(self, assignment: dict[str, Any]) -> str:
        mode = assignment.get("script_delivery_mode") or "shared_path"
        run_id = assignment["run_id"]
        run_dir = self.work_dir / f"run_{run_id}"
        data_dir = run_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        if mode == "shared_path":
            return self.translate_shared_path(assignment["script_path"])

        script_path = run_dir / "locustfile.py"
        csv_path = data_dir / "cases.csv"
        scenario_path = run_dir / "scenario.json"

        if mode == "inline":
            script_path.write_text(assignment.get("script_content") or "", encoding="utf-8")
            csv_path.write_text(assignment.get("csv_content") or "case\n", encoding="utf-8")
            scenario_path.write_text(assignment.get("scenario_content") or "{}", encoding="utf-8")
            return str(script_path)

        if mode == "fetch":
            urls = assignment.get("artifact_urls") or {}
            script_path.write_text(self._request("GET", urls["script"]), encoding="utf-8")
            csv_path.write_text(self._request("GET", urls["csv"]), encoding="utf-8")
            scenario_path.write_text(self._request("GET", urls["scenario"]), encoding="utf-8")
            return str(script_path)

        raise RuntimeError(f"Unsupported script delivery mode: {mode}")

    def start_locust_worker(self, assignment: dict[str, Any]) -> None:
        script_path = self.prepare_artifacts(assignment)
        command = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            script_path,
            "--worker",
            "--master-host",
            assignment["master_host"],
            "--master-port",
            str(assignment["master_port"]),
        ]
        log_dir = self.work_dir / f"run_{assignment['run_id']}"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = (log_dir / "locust-worker.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
        self.current_run_id = int(assignment["run_id"])
        time.sleep(1)
        if self.process.poll() is not None:
            raise RuntimeError(f"locust worker exited, code={self.process.returncode}")

    def stop_locust_worker(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self.process = None
            self.current_run_id = None
            return
        try:
            if os.name == "nt":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.process.terminate()
            self.process.wait(timeout=10)
        except Exception:
            self.process.kill()
        finally:
            self.process = None
            self.current_run_id = None

    def loop(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.register()
        while True:
            try:
                self.heartbeat()
                assignment = self.poll_assignment()
                assigned_run_id = assignment.get("run_id") if assignment and assignment.get("assigned") else None

                if not assigned_run_id:
                    if self.process is not None and self.process.poll() is not None:
                        self.process = None
                        self.current_run_id = None
                    time.sleep(self.poll_interval)
                    continue

                if self.current_run_id == assigned_run_id and self.process and self.process.poll() is None:
                    time.sleep(self.poll_interval)
                    continue

                if self.process and self.process.poll() is None:
                    self.stop_locust_worker()

                try:
                    self.start_locust_worker(assignment)
                    self.report_ready(int(assigned_run_id), "ready", "locust worker started")
                except Exception as exc:
                    self.report_ready(int(assigned_run_id), "failed", str(exc))
                    self.stop_locust_worker()
            except Exception as exc:
                print(f"[worker-agent] {exc}", flush=True)
            time.sleep(self.poll_interval)


if __name__ == "__main__":
    WorkerAgent().loop()
