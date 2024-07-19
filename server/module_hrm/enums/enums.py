from enum import Enum


class PageType(Enum):
    case = 1
    api = 2
    apiTree = 3
    config = 4


class CaseType(Enum):
    case = 1
    config = 2


class ApiType(Enum):
    api = 2
    folder = 1


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
    failed = 'failed'
    passed = 'passed'
    skipped = 'skipped'
    deselected = 'deselected'
    xfailed = 'xfailed'
    xpassed = 'xpassed'
    warnings = 'warnings'
    error = 'error'


class TstepTypeEnum(Enum):
    api = 1
    webui = 2
