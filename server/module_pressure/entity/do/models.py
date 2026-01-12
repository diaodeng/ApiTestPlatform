from sqlalchemy import (
    Column, Integer, String, DateTime, Enum, JSON, ForeignKey,
)
from sqlalchemy.sql import func
from datetime import datetime

from common.common_do import BaseModel
from module_pressure.enums import PressureRunStatus


class PressureRun(BaseModel):
    __tablename__ = "pressure_run"

    project_id = Column(Integer, nullable=False)
    scenario_id = Column(Integer, nullable=False)

    user_count = Column(Integer)
    spawn_rate = Column(Integer)

    status = Column(Enum(PressureRunStatus), nullable=False)

    error_message = Column(String(1024))

    start_at = Column(DateTime)
    end_at = Column(DateTime)


class PressureScenario(BaseModel):
    __tablename__ = "pressure_scenario"

    name = Column(String)
    engine = Column(String)
    dsl = Column(JSON)


class PressureWorkflow(BaseModel):
    __tablename__ = "pressure_workflow"

    name = Column(String)
    dsl = Column(JSON)


class PressureRun(BaseModel):
    __tablename__ = "pressure_run"

    workflow_id = Column(Integer)
    status = Column(String)
    master_port = Column(Integer)
