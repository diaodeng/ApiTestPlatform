from datetime import datetime

from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session

from common.common_enums import BusinessTypeEnum
from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.dao.ui_elements_dao import ElementsOperation
from module_hrm.entity.vo.elements_vo import ElementsModelForApi, ElementsQueryModel, ElementsPageQueryModel, ElementsAddModel, DeleteElementsModel, ElementsModel
from module_hrm.service.elements_service import ElementService
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.response_util import ResponseUtil

qtrElementController = APIRouter(prefix='/qtr/element', dependencies=[Depends(LoginService.get_current_user)])



@qtrElementController.get("/{element_id}", dependencies=[Depends(CheckUserInterfaceAuth('qtr:element:get'))])
async def element_detail(request: Request, api_id: int, query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        element_data = ElementService.element_detail_services(query_db, api_id)
        return ResponseUtil.success(data=element_data.model_dump(by_alias=True))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrElementController.get("/list", dependencies=[Depends(CheckUserInterfaceAuth('qtr:element:list'))])
async def element_list(request: Request,
                          page_query: ElementsPageQueryModel = Depends(ElementsPageQueryModel.as_query),
                          query_db: Session = Depends(get_db),
                          current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                          data_scope_sql: str = Depends(GetDataScope('QtrElements', user_alias='manager'))
                          ):
    try:
        # 获取分页数据
        page_query.manager = current_user.user.user_id
        page_data = ElementService.element_list_services(query_db, page_query, data_scope_sql, True)
        data = ResponseUtil.success(model_content=page_data)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrElementController.post("", dependencies=[Depends(CheckUserInterfaceAuth('qtr:element:add'))])
@log_decorator(title='元素管理', business_type=BusinessTypeEnum.ADD.value)
async def element_add(request: Request,
                  api_data: ElementsAddModel,
                  query_db: Session = Depends(get_db),
                  current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        # 获取分页数据
        api_data.manager = current_user.user.user_id
        api_data.author = current_user.user.user_name
        api_data.create_by = current_user.user.user_name
        api_data.update_by = current_user.user.user_name
        api_data.dept_id = current_user.user.dept_id
        tree_data = ElementService.add_element_services(query_db, api_data)
        return ResponseUtil.success(data=tree_data)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrElementController.put("", dependencies=[Depends(CheckUserInterfaceAuth('qtr:element:update'))])
@log_decorator(title='元素管理', business_type=BusinessTypeEnum.UPDATE.value)
async def element_update(request: Request,
                     page_query: ElementsModelForApi,
                     query_db: Session = Depends(get_db),
                     current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        # 获取分页数据
        if isinstance(page_query, dict):
            page_query = ElementsModelForApi(**CamelCaseUtil.transform_result(page_query))
        page_query.update_by = current_user.user.user_name
        page_query.update_time = datetime.now()
        data = ElementService.update_element_services(query_db, page_query, current_user)
        return ResponseUtil.success(data=data)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrElementController.delete("/{api_id}", dependencies=[Depends(CheckUserInterfaceAuth('qtr:element:delete'))])
@log_decorator(title='元素管理', business_type=BusinessTypeEnum.DELETE.value)
async def element_del(request: Request,
                  api_id, query_db: Session = Depends(get_db),
                  current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        # 获取分页数据
        data = ElementsOperation.delete(query_db, [api_id], False, current_user)
        return ResponseUtil.success(data="删除成功")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
