from module_pressure.engines import PressureEngine


class LocustEngine(PressureEngine):
    def start(self, job):
        call_locust_api("/start", job)

    def stop(self, job):
        call_locust_api("/stop")
