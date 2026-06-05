from sqlalchemy.orm import Session

from module_admin.entity.do.ai_prompt_template_do import SysAiPromptTemplate
from module_admin.entity.vo.ai_prompt_template_vo import AiPromptTemplatePageQueryModel


class AiPromptTemplateDao:
    """
    AI 提示词模板数据库访问层。
    """

    @classmethod
    def get_prompt_template_by_id(cls, db: Session, template_id: int):
        """
        根据主键获取提示词模板详情。
        :param db: orm对象
        :param template_id: 模板主键
        :return: 提示词模板数据库对象，不存在时返回None
        """
        return (
            db.query(SysAiPromptTemplate)
            .filter(SysAiPromptTemplate.template_id == template_id, SysAiPromptTemplate.del_flag == "0")
            .first()
        )

    @classmethod
    def get_prompt_template_by_code(cls, db: Session, template_code: str):
        """
        根据模板编码获取详情。
        :param db: orm对象
        :param template_code: 模板编码
        :return: 提示词模板数据库对象，不存在时返回None
        """
        return (
            db.query(SysAiPromptTemplate)
            .filter(SysAiPromptTemplate.template_code == template_code, SysAiPromptTemplate.del_flag == "0")
            .first()
        )

    @classmethod
    def get_prompt_template_list(cls, db: Session, query_object: AiPromptTemplatePageQueryModel):
        """
        根据查询参数获取 AI 提示词模板分页数据。
        :param db: orm对象
        :param query_object: 查询对象
        :return: 包含分页数据及总数的字典
        """
        query = db.query(SysAiPromptTemplate).filter(SysAiPromptTemplate.del_flag == "0")
        if query_object.keyword:
            like_keyword = f"%{query_object.keyword}%"
            query = query.filter(
                (SysAiPromptTemplate.template_code.like(like_keyword))
                | (SysAiPromptTemplate.template_name.like(like_keyword))
                | (SysAiPromptTemplate.template_category.like(like_keyword))
                | (SysAiPromptTemplate.provider_code.like(like_keyword))
                | (SysAiPromptTemplate.model_name.like(like_keyword))
            )
        if query_object.template_category:
            query = query.filter(SysAiPromptTemplate.template_category == query_object.template_category)
        if query_object.enabled is not None:
            query = query.filter(SysAiPromptTemplate.enabled == bool(query_object.enabled))
        query = query.order_by(SysAiPromptTemplate.sort.asc(), SysAiPromptTemplate.template_id.desc())
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
    def get_prompt_template_options(cls, db: Session, *, enabled_only: bool = True, template_categories: list[str] | None = None):
        """
        获取 AI 提示词模板下拉选项。
        :param db: orm对象
        :param enabled_only: 是否仅返回启用中的模板
        :param template_categories: 可选分类列表
        :return: 模板列表
        """
        query = db.query(SysAiPromptTemplate).filter(SysAiPromptTemplate.del_flag == "0")
        if enabled_only:
            query = query.filter(SysAiPromptTemplate.enabled.is_(True))
        if template_categories:
            query = query.filter(SysAiPromptTemplate.template_category.in_(template_categories))
        return query.order_by(SysAiPromptTemplate.sort.asc(), SysAiPromptTemplate.template_id.desc()).all()

    @classmethod
    def add_prompt_template_dao(cls, db: Session, prompt_template_data: dict):
        """
        新增 AI 提示词模板数据库记录。
        :param db: orm对象
        :param prompt_template_data: 需要写入数据库的字典
        :return: 新增后的数据库对象
        """
        db_prompt_template = SysAiPromptTemplate(**prompt_template_data)
        db.add(db_prompt_template)
        db.flush()
        return db_prompt_template

    @classmethod
    def edit_prompt_template_dao(cls, db: Session, template_id: int, prompt_template_data: dict):
        """
        编辑 AI 提示词模板数据库记录。
        :param db: orm对象
        :param template_id: 模板主键
        :param prompt_template_data: 更新字段字典
        :return: 无
        """
        (
            db.query(SysAiPromptTemplate)
            .filter(SysAiPromptTemplate.template_id == template_id, SysAiPromptTemplate.del_flag == "0")
            .update(prompt_template_data)
        )

    @classmethod
    def delete_prompt_template_dao(cls, db: Session, template_id: int, delete_info: dict):
        """
        逻辑删除 AI 提示词模板。
        :param db: orm对象
        :param template_id: 模板主键
        :param delete_info: 删除时需要更新的附加字段
        :return: 无
        """
        update_data = {"del_flag": "2", **delete_info}
        (
            db.query(SysAiPromptTemplate)
            .filter(SysAiPromptTemplate.template_id == template_id, SysAiPromptTemplate.del_flag == "0")
            .update(update_data)
        )
