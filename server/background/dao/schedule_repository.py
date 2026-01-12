from background.entity.vo.schedule import ScheduleCreate

class ScheduleRepository:

    def save(self, schedule: ScheduleCreate):
        pass

    def get_by_name(self, name: str) -> ScheduleCreate:
        pass

    def delete(self, name: str):
        pass

    def list_all(self) -> list[ScheduleCreate]:
        pass
