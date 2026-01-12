# modules/pressure/service/locust_service.py
from module_pressure.engines.locust.master import locust_master


class LocustControlService:

    def ensure_master(self):
        locust_master.start_master()

    def start(self, users: int, spawn_rate: int):
        self.ensure_master()
        locust_master.start_test(users, spawn_rate)

    def stop(self):
        locust_master.stop_test()

    def force_stop(self):
        locust_master.force_stop()

    def status(self) -> dict:
        return locust_master.status()


locust_service = LocustControlService()
