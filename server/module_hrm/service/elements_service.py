import json

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.ui_elements_dao import ElementsOperation
from module_hrm.dao.suite_dao import SuiteDetailDao
from module_hrm.entity.do.ui_elements_manager_do import QtrElements
from module_hrm.entity.vo.elements_vo import ElementsPageQueryModel, ElementsModel, \
    DeleteElementsModel, ElementsAddModel, ElementsModelForApi, ElementsQueryModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import export_list2excel, CamelCaseUtil
from utils.page_util import PageResponseModel


class ElementService:
    """
    element管理服务层
    """

    @classmethod
    def element_list_services(cls, query_db: Session, query_object: ElementsPageQueryModel, data_scope_sql: str,
                              is_page: bool = False):
        """
        获取element列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param data_scope_sql: 数据权限sql
        :param is_page: 是否开启分页
        :return: element列表信息对象
        """
        list_result = ElementsOperation.query_list(query_db, query_object, data_scope_sql, is_page)
        if is_page:
            element_list_result = PageResponseModel(
                **{
                    **list_result.model_dump(by_alias=True),
                    'rows': [{**row[0], **row[1], **row[2]} for row in list_result.rows]
                }
            )
        else:
            element_list_result = []
            if list_result:
                element_list_result = [{**row[0], **row[1], **row[2]} for row in list_result]
        return element_list_result

    @classmethod
    def add_element_services(cls, query_db: Session, add_element_object: ElementsAddModel):
        """
        新增element信息service
        :param query_db: orm对象
        :param page_object: 新增element对象
        :return: 新增element校验结果
        """
        add_element = ElementsModel(**add_element_object.model_dump(by_alias=True))
        element = ElementsOperation.get_element_detail_by_info(query_db,
                                                               ElementsModelForApi(name=add_element_object.name))
        if element:
            result = dict(is_success=False, message='element名称已存在')
        else:
            try:
                element_dao = ElementsOperation.add(query_db, add_element)
                query_db.commit()
                result = dict(is_success=True,
                              message='新增成功',
                              result=ElementsModelForApi.model_validate(element_dao).model_dump(by_alias=True))
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def copy_element_services(cls, query_db: Session, page_object: ElementsAddModel):
        """
        复制element信息service
        :param query_db: orm对象
        :param page_object: 新增element对象
        :return: 新增element校验结果
        """
        element = ElementsOperation.get_element_detail_by_info(query_db,
                                                               ElementsModelForApi(element_id=page_object.element_id))
        if not element:
            result = dict(is_success=False, message='原element不存在')
        else:
            try:
                new_data = element.__dict__.copy()
                new_data["name"] = page_object.name
                new_data["manager"] = page_object.manager
                new_data["create_by"] = page_object.create_by
                new_data["update_by"] = page_object.update_by
                new_data.pop("id", None)
                new_data.pop("element_id", None)
                new_data.pop("create_time", None)
                new_data.pop("update_time", None)
                new_data.pop("_sa_instance_state", None)

                new_element = QtrElements(**new_data)
                query_db.add(new_element)
                query_db.commit()
                result = dict(is_success=True, message='复制成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def update_element_services(cls, query_db: Session, page_object: ElementsModelForApi, user: CurrentUserModel = None):
        """
        编辑element信息service
        :param query_db: orm对象
        :param page_object: 编辑element对象
        :return: 编辑element校验结果
        """
        # edit = page_object.model_dump(exclude_unset=True)
        info = cls.element_detail_services(query_db, page_object.element_id)
        if info:
            if page_object.name and info.name != page_object.name:
                element = ElementsOperation.get_element_detail_by_info(query_db,
                                                                       ElementsModelForApi(name=page_object.name))
                if element:
                    result = dict(is_success=False, message='element名称已存在')
                    return CrudResponseModel(**result)
            try:
                ElementsOperation.update(query_db, page_object, user)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='element不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_element_services(cls,
                                query_db: Session,
                                page_object: DeleteElementsModel,
                                permanent_delete: bool = False,
                                user: CurrentUserModel = None):
        """
        删除element信息service
        :param query_db: orm对象
        :param page_object: 删除element对象
        :param permanent_delete: 是否永久删除
        :param user: 当前操作的用户信息
        :return: 删除element校验结果
        """
        if page_object.element_ids:
            try:
                ElementsOperation.delete(query_db, page_object.element_ids, permanent_delete, user)
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入elementid为空')
        return CrudResponseModel(**result)

    @classmethod
    def element_detail_services(cls, query_db: Session, element_id: int) -> ElementsModelForApi:
        """
        获取element详细信息service
        :param query_db: orm对象
        :param element_id: elementid
        :return: elementid对应的信息
        """
        element = ElementsOperation.get(query_db, element_id=element_id)
        if not element:
            return {}

        data = CamelCaseUtil.transform_result(element)
        result = ElementsModelForApi(**data)

        return result

    @staticmethod
    def export_element_list_services(element_list: list):
        """
        导出element信息service
        :param element_list: element信息列表
        :return: element信息对应excel的二进制数据
        """
        # 创建一个映射字典，将英文键映射到中文键
        mapping_dict = {
            "elementId": "element编号",
            "type": "类型test/config",
            "elementName": "element名称",
            "projectId": "所属项目",
            "moduleId": "所属模块",
            "include": "前置config/test",
            "request": "请求信息",
            "notes": "注释",
            "desc2mind": "脑图",
            "sort": "显示顺序",
            "status": "状态",
            "createBy": "创建者",
            "createTime": "创建时间",
            "updateBy": "更新者",
            "updateTime": "更新时间",
            "remark": "备注",
        }

        data = element_list

        for item in data:
            if item.get('status') == '0':
                item['status'] = '正常'
            else:
                item['status'] = '停用'
        new_data = [{mapping_dict.get(key): value for key, value in item.items() if mapping_dict.get(key)} for item in
                    data]
        binary_data = export_list2excel(new_data)

        return binary_data
