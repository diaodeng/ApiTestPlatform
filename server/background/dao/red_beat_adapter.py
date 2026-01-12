from redbeat import RedBeatSchedulerEntry
from celery.schedules import crontab
from background.entity.vo.schedule import ScheduleCreate

class RedBeatAdapter:

    def __init__(self, celery_app):
        self.app = celery_app

    def upsert(self, schedule: ScheduleCreate):
        entry = RedBeatSchedulerEntry(
            name=schedule.name,
            task=schedule.task,
            schedule=self._parse_cron(schedule.cron_expr),
            args=schedule.args,
            app=self.app,
            enabled=schedule.enabled,
        )
        entry.save()

    def delete(self, name: str):
        entry = RedBeatSchedulerEntry.from_key(f"redbeat:{name}", self.app)
        entry.delete()

    def enable(self, name: str, enabled: bool):
        entry = RedBeatSchedulerEntry.from_key(f"redbeat:{name}", self.app)
        entry.enabled = enabled
        entry.save()

    def _parse_cron(self, cron_expr: str):
        m, h, dom, mon, dow = cron_expr.split()
        return crontab(
            minute=m, hour=h,
            day_of_month=dom,
            month_of_year=mon,
            day_of_week=dow
        )
