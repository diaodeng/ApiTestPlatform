## 调试用接口数据
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi import Depends
from fastapi import Query, Body, Header, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.dao.mock_dao import MockRuleDao
from module_hrm.entity.vo.mock_vo import MockPageQueryModel, MockModel, AddMockRuleModel, DeleteMockRuleModel, \
    AddMockResponseModel, MockResponsePageQueryModel
from module_hrm.service.mock_service import MockService, MockResponseService, RuleMatcher
from utils.common_util import bytes2file_response
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

mockController = APIRouter(prefix='/hrm')


@mockController.api_route('/mock/{mock_path:path}', methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def mock_test(request: Request,
                    mock_path: str,
                    query_db: Session = Depends(get_db),
                    # query: str = Query(default=None),
                    # body = Body(default=None),
                    # content_type: str = Header(default=None)
                    ):

    try:
        try:
            try:
                body_data = await request.json()
            except:
                try:
                    form = await request.form()
                    body_data = dict(form)
                except:
                    body_data = await request.body()

            body_data = body_data.decode("utf-8") if isinstance(body_data, bytes) else body_data
        except:
            body_data = None
        logger.info(f"url: {request.url}, method: {request.method}")
        logger.info(f"request.query_params: {dict(request.query_params)}")
        logger.info(f"request.headers: {dict(request.headers)}")
        logger.info(f"body_data: {body_data}")
        setattr(request, "body_data", body_data)

        req = await RuleMatcher(request, query_db, f"/{mock_path}").match_response()

        if not req:

            method = request.method
            headers = dict(request.headers)
            query_params = dict(request.query_params)
            path_params = dict(request.path_params)
            req = {
                "method": method,
                "path": f"/{mock_path}",
                "query": query_params,
                "path_params": path_params,
                "body": body_data,
                "headers": headers,
                # "content_type": content_type,
                # "body2": body,
                # "query2": query,
                "message": "没有匹配到mock规则",
            }
            logger.info(json.dumps(req, ensure_ascii=False))
            return JSONResponse(content=req, status_code=500, media_type="application/json")
        logger.info(json.dumps(req, ensure_ascii=False))
        content_type = req.get("headers", {}).get("Content-Type")
        if not content_type:
            content_type = req.get("headers", {}).get("content-type")
        if not content_type:
            content_type = "application/json"

        # if content_type == "application/json":
        #     # req["body"] = json.loads(req.get("body"))
        # elif content_type == "application/x-www-form-urlencoded":
        #     # req["body"] = dict(req.get("body"))
        # elif content_type == "multipart/form-data":
        #     # req["body"] = dict(req.get("body"))
        # elif content_type == "text/plain":
        #     req["body"] = req.get("body")
        # elif content_type == "application/octet-stream":
        #     req["body"] = req.get("body")
        # elif content_type == "text/html":
        #     req["body"] = req.get("body")

        return Response(content=req.get("content"), media_type=content_type, headers=req.get("headers"), status_code=req.get("status_code"))
    except Exception as e:
        logger.error(f"mock测试失败, path: {mock_path}, error: {e}")
        logger.exception(e)
        return ResponseUtil.error(msg=f"mock测试失败, path: {mock_path}, error: {e}")



@mockController.api_route("/test", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def get_hrm_test(request: Request):
    try:
        method = request.method
        # 获取分页数据
        data = {"url": request.url,
                "method": method,
                "headers": request.headers,
                "cookies": request.cookies,
                "queryParams": request.query_params,
                "pathParams": request.path_params,
                }
        try:
            body_json = await request.json()
        except:
            body_json = None

        try:
            body_form = await request.form()
            body_form = dict(body_form)
        except:
            body_form = None

        try:
            body_data = await request.body()
        except:
            body_data = None

        if method in ["POST", "PUT"]:

            if not body_data and not body_json and not body_form:
                return {"error": "Missing request body"}
            data["body"] = body_data

        content_type = request.headers.get("req_content-type")
        if not content_type:
            content_type = "application/json"

        status_code = request.headers.get("req_status_code")
        if not status_code:
            status_code = 200
        else:
            status_code = int(status_code)

            # 处理DELETE的特殊逻辑
        if method == "DELETE":
            data["status"] = "deleted"

        result = Response(content=json.dumps(data), media_type=content_type, status_code=status_code)
        return result
    except Exception as e:
        return ResponseUtil.error(msg=str(e))


@mockController.get("/mockManager/ruleList", response_model=PageResponseModel)
async def get_mock_rule_list(request: Request,
                             page_query: MockPageQueryModel = Depends(MockPageQueryModel.as_query),
                             query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                             data_scope_sql: str = Depends(GetDataScope('MockRules', user_alias='manager'))
                             ):
    try:
        # 获取分页数据
        if not page_query.type:
            raise ValueError("参数错误")
        page_query.manager = current_user.user.user_id
        page_query_result = MockService.get_mock_rule_list_services(query_db, page_query, is_page=True,
                                                                    data_scope_sql=data_scope_sql)
        logger.info('获取成功')
        data = ResponseUtil.success(model_content=page_query_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/addRule", dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:addRule'))])
@log_decorator(title='mock规则管理', business_type=1)
async def add_hrm_mock_rule(request: Request,
                            add_mock_rule: AddMockRuleModel,
                            query_db: Session = Depends(get_db),
                            current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_module_result = MockService.add_mock_rule_services(query_db, add_mock_rule, current_user)
        if not add_module_result.is_success:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(data=add_module_result.result, msg=add_module_result.message)

        logger.info(add_module_result.message)
        return ResponseUtil.success(data=add_module_result.result, msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/copyRule",
                     dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:copyRule'))])
@log_decorator(title='mock规则复制', business_type=1)
async def copy_hrm_mock_rule(request: Request,
                             add_mock_rule: AddMockRuleModel,
                             query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_mock_rule.manager = current_user.user.user_id
        add_mock_rule.create_by = current_user.user.user_name
        add_mock_rule.update_by = current_user.user.user_name
        add_module_result = MockService.copy_mock_rule_services(query_db, add_mock_rule)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(msg=add_module_result.message)
        else:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.put("/mockManager/modifyRule",
                    dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:editRule'))])
@log_decorator(title='mock规则管理', business_type=2)
async def edit_hrm_mock_rule(request: Request,
                             edit_module: AddMockRuleModel,
                             query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        if not edit_module.name:
            raise ValueError("mock规则名不能为空")
        edit_module.update_by = current_user.user.user_name
        edit_module.update_time = datetime.now()
        edit_module_result = MockService.edit_mock_rule_services(query_db, edit_module, current_user)
        if edit_module_result.is_success:
            logger.info(edit_module_result.message)
            return ResponseUtil.success(msg=edit_module_result.message)
        else:
            logger.warning(edit_module_result.message)
            return ResponseUtil.failure(msg=edit_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/changeRuleInfo",
                     dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:editRule'))])
@log_decorator(title='mock规则管理', business_type=2)
async def change_rule_info(request: Request,
                        edit_module: AddMockRuleModel,
                        query_db: Session = Depends(get_db),
                        current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_module.update_by = current_user.user.user_name
        edit_module.update_time = datetime.now()
        edit_module_result = MockService.change_rule_info(query_db, edit_module, current_user)
        if edit_module_result.is_success:
            logger.info(edit_module_result.message)
            return ResponseUtil.success(msg=edit_module_result.message)
        else:
            logger.warning(edit_module_result.message)
            return ResponseUtil.failure(msg=edit_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.delete("/mockManager/ruleDelete",
                       dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:removeRule'))])
@log_decorator(title='mock规则管理', business_type=3)
async def delete_hrm_mock_rule(request: Request,
                               query_db: Session = Depends(get_db),
                               current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                               ):
    try:
        ids_json = await request.json()
        ids = ids_json.get('ruleIds', [])
        delete_module = DeleteMockRuleModel(ruleIds=ids)
        MockRuleDao.delete(query_db, delete_module, current_user)

        return ResponseUtil.success(msg="删除成功")

    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.get("/mockManager/rule/{mock_rule_id}",
                    response_model=MockModel,
                    dependencies=[
                        Depends(CheckUserInterfaceAuth(['hrm:mockManager:detailRule', "hrm.mock_rule:editRule"],
                                                       False))])
async def query_detail_hrm_mock_rule(request: Request, mock_rule_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_result = MockService.mock_rule_detail_services(query_db, mock_rule_id)
        logger.info(f'获取mock_rule_id为{mock_rule_id}的信息成功')
        return ResponseUtil.success(data=detail_result.model_dump(by_alias=True))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/rule/export",
                     dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:exportRule'))])
@log_decorator(title='mock规则管理', business_type=5)
async def export_hrm_mock_rule_list(request: Request,
                                    page_query: MockPageQueryModel = Depends(MockPageQueryModel.as_form),
                                    query_db: Session = Depends(get_db),
                                    data_scope_sql: str = Depends(GetDataScope('HrmCase', user_alias='manager'))
                                    ):
    try:
        # 获取全量数据
        query_result = MockService.get_mock_rule_list_services(query_db, page_query, is_page=False,
                                                               data_scope_sql=data_scope_sql)
        export_result = MockService.export_mock_rule_list_services(query_result)
        logger.info('导出成功')
        return ResponseUtil.streaming(data=bytes2file_response(export_result))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/addResponse",
                     dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:addResponse'))])
@log_decorator(title='mock规则响应管理', business_type=1)
async def add_hrm_mock_rule_response(request: Request,
                                     add_mock_rule: AddMockResponseModel,
                                     query_db: Session = Depends(get_db),
                                     current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        if not add_mock_rule.name:
            raise ValueError("mock响应名不能为空")
        add_mock_rule.manager = current_user.user.user_id
        add_mock_rule.create_by = current_user.user.user_name
        add_mock_rule.update_by = current_user.user.user_name
        add_mock_rule.dept_id = current_user.user.dept_id
        add_module_result = MockResponseService.add_mock_response_services(query_db, add_mock_rule)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(data=add_module_result.result, msg=add_module_result.message)
        else:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(data=add_module_result.result, msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.put("/mockManager/updateResponse",
                     dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:updateResponse'))])
@log_decorator(title='修改mock规则响应', business_type=2)
async def update_hrm_mock_rule_response(request: Request,
                                     add_mock_rule: AddMockResponseModel,
                                     query_db: Session = Depends(get_db),
                                     current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        if not add_mock_rule.name:
            raise ValueError("mock响应名不能为空")

        add_module_result = MockResponseService.edit_mock_response_services(query_db, add_mock_rule, current_user)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(data=add_module_result.result, msg=add_module_result.message)
        else:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(data=add_module_result.result, msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))

@mockController.put("/mockManager/updateResponsePriority",
                     dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:updateResponse'))])
@log_decorator(title='修改mock规则响应', business_type=2)
async def update_hrm_mock_rule_response_priority(request: Request,
                                     add_mock_rule: AddMockResponseModel,
                                     query_db: Session = Depends(get_db),
                                     current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_module_result = MockResponseService.edit_mock_response_services(query_db, add_mock_rule, current_user)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(data=add_module_result.result, msg=add_module_result.message)
        else:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(data=add_module_result.result, msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.get("/mockManager/responseList",
                    dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:responseList'))])
@log_decorator(title='mock规则响应管理', business_type=0)
async def rule_response_list(request: Request,
                             query_rule_response: MockResponsePageQueryModel = Depends(
                                 MockResponsePageQueryModel.as_query),
                             query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_module_result = MockResponseService.get_by_rule_id(query_db, query_rule_response.rule_id)

        return ResponseUtil.success(data=add_module_result, msg="success")

    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.get("/mockManager/responseDetail",
                    dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:responseDetail'))])
@log_decorator(title='mock规则响应详情查询', business_type=0)
async def rule_response_detail(request: Request,
                             query_rule_response: MockResponsePageQueryModel = Depends(
                                 MockResponsePageQueryModel.as_query),
                             query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_module_result = MockResponseService.get_response_detail_services(query_db, query_rule_response.rule_response_id)

        return ResponseUtil.success(data=add_module_result, msg="success")

    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/setDefaultResponse",
                    dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:updateResponse'))])
@log_decorator(title='设置mock规则默认响应', business_type=2)
async def set_default_response(request: Request,
                             query_rule_response: AddMockResponseModel,
                             query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_module_result = MockResponseService.set_default_response(query_db, query_rule_response, current_user)

        return ResponseUtil.success(data=add_module_result, msg="success")

    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))

@mockController.post("/mockManager/getResponseByCondition",
                    dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:responseList'))])
@log_decorator(title='mock规则响应管理', business_type=0)
async def get_response_by_condition(request: Request,
                             query_rule_response: AddMockResponseModel,
                             query_db: Session = Depends(get_db)):
    try:
        add_module_result = MockResponseService.get_by_response_condition(query_db, query_rule_response)

        return ResponseUtil.success(data=add_module_result, msg="success")

    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))