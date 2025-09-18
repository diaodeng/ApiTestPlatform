import json
import io
import csv
import uuid
from loguru import logger
from typing import AsyncGenerator, List

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import insert
from sqlalchemy.orm import Session

from config.database import SessionLocal
from config.get_db import get_db
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.case_dao import CaseDao, CaseParamsDao
from module_hrm.dao.suite_dao import SuiteDetailDao
from module_hrm.entity.do.case_do import HrmCase, HrmCaseParams
from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_params_vo import CaseParamsQueryModel, CaseParamsDeleteModel
from module_hrm.entity.vo.case_vo import CasePageQueryModel, CaseModel, CaseQuery, \
    DeleteCaseModel, AddCaseModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import export_list2excel, CamelCaseUtil
from utils.page_util import PageResponseModel


class CaseService:
    """
    用例管理服务层
    """

    @classmethod
    def get_case_list_services(cls, query_db: Session, query_object: CasePageQueryModel, is_page: bool = False,
                               data_scope_sql: str = 'true'):
        """
        获取用例列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 用例列表信息对象
        """
        list_result = CaseDao.get_case_list(query_db, query_object, is_page, data_scope_sql)
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
                case_dao = CaseDao.add_case_dao(query_db, add_case)
                query_db.commit()
                result = dict(is_success=True,
                              message='新增成功',
                              result=CaseModelForApi.model_validate(case_dao).model_dump(by_alias=True))
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
    def edit_case_services(cls, query_db: Session, page_object: CaseModel, user: CurrentUserModel = None):
        """
        编辑用例信息service
        :param query_db: orm对象
        :param page_object: 编辑用例对象
        :return: 编辑用例校验结果
        """
        # edit = page_object.model_dump(exclude_unset=True)
        info = cls.case_detail_services(query_db, page_object.case_id)
        if info:
            if page_object.case_name and info.case_name != page_object.case_name:
                case = CaseDao.get_case_detail_by_info(query_db, CaseModel(caseName=page_object.case_name))
                if case:
                    result = dict(is_success=False, message='用例名称已存在')
                    return CrudResponseModel(**result)
            try:
                CaseDao.edit_case_dao(query_db, page_object, user)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='用例不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_case_services(cls, query_db: Session, page_object: DeleteCaseModel, user: CurrentUserModel = None):
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
                    CaseDao.delete_case_dao(query_db, CaseModel(caseId=case_id), user)
                    CaseParamsDao.delete_table(query_db, use_case_id=case_id)
                    SuiteDetailDao.del_suite_detail_by_id(query_db, case_id)
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

        data = CamelCaseUtil.transform_result(case)
        result = CaseModelForApi(**data)
        if result.include is not None:
            result.include = json.loads(result.include)
        # new_request = TestCase(**result.request).model_dump(by_alias=True)
        # result.request = new_request

        return result

    @staticmethod
    def export_case_list_services(case_list: list):
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
        new_data = [{mapping_dict.get(key): value for key, value in item.items() if mapping_dict.get(key)} for item in
                    data]
        binary_data = export_list2excel(new_data)

        return binary_data


