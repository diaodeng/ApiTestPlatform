from sqlalchemy.orm import Session

from module_admin.entity.do.api_key_do import SysApiKey
from module_admin.entity.vo.api_key_vo import ApiKeyPageQueryModel


class ApiKeyDao:
    """
    API Key管理模块数据库操作层
    """

    @classmethod
    def get_api_key_by_id(cls, db: Session, api_key_id: int, user_id: int | None = None):
        """
        根据API Key主键获取API Key详情
        :param db: orm对象
        :param api_key_id: API Key主键
        :param user_id: 可选，所属用户ID，用于限制只查询当前用户的数据
        :return: API Key数据库对象，不存在时返回None
        """
        query = db.query(SysApiKey).filter(SysApiKey.api_key_id == api_key_id, SysApiKey.del_flag == "0")
        if user_id is not None:
            query = query.filter(SysApiKey.user_id == user_id)
        return query.first()

    @classmethod
    def get_api_key_by_key_code(cls, db: Session, key_code: str):
        """
        根据API Key公开标识获取API Key详情
        :param db: orm对象
        :param key_code: API Key公开标识
        :return: API Key数据库对象，不存在时返回None
        """
        return (
            db.query(SysApiKey)
            .filter(SysApiKey.key_code == key_code, SysApiKey.del_flag == "0")
            .first()
        )

    @classmethod
    def get_api_key_list(cls, db: Session, user_id: int, query_object: ApiKeyPageQueryModel):
        """
        根据查询参数获取当前用户的API Key分页数据
        :param db: orm对象
        :param user_id: 所属用户ID
        :param query_object: API Key分页查询对象
        :return: 包含分页数据及总数的字典
        """
        query = (
            db.query(SysApiKey)
            .filter(
                SysApiKey.user_id == user_id,
                SysApiKey.del_flag == "0",
                SysApiKey.key_name.like(f"%{query_object.key_name}%") if query_object.key_name else True,
            )
            .order_by(SysApiKey.api_key_id.desc())
        )
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
    def add_api_key_dao(cls, db: Session, api_key_data: dict):
        """
        新增API Key数据库操作
        :param db: orm对象
        :param api_key_data: 需要写入数据库的API Key字典
        :return: 新增后的API Key数据库对象
        """
        db_api_key = SysApiKey(**api_key_data)
        db.add(db_api_key)
        db.flush()
        return db_api_key

    @classmethod
    def edit_api_key_dao(cls, db: Session, api_key_id: int, api_key_data: dict):
        """
        编辑API Key数据库操作
        :param db: orm对象
        :param api_key_id: API Key主键
        :param api_key_data: 需要更新的API Key字段字典
        :return:
        """
        (
            db.query(SysApiKey)
            .filter(SysApiKey.api_key_id == api_key_id, SysApiKey.del_flag == "0")
            .update(api_key_data)
        )

    @classmethod
    def delete_api_key_dao(cls, db: Session, api_key_id: int, delete_info: dict):
        """
        删除API Key数据库操作，采用逻辑删除
        :param db: orm对象
        :param api_key_id: API Key主键
        :param delete_info: 删除时需要更新的附加字段字典
        :return:
        """
        update_data = {"del_flag": "2", **delete_info}
        (
            db.query(SysApiKey)
            .filter(SysApiKey.api_key_id == api_key_id, SysApiKey.del_flag == "0")
            .update(update_data)
        )
