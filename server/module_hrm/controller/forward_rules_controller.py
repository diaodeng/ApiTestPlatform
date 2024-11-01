from fastapi import APIRouter, Request
from fastapi import Depends

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.entity.dto.forward_rules_dto import ForwardRulesModelForApi
from module_hrm.entity.vo.forward_rules_vo import ForwardRulesQueryModel, ForwardRulesDeleteModel
from module_hrm.enums.enums import DelFlagEnum
from module_hrm.service.forward_rules_service import ForwardRulesService
from sqlalchemy.orm import Session
from utils.log_util import logger
from utils.page_util import *
from utils.response_util import *

forwardRulesController = APIRouter(prefix='/qtr/forwardRules', dependencies=[Depends(LoginService.get_current_user)])


@forwardRulesController.get("/all", response_model=PageResponseModel,
                            dependencies=[Depends(CheckUserInterfaceAuth('qtr:forwardRules:all'))])
async def get_all_rules(request: Request,
                        query_db: Session = Depends(get_db),
                        ):
    try:
        logger.info("查询所有转发规则")
        page_query_result = ForwardRulesService.query_all(query_db)
        data = ResponseUtil.success(data=page_query_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@forwardRulesController.get("/list", response_model=PageResponseModel,
                            dependencies=[Depends(CheckUserInterfaceAuth('qtr:forwardRules:list'))])
async def get_rules_by_page(request: Request,
                            page_query: ForwardRulesQueryModel = Depends(ForwardRulesQueryModel.as_query),
                            query_db: Session = Depends(get_db),
                            current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                            ):
    try:
        logger.info("分页查询转发规则")
        page_query.manager = current_user.user.user_id
        page_query_result = ForwardRulesService.query_list(query_db, query_info=page_query)
        data = ResponseUtil.success(dict_content=page_query_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@forwardRulesController.post("", response_model=PageResponseModel,
                             dependencies=[Depends(CheckUserInterfaceAuth('qtr:forwardRules:add'))])
@log_decorator(title='新增转发规则', business_type=1)
async def add_rules(request: Request,
                    page_query: ForwardRulesModelForApi,
                    query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                    ):
    try:
        logger.info("新增转发规则")
        page_query.manager = current_user.user.user_id
        page_query.create_by = current_user.user.user_name
        page_query.update_by = current_user.user.user_name
        ForwardRulesService.add(query_db, data=page_query)
        data = ResponseUtil.success(msg="新增成功")
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@forwardRulesController.post("/copy", response_model=PageResponseModel,
                             dependencies=[Depends(CheckUserInterfaceAuth('qtr:forwardRules:copy'))])
@log_decorator(title='复制转发规则', business_type=1)
async def add_rules(request: Request,
                    page_query: ForwardRulesModelForApi,
                    query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                    ):
    try:
        logger.info("复制转发规则")
        ForwardRulesService.copy(query_db, page_query, current_user)
        data = ResponseUtil.success(msg="复制成功")
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@forwardRulesController.put("", response_model=PageResponseModel,
                            dependencies=[Depends(CheckUserInterfaceAuth('qtr:forwardRules:edit'))])
@log_decorator(title='编辑转发规则', business_type=2)
async def add_rules(request: Request,
                    page_query: ForwardRulesModelForApi,
                    query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                    ):
    try:
        logger.info("编辑转发规则")
        page_query.update_by = current_user.user.user_name
        page_query.update_time = datetime.now()
        ForwardRulesService.update(query_db, page_query, current_user)
        data = ResponseUtil.success(msg="编辑成功")
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@forwardRulesController.delete("", response_model=PageResponseModel,
                               dependencies=[Depends(CheckUserInterfaceAuth('qtr:forwardRules:delete'))])
@log_decorator(title='删除转发规则', business_type=3)
async def add_rules(request: Request,
                    page_query: ForwardRulesDeleteModel,
                    query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                    ):
    try:
        logger.info("删除转发规则")
        data_info = ForwardRulesDeleteModel()
        data_info.update_by = current_user.user.user_name
        data_info.update_time = datetime.now()
        data_info.rule_id = page_query.rule_id
        data_info.del_flag = DelFlagEnum.delete.value

        ForwardRulesService.delete(query_db, data_info, current_user)
        data = ResponseUtil.success(msg="删除成功")
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@forwardRulesController.post("/changeStatus", response_model=PageResponseModel,
                             dependencies=[Depends(CheckUserInterfaceAuth('qtr:forwardRules:update'))])
@log_decorator(title='修改转发规则状态', business_type=2)
async def add_rules(request: Request,
                    page_query: ForwardRulesModelForApi,
                    query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                    ):
    try:
        logger.info("修改转发规则状态")
        data_info = ForwardRulesModelForApi()
        data_info.update_by = current_user.user.user_name
        data_info.update_time = datetime.now()
        data_info.rule_id = page_query.rule_id
        data_info.status = page_query.status

        ForwardRulesService.update(query_db, data_info, current_user)
        data = ResponseUtil.success(msg="状态修改成功")
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@forwardRulesController.get("/{data_id}", response_model=PageResponseModel,
                            dependencies=[Depends(CheckUserInterfaceAuth('qtr:forwardRules:detail'))])
async def add_rules(request: Request,
                    data_id: int,
                    query_db: Session = Depends(get_db),
                    ):
    try:
        logger.info("查询转发规则详情")
        data_obj = ForwardRulesService.detail(query_db, data_id)
        data = ResponseUtil.success(msg="编辑成功", data=data_obj.model_dump(by_alias=True))
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))



