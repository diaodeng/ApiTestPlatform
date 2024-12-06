import atexit
import os
import tempfile
import platform
import time

from apscheduler.job import Job
from apscheduler.jobstores.base import JobLookupError, ConflictingIdError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_ALL, EVENT_SCHEDULER_STARTED, EVENT_SCHEDULER_SHUTDOWN, EVENT_SCHEDULER_PAUSED, \
    EVENT_SCHEDULER_RESUMED, EVENT_EXECUTOR_ADDED, EVENT_EXECUTOR_REMOVED, EVENT_JOBSTORE_ADDED, EVENT_JOBSTORE_REMOVED, \
    EVENT_ALL_JOBS_REMOVED, EVENT_JOB_ADDED, EVENT_JOB_REMOVED, EVENT_JOB_MODIFIED, EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, \
    EVENT_JOB_MISSED, EVENT_JOB_SUBMITTED, EVENT_JOB_MAX_INSTANCES
import json
from datetime import datetime, timedelta


from config.database import engine, SQLALCHEMY_DATABASE_URL
from config.env import RedisConfig
from utils.log_util import logger
import module_task
from module_hrm.enums.enums import TaskStatusEnum


# 重写Cron定时
class MyCronTrigger(CronTrigger):
    @classmethod
    def from_crontab(cls, expr, timezone=None):
        values = expr.split()
        if len(values) != 6 and len(values) != 7:
            raise ValueError('Wrong number of fields; got {}, expected 6 or 7'.format(len(values)))

        second = values[0]
        minute = values[1]
        hour = values[2]
        if '?' in values[3]:
            day = None
        elif 'L' in values[5]:
            day = f"last {values[5].replace('L', '')}"
        elif 'W' in values[3]:
            day = cls.__find_recent_workday(int(values[3].split('W')[0]))
        else:
            day = values[3].replace('L', 'last')
        month = values[4]
        if '?' in values[5] or 'L' in values[5]:
            week = None
        elif '#' in values[5]:
            week = int(values[5].split('#')[1])
        else:
            week = values[5]
        if '#' in values[5]:
            day_of_week = int(values[5].split('#')[0]) - 1
        else:
            day_of_week = None
        year = values[6] if len(values) == 7 else None
        return cls(second=second, minute=minute, hour=hour, day=day, month=month, week=week,
                   day_of_week=day_of_week, year=year, timezone=timezone)

    @classmethod
    def __find_recent_workday(cls, day):
        now = datetime.now()
        date = datetime(now.year, now.month, day)
        if date.weekday() < 5:
            return date.day
        else:
            diff = 1
            while True:
                previous_day = date - timedelta(days=diff)
                if previous_day.weekday() < 5:
                    return previous_day.day
                else:
                    diff += 1

    # def get_next_fire_time(self, previous_fire_time, now):
    #     if SchedulerUtil.acquire_lock():
    #         return super().get_next_fire_time(previous_fire_time, now)
    #     else:
    #         logger.info("已被其他进程触发")
    #         return None


