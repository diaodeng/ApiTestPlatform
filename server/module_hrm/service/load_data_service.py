import json

import pymysql

from module_hrm.entity.vo.api_vo import ApiModel
from module_hrm.entity.vo.case_vo import CaseModel
from module_hrm.entity.vo.debugtalk_vo import DebugTalkModel
from module_hrm.entity.vo.env_vo import EnvModel
from module_hrm.entity.vo.module_vo import ModuleModel
from module_hrm.entity.vo.project_vo import ProjectModel
from module_hrm.utils.common import dict2list, list_dict2list


class OldDatabase():
    def __init__(self):
        self.host = "1882q56p71.51mypc.cn"
        self.port = 8723
        self.user = "root"
        self.password = "QLXo7WHPCKHBaG7gHMji"
        self.database = "hrm4"
        self.connect = pymysql.connect(host=self.host,
                                       port=self.port,
                                       user=self.user,
                                       password=self.password,
                                       database=self.database,
                                       charset='utf8')

    def __select(self, sql: str):
        cursor = self.connect.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        return result

    def close(self):
        self.connect.close()

    def api(self):
        return self.__select("select * from ApiInfo")

    def env(self):
        return self.__select("select * from EnvInfo")

    def project(self):
        return self.__select("select * from ProjectInfo")

    def project_by_name(self, name):
        return self.__select(f"select * from ProjectInfo where project_name = '{name}'")

    def debugtalk(self):
        return self.__select("select * from DebugTalk")

    def module(self):
        return self.__select("select * from ModuleInfo")

    def case(self):
        return self.__select("select * from TestCaseInfo")

    def suite(self):
        return self.__select("select * from TestSuite")

    def suite_detail(self):
        return self.__select("select * from TestSuiteDetail")


