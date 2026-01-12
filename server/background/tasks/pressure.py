# app/background/tasks/pressure.py
from module_pressure.services.dispatcher import run_pressure_job
from background.celery_app import celery_app

@celery_app.task("worker.tasks.pressure.run_case")
def run_pressure(job_id: int):
    run_pressure_job(job_id)



@celery_app.task(name="worker.tasks.report.generate")
def generate_report(test_id: int):
    print(f"Generate report {test_id}")



@celery_app.task(name="worker.tasks.control.start_test")
def start_test(test_id: int):
    print(f"Start test {test_id}")

@celery_app.task(name="worker.tasks.control.stop_test")
def stop_test(test_id: int):
    redis.set(f"test:cancel:{test_id}", 1)
    print(f"Stop test {test_id}")
