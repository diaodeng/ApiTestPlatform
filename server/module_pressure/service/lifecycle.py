# app/pressure/services/lifecycle.py
from module_pressure.events.publisher import publish_event

def update_status(job, new_status):
    job.status = new_status
    save(job)

    publish_event(
        job.id,
        "pressure.status",
        {
            "status": new_status
        }
    )
