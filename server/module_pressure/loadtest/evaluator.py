from datetime import datetime
import math

class CapabilityEvaluator:

    MIN_REQUIRED_SAMPLES = 5
    ERROR_RATE_THRESHOLD = 0.01
    RT_THRESHOLD_MS = 2000
    DECAY_LAMBDA = 0.05

    def evaluate(self, worker_id: str, engine: str):
        stats = query_stable_snapshot_stats(
            worker_id=worker_id,
            engine=engine,
            rt_threshold=self.RT_THRESHOLD_MS,
        )

        if not stats or stats["sample_count"] == 0:
            return None

        confidence = min(
            stats["sample_count"] / self.MIN_REQUIRED_SAMPLES,
            1.0,
        )

        # 衰减
        days = (datetime.now() - stats["last_snapshot_time"]).days
        confidence *= math.exp(-self.DECAY_LAMBDA * days)

        upsert_capability_model(
            worker_id=worker_id,
            engine=engine,
            max_concurrency=stats["max_concurrency"],
            max_qps=stats["max_qps"],
            avg_rt=stats["avg_rt"],
            avg_error_rate=stats["avg_error_rate"],
            confidence=confidence,
            sample_count=stats["sample_count"],
            last_snapshot_time=stats["last_snapshot_time"],
        )
