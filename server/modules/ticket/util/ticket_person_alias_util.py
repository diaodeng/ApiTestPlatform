"""
外部工单人员字段配对工具。

外部推送（``TicketExternalSyncRequestService``）与多维表格主动拉取
（``TicketBitablePullService``）都会产生"当前处理人"的两套别名：
历史别名 ``ticketAssignee/ticketAssigneeEmail`` 和规范名
``currentAssigneeName/currentAssigneeEmail``。两侧任一为空时必须按本工具的
同一规则互相补齐，避免两处实现漂移导致识别、群推送 @ 解析使用不一致的姓名邮箱。
"""


def _has_value(value) -> bool:
    """判断字段值是否非空（None、空字符串、空列表都视为空）。"""
    return value not in (None, "", [])


def complete_assignee_alias_pair(payload: dict) -> dict:
    """
    按"只有一侧为空时补齐缺失侧，双方都有值时各自保留"的规则补齐当前处理人别名对。

    处理两组字段：
    - 姓名：``ticketAssignee`` <-> ``currentAssigneeName``
    - 邮箱：``ticketAssigneeEmail`` <-> ``currentAssigneeEmail``

    :param payload: 含外部同步人员字段的字典，原地补齐后返回同一字典。
    :return: 传入的字典（便于链式调用）。
    """
    if not isinstance(payload, dict):
        return payload
    if not _has_value(payload.get("currentAssigneeName")) and _has_value(payload.get("ticketAssignee")):
        payload["currentAssigneeName"] = payload.get("ticketAssignee")
    if not _has_value(payload.get("currentAssigneeEmail")) and _has_value(payload.get("ticketAssigneeEmail")):
        payload["currentAssigneeEmail"] = payload.get("ticketAssigneeEmail")
    if not _has_value(payload.get("ticketAssignee")) and _has_value(payload.get("currentAssigneeName")):
        payload["ticketAssignee"] = payload.get("currentAssigneeName")
    if not _has_value(payload.get("ticketAssigneeEmail")) and _has_value(payload.get("currentAssigneeEmail")):
        payload["ticketAssigneeEmail"] = payload.get("currentAssigneeEmail")
    return payload
