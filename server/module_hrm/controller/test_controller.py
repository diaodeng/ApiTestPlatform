## 调试用接口数据
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.common_vo import DataScopeExpr
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.dao.mock_dao import MockRuleDao
from module_hrm.entity.do.mock_do import MockRules
from module_hrm.entity.vo.mock_vo import (
    AddMockResponseModel,
    AddMockRuleModel,
    DeleteMockResponseModel,
    DeleteMockRuleModel,
    MockModel,
    MockPageQueryModel,
    MockResponsePageQueryModel,
)
from module_hrm.service.mock_service import MockResponseService, MockService, RuleMatcher
from utils.common_util import bytes2file_response
from utils.log_util import logger, logger_mock
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
            except Exception:
                try:
                    form = await request.form()
                    body_data = dict(form)
                except Exception:
                    body_data = await request.body()

            body_data = body_data.decode("utf-8") if isinstance(body_data, bytes) else body_data
        except Exception:
            body_data = None
        logger_mock.info(f"url: {request.url}, method: {request.method}")
        logger_mock.info(f"request.query_params: {dict(request.query_params)}")
        logger_mock.info(f"request.headers: {dict(request.headers)}")
        logger_mock.info(f"body_data: {body_data}")
        setattr(request, "body_data", body_data)

        req = await RuleMatcher(request, query_db, f"/{mock_path}").match_response()

        if not req:
            method = request.method
            headers = dict(request.headers)
            query_params = dict(request.query_params)
            path_params = dict(request.path_params)
            req = {
                "code": 4444444,
                "success": False,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            logger_mock.info(json.dumps(req, ensure_ascii=False))
            return JSONResponse(content=req, status_code=505, media_type="application/json")
        logger_mock.info(json.dumps(req, ensure_ascii=False))
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

        return Response(content=req.get("content"), media_type=content_type, headers=req.get("headers"),
                        status_code=req.get("status_code"))
    except Exception as e:
        logger_mock.error(f"mock测试失败, path: {mock_path}, error: {e}")
        logger_mock.exception(e)
        return ResponseUtil.error(msg=f"mock测试失败, path: {mock_path}, error: {e}")


@mockController.api_route("/test{test_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def get_hrm_test(request: Request, test_path: str):
    try:
        method = request.method
        # 获取分页数据
        data = {"url": request.url.path,
                "method": method,
                "headers": dict(request.headers),
                "cookies": dict(request.cookies),
                "queryParams": dict(request.query_params),
                "pathParams": dict(request.path_params),
                }
        try:
            body_json = await request.json()
        except Exception:
            body_json = None

        try:
            body_form = await request.form()
            body_form = dict(body_form)
        except Exception:
            body_form = None

        try:
            body_data = await request.body()
            body_data = body_data.decode("utf-8") if isinstance(body_data, bytes) else body_data
        except Exception:
            body_data = None

        if method in ["POST", "PUT"]:

            if not body_data and not body_json and not body_form:
                return {"error": "Missing request body"}
            data["body"] = body_data

        if body_json:
            data["json"] = body_json
        if body_form:
            data["form"] = body_form

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
                             data_scope_sql: DataScopeExpr = Depends(GetDataScope(MockRules, user_alias='manager'))
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
        add_module_result = await MockService.add_mock_rule_services(query_db, add_mock_rule, current_user)
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
        edit_module_result = await MockService.edit_mock_rule_services(query_db, edit_module, current_user)
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
                        Depends(CheckUserInterfaceAuth(['hrm:mockManager:detailRule', "hrm:mockManager:editRule"],
                                                       False))])
