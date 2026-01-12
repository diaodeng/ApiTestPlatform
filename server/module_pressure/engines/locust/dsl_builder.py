import os, json
from jinja2 import Environment, FileSystemLoader

def compile_locust(dsl: dict, run_id: int):
    run_dir = f"workspace/runs/run_{run_id}"
    os.makedirs(run_dir + "/data", exist_ok=True)

    env = Environment(loader=FileSystemLoader("templates"))
    tpl = env.get_template("locustfile.j2")

    code = tpl.render(
        base_url=dsl["target"]["base_url"],
        tasks=dsl["tasks"],
        data_sources=dsl.get("data_sources", {})
    )

    script = f"{run_dir}/locustfile.py"
    with open(script, "w") as f:
        f.write(code)

    with open(f"{run_dir}/scenario.json", "w") as f:
        json.dump(dsl, f)

    return script



from celery import chain, group, chord

def build_pressure_workflow(test_id, case_ids, config):
    """
    购进任务流程
    """

    nodes = []

    if config.pre_check:  # 前置检查
        nodes.append(pre_check.s(test_id).set(queue="control"))

    # Case 执行
    case_tasks = [
        run_case.s(case_id).set(queue="pressure")
        for case_id in case_ids
    ]

    if config.parallel:  # 是否并发
        nodes.append(group(case_tasks))
    else:
        nodes.extend(case_tasks)

    if config.with_report:
        nodes.append(
            generate_report.s(test_id).set(queue="report")
        )

    return chain(*nodes)


#压测数据dsl示例
"""
{
  "flow": [
    {
      "name": "login",
      "extract": {
        "token": "$.token"
      }
    },
    {
      "if": "token != null",
      "then": [
        {
          "loop": 3,
          "request": {
            "method": "GET",
            "url": "/order",
            "headers": {"Authorization": "Bearer ${token}"}
          }
        }
      ]
    }
  ]
}

"""
from locust import TaskSet, task

def build_step(step):
    if "request" in step:
        return build_request(step)
    if "loop" in step:
        return build_loop(step)
    if "if" in step:
        return build_condition(step)


def build_taskset(dsl: dict):
    class DynamicTaskSet(TaskSet):
        pass

    for t in dsl["tasks"]:
        def make_task(tdef):
            @task(tdef.get("weight", 1))
            def _task(self):
                with self.client.request(
                        tdef["request"]["method"],
                        tdef["request"]["url"],
                        headers=render(tdef["request"].get("headers"))
                ) as resp:
                    extract_vars(resp, tdef.get("extract"))
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
