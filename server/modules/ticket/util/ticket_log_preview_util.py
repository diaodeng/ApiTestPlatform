from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogSearchHitModel

DEFAULT_TICKET_LOG_SEARCH_PREVIEW_CHARS = 500


def build_ticket_log_search_hit_previews(
    hits: list[TicketLogSearchHitModel], preview_chars: int = DEFAULT_TICKET_LOG_SEARCH_PREVIEW_CHARS
) -> list[TicketLogSearchHitModel]:
    """
    构造日志搜索结果的行首预览，降低大日志行的接口传输和前端表格渲染开销。
    :param hits: 完整日志命中列表
    :param preview_chars: 每条命中内容保留的最大字符数
    :return: 保留文件、行号等定位信息的预览命中列表
    """
    normalized_preview_chars = max(int(preview_chars or DEFAULT_TICKET_LOG_SEARCH_PREVIEW_CHARS), 1)
    previews = []
    for hit in hits:
        content = str(hit.content or "")
        content_length = len(content)
        previews.append(
            hit.model_copy(
                update={
                    "content": content[:normalized_preview_chars],
                    "content_length": content_length,
                    "content_truncated": content_length > normalized_preview_chars,
                }
            )
        )
    return previews