class CaseParamsService:
    @classmethod
    def get_case_params_pages_services(cls, query_db: Session, query_info: CaseParamsQueryModel) -> dict:
        """
        获取用例参数信息service
        :param query_db: orm对象
        :param case_id: 用例id
        :return: 用例参数信息
        """
        count = CaseParamsDao.get_table_row_count(query_db, use_case_id=query_info.case_id)
        case_params = CaseParamsDao.load_table_page(query_db,
                                                    use_case_id=query_info.case_id,
                                                    page=query_info.page_num,
                                                    page_size=query_info.page_size,
                                                    enabled=query_info.enabled,
                                                    )
        page_info = {
            'total': count,
            'page_num': query_info.page_num,
            'page_size': query_info.page_size,
            # 'total_page': math.ceil(count / query_info.page_size),
            'rows': case_params,
        }
        return page_info

    @classmethod
    def loadup_case_params_services(cls, query_db: Session, case_id: str|int, case_params: list[dict]):
        """
        获取用例参数信息service
        :param query_db: orm对象
        :param case_id: 用例id
        :return: 用例参数信息
        """
        CaseParamsDao.insert_table(query_db, use_case_id=case_id, table_data=case_params)

    @classmethod
    async def load_case_params_iter(cls, query_db: Session, case_id: int) -> AsyncGenerator[dict, None]:
        """
        加载用例参数信息service
        :param query_db: orm对象
        :param case_id: 用例id
        :return: 用例参数信息
        """
        async for case_param in CaseParamsDao.load_table_iter(query_db, use_case_id=case_id):
            yield case_param

    @classmethod
    def add_case_params_services(cls, query_db: Session, case_id: int, params: dict):
        """
        添加用例参数信息service
        :param query_db: orm对象
        :param case_id: 用例id
        :param params: 用例参数信息
        :return: 用例参数信息
        """
        CaseParamsDao.add_table_row(query_db, use_case_id=case_id, row_data=params)


    @classmethod
    def update_case_params_services(cls, query_db: Session, case_id: int, params: dict):

        """
        更新用例参数信息service
        :param query_db: orm对象
        :param case_id: 用例id
        :param params: 用例参数信息
        :return: 用例参数信息
        """
        CaseParamsDao.update_table_row(query_db, use_case_id=case_id, row_data=params)

    @classmethod
    def delete_case_params_services(cls, query_db: Session, delete_data: CaseParamsDeleteModel):
        """
        删除用例参数信息service
        :param query_db: orm对象
        :param case_id: 用例id
        :param params: 用例参数信息
        :return: 用例参数信息
        """
        CaseParamsDao.delete_table_row(query_db, use_case_id=delete_data.case_id, row_ids=delete_data.row_ids)

    @classmethod
    def import_csv_to_db(cls, file_name:str, content: bytes, case_id: int|str, current_user: CurrentUserModel) -> dict:
        """
        导入用例参数信息service
        :param query_db: orm对象
        :param file: 上传文件
        :param case_id: 用例id
        :param current_user: 当前用户
        :return: 用例参数信息
        """
        # 用文本流解析
        file_name = file_name
        logger.info(f'导入用例参数，用例id：{case_id}，文件名：{file_name}')
        batch_size = 1000
        buffer: List[dict] = []
        writed_line: int = 0
        sort_key = 100
        total = 0
        error_count = 0
        try:
            content = content
            logger.info(f'文件读取完成，导入用例参数，用例id：{case_id}，文件名：{file_name}，文件大小：{len(content)}')
            try:
                file_like = io.StringIO(content.decode("utf-8"))
            except UnicodeDecodeError:
                try:
                    file_like = io.StringIO(content.decode("gbk"))
                except UnicodeDecodeError:
                    raise Exception("文件编码不正确，请使用UTF-8或GBK编码")
            reader = csv.DictReader(file_like)
            logger.info(f'文件解析完成，导入用例参数，用例id：{case_id}，文件名：{file_name}，文件大小：{len(content)}')
            db = SessionLocal()
            for row in reader:
                try:
                    total += 1
                    enabled = row.pop("__enable", 1)
                    row_id = str(uuid.uuid4())
                    if enabled == '1' or enabled == 1:
                        enabled = True
                    else:
                        enabled = False
                    col_sort = 0
                    for key, value in row.items():
                        if value == '':
                            row[key] = None
                        buffer.append({
                            "dept_id": current_user.user.dept_id,
                            "create_by": current_user.user.user_id,
                            "update_by": current_user.user.user_id,
                            "manager": current_user.user.user_id,
                            "case_id": case_id,
                            "row_id": row_id,
                            "col_name": key,
                            "params_name": key,
                            "col_value": value,
                            "params_type": 1,
                            "enabled": enabled,
                            "sort_key": sort_key,
                            "col_sort": col_sort,
                        })
                        col_sort += 1
                except Exception as e:
                    error_count += 1
                    continue

                # 到达批量阈值，写入数据库
                if len(buffer) >= batch_size:
                    writed_line += len(buffer)
                    db.execute(insert(HrmCaseParams), buffer)
                    db.commit()
                    logger.info(f'写入数据库，导入用例参数，用例id：{case_id}，文件名：{file_name}，文件大小：{len(content)}，已写入文件行数：{total}')
                    buffer.clear()
                sort_key += 100
            # 剩余的数据写入
            if buffer:
                writed_line += len(buffer)
                db.execute(insert(HrmCaseParams), buffer)
                logger.info(f'写入数据库，导入用例参数，用例id：{case_id}，文件名：{file_name}，文件大小：{len(content)}，已写入文件行数：{total}')

            db.commit()
        finally:
            try:
                db.close()
            except Exception:
                pass

        logger.info(f"导入用例参数完成，共导入{total}条数据，{error_count}条数据导入失败")
        return {"total": total, "error_count": error_count}
