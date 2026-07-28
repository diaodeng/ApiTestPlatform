from sqlalchemy.orm import Session

from module_admin.entity.do.ai_provider_do import SysAiProvider
from module_admin.entity.vo.ai_provider_vo import AiProviderPageQueryModel


class AiProviderDao:
    """
    AI Provider 管理模块数据库操作层。
    """

    @classmethod
    def get_ai_provider_by_id(cls, db: Session, provider_id: int):
        """
        根据主键获取 AI Provider 详情。
        :param db: orm对象
        :param provider_id: Provider主键
        :return: AI Provider数据库对象，不存在时返回None
        """
        return (
            db.query(SysAiProvider)
            .filter(SysAiProvider.provider_id == provider_id, SysAiProvider.del_flag == "0")
            .first()
        )

    @classmethod
    def get_ai_provider_by_code(cls, db: Session, provider_code: str):
        """
        根据 Provider 编码获取详情。
        :param db: orm对象
        :param provider_code: Provider编码
        :return: AI Provider数据库对象，不存在时返回None
        """
        return (
            db.query(SysAiProvider)
            .filter(SysAiProvider.provider_code == provider_code, SysAiProvider.del_flag == "0")
            .first()
        )

    @classmethod
    def get_ai_provider_list(cls, db: Session, query_object: AiProviderPageQueryModel):
        """
        根据查询参数获取 AI Provider 分页数据。
        :param db: orm对象
        :param query_object: 查询对象
        :return: 包含分页数据及总数的字典
        """
        query = db.query(SysAiProvider).filter(SysAiProvider.del_flag == "0")
        if query_object.keyword:
            like_keyword = f"%{query_object.keyword}%"
            query = query.filter(
                (SysAiProvider.provider_code.like(like_keyword))
                | (SysAiProvider.provider_name.like(like_keyword))
                | (SysAiProvider.platform_code.like(like_keyword))
                | (SysAiProvider.api_protocol.like(like_keyword))
                | (SysAiProvider.preferred_agent_code.like(like_keyword))
                | (SysAiProvider.default_model.like(like_keyword))
            )
        if query_object.platform_code:
            query = query.filter(SysAiProvider.platform_code == query_object.platform_code)
        if query_object.api_protocol:
            query = query.filter(SysAiProvider.api_protocol == query_object.api_protocol)
        if query_object.enabled is not None:
            query = query.filter(SysAiProvider.enabled == bool(query_object.enabled))
        query = query.order_by(SysAiProvider.provider_level.desc(), SysAiProvider.provider_id.desc())
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
    def get_ai_provider_options(cls, db: Session, enabled_only: bool = True):
        """
        获取 AI Provider 下拉选项。
        :param db: orm对象
        :param enabled_only: 是否仅返回启用中的 Provider
        :return: Provider列表
        """
        query = db.query(SysAiProvider).filter(SysAiProvider.del_flag == "0")
        if enabled_only:
            query = query.filter(SysAiProvider.enabled.is_(True))
        return query.order_by(SysAiProvider.provider_level.desc(), SysAiProvider.provider_id.desc()).all()

    @classmethod
    def add_ai_provider_dao(cls, db: Session, ai_provider_data: dict):
        """
        新增 AI Provider 数据库记录。
        :param db: orm对象
        :param ai_provider_data: 需要写入数据库的字典
        :return: 新增后的数据库对象
        """
        db_ai_provider = SysAiProvider(**ai_provider_data)
        db.add(db_ai_provider)
        db.flush()
        return db_ai_provider

    @classmethod
    def edit_ai_provider_dao(cls, db: Session, provider_id: int, ai_provider_data: dict):
        """
        编辑 AI Provider 数据库记录。
        :param db: orm对象
        :param provider_id: Provider主键
        :param ai_provider_data: 更新字段字典
        :return: 无
        """
        (
            db.query(SysAiProvider)
            .filter(SysAiProvider.provider_id == provider_id, SysAiProvider.del_flag == "0")
            .update(ai_provider_data)
        )

    @classmethod
    def delete_ai_provider_dao(cls, db: Session, provider_id: int, delete_info: dict):
        """
        逻辑删除 AI Provider。
        :param db: orm对象
        :param provider_id: Provider主键
        :param delete_info: 删除时需要更新的附加字段
        :return: 无
        """
        update_data = {"del_flag": "2", **delete_info}
        (
            db.query(SysAiProvider)
            .filter(SysAiProvider.provider_id == provider_id, SysAiProvider.del_flag == "0")
            .update(update_data)
        )
