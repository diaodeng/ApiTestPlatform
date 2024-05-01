from module_hrm.dao.env_dao import *
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import CamelCaseUtil


class EnvService:
    """
    环境管理模块服务层
    """

    @classmethod
    def get_env_services(cls, query_db: Session, page_object: EnvModel, data_scope_sql: str):
        """
        获取环境信息service
        :param query_db: orm对象
        :param page_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 环境信息对象
        """
        env_list_result = EnvDao.get_env_list(query_db, page_object, data_scope_sql)

        return env_list_result

    @classmethod
    def get_env_list_services(cls, query_db: Session, page_object: EnvModel, data_scope_sql: str):
        """
        获取部门列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 环境列表信息对象
        """
        env_list_result = EnvDao.get_env_list(query_db, page_object, data_scope_sql)

        return CamelCaseUtil.transform_result(env_list_result)

    @classmethod
    def add_env_services(cls, query_db: Session, page_object: EnvModel):
        """
        新增环境信息service
        :param query_db: orm对象
        :param page_object: 新增环境对象
        :return: 新增环境校验结果
        """
        env = EnvDao.get_env_detail_by_info(query_db, EnvModel(env_name=page_object.env_name))
        if env:
            result = dict(is_success=False, message='环境名称已存在')
        else:
            try:
                EnvDao.add_env_dao(query_db, page_object)
                query_db.commit()
                result = dict(is_success=True, message='新增成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_env_services(cls, query_db: Session, env_object: EnvModel):
        """
        编辑环境信息service
        :param query_db: orm对象
        :param env_object: 编辑环境对象
        :return: 编辑环境校验结果
        """
        edit_env = env_object.model_dump(exclude_unset=True)
        env_info = cls.env_detail_services(query_db, edit_env.get('env_id'))
        if env_info:
            if env_info.env_name != env_object.env_name:
                env = EnvDao.get_env_detail_by_info(query_db, EnvModel(env_name=env_object.env_name))
                if env:
                    result = dict(is_success=False, message='环境名称不能重复')
                    return CrudResponseModel(**result)
            try:
                EnvDao.edit_env_dao(query_db, edit_env)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='环境不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_env_services(cls, query_db: Session, page_object: DeleteEnvModel):
        """
        删除环境信息service
        :param query_db: orm对象
        :param page_object: 删除环境对象
        :return: 删除环境校验结果
        """
        print(page_object.env_ids.split(','))
        if page_object.env_ids.split(','):
            env_id_list = page_object.env_ids.split(',')
            try:
                for env_id in env_id_list:
                    EnvDao.delete_env_dao(query_db, EnvModel(envId=env_id))
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入环境id为空')
        return CrudResponseModel(**result)

    @classmethod
    def env_detail_services(cls, query_db: Session, env_id: int):
        """
        获取环境详细信息service
        :param query_db: orm对象
        :param env_id: 环境id
        :return: 环境id对应的信息
        """
        env = EnvDao.get_env_detail_by_id(query_db, env_id=env_id)
        result = EnvModel(**CamelCaseUtil.transform_result(env))

        return result
