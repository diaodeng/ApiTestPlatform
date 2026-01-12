from pydantic import BaseModel
from typing import List, Optional

class Cron(BaseModel):
    minute: str = "*"
    hour: str = "*"
    day_of_week: str = "*"
    day_of_month: str = "*"
    month_of_year: str = "*"

class ScheduleCreate(BaseModel):
    name: str
    task: str
    cron: Cron
    args: Optional[List] = []
    enabled: bool = True
    type: str = ""
