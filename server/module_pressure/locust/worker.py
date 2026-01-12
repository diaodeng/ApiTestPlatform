# locust/worker.py
import os
from locust import HttpUser, task
from locust.env import Environment
from module_pressure.engines.locust.worker_stub import DemoUser
import requests
PLATFORM = ""

def start_worker(user_classes, master_host):
    env = Environment(user_classes=user_classes)
    env.create_worker_runner(master_host=master_host, master_port=5557)
    env.runner.greenlet.join()




# def register_to_platform():
#     requests.post(
#         f"{PLATFORM}/api/workers/register",
#         # json=collect_meta()
#     )

class DemoUser2(HttpUser):
    host = "http://127.0.0.1:8000"
    @task
    def noop(self):
        print("noop211111")



if __name__ == "__main__":
    # register_to_platform()
    start_worker(
        [DemoUser2],
        # master_host=os.getenv("MASTER_HOST")
        master_host="127.0.0.1",
    )
