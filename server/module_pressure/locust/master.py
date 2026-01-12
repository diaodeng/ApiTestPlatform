import time

from locust.env import Environment
# from locust.runners import MasterRunner
from locust.stats import stats_printer, stats_history
# from module_pressure.locust.control_api import create_control_api
from module_pressure.engines.locust.worker_stub import DemoUser, DemoUser2
import gevent

def start_master(user_classes):
    env = Environment(user_classes=user_classes)
    runner = env.create_master_runner("*", 5557)

    # create_control_api(env, runner)
    gevent.spawn(stats_printer(env.stats))
    # gevent.spawn(stats_history, env.stats)

    print("Waiting for workers to connect...")
    while len(runner.clients.ready) < 1:
        time.sleep(0.5)
    print("Connected!")


    runner.start(2, 2, user_classes=[DemoUser2])
    gevent.spawn_later(10, runner.stop)
    time.sleep(5)
    runner.start(2, 2, user_classes=[DemoUser])
    runner.greenlet.join()
    return env, runner


if __name__ == "__main__":
    start_master([DemoUser2])