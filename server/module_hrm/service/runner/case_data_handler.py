from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_vo import CaseModel
from module_hrm.entity.vo.case_vo_detail_for_run import TestCase
from module_hrm.entity.vo.env_vo import EnvModel, EnvModelForApi
from module_hrm.utils.common import key_value_dict


class CaseInfoHandle():
    """
    用例、配置、API数据处理
    """

    def __init__(self, case_obj: CaseModel | CaseModelForApi | dict):
        self.case_obj = self.__ensure_obj(case_obj)

    def __ensure_obj(self, case_obj):
        """

        """
        if not isinstance(case_obj, CaseModelForApi):
            case_obj = CaseModelForApi(**case_obj)
        return case_obj

    def from_db(self, case_obj: CaseModel | CaseModelForApi | dict = {}):
        """
        处理数据库查出来的数据，用于运行、前端展示
        """
        if case_obj:
            case_obj = self.__ensure_obj(case_obj)
        else:
            case_obj = self.case_obj
        return InToOut(case_obj)

    def from_page(self, case_obj: CaseModel | CaseModelForApi | dict = {}):
        """
        处理前端来的数据，处理后用于运行、保存
        """
        if case_obj:
            case_obj = self.__ensure_obj(case_obj)
        else:
            case_obj = self.case_obj
        return OutToIn(case_obj)


class OutToIn(object):
    def __init__(self, case_obj: CaseModelForApi):
        self.case_data = case_obj

    def toDb(self):
        return CaseInfoToDb(self)

    def toDebug(self, env_obj: EnvModel):
        info_obj = CaseInfoToRun(env_obj=env_obj, case_obj=self.case_data)
        return info_obj


class InToOut(object):
    def __init__(self, case_obj: CaseModelForApi):
        self.case_obj = case_obj

    def toPage(self):
        return CaseInfoToPage(self)

    def toRun(self, env_obj: EnvModel):
        return CaseInfoToRun(env_obj, self.case_obj)


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
    def __init__(self, env_obj: EnvModelForApi, case_obj: CaseModelForApi):

        self.env_obj = env_obj
        self.case_obj = case_obj

    def run_data(self) -> TestCase:
        """
        这里会创建目录和保存case数据为文件
        """
        # self._ensure_case_dir()
        env_varables = {}
        for group_name, group_value in self.env_obj.env_config.variables.items():
            env_varables.update(key_value_dict(group_value))

        test_case = self.case_obj
        test_case_dict = self.case_obj.model_dump(by_alias=True)
        test_case_dict["request"]["config"]["headers"] = key_value_dict(test_case.request.config.headers, True, True)

        env_varables.update(key_value_dict(test_case.request.config.variables, checkEnable=True))
        test_case_dict["request"]["config"]["variables"] = env_varables
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
        TestCase.validate(test_case_dict["request"])
        return TestCase(**test_case_dict["request"])

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

