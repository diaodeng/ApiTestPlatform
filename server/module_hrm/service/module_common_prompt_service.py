from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from module_hrm.dao.module_common_prompt_dao import ModuleCommonPromptDao
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.module_common_prompt_vo import (
    CreateModuleCommonPromptModel,
    ModuleCommonPromptModel,
    ModuleCommonPromptOptionModel,
    ModuleCommonPromptPageQueryModel,
    UpdateModuleCommonPromptModel,
)
from utils.page_util import PageResponseModel
from utils.log_util import logger


class ModuleCommonPromptService:
    """
    模块通用提示词业务服务，负责编码校验、事务编排和返回模型转换。
    """

    @staticmethod
    def _build_model(entity: Any, db: Session) -> ModuleCommonPromptModel:
        """将数据库实体转换为带关联数量的响应模型。"""
        module_count, project_count = ModuleCommonPromptDao.get_module_counts(db, entity.module_code)
        return ModuleCommonPromptModel(
            prompt_id=entity.prompt_id,
            module_code=entity.module_code,
            prompt_content=entity.prompt_content,
            enabled=bool(entity.enabled),
            remark=entity.remark or "",
            module_count=module_count,
            project_count=project_count,
            create_time=entity.create_time,
            update_time=entity.update_time,
        )

    @classmethod
    def get_page_services(cls, db: Session, query: ModuleCommonPromptPageQueryModel) -> PageResponseModel:
        """查询模块通用提示词分页列表。"""
        page = ModuleCommonPromptDao.get_page(db, query)
        rows = [cls._build_model(row, db).model_dump(by_alias=True) for row in page["rows"]]
        return PageResponseModel(
            rows=rows,
            page_num=page["page_num"],
            page_size=page["page_size"],
            total=page["total"],
            has_next=page["has_next"],
        )

    @classmethod
    def get_detail_services(cls, db: Session, prompt_id: int) -> ModuleCommonPromptModel | None:
        """查询模块通用提示词详情。"""
        entity = ModuleCommonPromptDao.get_by_id(db, prompt_id)
        return cls._build_model(entity, db) if entity else None

    @classmethod
    def get_options_services(
        cls, db: Session, keyword: str | None = None
    ) -> list[ModuleCommonPromptOptionModel]:
        """查询可用于新增配置的模块编码选项。"""
        return [ModuleCommonPromptOptionModel.model_validate(row._mapping) for row in ModuleCommonPromptDao.get_options(db, keyword=keyword)]

    @classmethod
    def get_prompt_text(cls, db: Session, module_code: str) -> ModuleCommonPromptModel | None:
        """查询启用中的模块通用说明，供工单分析链路使用。"""
        code = str(module_code or "").strip()
        if not code:
            return None
        entity = ModuleCommonPromptDao.get_by_code(db, code, enabled_only=True)
        return cls._build_model(entity, db) if entity else None

    @classmethod
    def add_services(
        cls, db: Session, request: CreateModuleCommonPromptModel, username: str
    ) -> CrudResponseModel:
        """新增模块通用提示词。"""
        code = request.module_code.strip()
        existing = ModuleCommonPromptDao.get_by_code(db, code, include_deleted=True)
        if existing:
            if existing.del_flag == "0":
                return CrudResponseModel(is_success=False, message="模块编码通用提示词已存在")
            try:
                ModuleCommonPromptDao.update(
                    db,
                    existing.prompt_id,
                    {
                        "prompt_content": request.prompt_content.strip(),
                        "enabled": bool(request.enabled),
                        "remark": request.remark or "",
                        "del_flag": "0",
                        "update_by": username,
                        "update_time": datetime.now(),
                    },
                )
                db.commit()
                db.refresh(existing)
                return CrudResponseModel(is_success=True, message="恢复成功", result=cls._build_model(existing, db))
            except Exception:
                db.rollback()
                raise
        now = datetime.now()
        try:
            entity = ModuleCommonPromptDao.add(
                db,
                {
                    "module_code": code,
                    "prompt_content": request.prompt_content.strip(),
                    "enabled": bool(request.enabled),
                    "remark": request.remark or "",
                    "create_by": username,
                    "update_by": username,
                    "create_time": now,
                    "update_time": now,
                },
            )
            db.commit()
            return CrudResponseModel(is_success=True, message="新增成功", result=cls._build_model(entity, db))
        except IntegrityError:
            db.rollback()
            return CrudResponseModel(is_success=False, message="模块编码通用提示词已存在")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def update_services(
        cls, db: Session, request: UpdateModuleCommonPromptModel, username: str
    ) -> CrudResponseModel:
        """修改模块通用提示词，编码保持不变。"""
        entity = ModuleCommonPromptDao.get_by_id(db, request.prompt_id)
        if not entity:
            return CrudResponseModel(is_success=False, message="模块通用提示词不存在")
        try:
            ModuleCommonPromptDao.update(
                db,
                request.prompt_id,
                {
                    "prompt_content": request.prompt_content.strip(),
                    "enabled": bool(request.enabled),
                    "remark": request.remark or "",
                    "update_by": username,
                    "update_time": datetime.now(),
                },
            )
            db.commit()
            db.refresh(entity)
            return CrudResponseModel(is_success=True, message="修改成功", result=cls._build_model(entity, db))
        except Exception:
            db.rollback()
            raise

    @classmethod
    def delete_services(cls, db: Session, prompt_id: int, username: str) -> CrudResponseModel:
        """逻辑删除模块通用提示词，并记录影响范围。"""
        entity = ModuleCommonPromptDao.get_by_id(db, prompt_id)
        if not entity:
            return CrudResponseModel(is_success=False, message="模块通用提示词不存在")
        module_count, project_count = ModuleCommonPromptDao.get_module_counts(db, entity.module_code)
        try:
            ModuleCommonPromptDao.soft_delete(
                db,
                prompt_id,
                {"update_by": username, "update_time": datetime.now()},
            )
            db.commit()
            logger.info(
                f"删除模块通用提示词成功: prompt_id={prompt_id}, module_code={entity.module_code}, "
                f"module_count={module_count}, project_count={project_count}"
            )
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception:
            db.rollback()
            raise
