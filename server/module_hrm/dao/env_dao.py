from sqlalchemy.orm import Session
from module_hrm.entity.do.env_do import HrmEnv
from module_hrm.entity.vo.env_vo import *
from utils.page_util import PageUtil
from utils.time_format_util import list_format_datetime


class EnvDao:
    """
    环境管理模块数据库操作层
    """

    @classmethod
    def get_env_by_id(cls, db: Session, env_id: int):
        """
        根据环境id获取在用环境信息
        :param db: orm对象
        :param env_id: 环境id
        :return: 在用环境信息对象
        """
        env_info = db.query(HrmEnv) \
            .filter(HrmEnv.env_id == env_id,
                    HrmEnv.status == 0,
                    HrmEnv.del_flag == 0) \
            .first()

        return env_info

    @classmethod
    def get_env_by_id_for_list(cls, db: Session, env_id: int):
        """
        用于获取环境列表的工具方法
        :param db: orm对象
        :param env_id: 环境id
        :return: 环境id对应的信息对象
        """
        env_info = db.query(HrmEnv) \
            .filter(HrmEnv.env_id == env_id,
                    HrmEnv.del_flag == 0) \
            .first()

        return env_info

    @classmethod
    def get_env_detail_by_id(cls, db: Session, env_id: int):
        """
        根据环境id获取环境详细信息
        :param db: orm对象
        :param env_id: 部门id
        :return: 部门信息对象
        """
        env_info = db.query(HrmEnv) \
            .filter(HrmEnv.env_id == env_id,
                    HrmEnv.del_flag == 0) \
            .first()

        return env_info

    @classmethod
    def get_env_detail_by_info(cls, db: Session, env: EnvModel):
        """
        根据环境参数获取环境信息
        :param db: orm对象
        :param env: 部门参数对象
        :return: 部门信息对象
        """
        env_info = db.query(HrmEnv) \
            .filter(HrmEnv.env_url == env.env_url if env.env_url else True,
                    HrmEnv.env_name == env.env_name if env.env_name else False) \
            .first()
        return env_info

    @classmethod
    def get_env_list(cls, db: Session, page_object: EnvQueryModel, data_scope_sql: str, is_page=False):
        """
        根据查询参数获取环境列表信息
        :param db: orm对象
        :param page_object: 不分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 环境列表信息对象
        """
        env_result = db.query(HrmEnv) \
            .filter(HrmEnv.del_flag == 0,
                    HrmEnv.status == page_object.status if page_object.status else True,
                    HrmEnv.env_name.like(f'%{page_object.env_name}%') if page_object.env_name else True,
                    eval(data_scope_sql))
        if page_object.only_self:
            env_result = env_result.filter(HrmEnv.manager == page_object.manager)

        env_result = env_result.order_by(HrmEnv.order_num) \
            .distinct()

        post_list = PageUtil.paginate(env_result, page_object.page_num, page_object.page_size, is_page)

        return post_list

    @classmethod
    def add_env_dao(cls, db: Session, env: EnvModel):
        """
        新增部门数据库操作
        :param db: orm对象
        :param env: 环境对象
        :return: 新增校验结果
        """
        db_env = HrmEnv(**env.model_dump())
        db.add(db_env)
        db.flush()

        return db_env

    @classmethod
    def edit_env_dao(cls, db: Session, env: dict):
        """
        编辑部门数据库操作
        :param db: orm对象
        :param env: 需要更新的部门字典
        :return: 编辑校验结果
        """
        db.query(HrmEnv) \
            .filter(HrmEnv.env_id == env.get('env_id')) \
            .update(env)

    @classmethod
    def delete_env_dao(cls, db: Session, env: EnvModel):
        """
        删除部门数据库操作
        :param db: orm对象
        :param env: 部门对象
        :return:
        """
        db.query(HrmEnv) \
            .filter(HrmEnv.env_id == env.env_id) \
            .update({HrmEnv.del_flag: '2', HrmEnv.update_by: env.update_by, HrmEnv.update_time: env.update_time})