class NewDatabase():
    def __init__(self):
        self.host = "1882q56p71.51mypc.cn"
        self.port = 59306
        self.user = "root"
        self.password = "iv3TVg50DW3mBb5DqVNT"
        self.database = "apitest"
        self.connect = pymysql.connect(host=self.host,
                                       port=self.port,
                                       user=self.user,
                                       password=self.password,
                                       database=self.database,
                                       charset='utf8')

    def __select(self, sql: str):
        cursor = self.connect.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        return result

    def close(self):
        self.connect.close()

    def api(self, datas):
        cursor = self.connect.cursor()
        new_datas = []
        for data in datas:
            new_data = []
            for item in data:
                if isinstance(item, str):
                    new_item = self.connect.escape_string(item)
                else:
                    new_item = item
                new_data.append(new_item)
            new_datas.append(tuple(new_data))
            print(new_datas)
        cursor.executemany(
            """insert into hrm_api_info(api_id,type,name,path,interface,parent_id,author,request_info,request_data_demo,response_data_demo,desc,create_by,update_by,create_time,update_time) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            new_datas)
        self.connect.commit()
        self.connect.close()


class CoverData():
    def __init__(self):
        pass

    def api(self, datas):
        new_datas = []
        user = "panda"
        for data in datas:
            api_model = ApiModel()
            api_model.api_id = data[0]
            api_model.create_time = data[1]
            api_model.update_time = data[2]
            api_model.type = 11 if data[3] == 1 else 10
            api_model.api_type = 4 if data[3] == 1 else 1
            api_model.name = data[4]
            api_model.path = data[5]
            api_model.interface = data[6]
            api_model.parent_id = data[7]
            api_model.author = user
            api_model.manager = 4

            if data[10]:
                request_info_json = eval(data[10])
                new_request_info = {}
                new_request_info.setdefault("config", {})["headers"] = dict2list(
                    request_info_json["config"].get("headers", {}))
                new_request_info.setdefault("config", {})["parameters"] = dict2list(
                    request_info_json["config"].get("parameters", {}))
                new_request_info.setdefault("config", {})["variables"] = list_dict2list(
                    request_info_json["config"].get("variables", []))
                new_request_info["teststeps"] = request_info_json["steps"]
                for step in new_request_info["teststeps"]:
                    step["request"]["headers"] = dict2list(step["request"].get("headers", {}))
                    step["request"]["cookies"] = dict2list(step["request"].get("cookies", {}))
                    step["request"]["data"] = dict2list(step["request"].get("data", {}))
                    step["request"]["params"] = dict2list(step["request"].get("params", {}))

                    step["variables"] = list_dict2list(step.get("variables", []))
                    step["extract"] = list_dict2list(step.get("extract", []))
                    old_validates = step["validate"]
                    new_validates = []
                    for validate in old_validates:
                        if "valicustom" in validate:
                            for cv in validate["valicustom"]:
                                new_validate = {}
                                new_validate["assert"] = cv.get("comparator", "")
                                new_validate["check"] = cv.get("check", "")
                                new_validate["expect"] = cv.get("expected", "")
                                new_validate["type"] = "string"
                                new_validate["desc"] = ""
                                new_validates.append(new_validate)
                        elif validate.get("comparator", ""):
                            new_validate = {}
                            new_validate["assert"] = validate.get("comparator", "")
                            new_validate["check"] = validate.get("check", "")
                            new_validate["expect"] = validate.get("expected", "")
                            new_validate["type"] = "string"
                            new_validate["desc"] = ""
                            new_validates.append(new_validate)
                    step["validate"] = new_validates

                    old_reqeust = step["request"]
                    old_reqeust.pop("dataType")
                    step["request"] = old_reqeust
                    old_include = step["include"]

                    step_include_id = step.get("include", {}).get("config", {}).get("id", None)
                    step_include_id = int(step_include_id) if step_include_id else step_include_id

                    step["include"] = {"config": {"id": step_include_id,
                                                  "allow_extend": False,
                                                  "name": ""
                                                  }}

                    if api_model.path == "${rdms_dubbo_uri}" or api_model.path == "$rdms_dubbo_uri":
                        step["include"] = {"config": {"id": 220,
                                                      "allow_extend": False,
                                                      "name": ""
                                                      }}
                        step["request"]["url"] = "https://${env}mockserver.rta-os.com/dubboJump"

                        new_json = {}
                        old_json = step["request"]["json"]
                        new_json["className"] = old_json["service"]
                        new_json["methodName"] = old_json["methodName"]
                        api_model.interface = new_json["methodName"]
                        new_json["types"] = old_json["paramType"]
                        new_json["params"] = []
                        for param in old_json["params"]:
                            try:
                                new_param = json.loads(param)
                                if isinstance(new_param, (dict, tuple, list)):
                                    new_json["params"].append(new_param)
                                else:
                                    new_json["params"].append(param)
                            except Exception as e:
                                new_json["params"].append(param)
                        step["request"]["json"] = json.dumps(new_json, ensure_ascii=False, indent=4)
                    elif api_model.path == "https://${env}mockserver.rta-os.com/dubboJump":
                        api_model.interface = step["request"]["json"]["methodName"]
                        step["request"]["json"] = json.dumps(step["request"]["json"], ensure_ascii=False, indent=4)
                    else:
                        step["request"]["json"] = json.dumps(step["request"].get("json", {}), ensure_ascii=False,
                                                             indent=4)
                    step["step_type"] = 1
                api_model.request_info = new_request_info
            api_model.request_data_demo = data[11]
            api_model.response_data_demo = data[12]
            api_model.desc = data[13]
            api_model.create_by = user
            api_model.update_by = user

            if api_model.path == "${rdms_dubbo_uri}" or api_model.path == "$rdms_dubbo_uri":
                api_model.path = "https://${env}mockserver.rta-os.com/dubboJump"

            new_datas.append(api_model)
            # data_dict = api_model.model_dump(by_alias=True)
            # print(data_dict)
            # data_dict.pop("id", None)
            # print(data_dict.values())
            # new_datas.append(tuple(data_dict.values()))
        return new_datas

    def env(self, datas):
        new_datas = []
        user = "panda"
        for data in datas:
            env_model = EnvModel()
            env_model.env_id = data[0]
            env_model.env_name = data[3]
            env_model.env_url = data[4]

            env_config = {"variables": []}
            if data[5]:
                new_env_vars = []
                env_var = eval(data[5])
                for i in env_var:
                    new_env_var = {}
                    new_env_var["key"] = i["group_name"]
                    new_env_var["value"] = []
                    for j in i["vars"]:
                        new_var = {}
                        new_var["key"] = j["key"]
                        new_var["value"] = j["value"]
                        new_var["desc"] = j["desc"]
                        new_var["enable"] = True
                        new_var["type"] = 'string'
                        new_env_var["value"].append(new_var)
                    new_env_vars.append(new_env_var)
                env_config["variables"] = new_env_vars

            env_model.env_config = env_config
            env_model.create_by = user

            new_datas.append(env_model)

        return new_datas

    def project(self, datas):
        new_datas = []
        user = "panda"
        for data in datas:
            env_model = ProjectModel()
            env_model.project_id = data[0]
            env_model.project_name = data[3]
            env_model.responsible_name = data[4]
            env_model.test_user = data[5]
            env_model.dev_user = data[6]
            env_model.publish_app = data[7]

            env_model.update_by = user
            env_model.create_by = user

            new_datas.append(env_model)

        return new_datas

    def debugtalk(self, datas):
        new_datas = []
        user = "panda"
        for data in datas:
            env_model = DebugTalkModel()
            env_model.debugtalk_id = data[0]
            env_model.debugtalk = data[3]
            env_model.project_id = data[4]

            env_model.update_by = user
            env_model.create_by = user

            new_datas.append(env_model)

        return new_datas

    def module(self, datas):
        new_datas = []
        user = "panda"
        for data in datas:
            env_model = ModuleModel()
            env_model.module_id = data[0]
            env_model.module_name = data[3]
            env_model.test_user = data[4]
            env_model.simple_desc = data[5]
            env_model.project_id = data[7]

            env_model.update_by = user
            env_model.create_by = user
            env_model.create_time = data[1]
            env_model.update_time = data[2]

            new_datas.append(env_model)

        return new_datas

    def case(self, datas):
        sql_connect = OldDatabase()
        new_datas = []
        user = "panda"
        for data in datas:
            api_model = CaseModel()
            api_model.case_id = data[0]
            api_model.case_name = data[4]
            api_model.type = 3 if data[3] == 1 else 4
            api_model.project_id = None

            pro_info = sql_connect.project_by_name(data[7])
            if pro_info:
                api_model.project_id = pro_info[0][0]

            api_model.module_id = data[11]
            api_model.notes = data[12]

            include = data[8]

            if data[10]:
                request_info_json = eval(data[10])
                new_request_info = {}

                include_data = {"config": {"id": None, "name": "", "allow_extend": False}}
                if include:
                    include = eval(include)
                    config = include["config"]
                    if config and config[0]:
                        config_id = config[0][0]
                        include_data["config"]["id"] = int(config_id) if config_id else None
                new_request_info.setdefault("config", {})["include"] = include_data

                new_request_info.setdefault("config", {})["headers"] = dict2list(
                    request_info_json["config"].get("headers", {}))
                new_request_info.setdefault("config", {})["parameters"] = dict2list(
                    request_info_json["config"].get("parameters", {}))
                new_request_info.setdefault("config", {})["variables"] = list_dict2list(
                    request_info_json["config"].get("variables", []))
                new_request_info["teststeps"] = request_info_json["steps"]
                for index, step in enumerate(new_request_info["teststeps"]):
                    if api_model.type == 4:
                        step = {
                            "name": "新增测试步骤",
                            "step_type": 1,
                            "step_id": "DJOcL8pv9C",
                            "request": {
                                "method": "GET",
                                "url": "",
                                "params": [],
                                "headers": [],
                                "json": {},
                                "data": [],
                                "cookies": [],
                                "timeout": 120.0,
                                "allow_redirects": False,
                                "verify": False,
                                "upload": {}
                            },
                            "include": {
                                "config": {
                                    "id": "",
                                    "name": "",
                                    "allow_extend": True
                                }
                            },
                            "testcase": None,
                            "variables": [],
                            "setup_hooks": [],
                            "teardown_hooks": [],
                            "extract": [],
                            "export": [],
                            "validate": [],
                            "validate_script": [],
                            "retry_times": 0,
                            "retry_interval": 0,
                            "thrift_request": None,
                            "sql_request": None,
                            "think_time": {
                                "strategy": "",
                                "limit": 0
                            },
                            "result": {}
                        }
                        new_request_info["teststeps"][index] = step
                        continue
                    step["request"]["headers"] = dict2list(step["request"].get("headers", {}))
                    step["request"]["cookies"] = dict2list(step["request"].get("cookies", {}))
                    step["request"]["data"] = dict2list(step["request"].get("data", {}))
                    step["request"]["params"] = dict2list(step["request"].get("params", {}))

                    step["variables"] = list_dict2list(step.get("variables", []))
                    step["extract"] = list_dict2list(step.get("extract", []))
                    old_validates = step["validate"]
                    new_validates = []
                    for validate in old_validates:
                        if "valicustom" in validate:
                            for cv in validate["valicustom"]:
                                new_validate = {}
                                new_validate["assert"] = cv.get("comparator", "")
                                new_validate["check"] = cv.get("check", "")
                                new_validate["expect"] = cv.get("expected", "")
                                new_validate["type"] = "string"
                                new_validate["desc"] = ""
                                new_validates.append(new_validate)
                        elif validate.get("comparator", ""):
                            new_validate = {}
                            new_validate["assert"] = validate.get("comparator", "")
                            new_validate["check"] = validate.get("check", "")
                            new_validate["expect"] = validate.get("expected", "")
                            new_validate["type"] = "string"
                            new_validate["desc"] = ""
                            new_validates.append(new_validate)
                    step["validate"] = new_validates

                    old_reqeust = step["request"]
                    old_reqeust.pop("dataType", None)
                    step["request"] = old_reqeust
                    old_include = step.get("include", {})

                    step_include_id = step.get("include", {}).get("config", {}).get("id", None)
                    step_include_id = int(step_include_id) if step_include_id else step_include_id

                    step["include"] = {"config": {"id": step_include_id,
                                                  "allow_extend": False,
                                                  "name": ""
                                                  }}
                    if step["request"]["url"] == "${rdms_dubbo_uri}" or step["request"]["url"] == "$rdms_dubbo_uri":
                        step["include"] = {"config": {"id": 220,
                                                      "allow_extend": False,
                                                      "name": ""
                                                      }}
                        step["request"]["url"] = "https://${env}mockserver.rta-os.com/dubboJump"

                        new_json = {}
                        old_json = step["request"]["json"]
                        new_json["className"] = old_json["service"]
                        new_json["methodName"] = old_json["methodName"]
                        new_json["types"] = old_json["paramType"]
                        new_json["params"] = []
                        for param in old_json["params"]:
                            try:
                                new_param = json.loads(param)
                                if isinstance(new_param, (dict, tuple, list)):
                                    new_json["params"].append(new_param)
                                else:
                                    new_json["params"].append(param)
                            except Exception as e:
                                new_json["params"].append(param)
                        step["request"]["json"] = json.dumps(new_json, ensure_ascii=False, indent=4)
                    elif step["request"]["url"] == "https://${env}mockserver.rta-os.com/dubboJump":
                        step["request"]["json"] = json.dumps(step["request"]["json"], ensure_ascii=False, indent=4)
                    else:
                        step["request"]["json"] = json.dumps(step["request"].get("json", {}), ensure_ascii=False,
                                                             indent=4)
                    step["step_type"] = 1
                api_model.request = new_request_info

            api_model.create_time = data[1]
            api_model.update_time = data[2]
            api_model.create_by = user
            api_model.update_by = user

            new_datas.append(api_model)
            # data_dict = api_model.model_dump(by_alias=True)
            # print(data_dict)
            # data_dict.pop("id", None)
            # print(data_dict.values())
            # new_datas.append(tuple(data_dict.values()))

        sql_connect.close()
        return new_datas


if __name__ == '__main__':
    pass
    # case_vo = TestCase(**case_detail)
    # print(case_vo)
    # step_vo = TStep(**case_vo.request)
    # print(step_vo)
