from module_hrm.dao.debugtalk_dao import *
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import CamelCaseUtil


class DebugTalkService:
    """
    DebugTalk管理模块服务层
    """

    @classmethod
    def get_debugtalk_services(cls, query_db: Session, page_object: DebugTalkModel, data_scope_sql: str):
        """
        获取DebugTalk信息service
        :param query_db: orm对象
        :param page_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: DebugTalk信息对象
        """
        debugtalk_list_result = DebugTalkDao.get_debugtalk_list(query_db)

        return debugtalk_list_result

    @classmethod
    def get_debugtalk_list_services(cls, query_db: Session, page_object: DebugTalkModel, data_scope_sql: str):
        """
        获取部门列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: DebugTalk列表信息对象
        """
        debugtalk_list_result = DebugTalkDao.get_debugtalk_list(query_db)
        return CamelCaseUtil.transform_result(debugtalk_list_result)

    @classmethod
    def add_debugtalk_services(cls, query_db: Session, page_object: DebugTalkModel):
        """
        新增DebugTalk信息service
        :param query_db: orm对象
        :param page_object: 新增DebugTalk对象
        :return: 新增DebugTalk校验结果
        """

        try:
            DebugTalkDao.add_debugtalk_dao(query_db, page_object)
            query_db.commit()
            result = dict(is_success=True, message='新增成功')
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_dept_services(cls, query_db: Session, debugtalk_object: DebugTalkModel):
        """
        编辑DebugTalk信息service
        :param query_db: orm对象
        :param debugtalk_object: 编辑DebugTalk对象
        :return: 编辑DebugTalk校验结果
        """
        edit_debugtalk = debugtalk_object.model_dump(exclude_unset=True)
        print('##################')
        print(debugtalk_object)
        print(edit_debugtalk)
        info = cls.debugtalk_detail_services(query_db, edit_debugtalk.get('debugtalk_id'))
        if info:
            try:
                DebugTalkDao.edit_debugtalk_dao(query_db, edit_debugtalk)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='DebugTalk不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_debugtalk_services(cls, query_db: Session, page_object: DeleteDebugTalkModel):
        """
        删除DebugTalk信息service
        :param query_db: orm对象
        :param page_object: 删除DebugTalk对象
        :return: 删除DebugTalk校验结果
        """
        if page_object.project_ids.split(','):
            project_id_list = page_object.project_ids.split(',')
            try:
                for project_id in project_id_list:
                    DebugTalkDao.delete_debugtalk_dao(query_db, DebugTalkModel(projectId=project_id, updateTime=page_object.update_time, updateBy=page_object.update_by))
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入DebugTalkid为空')
        return CrudResponseModel(**result)

    @classmethod
    def debugtalk_detail_services(cls, query_db: Session, debugtalk_id: int):
        """
        获取DebugTalk详细信息service
        :param query_db: orm对象
        :param debugtalk_id: DebugTalkid
        :return: DebugTalkid对应的信息
        """
        debugtalk = DebugTalkDao.get_debugtalk_detail_by_id(query_db, debugtalk_id=debugtalk_id)
        result = DebugTalkModel(**CamelCaseUtil.transform_result(debugtalk))

        return result