async def query_detail_hrm_mock_rule(request: Request, mock_rule_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_result = await MockService.mock_rule_detail_services(query_db, mock_rule_id)
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
                                    data_scope_sql: DataScopeExpr = Depends(GetDataScope(MockRules,
                                                                                         user_alias='manager'))
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
        add_module_result = await MockResponseService.add_mock_response_services(query_db, add_mock_rule)
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

        add_module_result = await MockResponseService.edit_mock_response_services(query_db, add_mock_rule, current_user)
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
                                                 current_user: CurrentUserModel = Depends(
                                                     LoginService.get_current_user)):
    try:
        add_module_result = await MockResponseService.edit_mock_response_services(query_db, add_mock_rule, current_user)
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
                             response_condition_keyword: str | None = Query(default=None,
                                                                           alias="responseConditionKeyword",
                                                                           description="按response_condition文本关键字过滤"),
                             query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """
    查询指定mock规则下的响应列表。

    :param request: FastAPI请求对象
    :param query_rule_response: 响应查询参数（rule_id/name/status等）
    :param response_condition_keyword: 响应条件关键字，按qtr_rule_response.response_condition模糊过滤
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: mock规则响应列表
    """
    try:
        add_module_result = await MockResponseService.get_by_rule_id(
            query_db,
            rule_id=query_rule_response.rule_id,
            name=query_rule_response.name,
            response_condition_keyword=response_condition_keyword,
            status=query_rule_response.status,
        )

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
    """
    查询mock响应详情。

    :param request: FastAPI请求对象
    :param query_rule_response: 响应查询参数（rule_response_id）
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: mock规则响应详情
    """
    try:
        add_module_result = await MockResponseService.get_response_detail_services(query_db,
                                                                                   query_rule_response.rule_response_id)

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
    """
    设置mock规则默认响应。

    :param request: FastAPI请求对象
    :param query_rule_response: 默认响应参数（rule_id/rule_response_id/response_condition）
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 设置结果
    """
    try:
        add_module_result = await MockResponseService.set_default_response(query_db, query_rule_response, current_user)

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
    """
    根据当前条件匹配mock响应列表。

    :param request: FastAPI请求对象
    :param query_rule_response: 条件参数（rule_id/response_condition）
    :param query_db: 数据库会话
    :return: 匹配到的mock响应列表
    """
    try:
        add_module_result = await MockResponseService.get_by_response_condition(query_db, query_rule_response)

        return ResponseUtil.success(data=add_module_result, msg="success")

    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.post("/mockManager/copyResponse",
                     dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:addResponse'))])
@log_decorator(title='复制mock规则响应', business_type=1)
async def copy_hrm_mock_rule_response(request: Request,
                                      add_mock_rule: AddMockResponseModel,
                                      query_db: Session = Depends(get_db),
                                      current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """
    复制mock规则响应。

    :param request: FastAPI请求对象
    :param add_mock_rule: 复制参数（rule_response_id/name/rule_id）
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 复制结果
    """
    try:
        if not add_mock_rule.name:
            raise ValueError("复制后的mock响应名不能为空")
        add_mock_rule.manager = current_user.user.user_id
        add_mock_rule.create_by = current_user.user.user_name
        add_mock_rule.update_by = current_user.user.user_name
        add_mock_rule.dept_id = current_user.user.dept_id
        add_module_result = await MockResponseService.copy_mock_response_services(query_db, add_mock_rule)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(data=add_module_result.result, msg=add_module_result.message)
        logger.warning(add_module_result.message)
        return ResponseUtil.failure(data=add_module_result.result, msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@mockController.delete("/mockManager/responseDelete",
                       dependencies=[Depends(CheckUserInterfaceAuth('hrm:mockManager:updateResponse'))])
@log_decorator(title='删除mock规则响应', business_type=3)
async def delete_hrm_mock_response(request: Request,
                                   delete_rule_response: DeleteMockResponseModel,
                                   query_db: Session = Depends(get_db),
                                   current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """
    删除mock规则响应（支持批量）。

    :param request: FastAPI请求对象
    :param delete_rule_response: 删除参数（rule_response_ids）
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 删除结果
    """
    try:
        delete_rule_response.update_by = current_user.user.user_name
        add_module_result = MockResponseService.delete_mock_response_services(query_db, delete_rule_response,
                                                                              current_user)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(data=add_module_result.result, msg=add_module_result.message)
        logger.warning(add_module_result.message)
        return ResponseUtil.failure(data=add_module_result.result, msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
