from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.vo.common_vo import CrudResponseModel
from modules.ticket.dao.ticket_version_dao import TicketVersionDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketVersion, TicketVersionRelease
from modules.ticket.entity.model.ticket_version_model import TicketVersionListItem
from modules.ticket.entity.vo.ticket_version_vo import (
    TicketVersionCreateModel,
    TicketVersionListItemResponseModel,
    TicketVersionOptionResponseModel,
    TicketVersionQueryModel,
    TicketVersionReleaseCreateModel,
    TicketVersionReleaseResponseModel,
    TicketVersionReleaseUpdateModel,
    TicketVersionUpdateModel,
)
from modules.ticket.util.ticket_common_util import normalize_ticket_version_key
from utils.common_util import CamelCaseUtil
from utils.page_util import PageResponseModel


def _user_name(current_user: CurrentUserModel | None) -> str:
    """读取当前操作人名称。"""
    return str(getattr(getattr(current_user, "user", None), "user_name", "") or "system")


class TicketVersionService:
    """项目版本中心业务服务，维护版本主数据、发布事实和工单版本关联。"""

    VERSION_ID_FIELDS = {
        "affected": "affected_version_id",
        "planned_fix": "planned_fix_version_id",
        "fixed": "fixed_version_id",
        "released": "released_version_id",
    }

    @classmethod
    def list_version_services(cls, db: Session, query: TicketVersionQueryModel):
        """查询项目版本列表，并返回最近发布摘要。"""
        version_query = TicketVersionDao.build_version_query(db, query)

        def build_item(version: TicketVersion) -> TicketVersionListItem:
            releases = TicketVersionDao.list_releases(db, version.version_id)
            return TicketVersionListItem(version=version, releases=tuple(releases))

        def build_response(item: TicketVersionListItem) -> TicketVersionListItemResponseModel:
            latest_release = item.releases[0] if item.releases else None
            return TicketVersionListItemResponseModel(
                version_id=item.version.version_id,
                project_id=item.version.project_id,
                project_name=item.version.project_name,
                version_key=item.version.version_key,
                version_name=item.version.version_name,
                lifecycle_status=item.version.lifecycle_status,
                planned_release_at=item.version.planned_release_at,
                default_branch=item.version.default_branch or "",
                enabled=item.version.enabled,
                remark=item.version.remark,
                source=item.version.source,
                release_count=len(item.releases),
                latest_release=(
                    TicketVersionReleaseResponseModel.model_validate(latest_release) if latest_release else None
                ),
            )

        if query.is_page:
            total = version_query.count()
            versions = version_query.offset((query.page_num - 1) * query.page_size).limit(query.page_size).all()
            rows = [build_response(build_item(version)) for version in versions]
            return PageResponseModel(
                rows=rows,
                page_num=query.page_num,
                page_size=query.page_size,
                total=total,
                has_next=total > query.page_num * query.page_size,
            )
        return [build_response(build_item(version)) for version in version_query.all()]

    @classmethod
    def list_version_options(
        cls, db: Session, project_id: int, include_discovered: bool = True
    ) -> list[TicketVersionOptionResponseModel]:
        """返回项目可选版本，待确认版本会保留状态供界面标识。"""
        query = db.query(TicketVersion).filter(
            TicketVersion.project_id == project_id,
            TicketVersion.enabled.is_(True),
        )
        if not include_discovered:
            query = query.filter(TicketVersion.lifecycle_status == "confirmed")
        versions = query.order_by(TicketVersion.planned_release_at.desc(), TicketVersion.version_key.desc()).all()
        return [
            TicketVersionOptionResponseModel(
                version_id=version.version_id,
                version_key=version.version_key,
                version_name=version.version_name or version.version_key,
                lifecycle_status=version.lifecycle_status,
                default_branch=version.default_branch or "",
            )
            for version in versions
        ]

    @classmethod
    def create_version(
        cls, db: Session, payload: TicketVersionCreateModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """人工创建项目版本，防止同项目重复维护同一版本。"""
        version_key = normalize_ticket_version_key(payload.version_key)
        if not version_key:
            return CrudResponseModel(is_success=False, message="版本标识无效")
        if TicketVersionDao.get_version_by_project_and_key(db, payload.project_id, version_key):
            return CrudResponseModel(is_success=False, message="该项目版本已存在")
        project_name = cls.resolve_project_name(db, payload.project_id, payload.project_name)
        if not project_name:
            return CrudResponseModel(is_success=False, message="所属项目不存在")
        now = datetime.now()
        try:
            version = TicketVersionDao.add_version(
                db,
                TicketVersion(
                    project_id=payload.project_id,
                    project_name=project_name,
                    version_key=version_key,
                    version_name=payload.version_name or version_key,
                    lifecycle_status=payload.lifecycle_status or "confirmed",
                    source="manual",
                    raw_version=version_key,
                    planned_release_at=payload.planned_release_at,
                    default_branch=payload.default_branch,
                    enabled=payload.enabled,
                    remark=payload.remark,
                    create_by=_user_name(current_user),
                    update_by=_user_name(current_user),
                    create_time=now,
                    update_time=now,
                ),
            )
            db.commit()
            return CrudResponseModel(
                is_success=True, message="版本创建成功", result=CamelCaseUtil.transform_result(version)
            )
        except Exception:
            db.rollback()
            raise

    @classmethod
    def update_version(
        cls, db: Session, payload: TicketVersionUpdateModel, current_user: CurrentUserModel
    ) -> CrudResponseModel:
        """更新版本展示、状态和计划信息，版本标识不可跨项目迁移。"""
        version = TicketVersionDao.get_version_by_id(db, payload.version_id)
        if not version:
            return CrudResponseModel(is_success=False, message="版本不存在")
        version_key = normalize_ticket_version_key(payload.version_key)
        if not version_key:
            return CrudResponseModel(is_success=False, message="版本标识无效")
        if payload.project_id != version.project_id or version_key != version.version_key:
            return CrudResponseModel(
                is_success=False, message="已创建版本不允许修改项目或版本标识，请新建版本后重新关联"
            )
        duplicate = TicketVersionDao.get_version_by_project_and_key(db, payload.project_id, version_key)
        if duplicate and duplicate.version_id != version.version_id:
            return CrudResponseModel(is_success=False, message="该项目版本已存在")
        project_name = cls.resolve_project_name(db, payload.project_id, payload.project_name)
        if not project_name:
            return CrudResponseModel(is_success=False, message="所属项目不存在")
        data = payload.model_dump(by_alias=False)
        data.update(
            {
                "project_name": project_name,
                "version_key": version_key,
                "version_name": payload.version_name or version_key,
                "update_by": _user_name(current_user),
                "update_time": datetime.now(),
            }
        )
        data.pop("version_id", None)
        try:
            TicketVersionDao.update_version(db, version.version_id, data)
            db.commit()
            return CrudResponseModel(is_success=True, message="版本更新成功")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def save_release(
        cls,
        db: Session,
        payload: TicketVersionReleaseCreateModel | TicketVersionReleaseUpdateModel,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """新增或更新版本发布事实，不在此动作中自动关闭工单。"""
        version = TicketVersionDao.get_version_by_id(db, payload.version_id)
        if not version:
            return CrudResponseModel(is_success=False, message="版本不存在")
        now = datetime.now()
        data = payload.model_dump(by_alias=False)
        data["environment"] = str(data.get("environment") or "production").strip() or "production"
        data["batch_no"] = str(data.get("batch_no") or "default").strip() or "default"
        data["release_status"] = str(data.get("release_status") or "planned").strip() or "planned"
        if data["release_status"] not in {"planned", "released", "rolled_back"}:
            return CrudResponseModel(is_success=False, message="发布状态无效")
        if data["release_status"] == "released" and not data.get("released_at"):
            data["released_at"] = now
        if data["release_status"] == "rolled_back" and not data.get("rollback_at"):
            data["rollback_at"] = now
        data["release_by"] = _user_name(current_user)
        data["update_by"] = _user_name(current_user)
        data["update_time"] = now
        try:
            release_id = data.pop("release_id", None)
            if release_id:
                release = TicketVersionDao.get_release_by_id(db, release_id)
                if not release:
                    return CrudResponseModel(is_success=False, message="发布记录不存在")
                TicketVersionDao.update_release(db, release_id, data)
                message = "发布记录更新成功"
            else:
                data["create_by"] = _user_name(current_user)
                data["create_time"] = now
                TicketVersionDao.add_release(db, TicketVersionRelease(**data))
                message = "发布记录创建成功"
            db.commit()
            return CrudResponseModel(is_success=True, message=message)
        except Exception:
            db.rollback()
            raise

    @classmethod
    def list_release_services(cls, db: Session, version_id: int) -> list[TicketVersionReleaseResponseModel]:
        """查询一个版本的发布历史。"""
        return [
            TicketVersionReleaseResponseModel.model_validate(release)
            for release in TicketVersionDao.list_releases(db, version_id)
        ]

    @classmethod
    def resolve_project_name(cls, db: Session, project_id: int, fallback: str = "") -> str:
        """获取项目名称，避免版本中心保存失效项目。"""
        fallback_name = str(fallback or "").strip()
        if fallback_name:
            return fallback_name
        project = db.query(HrmProject).filter(HrmProject.project_id == project_id, HrmProject.del_flag == "0").first()
        return str(project.project_name if project else "").strip()

    @classmethod
    def resolve_or_create_candidate(
        cls,
        db: Session,
        *,
        project_id: int | None,
        project_name: str = "",
        version_key: str | None,
        source: str,
        ticket_id: int | None = None,
    ) -> TicketVersion | None:
        """解析版本中心记录；不存在时创建待确认候选版本。"""
        normalized_key = normalize_ticket_version_key(version_key)
        if not project_id or not normalized_key:
            return None
        existing = TicketVersionDao.get_version_by_project_and_key(db, project_id, normalized_key)
        if existing:
            return existing
        now = datetime.now()
        return TicketVersionDao.add_version(
            db,
            TicketVersion(
                project_id=project_id,
                project_name=cls.resolve_project_name(db, project_id, project_name),
                version_key=normalized_key,
                version_name=normalized_key,
                lifecycle_status="discovered",
                source=source,
                raw_version=str(version_key or "").strip(),
                first_ticket_id=ticket_id,
                first_detected_at=now,
                enabled=True,
                create_by="system",
                update_by="system",
                create_time=now,
                update_time=now,
            ),
        )

    @classmethod
    def assign_detected_ticket_version(
        cls,
        db: Session,
        ticket: Ticket,
        *,
        version_type: str,
        version_key: str | None,
        source: str,
    ) -> TicketVersion | None:
        """将输入边界识别到的版本文本解析为版本中心ID，不在工单保存版本文本。"""
        version_id_field = cls.VERSION_ID_FIELDS.get(version_type)
        if not version_id_field:
            raise ValueError(f"不支持的工单版本类型：{version_type}")
        version = cls.resolve_or_create_candidate(
            db,
            project_id=ticket.project_id,
            project_name=ticket.merchant_name,
            version_key=version_key,
            source=source,
            ticket_id=ticket.ticket_id,
        )
        if version:
            setattr(ticket, version_id_field, version.version_id)
        return version

    @classmethod
    def validate_ticket_version_ids(cls, db: Session, ticket: Ticket) -> None:
        """校验工单已关联版本均属于当前项目，避免跨项目版本污染。"""
        if not ticket.project_id:
            return
        for version_id_field in cls.VERSION_ID_FIELDS.values():
            existing_id = getattr(ticket, version_id_field, None)
            version = TicketVersionDao.get_version_by_id(db, existing_id) if existing_id else None
            if not version:
                setattr(ticket, version_id_field, None)
            elif version.project_id != ticket.project_id:
                raise ValueError(f"版本[{version.version_key}]不属于当前项目")

    @classmethod
    def attach_ticket_version_labels(cls, db: Session, items: list[dict[str, Any]]) -> None:
        """为接口返回补充版本展示名称，展示值不落库也不参与关联。"""
        version_ids: set[int] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            for field in cls.VERSION_ID_FIELDS.values():
                parts = field.split("_")
                camel_field = parts[0] + "".join(part.title() for part in parts[1:])
                version_id = item.get(field) or item.get(camel_field)
                if version_id:
                    version_ids.add(int(version_id))
        if not version_ids:
            return
        versions = db.query(TicketVersion).filter(TicketVersion.version_id.in_(version_ids)).all()
        version_map = {version.version_id: version for version in versions}
        response_fields = {
            "affected_version_id": ("affectedVersionId", "affectedVersion"),
            "planned_fix_version_id": ("plannedFixVersionId", "plannedFixVersion"),
            "fixed_version_id": ("fixedVersionId", "fixedVersion"),
            "released_version_id": ("releasedVersionId", "releasedVersion"),
        }
        for item in items:
            if not isinstance(item, dict):
                continue
            for id_field, (camel_id_field, response_field) in response_fields.items():
                raw_version_id = item.get(id_field) or item.get(camel_id_field)
                version_id = int(raw_version_id) if raw_version_id else None
                version = version_map.get(version_id)
                if version_id:
                    item[camel_id_field] = str(version_id)
                item[response_field] = version.version_name if version else ""
            affected_raw_id = item.get("affected_version_id") or item.get("affectedVersionId")
            affected_version = version_map.get(int(affected_raw_id)) if affected_raw_id else None
            item["versionKey"] = affected_version.version_key if affected_version else ""

    @classmethod
    def get_version_name_map(cls, db: Session, version_ids: set[int]) -> dict[int, str]:
        """批量读取版本展示名称，供统计和只读接口按 ID 组装文案。"""
        if not version_ids:
            return {}
        return {
            version.version_id: version.version_name or version.version_key
            for version in db.query(TicketVersion).filter(TicketVersion.version_id.in_(version_ids)).all()
        }
