from celery import chain, group, chord

def build_pressure_workflow(test_id, case_ids, config):
    nodes = []

    if config.pre_check:  # 前置检查
        nodes.append(pre_check.s(test_id).set(queue="control"))

    # Case 执行
    case_tasks = [
        run_case.s(case_id).set(queue="pressure")
        for case_id in case_ids
    ]

    if config.parallel:  # 是否并发
        if config.with_report:
            nodes.append(
                chord(
                    case_tasks,
                    generate_report.s(test_id).set(queue="report")
                )
            )
        else:
            nodes.append(group(case_tasks))
    else:
        nodes.extend(case_tasks)

    return chain(*nodes)



from locust import TaskSet, task

def build_taskset(dsl: dict):
    class DynamicTaskSet(TaskSet):
        pass

    for t in dsl["tasks"]:
        def make_task(tdef):
            @task(tdef.get("weight", 1))
            def _task(self):
                self.client.request(
                    method=tdef["method"],
                    url=tdef["url"]
                )
            return _task

        setattr(
            DynamicTaskSet,
            f"task_{len(DynamicTaskSet.tasks)}",
            make_task(t)
        )

    return DynamicTaskSet


from locust import HttpUser

def build_user(dsl):
    taskset = build_taskset(dsl)

    class DynamicUser(HttpUser):
        tasks = [taskset]
        wait_time = lambda self: 0.1

    return DynamicUser
