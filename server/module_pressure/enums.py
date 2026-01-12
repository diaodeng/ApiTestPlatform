from enum import Enum


class PressureRunStatus(str, Enum):
    INIT = "init"
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELED = "canceled"


class PressureJobStatus(Enum):
    INIT = "init"
    WAIT_RESOURCE = "wait_resource"
    READY = "ready"
    SCHEDULED = "scheduled"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELED = "canceled"
