"""资源采集服务配置数据访问层，只承担 ORM 查询与持久化。"""

from datetime import datetime

from sqlalchemy.orm import Session

from modules.metrics.entity.do.metrics_do import MetricsCollectorProfile


class MetricsCollectorDao:
    """采集服务配置 DAO。"""

    @classmethod
    def list_profiles(cls, db: Session) -> list[MetricsCollectorProfile]:
        """查询全部采集服务，按创建时间倒序。"""
        return db.query(MetricsCollectorProfile).order_by(MetricsCollectorProfile.profile_id.desc()).all()

    @classmethod
    def get_profile(cls, db: Session, profile_id: int) -> MetricsCollectorProfile | None:
        """按主键查询单个采集服务。"""
        return db.query(MetricsCollectorProfile).filter(MetricsCollectorProfile.profile_id == profile_id).first()

    @classmethod
    def add_profile(cls, db: Session, values: dict) -> MetricsCollectorProfile:
        """新增采集服务并返回带主键的 ORM 实体。"""
        row = MetricsCollectorProfile(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def update_profile(cls, db: Session, profile_id: int, values: dict) -> bool:
        """按主键更新采集服务字段，返回是否命中行。"""
        values = {**values, "update_time": datetime.now()}
        return db.query(MetricsCollectorProfile).filter(MetricsCollectorProfile.profile_id == profile_id).update(values) == 1

    @classmethod
    def delete_profile(cls, db: Session, profile_id: int) -> bool:
        """按主键删除采集服务，返回是否命中行。"""
        return db.query(MetricsCollectorProfile).filter(MetricsCollectorProfile.profile_id == profile_id).delete() == 1

    @classmethod
    def count_profiles(cls, db: Session) -> int:
        """统计采集服务总数。"""
        return db.query(MetricsCollectorProfile).count()
