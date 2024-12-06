from enum import Enum

class RequestTypeEnum(Enum):
    http = 1
    websocket = 2
    webui = 3
    folder = 4

# 根据枚举值获取枚举名称
def get_enum_name(enum_class, enum_value):
    try:
        # 通过枚举的值获取枚举成员
        enum_member = enum_class(enum_value)
        # 返回枚举成员的名称
        return enum_member.name
    except ValueError:
        # 如果值不在枚举中，捕获异常并处理
        return None

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

