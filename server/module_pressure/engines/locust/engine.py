from ..base import PressureEngine
from .dsl_builder import build_user


class LocustEngine(PressureEngine):
    def start(self, job):
        call_locust_api("/start", job)

    def stop(self, job):
        call_locust_api("/stop")

    def metrics(self, job):
        call_locust_api("/metrics")

    def prepare(self):
        dsl = load_dsl(self.job.dsl_id)
        self.user_class = build_user(dsl)

        self.env, self.runner = start_master([self.user_class])

    @classmethod
    def generate_report(cls, job_id):
        metrics = load_metrics(job_id)

        return {
            "max_rps": max(m.rps for m in metrics),
            "avg_rt": sum(m.avg_rt for m in metrics) / len(metrics),
            "fail_rate": max(m.fail_rate for m in metrics)
        }

    @classmethod
    def export_stats(cls, stats):
        total = stats.total
        return {
            "rps": total.current_rps,
            "avg_rt": total.avg_response_time,
            "p95": total.get_response_time_percentile(0.95),
            "fail_rate": total.fail_ratio
        }