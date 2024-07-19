import datetime
import importlib.util
import sys

from module_hrm.dao.debugtalk_dao import *
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.exceptions import DebugtalkRepeatedError
from module_hrm.utils.util import find_source_repeat, get_func_map, get_func_doc_map
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.snowflake import snowIdWorker
from sqlalchemy import or_


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
        获取debugtalk列表信息service
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
            page_object.debugtalk_id = snowIdWorker.get_id()
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
                    DebugTalkDao.delete_debugtalk_dao(query_db, DebugTalkModel(projectId=project_id,
                                                                               updateTime=page_object.update_time,
                                                                               updateBy=page_object.update_by))
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

    @classmethod
    def debugtalk_source_for_caseid_or_projectid(cls, query_db: Session, case_ids=[], project_ids=[]):
        """
        根据用例ID或者项目名称查询相关的所有debugtalk，并将所有debugtalk合并为一个文件；
        合并过程中不同文件如果存在相同名称的方法会抛出异常：ApiManager.exceptions.DebugtalkRepeatedError
        """
        # 校验多个debugtalk文件中有没有相同的类和方法,有重复的则中断执行
        all_source = ["import logging", "logger = logging.getLogger('HttpRunnerManager')"]

        common_debugtalk = query_db.query(HrmDebugTalk).filter(
            or_(HrmDebugTalk.debugtalk_id == -1, HrmDebugTalk.debugtalk_id == None)).first().debugtalk

        if common_debugtalk:
            all_source.append(common_debugtalk)

        if case_ids:
            case_projects = query_db.query(HrmCase).filter(HrmCase.case_id.in_(case_ids)).group_by(HrmCase.project_id)

            if case_projects:
                project_ids = project_ids.extend([case_project.project_id for case_project in case_projects])

        if project_ids:
            debugtalks = query_db.query(HrmDebugTalk).filter(
                HrmDebugTalk.project_id.in_(project_ids)).all()
            all_source.extend([debugtalk.debugtalk for debugtalk in debugtalks])

        repeated_symbols = find_source_repeat(all_source)
        if repeated_symbols:
            print(repeated_symbols)
            raise DebugtalkRepeatedError(f"debugtalk中存在重复的方法或者类：{','.join(repeated_symbols)}")

        # 合并debugtalk文件源码
        # debugtalk_data = ""
        # for debugtalk in debugtalks:
        #     debugtalk_data += f"{debugtalk[0]}\n"

        debugtalks_data = "\n".join(all_source)
        return debugtalks_data


class DebugTalkHandler:
    def __init__(self, debugtalk_source: str):
        """
        :param case_ids:
        :param project_names:
        """
        self.debugtalks_data: str = debugtalk_source
        self.module_name = None

    def source(self):
        return self.debugtalks_data

    def _import_debugtalk(self, user=None):
        self.module_name = f'Debugtalk{user or ""}{int(datetime.datetime.now().timestamp() * 100000)}'
        logger.info(f"开始载入模块 {self.module_name}")
        # 创建模块规范对象
        spec = importlib.util.spec_from_loader(self.module_name, loader=None)

        # 创建模块对象
        module = importlib.util.module_from_spec(spec)

        # 将数据流中的代码加载到模块对象中
        exec(self.debugtalks_data, module.__dict__)

        # 将模块对象添加到 sys.modules 中，以便后续导入
        sys.modules[self.module_name] = module
        return module

    def func_map(self, user=None) -> dict:
        module = self._import_debugtalk(user)
        return get_func_map(module)

    def func_doc_map(self, user=None, filter=None) -> dict:
        module = self._import_debugtalk(user)
        return get_func_doc_map(module, filter=filter)

    def del_import(self):
        if self.module_name:
            del sys.modules[self.module_name]
            logger.info(f"成功卸载模块 {self.module_name}")
