from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogSearchHitModel


def build_ticket_log_search_hit_previews(
    hits: list[TicketLogSearchHitModel], preview_chars: int | None = None
) -> list[TicketLogSearchHitModel]:
    """
    兼容旧调用的搜索结果透传函数，搜索服务已在 rg/Python 路径按配置完成单行限制。
    :param hits: 已完成单行字节限制的日志命中列表
    :param preview_chars: 保留的兼容参数，不再执行固定字符截断
    :return: 原命中列表
    """
    return hits
