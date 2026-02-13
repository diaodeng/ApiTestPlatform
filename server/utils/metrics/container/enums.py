import enum


class ModeEnum(enum.Enum):
    LINUX = "linux_host"
    WINDOWS = "windows"
    CGROUP_1 = "cgroup_v1"
    CGROUP_2 = "cgroup_v2"