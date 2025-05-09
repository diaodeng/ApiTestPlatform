import importlib.util
import importlib.util
import sys
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from module_hrm.dao.debugtalk_dao import DebugTalkDao
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.do.debugtalk_do import HrmDebugTalk
from module_hrm.entity.vo.case_vo import CaseRunModel, ProjectDebugtalkInfoModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.debugtalk_vo import DebugTalkQueryModel, DeleteDebugTalkModel, DebugTalkModel
from module_hrm.exceptions import DebugtalkError
from module_hrm.utils import debugtalk_common
from module_hrm.utils.util import get_func_map, get_func_doc_map
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.snowflake import snowIdWorker


class DebugTalkService:
    """
    DebugTalk管理模块服务层
    """

    @classmethod
    def get_debugtalk_list_services(cls, query_db: Session, page_object: DebugTalkQueryModel, data_scope_sql: str):
        """
        获取debugtalk列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: DebugTalk列表信息对象
        """
        debugtalk_list_result = DebugTalkDao.get_debugtalk_list(query_db, page_object, data_scope_sql)
        if page_object.is_page:
            case_list_result = PageResponseModel(
                **{
                    **debugtalk_list_result.model_dump(by_alias=True),
                    'rows': [{**row[0], **row[1]} for row in debugtalk_list_result.rows]
                }
            )
        else:
            case_list_result = []
            if debugtalk_list_result:
                case_list_result = [{**row[0], **row[1]} for row in debugtalk_list_result]
        return case_list_result

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
    def edit_debugtalk_services(cls, query_db: Session, debugtalk_object: DebugTalkModel):
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
    def debugtalk_detail_services(cls, query_db: Session, id: int):
        """
        获取DebugTalk详细信息service
        :param query_db: orm对象
        :param debugtalk_id: DebugTalkid / project_id
        :return: DebugTalkid对应的信息
        """
        debugtalk = DebugTalkDao.get_debugtalk_detail_by_id(query_db, id=id)
        result = DebugTalkModel(**CamelCaseUtil.transform_result(debugtalk))

        return result

    @classmethod
    def debugtalk_source(cls, query_db: Session, project_id: int = None, case_id: int = None) -> tuple:
        """
        根据项目ID或者caseId查询debugtalk
        project_id and case_id，优先使用projectId,不会使用case_id
        project_id or case_id，根据给的ID查询debugtalk
        not any([project_id, case_id])，只返回公共的debugtalk内容


        :param query_db:
        :param project_id:
        :param case_id:
        :return: tuple(common_debugtalk, project_debugtalk),其中project_debugtalk可能为None
        """

        common_debugtalk = cls.commondebugtalk_source(query_db=query_db)

        project_debugtalk = cls.project_debugtalk_source(query_db=query_db, project_id=project_id, case_id=case_id)

        return common_debugtalk, project_debugtalk

    @classmethod
    def commondebugtalk_source(cls, query_db: Session) -> str:

        common_debugtalk = query_db.query(HrmDebugTalk).filter(
            or_(HrmDebugTalk.project_id == -1, HrmDebugTalk.project_id == None)).first()
        common_debugtalk = common_debugtalk.debugtalk if common_debugtalk else ""
        return common_debugtalk

    @classmethod
    def project_debugtalk_source(cls, query_db: Session, project_id: int, case_id=None) -> str:
        project_debugtalk = ""
        if not project_id and case_id:
            project_info = query_db.query(HrmCase).filter(HrmCase.case_id == case_id).first()
            project_id = project_info.project_id if project_info else None
        if project_id:
            project_debugtalk = query_db.query(HrmDebugTalk).filter(
                HrmDebugTalk.project_id == project_id).first()
            project_debugtalk = project_debugtalk.debugtalk if project_debugtalk else ""

        return project_debugtalk

    @classmethod
    def project_debugtalk_map(cls, query_db: Session, project_id: int = None, case_id: int = None,
                              run_info: CaseRunModel = None) -> ProjectDebugtalkInfoModel:
        project_debugtalk_set = run_info.project_debugtalk_set.get(project_id, None)
        if project_debugtalk_set:
            return project_debugtalk_set
        else:
            try:
                common_debugtalk_source = cls.commondebugtalk_source(query_db)
                project_debugtalk_source = cls.project_debugtalk_source(query_db, project_id, case_id)
                debugtalk_obj = DebugTalkHandler(project_debugtalk_source, common_debugtalk_source,
                                                 project_id or case_id)
                pdm = ProjectDebugtalkInfoModel()
                pdm.func_map = debugtalk_obj.func_map(run_info.runner)
                pdm.module_instance = debugtalk_obj.mudule_instances
                pdm.module_names = debugtalk_obj.module_names
                run_info.project_debugtalk_set[project_id] = pdm
                return pdm
            except Exception as e:
                logger.error(f"debugtalk加载异常:{e}")
                raise DebugtalkError(f"debugtalk加载异常:{e}")


class DebugTalkHandler:
    def __init__(self, debugtalk_source: str, common_debugtalk_source: str = None, project_id: int = ""):
        """
        :param debugtalk_source:
        :param common_debugtalk_source:
        """
        self.common_debugtalk_source: str = common_debugtalk_source
        self.debugtalks_data: str = debugtalk_source
        self.project_id: int = project_id
        self.module_names = []
        self.mudule_instances = []

    def source(self):
        return self.debugtalks_data

    def _import_debugtalk(self, debugtalk_source, user=None):
        module_name = f'Debugtalk_{user or ""}_{self.project_id}_{int(datetime.now().timestamp() * 100000)}'
        self.module_names.append(module_name)
        logger.info(f"开始载入模块 {module_name}")
        # 创建模块规范对象
        spec = importlib.util.spec_from_loader(module_name, loader=None)

        # 创建模块对象
        module = importlib.util.module_from_spec(spec)
        self.mudule_instances.append(module)

        # 将数据流中的代码加载到模块对象中
        if debugtalk_source is None:
            debugtalk_source = ""
        exec(debugtalk_source, module.__dict__)
        setattr(module, "logger", logger)

        # 将模块对象添加到 sys.modules 中，以便后续导入
        sys.modules[module_name] = module
        return module

    def func_map(self, user=None) -> dict:
        default_debugtalk = get_func_map(debugtalk_common)

        module = self._import_debugtalk(self.common_debugtalk_source, user)
        common_debugtalk = get_func_map(module)

        project_debugtalk_module = self._import_debugtalk(self.debugtalks_data, user)
        project_debugtalk = get_func_map(project_debugtalk_module)

        default_debugtalk.update(common_debugtalk)
        default_debugtalk.update(project_debugtalk)

        return default_debugtalk

    def func_doc_map(self, user=None, filter=None) -> dict:
        default_debugtalk = get_func_doc_map(debugtalk_common, filter)

        if self.common_debugtalk_source:
            module = self._import_debugtalk(self.common_debugtalk_source, user)
            common_debugtalk = get_func_doc_map(module, filter)
            default_debugtalk.update(common_debugtalk)

        if self.debugtalks_data:
            project_debugtalk_module = self._import_debugtalk(self.debugtalks_data, user)
            project_debugtalk = get_func_doc_map(project_debugtalk_module, filter)
            default_debugtalk.update(project_debugtalk)

        return default_debugtalk

    def del_import(self):
        for module_name in self.module_names:
            self.del_module(module_name)

    @classmethod
    def del_module(cls, module_name):
        if module_name in sys.modules:
            del sys.modules[module_name]
            logger.info(f"成功卸载模块 {module_name}")
