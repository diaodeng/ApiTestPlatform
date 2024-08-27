from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.dao.api_dao import ApiOperation
from module_hrm.entity.vo.api_vo import ApiModelForApi, ApiQueryModel, ApiModel
from module_hrm.service.api_service import api_tree
from utils.log_util import *
from utils.page_util import *
from utils.response_util import *

hrmApiController = APIRouter(prefix='/hrm/api', dependencies=[Depends(LoginService.get_current_user)])


@hrmApiController.get("/mult/tree", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:tree'))])
async def api_tree_handle(request: Request, page_query: str = "111", query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        tree_data = api_tree(query_db, page_query)
        data = ResponseUtil.success(data=tree_data)
        return data
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
                  api_data: ApiModel,
                  query_db: Session = Depends(get_db),
                  current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        # 获取分页数据
        api_data.author = current_user.user.user_name
        api_data.create_by = current_user.user.user_name
        api_data.update_by = current_user.user.user_name
        tree_data = ApiOperation.add(query_db, api_data)
        return ResponseUtil.success(data=tree_data)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmApiController.put("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:update'))])
async def api_update(request: Request, page_query: ApiModel, query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        if isinstance(page_query, dict):
            page_query = ApiModel(**CamelCaseUtil.transform_result(page_query))

        data = ApiOperation.update(query_db, page_query)
        return ResponseUtil.success(data=data)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmApiController.delete("/{api_id}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:api:delete'))])
async def api_del(request: Request, api_id, query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        data = ApiOperation.delete_recursion(query_db, [api_id])
        return ResponseUtil.success(data="删除成功")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
