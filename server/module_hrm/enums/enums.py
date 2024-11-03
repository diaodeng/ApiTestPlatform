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
    run_detail = 14
    api_http = 15
    api_websocket = 16


class CaseRunStatus(Enum):
    passed = 1
    failed = 2
    skipped = 3
    deselected = 4
    xfailed = 5
    xpassed = 6
    warnings = 7
    error = 8


class QtrDataStatusEnum(Enum):
    """
    这里的值应该和CaseStatusEnum对应的值保持一致
    """
    disabled = 1
    normal = 2


class CaseStatusEnum(Enum):
    disabled = 1
    normal = 2
    skipped = 4
    xfailed = 8
    xpassed = 16


class TstepTypeEnum(Enum):
    http = 1
    websocket = 2
    webui = 3
    folder = 4


class RunTypeEnum(Enum):
    case = 1
    model = 2
    suite = 4
    project = 8
    api = 16
    case_debug = 32


class RunModelEnum(Enum):
    manual = 1  # 手动执行
    task = 2  # 定时任务执行


class ParameterTypeEnum(Enum):
    file = 1
    sql = 2
    local_table = 3
    local_source = 4


class TaskStatusEnum(Enum):

    running = 1  # 提交执行，开始执行
    max_instances = 2  # 达到限制最大实例数
    success = 3  # 执行成功
    error = 4  # 任务执行异常
    missed = 5  # 错过执行时间
    stop = 6  # 停止状态，未开始执行


class ForwardRulesEnum(Enum):
    disabled = 1
    normal = 2


class DelFlagEnum(Enum):
    delete = 2
    normal = 1


class ForwardRuleMatchTypeEnum(Enum):
    url_equal = 1
    url_not_equal = 2
    url_contain = 4
    host_equal = 8
    host_not_equal = 16
    host_contain = 32
    path_equal = 64
    path_not_equal = 128
    path_contain = 256
