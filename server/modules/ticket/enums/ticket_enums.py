from enum import Enum


class TicketStatus(str, Enum):
    """
    工单状态枚举，用于定义默认状态机的状态编码。
    """

    PENDING = "pending"
    PROCESSING = "processing"
    WAIT_USER = "wait_user"
    WAIT_DEV = "wait_dev"
    WAIT_RELEASE = "wait_release"
    WAIT_VERIFY = "wait_verify"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"
    NON_PROBLEM = "non_problem"
    DESIGN_AS_EXPECTED = "design_as_expected"
    USER_MISOPERATION = "user_misoperation"
    DUPLICATED = "duplicated"


class TicketPriority(str, Enum):
    """
    工单优先级枚举，区分对方优先级和内部处理优先级。
    """

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class TicketSeverity(str, Enum):
    """
    工单严重等级枚举，用于描述影响程度。
    """

    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    TRIVIAL = "trivial"


class TicketEventType(str, Enum):
    """
    工单事件类型枚举，用于统一沉淀时间线、排查过程和后续 AI 学习数据。
    """

    TICKET_CREATED = "TICKET_CREATED"
    TICKET_UPDATED = "TICKET_UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNED = "ASSIGNED"
    COMMENTED = "COMMENTED"
    ANALYSIS = "ANALYSIS"
    RCA = "RCA"
    REPRODUCED = "REPRODUCED"
    LOG_ANALYSIS = "LOG_ANALYSIS"
    DB_CHECK = "DB_CHECK"
    FIX_APPLIED = "FIX_APPLIED"
    DEPLOYED = "DEPLOYED"
    VERIFIED = "VERIFIED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    AI_ANALYZED = "AI_ANALYZED"
    AI_RECOMMENDED = "AI_RECOMMENDED"


class EmbeddingObjectType(str, Enum):
    """
    Embedding 对象类型枚举，后续可覆盖工单、知识库、日志摘要等多类内容。
    """

    TICKET = "ticket"
    KNOWLEDGE = "knowledge"
    COMMENT = "comment"
    EVENT = "event"
    LOG_SUMMARY = "log_summary"
