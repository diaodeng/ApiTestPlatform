from background.dao.schedule_repository import ScheduleRepository
from background.dao.red_beat_adapter import RedBeatAdapter
from background.entity.vo.schedule import ScheduleCreate

class ScheduleService:

    def __init__(
        self,
        repo: ScheduleRepository,
        scheduler: RedBeatAdapter,
    ):
        self.repo = repo
        self.scheduler = scheduler

    def create(self, schedule: ScheduleCreate):
        # 1. 写数据库（事实源）
        self.repo.save(schedule)

        # 2. 投影到 RedBeat
        self.scheduler.upsert(schedule)

    def update(self, schedule: ScheduleCreate):
        self.repo.save(schedule)
        self.scheduler.upsert(schedule)

    def set_enabled(self, name: str, enabled: bool):
        schedule = self.repo.get_by_name(name)
        schedule.enabled = enabled

        self.repo.save(schedule)
        self.scheduler.enable(name, enabled)

    def delete(self, name: str):
        self.repo.delete(name)
        self.scheduler.delete(name)

    def rebuild_all(self):
        schedules = self.repo.list_all()
        for s in schedules:
            self.scheduler.upsert(s)
