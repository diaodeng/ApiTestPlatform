from dataclasses import dataclass

from modules.ticket.entity.do.ticket_do import TicketAiRepoMapping, TicketVersion, TicketVersionRelease


@dataclass(frozen=True)
class TicketVersionListItem:
    """版本列表业务对象，组合版本主数据与对应发布记录。"""

    version: TicketVersion
    releases: tuple[TicketVersionRelease, ...]


@dataclass(frozen=True)
class TicketAiRepoMappingListItem:
    """AI 仓库映射列表业务对象，组合映射实体与版本中心实体。"""

    mapping: TicketAiRepoMapping
    version: TicketVersion | None
