import json
from datetime import datetime

from fastapi import APIRouter
from fastapi import Depends
from fastapi.requests import Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_message.entity.vo.message_manager_vo import MessageManagerPageQueryModel, MessageDeleteModel, MessageManagerModelForApi
from module_message.entity.dto.message_manager_dto import MessageManagerModel
from module_message.service.message_service import MessageService
from utils.common_util import bytes2file_response
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

messageController = APIRouter(prefix='/qtr/message', dependencies=[Depends(LoginService.get_current_user)])


@messageController.get("/list", response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth('qtr:message:list'))]
                       )
async def get_qtr_message_list(request: Request,
                           message_page_query: MessageManagerPageQueryModel = Depends(MessageManagerPageQueryModel.as_query),
                           query_db: Session = Depends(get_db),
                           data_scope_sql: str = Depends(GetDataScope('QtrMessageManager', user_alias='manager'))
                           ):
    try:
        # 获取分页数据
        notice_page_query_result = MessageService.get_message_list_services(query_db, message_page_query, data_scope_sql,
                                                                    is_page=True)
        logger.info('获取成功')
        return ResponseUtil.success(model_content=notice_page_query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@messageController.post("", dependencies=[Depends(CheckUserInterfaceAuth('qtr:message:add'))])
@log_decorator(title='消息通知配置管理', business_type=1)
async def add_qtr_message(request: Request, add_message: MessageManagerModelForApi, query_db: Session = Depends(get_db),
                      current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_message = MessageManagerModel.model_validate(add_message)
        add_message.create_by = current_user.user.user_name
        add_message.update_by = current_user.user.user_name
        add_message.dept_id = current_user.user.dept_id
        add_message.manager = current_user.user.user_id

        add_message_result = MessageService.add_message_services(query_db, add_message)
        if add_message_result.is_success:
            logger.info(add_message_result.message)
            return ResponseUtil.success(msg=add_message_result.message)
        else:
            logger.warning(add_message_result.message)
            return ResponseUtil.failure(msg=add_message_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@messageController.put("", dependencies=[Depends(CheckUserInterfaceAuth('qtr:message:edit'))])
@log_decorator(title='消息通知配置管理', business_type=2)
async def edit_qtr_message(request: Request, edit_message: MessageManagerModel, query_db: Session = Depends(get_db),
                       current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_message.update_by = current_user.user.user_name
        edit_message.update_time = datetime.now()
        edit_message_result = MessageService.edit_message_services(query_db, edit_message)
        if edit_message_result.is_success:
            logger.info(edit_message_result.message)
            return ResponseUtil.success(msg=edit_message_result.message)
        else:
            logger.warning(edit_message_result.message)
            return ResponseUtil.failure(msg=edit_message_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@messageController.put("/changeStatus", dependencies=[Depends(CheckUserInterfaceAuth('qtr:message:changeStatus'))])
@log_decorator(title='消息通知配置管理', business_type=2)
async def change_status_qtr_message(request: Request, edit_message: MessageManagerModel, query_db: Session = Depends(get_db),
                                current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:

        message_info = MessageManagerModel()
        message_info.status = edit_message.status
        message_info.message_id = edit_message.message_id
        message_info.update_by = current_user.user.user_name
        message_info.update_time = datetime.now()
        edit_message_result = MessageService.edit_message_services(query_db, message_info)
        if edit_message_result.is_success:
            logger.info(edit_message_result.message)
            return ResponseUtil.success(msg=edit_message_result.message)
        else:
            logger.warning(edit_message_result.message)
            return ResponseUtil.failure(msg=edit_message_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@messageController.delete("/delete", dependencies=[Depends(CheckUserInterfaceAuth('qtr:message:remove'))])
@log_decorator(title='消息通知配置管理', business_type=3)
async def delete_qtr_message(request: Request, message_del: MessageDeleteModel, query_db: Session = Depends(get_db)):
    try:
        delete_message_result = MessageService.delete_message_services(query_db, message_del)
        if delete_message_result.is_success:
            logger.info(delete_message_result.message)
            return ResponseUtil.success(msg=delete_message_result.message)
        else:
            logger.warning(delete_message_result.message)
            return ResponseUtil.failure(msg=delete_message_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@messageController.get("/{message_id}", response_model=MessageManagerModel,
                      dependencies=[Depends(CheckUserInterfaceAuth('qtr:message:query'))])
async def query_detail_qtr_message(request: Request, message_id: int, query_db: Session = Depends(get_db)):
    try:
        message_detail_result = MessageService.message_detail_services(query_db, message_id)
        logger.info(f'获取message_id为{message_id}的信息成功')
        return ResponseUtil.success(data=message_detail_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@messageController.post("/export", dependencies=[Depends(CheckUserInterfaceAuth('qtr:message:export'))])
@log_decorator(title='消息通知配置管理', business_type=5)
async def export_qtr_message_list(request: Request,
                              message_page_query: MessageManagerPageQueryModel = Depends(MessageManagerPageQueryModel.as_form),
                              query_db: Session = Depends(get_db),
                              data_scope_sql: str = Depends(GetDataScope('QtrMessage', user_alias='manager'))
                              ):
    try:
        # 获取全量数据
        # message_query_result = MessageService.get_message_list_services(query_db, message_page_query, data_scope_sql, is_page=False)
        message_export_result = await MessageService.export_message_list_services(query_db, message_page_query, data_scope_sql)
        logger.info('导出成功')
        return ResponseUtil.streaming(data=bytes2file_response(message_export_result))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
