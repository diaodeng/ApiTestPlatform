from sqlalchemy import or_
from sqlalchemy.orm import Session

from modules.ticket.entity.do.ticket_do import TicketVersion, TicketVersionRelease
from modules.ticket.entity.vo.ticket_version_vo import TicketVersionQueryModel


class TicketVersionDao:
    """项目版本中心的数据访问。"""

    @classmethod
    def get_version_by_id(cls, db: Session, version_id: int) -> TicketVersion | None:
        """按主键查询版本。"""
        return db.query(TicketVersion).filter(TicketVersion.version_id == version_id).first()

    @classmethod
    def get_version_by_project_and_key(cls, db: Session, project_id: int, version_key: str) -> TicketVersion | None:
        """按项目和规范化版本标识查询版本。"""
        return (
            db.query(TicketVersion)
            .filter(TicketVersion.project_id == project_id, TicketVersion.version_key == version_key)
            .first()
        )

    @classmethod
    def build_version_query(cls, db: Session, query: TicketVersionQueryModel):
        """构建项目版本查询，保持 ORM 实体供服务层完成业务编排。"""
        keyword = str(query.keyword or "").strip()
        version_query = (
            db.query(TicketVersion)
            .filter(
                TicketVersion.project_id == query.project_id if query.project_id else True,
                TicketVersion.lifecycle_status == query.lifecycle_status if query.lifecycle_status else True,
                TicketVersion.enabled == query.enabled if query.enabled is not None else True,
                or_(
                    TicketVersion.version_key.like(f"%{keyword}%"),
                    TicketVersion.version_name.like(f"%{keyword}%"),
                    TicketVersion.project_name.like(f"%{keyword}%"),
                )
                if keyword
                else True,
            )
            .order_by(
                TicketVersion.project_id.asc(),
                TicketVersion.lifecycle_status.asc(),
                TicketVersion.planned_release_at.desc(),
                TicketVersion.version_key.desc(),
            )
        )
        return version_query

    @classmethod
    def add_version(cls, db: Session, version: TicketVersion) -> TicketVersion:
        """新增项目版本。"""
        db.add(version)
        db.flush()
        return version

    @classmethod
    def update_version(cls, db: Session, version_id: int, data: dict) -> None:
        """更新项目版本。"""
        db.query(TicketVersion).filter(TicketVersion.version_id == version_id).update(data)

    @classmethod
    def list_releases(cls, db: Session, version_id: int) -> list[TicketVersionRelease]:
        """按版本查询发布记录。"""
        return (
            db.query(TicketVersionRelease)
            .filter(TicketVersionRelease.version_id == version_id)
            .order_by(TicketVersionRelease.released_at.desc(), TicketVersionRelease.update_time.desc())
            .all()
        )

    @classmethod
    def get_release_by_id(cls, db: Session, release_id: int) -> TicketVersionRelease | None:
        """按主键查询发布记录。"""
        return db.query(TicketVersionRelease).filter(TicketVersionRelease.release_id == release_id).first()

    @classmethod
    def add_release(cls, db: Session, release: TicketVersionRelease) -> TicketVersionRelease:
        """新增发布记录。"""
        db.add(release)
        db.flush()
        return release

    @classmethod
    def update_release(cls, db: Session, release_id: int, data: dict) -> None:
        """更新发布记录。"""
        db.query(TicketVersionRelease).filter(TicketVersionRelease.release_id == release_id).update(data)
