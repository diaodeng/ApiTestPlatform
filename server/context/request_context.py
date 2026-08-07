import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

DEFAULT_REQUEST_ID = "-"

request_id_var = ContextVar("request_id", default=DEFAULT_REQUEST_ID)


def generate_trace_id(prefix: str | None = None) -> str:
    """
    生成日志追踪ID，用于 HTTP 请求、定时任务和后台任务日志串联。

    :param prefix: 可选业务前缀，例如 job、ticket-sync。
    :return: 短追踪ID字符串。
    """
    trace_id = uuid.uuid4().hex[:8]
    normalized_prefix = str(prefix or "").strip()
    return f"{normalized_prefix}-{trace_id}" if normalized_prefix else trace_id


def get_current_trace_id(default: str | None = None) -> str:
    """
    获取当前日志追踪ID。

    :param default: 当前上下文为空时返回的默认值。
    :return: 当前上下文中的追踪ID。
    """
    trace_id = str(request_id_var.get() or "").strip()
    if trace_id and trace_id != DEFAULT_REQUEST_ID:
        return trace_id
    return default if default is not None else DEFAULT_REQUEST_ID


@contextmanager
def trace_context(trace_id: str | None = None, *, prefix: str | None = None) -> Iterator[str]:
    """
    临时设置日志追踪上下文，退出时自动恢复上一个追踪ID。

    :param trace_id: 指定追踪ID；为空时自动生成。
    :param prefix: 自动生成追踪ID时使用的业务前缀。
    :return: 当前生效的追踪ID。
    """
    resolved_trace_id = str(trace_id or "").strip() or generate_trace_id(prefix)
    token = request_id_var.set(resolved_trace_id)
    try:
        yield resolved_trace_id
    finally:
        request_id_var.reset(token)
