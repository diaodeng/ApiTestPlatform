## 调试用接口数据
from fastapi import APIRouter, Request

from utils.response_util import ResponseUtil

testController = APIRouter(prefix='/hrm/test')


@testController.get("/get")
async def get_hrm_test(request: Request,
                       param1=None
                       ):
    try:
        # 获取分页数据
        data = {"url": request.url,
                "method": request.method,
                "headers": request.headers,
                "cookies": request.cookies,
                "body": request.body,
                "queryParams": request.query_params,
                "pathParams": request.path_params,
                "data": {"name": "name",
                         "value": "value",
                         "1234": "1234",
                         "5678": 5678,
                         "map": {
                                 "name": "name",
                                 "value": "value",
                                 "int_str": "1122",
                                 "int": 1122,
                                 "float_str": "1122.01",
                                 "float": 1122.01,
                             },
                         "row": [
                             {
                                 "name": "name",
                                 "value": "value",
                                 "1234": "1122",
                                 "5678": 1122,
                             },
                             {
                                 "name": "name",
                                 "value": "value",
                                 "1234": "1133",
                                 "5678": 1133,
                             }
                         ]
                         }

                }
        result = ResponseUtil.success(dict_content=data)
        return result
    except Exception as e:
        return ResponseUtil.error(msg=str(e))


@testController.post("/post")
def add_hrm_test(request: Request):
    try:
        data = {"url": request.url,
                "method": request.method,
                "headers": request.headers,
                "cookies": request.cookies,
                "body": request.body,
                "queryParams": request.query_params,
                "pathParams": request.path_params,
                "data": {"name": "name",
                         "value": "value",
                         "1234": "1234",
                         "5678": 5678,
                         "row": [
                             {
                                 "name": "name",
                                 "value": "value",
                                 "1234": "1122",
                                 "5678": 1122,
                             },
                             {
                                 "name": "name",
                                 "value": "value",
                                 "1234": "1133",
                                 "5678": 1133,
                             }
                         ]
                         }
                }
        result = ResponseUtil.success(dict_content=data)
        return result
    except Exception as e:
        return ResponseUtil.error(msg=str(e))


@testController.post("/put")
async def copy_hrm_test(request: Request):
    try:

        return ResponseUtil.success(msg="")

    except Exception as e:
        return ResponseUtil.error(msg=str(e))


@testController.put("/delete")
async def edit_hrm_test(request: Request):
    try:

        return ResponseUtil.success(msg="")

    except Exception as e:
        return ResponseUtil.error(msg=str(e))
