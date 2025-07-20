## 调试用接口数据
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi import Depends
from fastapi import Query, Body, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.entity.vo.mock_vo import MockPageQueryModel
from module_hrm.service.case_service import CaseService
from utils.common_util import bytes2file_response
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

mockController = APIRouter(prefix='/hrm')


@mockController.api_route('/mock/{mock_path:path}', methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def mock_test(request: Request,
                    mock_path: str,
                    query: str = Query(default=None),
                    body: dict = Body(default=None),
                    content_type: str = Header(default=None)
                    ):
    method = request.method
    headers = dict(request.headers)
    query_params = dict(request.query_params)
    path_params = dict(request.path_params)

    try:
        body_data = await request.json()
    except:
        body_data = {}

    req = {
        "method": method,
        "path": mock_path,
        "query": query_params,
        "path_params": path_params,
        "body": body_data,
        "headers": headers,
        "content_type": content_type,
        "body2": body,
        "query2": query,
    }
    return ResponseUtil.success(msg='success', data=req)



class Item(BaseModel):
    name: str
    price: float

async def common_parameters(
    # item_id: int = Path(..., gt=0),
    q: str = Query(None, min_length=3),
    x_token: str = Header(..., alias="X-Token")
):
    return {"q": q, "x_token": x_token}


@mockController.api_route("/test", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def get_hrm_test(request: Request,
                       commons: dict = Depends(common_parameters),
                       item: Optional[Item] = Body(None)
                       ):
    try:
        method = request.method
        # 获取分页数据
        data = {"url": request.url,
                "method": method,
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
                         },
                **commons

                }

        if method in ["POST", "PUT"]:
            if not item:
                return {"error": "Missing request body"}
            data["item"] = item.model_dump()

            # 处理DELETE的特殊逻辑
        if method == "DELETE":
            data["status"] = "deleted"

        result = ResponseUtil.success(dict_content=data)
        return result
    except Exception as e:
        return ResponseUtil.error(msg=str(e))



@mockController.get("/mockManager/ruleList", response_model=PageResponseModel)
async def get_mock_rule_list(request: Request,
                            page_query: MockPageQueryModel = Depends(MockPageQueryModel.as_query),
                            query_db: Session = Depends(get_db),
                            current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                            data_scope_sql: str = Depends(GetDataScope('HrmCase', user_alias='manager'))
                            ):
    try:
        # 获取分页数据
        if not page_query.type:
            raise ValueError("参数错误")
        page_query.manager = current_user.user.user_id
        page_query_result = CaseService.get_case_list_services(query_db, page_query, is_page=True, data_scope_sql=data_scope_sql)
        logger.info('获取成功')
        data = ResponseUtil.success(model_content=page_query_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/addRule", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:add'))])
@log_decorator(title='用例管理', business_type=1)
async def add_hrm_case(request: Request,
                       add_case: AddCaseModel,
                       query_db: Session = Depends(get_db),
                       current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        if not add_case.type:
            raise ValueError("参数错误")
        if not add_case.case_name:
            raise ValueError("用例名不能为空")
        add_case.manager = current_user.user.user_id
        add_case.create_by = current_user.user.user_name
        add_case.update_by = current_user.user.user_name
        add_case.dept_id = current_user.user.dept_id
        add_module_result = CaseService.add_case_services(query_db, add_case)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(data=add_module_result.result, msg=add_module_result.message)
        else:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(data=add_module_result.result, msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/copyRule", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:copy'))])
@log_decorator(title='用例复制', business_type=1)
async def copy_hrm_case(request: Request,
                        add_case: AddCaseModel,
                        query_db: Session = Depends(get_db),
                        current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_case.manager = current_user.user.user_id
        add_case.create_by = current_user.user.user_name
        add_case.update_by = current_user.user.user_name
        add_module_result = CaseService.copy_case_services(query_db, add_case)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(msg=add_module_result.message)
        else:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.put("/mockManager/modifyRule", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:edit'))])
@log_decorator(title='用例管理', business_type=2)
async def edit_hrm_case(request: Request,
                        edit_module: CaseModel,
                        query_db: Session = Depends(get_db),
                        current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        if not edit_module.case_name:
            raise ValueError("用例名不能为空")
        edit_module.update_by = current_user.user.user_name
        edit_module.update_time = datetime.now()
        edit_module_result = CaseService.edit_case_services(query_db, edit_module, current_user)
        if edit_module_result.is_success:
            logger.info(edit_module_result.message)
            return ResponseUtil.success(msg=edit_module_result.message)
        else:
            logger.warning(edit_module_result.message)
            return ResponseUtil.failure(msg=edit_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/ruleStatus", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:edit'))])
@log_decorator(title='用例管理', business_type=2)
async def change_status(request: Request,
                        edit_module: CaseModel,
                        query_db: Session = Depends(get_db),
                        current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:

        new_case_model = CaseModel()
        new_case_model.status = edit_module.status
        new_case_model.case_id = edit_module.case_id
        new_case_model.update_by = current_user.user.user_name
        new_case_model.update_time = datetime.now()
        edit_module_result = CaseService.edit_case_services(query_db, new_case_model, current_user)
        if edit_module_result.is_success:
            logger.info(edit_module_result.message)
            return ResponseUtil.success(msg=edit_module_result.message)
        else:
            logger.warning(edit_module_result.message)
            return ResponseUtil.failure(msg=edit_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.delete("/mockManager/rule/{ids}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:remove'))])
@log_decorator(title='用例管理', business_type=3)
async def delete_hrm_case(request: Request,
                          ids: str,
                          query_db: Session = Depends(get_db),
                          current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                          ):
    try:
        delete_module = DeleteCaseModel(caseIds=ids)
        delete_module_result = CaseService.delete_case_services(query_db, delete_module, current_user)
        if delete_module_result.is_success:
            logger.info(delete_module_result.message)
            return ResponseUtil.success(msg=delete_module_result.message)
        else:
            logger.warning(delete_module_result.message)
            return ResponseUtil.failure(msg=delete_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.get("/mockManager/rule/{case_id}",
                    response_model=CaseModel,
                    dependencies=[Depends(CheckUserInterfaceAuth(['hrm:case:detail', "hrm.case:edit"],
                                                                 False))])
async def query_detail_hrm_case(request: Request, case_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_result = CaseService.case_detail_services(query_db, case_id)
        logger.info(f'获取case_id为{case_id}的信息成功')
        return ResponseUtil.success(data=detail_result.model_dump(by_alias=True))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/rule/export", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:export'))])
@log_decorator(title='用例管理', business_type=5)
async def export_hrm_case_list(request: Request,
                               page_query: CasePageQueryModel = Depends(CasePageQueryModel.as_form),
                               query_db: Session = Depends(get_db),
                               data_scope_sql: str = Depends(GetDataScope('HrmCase', user_alias='manager'))
                               ):
    try:
        # 获取全量数据
        query_result = CaseService.get_case_list_services(query_db, page_query, is_page=False, data_scope_sql=data_scope_sql)
        export_result = CaseService.export_case_list_services(query_result)
        logger.info('导出成功')
        return ResponseUtil.streaming(data=bytes2file_response(export_result))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))