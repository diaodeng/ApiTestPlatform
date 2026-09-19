"""配置任务资源数据访问层，只封装 ORM 查询与持久化。"""

from datetime import datetime

from sqlalchemy.orm import Session

from modules.configuration_task.entity.do.resource_object_do import ResourceObject


class ResourceDao:
    """资源对象 DAO。"""

    @classmethod
    def get_resource(cls, db: Session, resource_id: int) -> ResourceObject | None:
        """按资源 ID 查询资源实体。"""
        return db.query(ResourceObject).filter(ResourceObject.resource_id == resource_id).first()

    @classmethod
    def get_by_identity(cls, db: Session, agent_code: str, object_key: str, version: int) -> ResourceObject | None:
        """按 Agent、受控 key 和版本精确查询资源身份。"""
        return (
            db.query(ResourceObject)
            .filter(
                ResourceObject.agent_code == agent_code,
                ResourceObject.object_key == object_key,
                ResourceObject.version == version,
            )
            .first()
        )

    @classmethod
    def get_visible_resource(
        cls, db: Session, resource_id: int, operator: str | None, is_admin: bool
    ) -> ResourceObject | None:
        """按当前用户范围查询资源；管理员可查看全部资源。"""
        query = db.query(ResourceObject).filter(ResourceObject.resource_id == resource_id)
        if not is_admin:
            query = query.filter(ResourceObject.create_by == (operator or ""))
        return query.first()

    @classmethod
    def list_resources(
        cls,
        db: Session,
        resource_id: int | None = None,
        agent_code: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        operator: str | None = None,
        is_admin: bool = False,
    ) -> list[ResourceObject]:
        """按查询条件和用户范围返回资源实体。"""
        query = db.query(ResourceObject)
        if resource_id is not None:
            query = query.filter(ResourceObject.resource_id == resource_id)
        if agent_code:
            query = query.filter(ResourceObject.agent_code == agent_code)
        if status:
            query = query.filter(ResourceObject.status == status)
        if keyword:
            query = query.filter(ResourceObject.original_file_name.like(f"%{keyword}%"))
        if not is_admin:
            query = query.filter(ResourceObject.create_by == (operator or ""))
        return query.order_by(ResourceObject.resource_id.desc()).limit(limit).all()

    @classmethod
    def add_resource(cls, db: Session, values: dict) -> ResourceObject:
        """新增资源实体并刷新 Snowflake 主键。"""
        row = ResourceObject(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def update_resource(cls, db: Session, resource_id: int, values: dict) -> bool:
        """按资源 ID 更新资源元数据，返回是否命中记录。"""
        values = {**values, "update_time": datetime.now()}
        return db.query(ResourceObject).filter(ResourceObject.resource_id == resource_id).update(values) == 1
