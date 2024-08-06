from module_hrm.dao.case_dao import CaseDao
from module_hrm.dao.env_dao import EnvDao
from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_vo import CaseModel
from module_hrm.entity.vo.case_vo_detail_for_run import TestCase
from module_hrm.entity.vo.env_vo import EnvModel, EnvModelForApi
from module_hrm.utils.common import key_value_dict
from sqlalchemy.orm import Session

from utils.common_util import CamelCaseUtil


class CaseInfoHandle():
    """
    用例、配置、API数据处理
    """

    def __init__(self, query_db: Session = None):
        self.query_db = query_db
        self.case_obj = None

    def __ensure_obj(self, case_obj):
        """

        """
        if not case_obj:
            return None
        if isinstance(case_obj, dict):
            case_obj = CaseModelForApi(**case_obj)
        elif isinstance(case_obj, (int, str)):
            case_orm = CaseDao.get_case_by_id(self.query_db, case_obj)
            case_obj = CaseModelForApi(**CamelCaseUtil.transform_result(case_orm))
        elif not isinstance(case_obj, CaseModelForApi):
            case_obj = CaseModelForApi(**case_obj.dict())
        return case_obj

    def from_db(self, case_obj: CaseModel | CaseModelForApi | dict | int | str):
        """
        处理数据库查出来的数据，用于运行、前端展示
        """
        self.case_obj = self.__ensure_obj(case_obj)
        return InToOut(self.query_db, self.case_obj)

    def from_page(self, case_obj: CaseModel | CaseModelForApi | dict | int | str):
        """
        处理前端来的数据，处理后用于运行、保存
        """
        self.case_obj = self.__ensure_obj(case_obj)
        return OutToIn(self.query_db, self.case_obj)


class OutToIn(object):
    def __init__(self, query_db: Session, case_obj: CaseModelForApi):
        self.query_db = query_db
        self.case_data = case_obj

    def toDb(self):
        return CaseInfoToDb(self)

    def toDebug(self, env_obj: EnvModel | str | int):
        info_obj = CaseInfoToRun(self.query_db, env_obj=env_obj, case_obj=self.case_data)
        return info_obj


class InToOut(object):
    def __init__(self, query_db: Session, case_obj: CaseModelForApi):
        self.query_db = query_db
        self.case_obj = case_obj

    def toPage(self):
        return CaseInfoToPage(self)

    def toRun(self, env_obj: EnvModel):
        return CaseInfoToRun(self.query_db, env_obj, self.case_obj)


class CaseInfoToPage(object):
    def __init__(self, data_obj: InToOut):
        self.case_obj = data_obj.case_obj

    def asApi(self) -> dict:
        return self.case_obj.model_dump(exclude_unset=True, by_alias=True)

    def asCase(self) -> dict:
        return self.asApi()

    def asConfig(self) -> dict:
        return self.asApi()


class CaseInfoToApi(object):
    def __init__(self, out_to_in: OutToIn):
        self._out_to_in = out_to_in
        step_length = len(self._out_to_in.case_data.get("request", {}).get("steps", []))
        if step_length > 1:
            raise AttributeError(
                f"api的步骤只能为1，{self._out_to_in.case_data.get('name', '')}:数据步骤太多（{step_length}）")
        self._api_data = self._out_to_in.case_data

    def data(self):
        return self._api_data


class CaseInfoToDb(object):
    def __init__(self, out_to_in: OutToIn):
        self.case_obj: CaseModelForApi = out_to_in.case_data

    def asCase(self) -> CaseModel:
        case_data = CaseModel(**self.case_obj.model_dump(by_alias=True))
        return case_data

    def asApi(self) -> CaseModel:
        return self.asCase()

    def asConfig(self) -> CaseModel:
        return self.asCase()


class CaseInfoToRun(object):
    def __init__(self, query_db: Session, env_obj: EnvModelForApi | EnvModel | str | int, case_obj: CaseModelForApi):
        self.query_db = query_db
        self.env_obj = self.__ensure_env_obj(env_obj)
        self.case_obj = case_obj

    def __ensure_env_obj(self, env) -> EnvModelForApi:
        if not env:
            raise AttributeError("请选择执行环境")
        if isinstance(env, (str, int)):
            env = EnvModelForApi(**CamelCaseUtil.transform_result(EnvDao.get_env_by_id(self.query_db, env)))
        elif isinstance(env, dict):
            env = EnvModelForApi(**env)
        elif not isinstance(env, EnvModelForApi):
            env = EnvModelForApi(**env.dict())
        return env

    def __include_handle(self) -> CaseModelForApi | None:
        include_config_id = self.case_obj.request.config.include.configId
        test_include = None
        if include_config_id:
            include_config = CaseDao.get_case_by_id(self.query_db, include_config_id)
            if include_config:
                test_include = CaseModelForApi(**CamelCaseUtil.transform_result(include_config))
        return test_include

    def __data_covert(self, data_obj: CaseModelForApi) -> TestCase:
        """
        将数据转换为测试用例的格式
        """
        # 处理数据
        test_case = data_obj
        test_case_dict = data_obj.model_dump(by_alias=True)
        test_case_dict["request"]["config"]["headers"] = key_value_dict(test_case.request.config.headers, True, True)

        test_case_dict["request"]["config"]["variables"] = key_value_dict(test_case.request.config.variables,
                                                                          checkEnable=True)
        test_case_dict["request"]["config"]["parameters"] = key_value_dict(test_case.request.config.parameters)

        teststeps_list = []
        for teststep in test_case.request.teststeps:
            step_dict = teststep.model_dump(by_alias=True)
            step_dict["variables"] = key_value_dict(teststep.variables, checkEnable=True)
            step_dict["extract"] = key_value_dict(teststep.extract)

            step_dict["request"]["headers"] = key_value_dict(teststep.request.headers, True, True)
            step_dict["request"]["data"] = key_value_dict(teststep.request.data, checkEnable=True)
            step_dict["request"]["cookies"] = key_value_dict(teststep.request.cookies)
            step_dict["request"]["params"] = key_value_dict(teststep.request.params, checkEnable=True)
            teststeps_list.append(step_dict)
        test_case_dict["request"]["teststeps"] = teststeps_list
        # TestCase.validate(test_case_dict["request"])
        test_case_obj = TestCase(**test_case_dict["request"])
        return test_case_obj

    def run_data(self) -> TestCase:
        """
        这里会创建目录和保存case数据为文件
        """
        # self._ensure_case_dir()

        env_varables = {}
        for group_name, group_value in self.env_obj.env_config.variables.items():
            env_varables.update(key_value_dict(group_value))

        include_config_obj = self.__include_handle()
        include_config_obj_for_run =None
        if include_config_obj:
            include_config_obj_for_run = self.__data_covert(include_config_obj)

        test_case_obj = self.__data_covert(self.case_obj)
        test_case_obj.case_id = self.case_obj.case_id

        # 处理变量， 优先级： 环境变量 < include < case
        if include_config_obj_for_run:
            env_varables.update(include_config_obj_for_run.config.variables)
        env_varables.update(test_case_obj.config.variables)
        test_case_obj.config.variables = env_varables

        return test_case_obj

    def debug_data(self) -> TestCase:
        """
        用测试用例入库的数据转成测试用的数据
        """
        return self.run_data()

    def case_data(self) -> TestCase:
        """
        这里只是处理数据，不会处理文件目录
        """
        return self.run_data()
