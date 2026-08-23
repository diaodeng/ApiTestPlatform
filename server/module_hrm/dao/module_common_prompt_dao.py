from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from module_hrm.entity.do.module_common_prompt_do import HrmModuleCommonPrompt
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.vo.module_common_prompt_vo import ModuleCommonPromptPageQueryModel
from module_hrm.enums.enums import QtrDataStatusEnum


class ModuleCommonPromptDao:
    """
    模块通用提示词数据访问层，只负责查询和持久化。
    """

    @classmethod
    def get_by_id(cls, db: Session, prompt_id: int):
        """查询有效的模块通用提示词。"""
        return (
            db.query(HrmModuleCommonPrompt)
            .filter(
                HrmModuleCommonPrompt.prompt_id == prompt_id,
                HrmModuleCommonPrompt.del_flag == "0",
            )
            .first()
        )

    @classmethod
    def get_by_code(cls, db: Session, module_code: str, *, enabled_only: bool = False, include_deleted: bool = False):
        """按模块编码查询提示词。"""
        query = db.query(HrmModuleCommonPrompt).filter(HrmModuleCommonPrompt.module_code == module_code)
        if not include_deleted:
            query = query.filter(HrmModuleCommonPrompt.del_flag == "0")
        if enabled_only:
            query = query.filter(HrmModuleCommonPrompt.enabled.is_(True))
        return query.first()

    @classmethod
    def get_page(cls, db: Session, query_object: ModuleCommonPromptPageQueryModel):
        """分页查询模块通用提示词。"""
        query = db.query(HrmModuleCommonPrompt).filter(HrmModuleCommonPrompt.del_flag == "0")
        if query_object.keyword:
            keyword = f"%{query_object.keyword}%"
            query = query.filter(
                HrmModuleCommonPrompt.module_code.like(keyword)
                | HrmModuleCommonPrompt.prompt_content.like(keyword)
                | HrmModuleCommonPrompt.remark.like(keyword)
            )
        if query_object.module_code:
            query = query.filter(HrmModuleCommonPrompt.module_code == query_object.module_code)
        if query_object.enabled is not None:
            query = query.filter(HrmModuleCommonPrompt.enabled == bool(query_object.enabled))
        query = query.order_by(HrmModuleCommonPrompt.update_time.desc(), HrmModuleCommonPrompt.prompt_id.desc())
        total = query.count()
        rows = query.offset((query_object.page_num - 1) * query_object.page_size).limit(query_object.page_size).all()
        return {
            "rows": rows,
            "page_num": query_object.page_num,
            "page_size": query_object.page_size,
            "total": total,
            "has_next": total > query_object.page_num * query_object.page_size,
        }

    @classmethod
    def get_options(cls, db: Session, *, keyword: str | None = None):
        """查询当前有效模块编码及其关联数量。"""
        query = (
            db.query(
                HrmModule.module_code.label("module_code"),
                func.count(HrmModule.module_id).label("module_count"),
                func.count(distinct(HrmModule.project_id)).label("project_count"),
            )
            .filter(HrmModule.module_code.isnot(None), HrmModule.module_code != "", HrmModule.status == QtrDataStatusEnum.normal.value)
            .group_by(HrmModule.module_code)
            .order_by(HrmModule.module_code.asc())
        )
        if keyword:
            query = query.filter(HrmModule.module_code.like(f"%{keyword}%"))
        return query.all()

    @classmethod
    def get_module_counts(cls, db: Session, module_code: str) -> tuple[int, int]:
        """统计编码对应的有效模块数和项目数。"""
        row = (
            db.query(
                func.count(HrmModule.module_id),
                func.count(distinct(HrmModule.project_id)),
            )
            .filter(HrmModule.module_code == module_code, HrmModule.status == QtrDataStatusEnum.normal.value)
            .one()
        )
        return int(row[0] or 0), int(row[1] or 0)

    @classmethod
    def add(cls, db: Session, data: dict):
        """新增模块通用提示词。"""
        entity = HrmModuleCommonPrompt(**data)
        db.add(entity)
        db.flush()
        return entity

    @classmethod
    def update(cls, db: Session, prompt_id: int, data: dict) -> int:
        """更新模块通用提示词。"""
        return (
            db.query(HrmModuleCommonPrompt)
            .filter(HrmModuleCommonPrompt.prompt_id == prompt_id, HrmModuleCommonPrompt.del_flag == "0")
            .update(data)
        )

    @classmethod
    def soft_delete(cls, db: Session, prompt_id: int, data: dict) -> int:
        """逻辑删除模块通用提示词。"""
        return (
            db.query(HrmModuleCommonPrompt)
            .filter(HrmModuleCommonPrompt.prompt_id == prompt_id, HrmModuleCommonPrompt.del_flag == "0")
            .update({"del_flag": "2", **data})
        )
