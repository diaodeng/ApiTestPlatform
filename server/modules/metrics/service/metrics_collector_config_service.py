"""资源采集服务配置管理：CRUD、业务校验、推送状态回写。

只做配置这一件事；采集线程的运行管理在 metrics_collector_runtime_service 中。
"""

from dataclasses import dataclass
from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from modules.metrics.dao.metrics_collector_dao import MetricsCollectorDao
from modules.metrics.entity.do.metrics_do import MetricsCollectorProfile
from modules.metrics.entity.vo.metrics_vo import MetricsCollectorSaveModel
from modules.metrics.util.metrics_secret_util import decrypt_password, encrypt_password


@dataclass
class ServiceResult:
    """采集服务操作的统一结果，供控制器转换为 HTTP 响应。"""

    is_success: bool
    message: str
    result: dict | None = None


class MetricsCollectorConfigService:
    """采集服务配置业务编排。"""

    @classmethod
    def to_response(cls, row: MetricsCollectorProfile) -> dict:
        """把 ORM 实体转换为对外响应 dict，密码只返回是否已设置的标记。"""
        return {
            "profileId": row.profile_id,
            "profileName": row.profile_name,
            "enabled": bool(row.enabled),
            "pushUrl": row.push_url,
            "authUser": row.auth_user,
            "authPasswordSet": bool(row.auth_password_cipher),
            "jobLabel": row.job_label,
            "instanceLabel": row.instance_label,
            "machineLabel": row.machine_label,
            "intervalSeconds": row.interval_seconds,
            "batchSize": row.batch_size,
            "timeoutSeconds": row.timeout_seconds,
            "extendedEnabled": bool(row.extended_enabled),
            "revision": row.revision,
            "lastPushTime": row.last_push_time,
            "lastPushStatus": row.last_push_status,
            "lastPushMessage": row.last_push_message,
            "pushFailureCount": row.push_failure_count,
            "remark": row.remark,
            "createTime": row.create_time,
            "updateTime": row.update_time,
        }

    @classmethod
    def list_collectors(cls, db: Session) -> list[dict]:
        """查询全部采集服务配置（数量有限，不做分页）。"""
        return [cls.to_response(row) for row in MetricsCollectorDao.list_profiles(db)]

    @classmethod
    def get_collector(cls, db: Session, profile_id: int) -> dict | None:
        """查询单个采集服务配置。"""
        row = MetricsCollectorDao.get_profile(db, profile_id)
        return cls.to_response(row) if row else None

    @classmethod
    def create_collector(cls, db: Session, model: MetricsCollectorSaveModel, operator: str) -> ServiceResult:
        """新增采集服务，密码明文加密后落库。"""
        name = model.profile_name.strip()
        if not name:
            return ServiceResult(False, "采集服务名称不能为空")
        for row in MetricsCollectorDao.list_profiles(db):
            if row.profile_name == name:
                return ServiceResult(False, f"采集服务名称已存在: {name}")
        values = {
            "profile_name": name,
            "enabled": model.enabled,
            "push_url": model.push_url.strip(),
            "auth_user": model.auth_user.strip(),
            "auth_password_cipher": encrypt_password(model.auth_password) if model.auth_password else "",
            "job_label": model.job_label.strip() or "QTR",
            "instance_label": model.instance_label.strip() or "TEST_ENV",
            "machine_label": model.machine_label.strip(),
            "interval_seconds": model.interval_seconds,
            "batch_size": model.batch_size,
            "timeout_seconds": model.timeout_seconds,
            "extended_enabled": model.extended_enabled,
            "revision": 1,
            "create_by": operator,
            "update_by": operator,
            "remark": model.remark or "",
        }
        row = MetricsCollectorDao.add_profile(db, values)
        db.commit()
        logger.info(f"新增采集服务: id={row.profile_id}, name={name}, enabled={model.enabled}, operator={operator}")
        return ServiceResult(True, "新增成功", {"profileId": row.profile_id})

    @classmethod
    def update_collector(cls, db: Session, profile_id: int, model: MetricsCollectorSaveModel, operator: str) -> ServiceResult:
        """修改采集服务；revision 自增触发采集线程热生效，未填密码时保留旧密码。"""
        row = MetricsCollectorDao.get_profile(db, profile_id)
        if not row:
            return ServiceResult(False, "采集服务不存在")
        name = model.profile_name.strip()
        if not name:
            return ServiceResult(False, "采集服务名称不能为空")
        for other in MetricsCollectorDao.list_profiles(db):
            if other.profile_id != profile_id and other.profile_name == name:
                return ServiceResult(False, f"采集服务名称已存在: {name}")
        values = {
            "profile_name": name,
            "enabled": model.enabled,
            "push_url": model.push_url.strip(),
            "auth_user": model.auth_user.strip(),
            "job_label": model.job_label.strip() or "QTR",
            "instance_label": model.instance_label.strip() or "TEST_ENV",
            "machine_label": model.machine_label.strip(),
            "interval_seconds": model.interval_seconds,
            "batch_size": model.batch_size,
            "timeout_seconds": model.timeout_seconds,
            "extended_enabled": model.extended_enabled,
            "revision": row.revision + 1,
            "update_by": operator,
            "remark": model.remark or "",
        }
        if model.auth_password:
            values["auth_password_cipher"] = encrypt_password(model.auth_password)
        MetricsCollectorDao.update_profile(db, profile_id, values)
        db.commit()
        logger.info(
            f"修改采集服务: id={profile_id}, name={name}, enabled={model.enabled}, "
            f"password_changed={bool(model.auth_password)}, operator={operator}"
        )
        return ServiceResult(True, "修改成功")

    @classmethod
    def update_collector_status(cls, db: Session, profile_id: int, enabled: bool, operator: str) -> ServiceResult:
        """启停采集服务；仅切换 enabled 并自增 revision，其他配置保持不变。"""
        row = MetricsCollectorDao.get_profile(db, profile_id)
        if not row:
            return ServiceResult(False, "采集服务不存在")
        if bool(row.enabled) == enabled:
            return ServiceResult(True, "状态未变化")
        MetricsCollectorDao.update_profile(
            db,
            profile_id,
            {"enabled": enabled, "revision": row.revision + 1, "update_by": operator},
        )
        db.commit()
        logger.info(f"切换采集服务状态: id={profile_id}, name={row.profile_name}, enabled={enabled}, operator={operator}")
        return ServiceResult(True, "启停成功" if enabled else "停止成功")

    @classmethod
    def delete_collector(cls, db: Session, profile_id: int, operator: str) -> ServiceResult:
        """删除采集服务；运行中的线程会因配置消失在下一轮轮询中自动停止。"""
        row = MetricsCollectorDao.get_profile(db, profile_id)
        if not row:
            return ServiceResult(False, "采集服务不存在")
        MetricsCollectorDao.delete_profile(db, profile_id)
        db.commit()
        logger.info(f"删除采集服务: id={profile_id}, name={row.profile_name}, operator={operator}")
        return ServiceResult(True, "删除成功")

    @classmethod
    def record_push_result(
        cls,
        db: Session,
        profile_id: int,
        success: bool,
        message: str = "",
    ) -> None:
        """回写推送结果状态，供列表页展示最近推送情况。

        由采集线程在独立会话中调用，任何异常只记日志，绝不影响采集循环。
        """
        try:
            values = {
                "last_push_time": datetime.now(),
                "last_push_status": "success" if success else "failed",
                "last_push_message": (message or "")[:500],
            }
            if not success:
                row = MetricsCollectorDao.get_profile(db, profile_id)
                values["push_failure_count"] = (row.push_failure_count if row else 0) + 1
            MetricsCollectorDao.update_profile(db, profile_id, values)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"回写采集推送状态失败: profileId={profile_id}, error={exc}")

    @classmethod
    def load_push_profiles(cls, db: Session) -> list[MetricsCollectorProfile]:
        """加载采集线程需要的启用配置（含解密后的认证信息），供运行时轮询。"""
        profiles: list[MetricsCollectorProfile] = []
        for row in MetricsCollectorDao.list_profiles(db):
            if not row.enabled:
                continue
            if not row.push_url:
                continue
            profiles.append(row)
        return profiles

    @classmethod
    def decrypt_profile_password(cls, row: MetricsCollectorProfile) -> str:
        """解密指定配置的认证密码，供采集线程推送时使用。"""
        return decrypt_password(row.auth_password_cipher)
