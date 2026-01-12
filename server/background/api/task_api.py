from fastapi import APIRouter, HTTPException
from redbeat import RedBeatSchedulerEntry
from celery.schedules import crontab

from background.entity.vo.schedule import ScheduleCreate
from background.celery_app import celery_app
from background.service.schedule_service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["Schedules"])

@router.post("")
def create_schedule(data: ScheduleCreate):
    """
    参数示例
    POST /schedules
{
  "name": "daily_add_chain",
  "task": "app.tasks.scheduler_tasks.run_add_chain",
  "cron": {
    "hour": "2",
    "minute": "0"
  },
  "args": [5, 6],
  "enabled": true
}

    """
    ScheduleService.create(data)

    """
    from worker.celery_app import app as celery_app

def start_pressure(case_id: int):
    celery_app.send_task(
        "worker.tasks.pressure.run_case",
        args=[case_id],
        queue="pressure",
        routing_key="pressure.run",
    )

    """

    return {"message": "created"}

@router.get("")
def list_schedules():
    entries = RedBeatSchedulerEntry.all(celery_app)
    return [
        {
            "name": e.name,
            "task": e.task,
            "args": e.args,
            "enabled": e.enabled,
            "schedule": str(e.schedule),
        }
        for e in entries
    ]


@router.get("/{name}")
def get_schedule(name: str):
    try:
        entry = RedBeatSchedulerEntry.from_key(f"redbeat:{name}", celery_app)
    except KeyError:
        raise HTTPException(404, "not found")

    return {
        "name": entry.name,
        "task": entry.task,
        "args": entry.args,
        "enabled": entry.enabled,
        "schedule": str(entry.schedule),
    }


@router.put("/{name}")
def update_schedule(name: str, data: ScheduleCreate):
    try:
        entry = RedBeatSchedulerEntry.from_key(f"redbeat:{name}", celery_app)
    except KeyError:
        raise HTTPException(404, "not found")

    entry.task = data.task
    entry.args = data.args
    entry.schedule = crontab(**data.cron.dict())
    entry.enabled = data.enabled
    entry.save()

    return {"message": "updated"}

@router.patch("/{name}/enable")
def enable_schedule(name: str, enabled: bool):
    entry = RedBeatSchedulerEntry.from_key(f"redbeat:{name}", celery_app)
    entry.enabled = enabled
    entry.save()
    return {"enabled": enabled}


@router.delete("/{name}")
def delete_schedule(name: str):
    entry = RedBeatSchedulerEntry.from_key(f"redbeat:{name}", celery_app)
    entry.delete()
    return {"message": "deleted"}

