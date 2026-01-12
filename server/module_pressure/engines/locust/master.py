# modules/pressure/engine/locust/master.py
from locust.env import Environment
from locust.runners import MasterRunner
from locust.stats import stats_printer, stats_history
import gevent
import threading

from .worker_stub import DemoUser


class LocustMaster:
    def __init__(self):
        self.env = Environment(user_classes=[DemoUser])
        self.runner: MasterRunner | None = None
        self._greenlets_started = False

    def start_master(self, master_bind_host:str="*", master_bind_port:int=5557):
        if self.runner:
            return

        self.runner = self.env.create_master_runner(master_bind_host=master_bind_host, master_bind_port=master_bind_port)

        # 启动统计协程（必须）
        if not self._greenlets_started:
            gevent.spawn(stats_printer(self.env.stats))
            gevent.spawn(stats_history, self.env.stats)
            self._greenlets_started = True

    def start_test(self, users: int, spawn_rate: int, user_classes=None):
        if not self.runner:
            raise RuntimeError("Locust master not started")

        self.runner.start(users, spawn_rate, user_classes=user_classes)

    def stop_test(self):
        if self.runner:
            self.runner.quit()

    def force_stop(self):
        if self.runner:
            self.runner.stop()

    def status(self) -> dict:
        if not self.runner:
            return {"state": "not_started"}

        return {
            "state": self.runner.state,
            "user_count": self.runner.user_count,
            "worker_count": self.runner.worker_count,
            "workers": list(self.runner.clients.keys()),
            "requests": self.env.stats.total.num_requests,
            "failures": self.env.stats.total.num_failures,
        }


# ⭐ 全局单例（一个 master）
locust_master = LocustMaster()
