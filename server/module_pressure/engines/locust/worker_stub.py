# 这里面不做实现，只是固定文件

from locust import HttpUser, task

class DemoUser(HttpUser):
    host = "http://127.0.0.1:8000"
    @task
    def noop(self):
        print("noop")


class DemoUser2(HttpUser):
    host = "http://127.0.0.1:8000"
    @task
    def noop(self):
        print("noop2")