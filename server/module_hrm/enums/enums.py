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


class FuncTypeEnum(Enum):
    """
    方法类型
    """
    basic = 1  # 基础方法
    custom = 2  # 封装方法

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
    deleted = 3


class CaseStatusEnum(Enum):
    disabled = 1
    normal = 2
    skipped = 4
    xfailed = 8
    xpassed = 16


class TstepTypeEnum(Enum):
    """
    测试步骤的类型
    """
    http = 1
    websocket = 2
    webui = 3
    folder = 4


class RunTypeEnum(Enum):
    """
    执行的数据类型
    """
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
    """
    用例参数化的数据来源
    """
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

class AgentResponseEnum(Enum):
    SUCCESS = 200                   # 转发操作成功完成
    FAILURE = 400                   # 转发操作失败
    OPERATION_TIMEOUT = 407         # 异步操作未在预定时间内完成，导致超时
    CONNECTION_TIMEOUT = 408        # 在尝试建立连接时超过了预定的时间限制，连接未能成功建立
    TRANSFER_TIMEOUT = 409          # 在数据传输过程中超过了预定的时间限制，数据未能完全传输到目标地址
    CONNECTION_EXCEPTION = 410      # 在建立连接或维持连接过程中出现了异常，如网络错误、协议不匹配等
    TASK_CANCELLED = 418            # 任务被取消
    UNKNOWN_EXCEPTION = 500         # 发生了未预期的异常
    WEBSOCKET_NOT_CONNECTED = 5008  # WebSocket 连接尚未建立或已断开，无法进行通信


class ScopeEnum(Enum):
    """
    数据的作用范围
    """
    globals = 1
    project = 2
    module = 4
    case = 8


class AssertOriginalEnum(Enum):
    """
    断言实际值取值方式
    """
    expression: int = 1  # 表达式
    original: int = 2  # 原始值



class CodeTypeEnum(Enum):
    """
    将要执行的代码的类型
    """
    python = 1
    js = 2


class ConfigDataTypeEnum(Enum):
    """
    配置的数据类型
    """
    string = "string"
    int = "int"
    boolean = "boolean"
    float = "float"
    json = "json"
    any = "any"


if __name__ == "__main__":

    eval("print")