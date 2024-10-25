from fastapi import APIRouter, Request
from fastapi import Depends

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.entity.vo.module_vo import *
from module_hrm.service.module_service import *
from utils.common_util import bytes2file_response
from utils.log_util import *
from utils.page_util import *
from utils.response_util import *
from utils.snowflake import snowIdWorker

moduleController = APIRouter(prefix='/hrm/module', dependencies=[Depends(LoginService.get_current_user)])


@moduleController.get("/list", response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth('hrm:module:list'))])
async def get_hrm_module_list(request: Request,
                              page_query: ModulePageQueryModel = Depends(ModulePageQueryModel.as_query),
                              query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        page_query_result = ModuleService.get_module_list_services(query_db, page_query, is_page=True)
        logger.info('获取成功')
        return ResponseUtil.success(model_content=page_query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@moduleController.get("/selectModuleList", response_model=List[ModuleModel],
                      dependencies=[Depends(CheckUserInterfaceAuth('hrm:project:list'))])
async def get_hrm_module_list_all(request: Request,
                                  query: ModuleQueryModel = Depends(ModuleQueryModel),
                                  query_db: Session = Depends(get_db)):
    try:
        query_result = ModuleService.get_module_list_services_all(query_db, query)
        logger.info('获取成功')
        return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@moduleController.get("/showModuleList", response_model=List[ModuleModel],
                      dependencies=[Depends(CheckUserInterfaceAuth('hrm:project:list'))])
async def get_hrm_module_list_show(request: Request,
                                   query: ModuleQueryModel = Depends(ModuleQueryModel),
                                   query_db: Session = Depends(get_db)):
    try:
        query_result = ModuleService.get_module_list_services_show(query_db, query)
        logger.info('获取成功')
        return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@moduleController.post("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:module:add'))])
@log_decorator(title='模块管理', business_type=1)
async def add_hrm_module(request: Request,
                         add_module: AddModuleModel,
                         query_db: Session = Depends(get_db),
                         current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_module.manager = current_user.user.user_id
        add_module.create_by = current_user.user.user_name
        add_module.update_by = current_user.user.user_name
        add_module.module_id = snowIdWorker.get_id()
        add_module_result = ModuleService.add_module_services(query_db, add_module)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(msg=add_module_result.message)
        else:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@moduleController.put("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:module:edit'))])
@log_decorator(title='模块管理', business_type=2)
async def edit_hrm_module(request: Request,
                          edit_module: ModuleModel,
                          query_db: Session = Depends(get_db),
                          current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_module.update_by = current_user.user.user_name
        edit_module.update_time = datetime.now()
        edit_module_result = ModuleService.edit_module_services(query_db, edit_module)
        if edit_module_result.is_success:
            logger.info(edit_module_result.message)
            return ResponseUtil.success(msg=edit_module_result.message)
        else:
            logger.warning(edit_module_result.message)
            return ResponseUtil.failure(msg=edit_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@moduleController.delete("/{module_ids}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:module:remove'))])
@log_decorator(title='模块管理', business_type=3)
async def delete_hrm_module(request: Request, module_ids: str, query_db: Session = Depends(get_db)):
    try:
        delete_module = DeleteModuleModel(moduleIds=module_ids)
        delete_module_result = ModuleService.delete_module_services(query_db, delete_module)
        if delete_module_result.is_success:
            logger.info(delete_module_result.message)
            return ResponseUtil.success(msg=delete_module_result.message)
        else:
            logger.warning(delete_module_result.message)
            return ResponseUtil.failure(msg=delete_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@moduleController.get("/{module_id}",
                      response_model=ModuleModel,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:module:detail', 'hrm:module:edit'], False))])
async def query_detail_hrm_module(request: Request, module_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_result = ModuleService.module_detail_services(query_db, module_id)
        logger.info(f'获取module_id为{module_id}的信息成功')
        return ResponseUtil.success(data=detail_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@moduleController.post("/export", dependencies=[Depends(CheckUserInterfaceAuth('hrm:module:export'))])
@log_decorator(title='模块管理', business_type=5)
async def export_hrm_module_list(request: Request,
                                 page_query: ModulePageQueryModel = Depends(ModulePageQueryModel.as_form),
                                 query_db: Session = Depends(get_db)):
    try:
        # 获取全量数据
        query_result = ModuleService.get_module_list_services(query_db, page_query, is_page=False)
        export_result = ModuleService.export_module_list_services(query_result)
        logger.info('导出成功')
        return ResponseUtil.streaming(data=bytes2file_response(export_result))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
