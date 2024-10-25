from fastapi import APIRouter, Request
from fastapi import Depends

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.entity.vo.case_vo import CasePageQueryModel
from module_hrm.enums.enums import DataType
from module_hrm.service.config_service import ConfigService, Session
from utils.log_util import *
from utils.page_util import *
from utils.response_util import *

hrmConfigController = APIRouter(prefix='/hrm/config', dependencies=[Depends(LoginService.get_current_user)])


@hrmConfigController.get("/list", response_model=PageResponseModel,
                         dependencies=[Depends(CheckUserInterfaceAuth('hrm:config:list'))])
async def get_config_list(request: Request, page_query: CasePageQueryModel = Depends(CasePageQueryModel.as_query),
                       query_db: Session = Depends(get_db),
                       current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                       ):
    try:
        # 获取分页数据
        page_query.manager = current_user.user.user_id
        page_query.type = DataType.config.value
        page_query.page_size = 10000
        page_query_result = ConfigService.get_config_select(query_db, page_query, is_page=True)
        data = ResponseUtil.success(model_content=page_query_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmConfigController.get("/all", response_model=PageResponseModel,
                         dependencies=[Depends(CheckUserInterfaceAuth('hrm:config:list'))])
async def get_config_all(request: Request, page_query: CasePageQueryModel = Depends(CasePageQueryModel.as_query),
                       query_db: Session = Depends(get_db),
                       current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                       ):
    try:
        # 获取分页数据
        page_query.manager = current_user.user.user_id
        page_query.type = DataType.config.value
        page_query.page_size = 10000
        page_query_result = ConfigService.get_config_select(query_db, page_query, is_page=False)
        for page_info in page_query_result:
            page_info["global"] = False if page_info["projectId"] and page_info["moduleId"] else True
            page_info["isSelf"] = True if page_info["manager"] == page_query.manager else False

        data = ResponseUtil.success(data=page_query_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))