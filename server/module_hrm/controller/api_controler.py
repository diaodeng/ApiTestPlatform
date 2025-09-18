from datetime import datetime

from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.dao.api_dao import ApiOperation
from module_hrm.entity.vo.api_vo import ApiModelForApi, ApiModel, ApiPageQueryModel
from module_hrm.entity.vo.case_vo import AddCaseModel
from module_hrm.enums.enums import TstepTypeEnum
from module_hrm.service.api_service import api_tree
from module_hrm.service.case_service import CaseService
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.response_util import ResponseUtil

hrmApiController = APIRouter(prefix='/hrm/api', dependencies=[Depends(LoginService.get_current_user)])


@hrmApiController.get("/mult/tree", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:tree'))])
async def api_tree_handle(request: Request,
                          page_query: ApiPageQueryModel = Depends(ApiPageQueryModel.as_query),
                          query_db: Session = Depends(get_db),
                          current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                          data_scope_sql: str = Depends(GetDataScope('ApiInfo', user_alias='manager'))
                          ):
    try:
        # 获取分页数据
        page_query.manager = current_user.user.user_id
        tree_data = api_tree(query_db, page_query, data_scope_sql)
        data = ResponseUtil.success(data=tree_data)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmApiController.post("/copyAsCase", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:add'))])
async def api_copy_as_case(request: Request,
                           api_data: ApiModelForApi,
                           query_db: Session = Depends(get_db),
                           current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        # 获取分页数据
        caseMode = AddCaseModel()
        caseMode.manager = current_user.user.user_id
        caseMode.create_by = current_user.user.user_name
        caseMode.update_by = current_user.user.user_name

        caseMode.case_name = api_data.name
        caseMode.request = api_data.request_info
        data = CaseService.add_case_services(query_db, caseMode)
        return ResponseUtil.success(data=data)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmApiController.get("/detail/{api_id}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:get'))])
async def api_detail(request: Request, api_id: int, query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        tree_data = ApiOperation.get(query_db, api_id)
        data = ApiModelForApi(**CamelCaseUtil.transform_result(tree_data))
        return ResponseUtil.success(data=data.model_dump(by_alias=True))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmApiController.post("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:add'))])
async def api_add(request: Request,
                  api_data: ApiModelForApi,
                  query_db: Session = Depends(get_db),
                  current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        # 获取分页数据
        api_data.manager = current_user.user.user_id
        api_data.author = current_user.user.user_name
        api_data.create_by = current_user.user.user_name
        api_data.update_by = current_user.user.user_name
        api_data.dept_id = current_user.user.dept_id
        tree_data = ApiOperation.add(query_db, api_data)
        tree_data["isParent"] = True if tree_data["apiType"] == TstepTypeEnum.folder.value else False
        return ResponseUtil.success(data=tree_data)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmApiController.put("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:update'))])
async def api_update(request: Request,
                     page_query: ApiModelForApi,
                     query_db: Session = Depends(get_db),
                     current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        # 获取分页数据
        if isinstance(page_query, dict):
            page_query = ApiModel(**CamelCaseUtil.transform_result(page_query))
        page_query.update_by = current_user.user.user_name
        page_query.update_time = datetime.now()
        data = ApiOperation.update(query_db, page_query, current_user)
        return ResponseUtil.success(data=data)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmApiController.delete("/{api_id}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:delete'))])
async def api_del(request: Request,
                  api_id, query_db: Session = Depends(get_db),
                  current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        # 获取分页数据
        data = ApiOperation.delete_recursion(query_db, [api_id], current_user)
        return ResponseUtil.success(data="删除成功")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