class SchedulerUtil:
    """
    定时任务相关方法
    """

    def __init__(self, table_name="apscheduler_jobs", redis_db=None):
        job_stores = {
            # 'default': MemoryJobStore(),
            'sqlalchemy': SQLAlchemyJobStore(url=SQLALCHEMY_DATABASE_URL, engine=engine, tablename=table_name),
            'redis': RedisJobStore(
                **dict(
                    host=RedisConfig.redis_host,
                    port=RedisConfig.redis_port,
                    username=RedisConfig.redis_username,
                    password=RedisConfig.redis_password,
                    db=redis_db or RedisConfig.redis_database
                )
            )
        }
        executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }
        job_defaults = {
            'coalesce': False,
            'max_instance': 1
        }
        self.scheduler = BackgroundScheduler()
        self.scheduler.configure(jobstores=job_stores, executors=executors, job_defaults=job_defaults)

        # if self.acquire_lock():
        self.scheduler.start()
        logger.info("scheduler启动了")

        self.add_event()

    @classmethod
    def event_status(cls, event):
        status = TaskStatusEnum.success.value
        message = "执行成功"
        if event.code == EVENT_JOB_SUBMITTED:
            status = TaskStatusEnum.running.value
            message = "准备执行/执行中"
        elif event.code == EVENT_JOB_MAX_INSTANCES:
            status = TaskStatusEnum.max_instances.value
            message = "超过最大并发数"
        elif event.code == EVENT_JOB_EXECUTED:
            status = TaskStatusEnum.success.value
            message = "执行成功"
        elif event.code == EVENT_JOB_ERROR:
            status = TaskStatusEnum.error.value
            message = "执行异常"
        elif event.code == EVENT_JOB_MISSED:
            status = TaskStatusEnum.missed.value
            message = "错过执行时间"
        return status, message

    @classmethod
    def cron_trigger_from_crontab(cls, expr, timezone=None):
        return MyCronTrigger.from_crontab(expr, timezone)

    @classmethod
    def acquire_lock(cls):
        lock_file = os.path.join(tempfile.gettempdir(), "scheduler.lock")
        global qtr_scheduler_lock_handle
        qtr_scheduler_lock_handle = open(lock_file, "w")
        if platform.system() != "Windows":
            import fcntl
            try:
                fcntl.lockf(qtr_scheduler_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except IOError:
                return False

        else:
            import msvcrt
            try:
                msvcrt.locking(qtr_scheduler_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except IOError:
                return False

    @classmethod
    def acquire_redis_lock(cls, redis, lock_name, acquire_timeout=10):
        end_time = time.time() + acquire_timeout
        r = redis
        while time.time() < end_time:
            if r.sernx(lock_name, 1):
                r.expire(lock_name, 10)
                return True
            elif not r.ttl(lock_name):
                r.expire(lock_name, 10)
                time.sleep(0.1)
            return False

    @classmethod
    def release_redis_lock(cls, redis, lock_name):
        r = redis
        r.delete(lock_name)

    def add_event(self):
        self.scheduler.add_listener(self.event_listener_all, EVENT_ALL)
        self.scheduler.add_listener(self.event_listener_executor_added, EVENT_EXECUTOR_ADDED)
        self.scheduler.add_listener(self.event_listener_executor_removed, EVENT_EXECUTOR_REMOVED)
        self.scheduler.add_listener(self.event_listener_job_added, EVENT_JOB_ADDED)
        self.scheduler.add_listener(self.event_listener_job_modified, EVENT_JOB_MODIFIED)
        self.scheduler.add_listener(self.event_listener_job_removed, EVENT_JOB_REMOVED)
        self.scheduler.add_listener(self.event_listener_job_submitted, EVENT_JOB_SUBMITTED)
        self.scheduler.add_listener(self.event_listener_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self.event_listener_job_error, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self.event_listener_job_missed, EVENT_JOB_MISSED)
        self.scheduler.add_listener(self.event_listener_scheduler_shutdown, EVENT_SCHEDULER_SHUTDOWN)
        self.scheduler.add_listener(self.event_listener_scheduler_started, EVENT_SCHEDULER_STARTED)

    async def close_scheduler(self):
        """
        应用关闭时关闭定时任务
        :return:
        """
        self.scheduler.shutdown()
        logger.info("关闭定时任务成功")

    def get_scheduler_job(self, job_id):
        """
        根据任务id获取任务对象
        :param job_id: 任务id
        :return: 任务对象
        """
        try:
            query_job = self.scheduler.get_job(job_id=str(job_id))

            return query_job
        except JobLookupError as e:
            logger.info(f"job {job_id} 不存在")

    def add_scheduler_job(self, job_info):
        """
        根据输入的任务对象信息添加任务
        :param job_info: 任务对象信息
        :return:
        """
        try:
            hasJob = self.get_scheduler_job(str(job_info.job_id))
            if hasJob:
                logger.info("已经存在相同的job")
                return
            self.scheduler.add_job(
                func=eval(job_info.invoke_target),
                trigger=self.cron_trigger_from_crontab(job_info.cron_expression),
                args=job_info.job_args.split(',') if job_info.job_args else None,
                kwargs=json.loads(job_info.job_kwargs) if job_info.job_kwargs else None,
                id=str(job_info.job_id),
                name=job_info.job_name,
                misfire_grace_time=1000000000000 if job_info.misfire_policy == '3' else None,
                coalesce=True if job_info.misfire_policy == '2' else False,
                max_instances=3 if job_info.concurrent == '0' else 1,
                jobstore=job_info.job_group,
                executor=job_info.job_executor
            )
            return True
        except ConflictingIdError as e:
            logger.error(f"任务创建失败，已经存在id为：{job_info.job_id}的任务")
            return False
        finally:
            pass

    def execute_scheduler_job_once(self, job_info):
        """
        根据输入的任务对象执行一次任务
        :param job_info: 任务对象信息
        :return:
        """
        # if not self.acquire_lock():return
        try:
            self.scheduler.add_job(
                func=eval(job_info.invoke_target),
                trigger='date',
                run_date=datetime.now() + timedelta(seconds=1),
                args=job_info.job_args.split(',') if job_info.job_args else None,
                kwargs=json.loads(job_info.job_kwargs) if job_info.job_kwargs else None,
                id=f"{str(job_info.job_id)}",
                name=job_info.job_name,
                misfire_grace_time=1000000000000 if job_info.misfire_policy == '3' else None,
                coalesce=True if job_info.misfire_policy == '2' else False,
                max_instances=3 if job_info.concurrent == '0' else 1,
                jobstore=job_info.job_group,
                executor=job_info.job_executor
            )
        except ConflictingIdError as e:
            logger.error(f"任务创建失败，已经存在id为：{job_info.job_id}的任务")
        finally:
            pass

    def remove_scheduler_job(self, job_id):
        """
        根据任务id移除任务
        :param job_id: 任务id
        :return:
        """

        try:
            self.scheduler.remove_job(job_id=str(job_id))
        except JobLookupError as e:
            logger.info(f"没有找到定时任务：{job_id}")

    def get_job_list(self) -> list[Job]:
        return self.scheduler.get_jobs()

    def event_listener_all(self, event):
        pass

    def event_listener_scheduler_start(self, event):
        logger.info("event_listener_scheduler_start")

    def event_listener_executor_added(self, event):
        logger.info("event_listener_executor_added")

    def event_listener_executor_removed(self, event):
        logger.info("event_listener_executor_removed")

    def event_listener_job_added(self, event):
        logger.info(f"event_listener_job_added:[{event.code}] {event.job_id}")

    def event_listener_job_modified(self, event):
        logger.info("event_listener_job_modified")

    def event_listener_job_removed(self, event):
        logger.info(f"event_listener_job_removed:[{event.code}] {event.job_id}")

    def event_listener_job_executed(self, event):
        logger.info(f"event_listener_job_executed:[{event.code}] {event.job_id}")

    def event_listener_job_error(self, event):
        logger.info(f"event_listener_job_error:[{event.code}] {event.job_id}")

    def event_listener_job_missed(self, event):
        logger.info(f"event_listener_job_missed:[{event.code}] {event.job_id}")

    def event_listener_job_submitted(self, event):
        logger.info(f"event_listener_job_submitted:[{event.code}] {event.job_id}")

    def event_listener_scheduler_shutdown(self, event):
        running_jobs = self.scheduler.get_jobs()
        logger.info(f"正在运行的任务数量：{len(running_jobs)}")
        for job in running_jobs:
            self.remove_scheduler_job(job.id)
            logger.info(f"任务[{job.id}-{job.name}]被停止")
        logger.info(f"event_listener_scheduler_shutdown:[{event.code}]")

    def event_listener_scheduler_started(self, event):
        logger.info(f"event_listener_scheduler_started:[{event.code}]")
