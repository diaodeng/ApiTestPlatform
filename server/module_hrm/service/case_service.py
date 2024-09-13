import copy

from module_hrm.dao.case_dao import *
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase as TestCaseDetailForHandle
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import export_list2excel, CamelCaseUtil
from utils.page_util import PageResponseModel
from utils.snowflake import snowIdWorker


class CaseService:
    """
    用例管理服务层
    """
    @classmethod
    def get_case_list_services(cls, query_db: Session, query_object: CasePageQueryModel, is_page: bool = False):
        """
        获取用例列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 用例列表信息对象
        """
        list_result = CaseDao.get_case_list(query_db, query_object, is_page)
        if is_page:
            case_list_result = PageResponseModel(
                **{
                    **list_result.model_dump(by_alias=True),
                    'rows': [{**row[0], **row[1], **row[2]} for row in list_result.rows]
                }
            )
        else:
            case_list_result = []
            if list_result:
                case_list_result = [{**row[0], **row[1], **row[2]} for row in list_result]
        return case_list_result

    @classmethod
    def add_case_services(cls, query_db: Session, page_object: AddCaseModel):
        """
        新增用例信息service
        :param query_db: orm对象
        :param page_object: 新增用例对象
        :return: 新增用例校验结果
        """
        add_case = CaseModel(**page_object.model_dump(by_alias=True))
        case = CaseDao.get_case_detail_by_info(query_db, CaseQuery(caseName=page_object.case_name))
        if case:
            result = dict(is_success=False, message='用例名称已存在')
        else:
            try:
                CaseDao.add_case_dao(query_db, add_case)
                query_db.commit()
                result = dict(is_success=True, message='新增成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def copy_case_services(cls, query_db: Session, page_object: AddCaseModel):
        """
        新增用例信息service
        :param query_db: orm对象
        :param page_object: 新增用例对象
        :return: 新增用例校验结果
        """
        case = CaseDao.get_case_detail_by_info(query_db, CaseQuery(caseId=page_object.case_id))
        if not case:
            result = dict(is_success=False, message='原用例不存在')
        else:
            try:
                new_data = case.__dict__.copy()
                new_data["case_name"] = page_object.case_name
                new_data["manager"] = page_object.manager
                new_data["create_by"] = page_object.create_by
                new_data["update_by"] = page_object.update_by
                new_data.pop("id", None)
                new_data.pop("case_id", None)
                new_data.pop("create_time", None)
                new_data.pop("update_time", None)
                new_data.pop("_sa_instance_state", None)

                new_case = HrmCase(**new_data)
                query_db.add(new_case)
                query_db.commit()
                result = dict(is_success=True, message='复制成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_case_services(cls, query_db: Session, page_object: CaseModel):
        """
        编辑用例信息service
        :param query_db: orm对象
        :param page_object: 编辑用例对象
        :return: 编辑用例校验结果
        """
        # edit = page_object.model_dump(exclude_unset=True)
        info = cls.case_detail_services(query_db, page_object.case_id)
        if info:
            if info.case_name != page_object.case_name:
                case = CaseDao.get_case_detail_by_info(query_db, CaseModel(caseName=page_object.case_name))
                if case:
                    result = dict(is_success=False, message='用例名称已存在')
                    return CrudResponseModel(**result)
            try:
                CaseDao.edit_case_dao(query_db, page_object)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='用例不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_case_services(cls, query_db: Session, page_object: DeleteCaseModel):
        """
        删除用例信息service
        :param query_db: orm对象
        :param page_object: 删除用例对象
        :return: 删除用例校验结果
        """
        if page_object.case_ids.split(','):
            id_list = page_object.case_ids.split(',')
            try:
                for case_id in id_list:
                    CaseDao.delete_case_dao(query_db, CaseModel(caseId=case_id))
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入用例id为空')
        return CrudResponseModel(**result)

    @classmethod
    def case_detail_services(cls, query_db: Session, case_id: int) -> CaseModelForApi:
        """
        获取用例详细信息service
        :param query_db: orm对象
        :param case_id: 用例id
        :return: 用例id对应的信息
        """
        case = CaseDao.get_case_by_id(query_db, case_id=case_id)
        if not case:
            return {}
        result = CaseModelForApi(**CamelCaseUtil.transform_result(case))
        if result.include is not None:
            result.include = json.loads(result.include)
        # new_request = TestCase(**result.request).model_dump(by_alias=True)
        # result.request = new_request

        return result

    @staticmethod
    def export_case_list_services(case_list: List):
        """
        导出用例信息service
        :param case_list: 用例信息列表
        :return: 用例信息对应excel的二进制数据
        """
        # 创建一个映射字典，将英文键映射到中文键
        mapping_dict = {
            "caseId": "用例编号",
            "type": "类型test/config",
            "caseName": "用例名称",
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

        data = case_list

        for item in data:
            if item.get('status') == '0':
                item['status'] = '正常'
            else:
                item['status'] = '停用'
        new_data = [{mapping_dict.get(key): value for key, value in item.items() if mapping_dict.get(key)} for item in data]
        binary_data = export_list2excel(new_data)

        return binary_data
