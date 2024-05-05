from module_hrm.dao.module_dao import *
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import export_list2excel, CamelCaseUtil


class ModuleService:
    """
    模块管理模块服务层
    """
    @classmethod
    def get_module_list_services(cls, query_db: Session, query_object: ModulePageQueryModel, is_page: bool = False):
        """
        获取模块列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 模块列表信息对象
        """
        list_result = ModuleDao.get_module_list(query_db, query_object, is_page)

        return list_result


    @classmethod
    def get_module_list_services_all(cls, query_db: Session, page_object: ModuleModel):
        """
        获取项目信息service
        :param query_db: orm对象
        :param page_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 项目信息对象
        """
        project_list_result = ModuleDao.get_module_list_all(query_db, page_object)

        return CamelCaseUtil.transform_result(project_list_result)

    @classmethod
    def get_module_list_services_show(cls, query_db: Session, page_object: ModuleModel):
        """
        获取项目信息service
        :param query_db: orm对象
        :param page_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 项目信息对象
        """
        project_list_result = ModuleDao.get_module_list_show(query_db, page_object)

        return CamelCaseUtil.transform_result(project_list_result)

    @classmethod
    def add_module_services(cls, query_db: Session, page_object: AddModuleModel):
        """
        新增模块信息service
        :param query_db: orm对象
        :param page_object: 新增模块对象
        :return: 新增模块校验结果
        """
        add_module = ModuleModel(**page_object.model_dump(by_alias=True))
        module = ModuleDao.get_module_detail_by_info(query_db, ModuleQuery(moduleName=page_object.module_name))
        if module:
            result = dict(is_success=False, message='模块名称已存在')
        else:
            try:
                add_result = ModuleDao.add_module_dao(query_db, add_module)
                module_id = add_result.module_id
                if page_object.project_id:
                    ModuleDao.add_module_project_dao(query_db, ModuleProjectModel(moduleId=module_id, projectId=page_object.project_id))
                query_db.commit()
                result = dict(is_success=True, message='新增成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_module_services(cls, query_db: Session, page_object: ModuleModel):
        """
        编辑模块信息service
        :param query_db: orm对象
        :param page_object: 编辑模块对象
        :return: 编辑模块校验结果
        """
        edit = page_object.model_dump(exclude_unset=True)
        info = cls.module_detail_services(query_db, edit.get('module_id'))
        if info:
            if info.module_name != page_object.module_name:
                module = ModuleDao.get_module_detail_by_info(query_db, ModuleModel(moduleName=page_object.module_name))
                if module:
                    result = dict(is_success=False, message='模块名称已存在')
                    return CrudResponseModel(**result)
            try:
                ModuleDao.edit_module_dao(query_db, edit)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='模块不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_module_services(cls, query_db: Session, page_object: DeleteModuleModel):
        """
        删除模块信息service
        :param query_db: orm对象
        :param page_object: 删除模块对象
        :return: 删除模块校验结果
        """
        if page_object.module_ids.split(','):
            id_list = page_object.module_ids.split(',')
            try:
                for module_id in id_list:
                    ModuleDao.delete_module_dao(query_db, ModuleModel(moduleId=module_id))
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入模块id为空')
        return CrudResponseModel(**result)

    @classmethod
    def module_detail_services(cls, query_db: Session, module_id: int):
        """
        获取模块详细信息service
        :param query_db: orm对象
        :param module_id: 模块id
        :return: 模块id对应的信息
        """
        module = ModuleDao.get_module_detail_by_id(query_db, module_id=module_id)
        result = ModuleModel(**CamelCaseUtil.transform_result(module))

        return result

    @staticmethod
    def export_module_list_services(module_list: List):
        """
        导出模块信息service
        :param module_list: 模块信息列表
        :return: 模块信息对应excel的二进制数据
        """
        # 创建一个映射字典，将英文键映射到中文键
        mapping_dict = {
            "moduleId": "模块编号",
            "moduleName": "模块名称",
            "testUser": "测试人员",
            "simpleDesc": "简要说明",
            "otherDesc": "全体说明",
            "sort": "显示顺序",
            "status": "状态",
            "createBy": "创建者",
            "createTime": "创建时间",
            "updateBy": "更新者",
            "updateTime": "更新时间",
            "remark": "备注",
        }

        data = module_list

        for item in data:
            if item.get('status') == '0':
                item['status'] = '正常'
            else:
                item['status'] = '停用'
        new_data = [{mapping_dict.get(key): value for key, value in item.items() if mapping_dict.get(key)} for item in data]
        binary_data = export_list2excel(new_data)

        return binary_data
