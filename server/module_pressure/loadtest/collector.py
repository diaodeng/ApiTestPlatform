class CapabilityCollector:

    def record(self, result: LoadTestResult):
        snapshot = WorkerCapabilitySnapshot(
            worker_id=result.worker_id,
            engine=result.engine,
            concurrency=result.concurrency,
            actual_qps=result.actual_qps,
            avg_rt_ms=result.avg_rt_ms,
            error_rate=result.fail_requests / result.total_requests,
            success=result.fail_requests == 0,
            timestamp=datetime.utcnow(),
        )
        save_snapshot(snapshot)


