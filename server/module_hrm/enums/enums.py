from enum import Enum


class PageType(Enum):
    case = 1
    api = 2
    apiTree = 3
    config = 4


class DataType(Enum):
    project = 1
    module = 2
    case = 3
    config = 4
    suite = 5
    report = 6
    env = 7
    debugtalk = 8
    task = 9
    api = 10
    folder = 11
    suite_detail = 12
    suite_case_list = 13


class CaseRunStatus(Enum):
    passed = 1
    failed = 2
    skipped = 3
    deselected = 4
    xfailed = 5
    xpassed = 6
    warnings = 7
    error = 8


class TstepTypeEnum(Enum):
    http = 1
    websocket = 2
    webui = 3


class RunType(Enum):
    case = 1
    api = 2
    case_debug = 3
    api_debug = 4


class RunModeEnum(Enum):
    case = 1
    model = 2
    suite = 3
    project = 4
