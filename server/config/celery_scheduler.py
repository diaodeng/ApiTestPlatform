import json
import time
from datetime import datetime

from celery.beat import Scheduler
from sqlalchemy.orm import Session

from config.database import SessionLocal
from module_task.celery_contract import CELERY_EXECUTE_JOB_TASK, build_task_payload
from module_task.celery_job_models import CeleryPeriodicTask
from module_task.celery_schedule_parser import build_interval_schedule, parse_cron_to_schedule
from utils.log_util import logger


class DatabaseScheduler(Scheduler):
    """
    从数据库读取任务配置的 Celery Beat 调度器。
    """

    sync_interval_seconds = 10

    def __init__(self, *args, **kwargs):
        """
        初始化调度器内部缓存。

        :param args: 父类参数。
        :param kwargs: 父类参数。
        """
        self._last_sync_timestamp = 0.0
        self._entry_fingerprints: dict[str, str] = {}
        super().__init__(*args, **kwargs)

    def setup_schedule(self):
        """
        初始化调度表并立即从数据库同步一次。

        :return: 无返回值。
        """
        super().setup_schedule()
        self._sync_database_jobs(force=True)

    def sync(self):
        """
        覆盖父类 sync，数据库调度器不做本地落盘。

        :return: 无返回值。
        """
        return

    def tick(self, *args, **kwargs):
        """
        在每次调度循环前尝试同步数据库任务。

        :param args: 父类 tick 透传参数。
        :param kwargs: 父类 tick 透传参数。
        :return: 下一次调度检查等待秒数。
        """
        self._sync_database_jobs()
        return super().tick(*args, **kwargs)

    @staticmethod
    def _build_entry_name(task_id: int) -> str:
        """
        生成 beat entry 唯一名称。

        :param task_id: 任务ID。
        :return: entry 名称。
        """
        return f"task:{task_id}"

    @staticmethod
    def _build_schedule_obj(task_row: CeleryPeriodicTask):
        """
        构建 Celery schedule 对象。

        :param task_row: 任务配置行对象。
        :return: Celery schedule 对象。
        """
        schedule_type = (task_row.schedule_type or "").strip().lower()
        if schedule_type == "crontab":
            return parse_cron_to_schedule(task_row.cron_expression or "")
        if schedule_type == "interval":
            return build_interval_schedule(task_row.interval_every or 0, task_row.interval_period or "")
        raise ValueError(f"不支持的 schedule_type: {task_row.schedule_type}")

    def _dispatch_due_one_off_tasks(self, session: Session, one_off_tasks: list[CeleryPeriodicTask]):
        """
        处理到期的单次任务（once）。

        :param session: 数据库会话。
        :param one_off_tasks: 单次任务列表。
        :return: 无返回值。
        """
        now = datetime.now()
        changed = False
        for task in one_off_tasks:
            if task.one_off_consumed:
                continue
            if not task.one_off_eta:
                logger.warning(f"单次任务[{task.task_id}] 缺少 one_off_eta，已跳过")
                continue
            if task.one_off_eta > now:
                continue

            payload = build_task_payload(task_row=task, trigger_type="once")
            self.app.send_task(
                CELERY_EXECUTE_JOB_TASK,
                args=[payload],
                queue=payload["queue_name"],
            )
            task.one_off_consumed = True
            task.enabled = False
            task.last_status = "queued"
            task.last_message = "单次任务已提交执行"
            task.update_time = now
            changed = True
            logger.info(f"单次任务已提交执行: task_id={task.task_id}, task_name={task.task_name}")

        if changed:
            session.commit()

    def _sync_database_jobs(self, force: bool = False):
        """
        同步数据库中的任务配置到 Beat 内存调度表。

        :param force: 是否强制同步。
        :return: 无返回值。
        """
        now_monotonic = time.monotonic()
        if not force and now_monotonic - self._last_sync_timestamp < self.sync_interval_seconds:
            return
        self._last_sync_timestamp = now_monotonic

        session = SessionLocal()
        try:
            rows = (
                session.query(CeleryPeriodicTask)
                .filter(CeleryPeriodicTask.enabled.is_(True))
                .all()
            )
            periodic_rows: list[CeleryPeriodicTask] = []
            one_off_rows: list[CeleryPeriodicTask] = []
            for row in rows:
                if (row.schedule_type or "").strip().lower() == "once":
                    one_off_rows.append(row)
                else:
                    periodic_rows.append(row)

            self._dispatch_due_one_off_tasks(session, one_off_rows)

            next_schedule = {}
            next_fingerprints: dict[str, str] = {}

            for task_row in periodic_rows:
                entry_name = self._build_entry_name(task_row.task_id)
                try:
                    schedule_obj = self._build_schedule_obj(task_row)
                except Exception as exc:
                    logger.warning(f"任务[{entry_name}] 调度解析失败，已跳过: {exc}")
                    continue

                payload = build_task_payload(task_row=task_row, trigger_type="scheduler")
                options = {"queue": payload["queue_name"]}
                fingerprint = json.dumps(
                    {
                        "task": CELERY_EXECUTE_JOB_TASK,
                        "schedule": str(schedule_obj),
                        "args_json": payload["args_json"],
                        "kwargs_json": payload["kwargs_json"],
                        "queue_name": payload["queue_name"],
                        "allow_concurrent": payload["allow_concurrent"],
                        "lock_ttl_seconds": payload["lock_ttl_seconds"],
                        "task_key": payload["task_key"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )

                old_entry = self.schedule.get(entry_name)
                if old_entry and self._entry_fingerprints.get(entry_name) == fingerprint:
                    next_schedule[entry_name] = old_entry
                    next_fingerprints[entry_name] = fingerprint
                    continue

                entry_kwargs = {}
                if old_entry:
                    entry_kwargs["last_run_at"] = old_entry.last_run_at
                    entry_kwargs["total_run_count"] = old_entry.total_run_count

                next_schedule[entry_name] = self.Entry(
                    name=entry_name,
                    task=CELERY_EXECUTE_JOB_TASK,
                    schedule=schedule_obj,
                    args=(payload,),
                    kwargs={},
                    options=options,
                    app=self.app,
                    **entry_kwargs,
                )
                next_fingerprints[entry_name] = fingerprint

            removed_entries = sorted(set(self.schedule.keys()) - set(next_schedule.keys()))
            if removed_entries:
                logger.info(f"Celery Beat 同步移除任务: {removed_entries}")

            self.schedule.clear()
            self.schedule.update(next_schedule)
            self._entry_fingerprints = next_fingerprints
        except Exception as exc:
            session.rollback()
            logger.exception(f"Celery Beat 同步数据库任务失败: {exc}")
        finally:
            session.close()
