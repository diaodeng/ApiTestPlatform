from fastapi import APIRouter, Request
from fastapi import Depends
from config.get_db import get_db
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.service.suite_service import *
from utils.response_util import *
from utils.log_util import *
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.aspect.data_scope import GetDataScope
from module_admin.annotation.log_annotation import log_decorator
from utils.snowflake import snowIdWorker

suiteController = APIRouter(prefix='/qtr/suite', dependencies=[Depends(LoginService.get_current_user)])


@suiteController.get("/list", response_model=List[SuiteModel],
                     dependencies=[Depends(CheckUserInterfaceAuth('qtr:suite:list'))])
async def get_qtr_suite_list(request: Request,
                             suite_query: SuitePageQueryModel = Depends(SuitePageQueryModel.as_query),
                             query_db: Session = Depends(get_db),
                             data_scope_sql: str = Depends(GetDataScope('QtrSuite')),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                             ):
    try:
        suite_query.manager = current_user.user.user_id
        suite_query_result = SuiteService.get_suite_list_services(query_db, suite_query, data_scope_sql, is_page=True)
        logger.info('获取成功')
        return ResponseUtil.success(model_content=suite_query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@suiteController.post("", dependencies=[Depends(CheckUserInterfaceAuth('qtr:suite:add'))])
@log_decorator(title='测试套件', business_type=1)
async def add_qtr_suite(request: Request,
                        add_suite: SuiteModel,
                        query_db: Session = Depends(get_db),
                        current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_suite.manager = current_user.user.user_id
        add_suite.create_by = current_user.user.user_name
        add_suite.update_by = current_user.user.user_name
        add_suite.suite_id = snowIdWorker.get_id()
        add_suite_result = SuiteService.add_suite_services(query_db, add_suite)
        if add_suite_result.is_success:
            logger.info(add_suite_result.message)
            return ResponseUtil.success(data=add_suite_result)
        else:
            logger.warning(add_suite_result.message)
            return ResponseUtil.failure(msg=add_suite_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@suiteController.put("", dependencies=[Depends(CheckUserInterfaceAuth('qtr:suite:edit'))])
@log_decorator(title='测试套件', business_type=2)
async def edit_qtr_suite(request: Request,
                         edit_suite: SuiteModel,
                         query_db: Session = Depends(get_db),
                         current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_suite.update_by = current_user.user.user_name
        edit_suite.update_time = datetime.now()
        edit_suite_result = SuiteService.edit_suite_services(query_db, edit_suite)
        if edit_suite_result.is_success:
            logger.info(edit_suite_result.message)
            return ResponseUtil.success(msg=edit_suite_result.message)
        else:
            logger.warning(edit_suite_result.message)
            return ResponseUtil.failure(msg=edit_suite_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@suiteController.delete("/{suite_ids}", dependencies=[Depends(CheckUserInterfaceAuth('qtr:suite:remove'))])
@log_decorator(title='测试套件', business_type=3)
async def delete_hrm_env(request: Request,
                         suite_ids: str,
                         query_db: Session = Depends(get_db),
                         current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        delete_suite = DeleteSuiteModel(suiteIds=suite_ids)
        delete_suite_result = SuiteService.delete_suite_services(query_db, delete_suite)
        if delete_suite_result.is_success:
            logger.info(delete_suite_result.message)
            return ResponseUtil.success(msg=delete_suite_result.message)
        else:
            logger.warning(delete_suite_result.message)
            return ResponseUtil.failure(msg=delete_suite_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@suiteController.get("/{suite_id}", response_model=SuiteModel,
                     dependencies=[Depends(CheckUserInterfaceAuth(['qtr:suite:detail', "qtr:suite:edit"], False))])
async def query_detail_suite(request: Request, suite_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_suite_result = SuiteService.get_suite_services(query_db, suite_id)
        logger.info(f'获取suite_id为{suite_id}的信息成功')
        return ResponseUtil.success(data=detail_suite_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
