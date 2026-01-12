

class CapabilityAllocator:

    def allocate(self, plan: LoadTestPlan):
        workers = load_capable_workers(plan.engine)

        total_capacity = sum(w.max_stable_qps for w in workers)

        if total_capacity < plan.target_qps:
            raise InsufficientCapacityError()

        allocations = []
        for w in workers:
            ratio = w.max_stable_qps / total_capacity
            allocations.append({
                "worker_id": w.worker_id,
                "qps": plan.target_qps * ratio,
            })

        return allocations
