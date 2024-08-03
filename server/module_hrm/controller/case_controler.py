from fastapi import APIRouter, Request
from fastapi import Depends
from config.get_db import get_db
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.service.case_service import *
from module_hrm.entity.vo.case_vo import *
from utils.response_util import *
from utils.log_util import *
from utils.page_util import *
from utils.common_util import bytes2file_response
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.annotation.log_annotation import log_decorator
from utils.snowflake import snowIdWorker

caseController = APIRouter(prefix='/hrm/case', dependencies=[Depends(LoginService.get_current_user)])


@caseController.get("/list", response_model=PageResponseModel, dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:list'))])
async def get_hrm_case(request: Request, page_query: CasePageQueryModel = Depends(CasePageQueryModel.as_query), query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        if not page_query.type:
            raise ValueError("参数错误")
        page_query_result = CaseService.get_case_list_services(query_db, page_query, is_page=True)
        logger.info('获取成功')
        data = ResponseUtil.success(model_content=page_query_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@caseController.post("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:add'))])
@log_decorator(title='用例管理', business_type=1)
async def add_hrm_case(request: Request, add_case: AddCaseModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        if not add_case.type:
            raise ValueError("参数错误")
        add_case.create_by = current_user.user.user_name
        add_case.update_by = current_user.user.user_name
        # add_case.case_id = snowIdWorker.get_id()
        add_module_result = CaseService.add_case_services(query_db, add_case)
        if add_module_result.is_success:
            logger.info(add_module_result.message)
            return ResponseUtil.success(msg=add_module_result.message)
        else:
            logger.warning(add_module_result.message)
            return ResponseUtil.failure(msg=add_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@caseController.put("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:edit'))])
@log_decorator(title='用例管理', business_type=2)
async def edit_hrm_case(request: Request, edit_module: CaseModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_module.update_by = current_user.user.user_name
        edit_module.update_time = datetime.now()
        edit_module_result = CaseService.edit_case_services(query_db, edit_module)
        if edit_module_result.is_success:
            logger.info(edit_module_result.message)
            return ResponseUtil.success(msg=edit_module_result.message)
        else:
            logger.warning(edit_module_result.message)
            return ResponseUtil.failure(msg=edit_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@caseController.delete("/{case_ids}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:remove'))])
@log_decorator(title='用例管理', business_type=3)
async def delete_hrm_case(request: Request, case_ids: str, query_db: Session = Depends(get_db)):
    try:
        delete_module = DeleteCaseModel(caseIds=case_ids)
        delete_module_result = CaseService.delete_case_services(query_db, delete_module)
        if delete_module_result.is_success:
            logger.info(delete_module_result.message)
            return ResponseUtil.success(msg=delete_module_result.message)
        else:
            logger.warning(delete_module_result.message)
            return ResponseUtil.failure(msg=delete_module_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@caseController.get("/{case_id}", response_model=CaseModel, dependencies=[Depends(CheckUserInterfaceAuth(['hrm:case:detail', "hrm.case:edit"], False))])
async def query_detail_hrm_case(request: Request, case_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_result = CaseService.case_detail_services(query_db, case_id)
        logger.info(f'获取case_id为{case_id}的信息成功')
        return ResponseUtil.success(data=detail_result.model_dump(exclude_unset=True, by_alias=True))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@caseController.post("/export", dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:export'))])
@log_decorator(title='用例管理', business_type=5)
async def export_hrm_case_list(request: Request, page_query: CasePageQueryModel = Depends(CasePageQueryModel.as_form), query_db: Session = Depends(get_db)):
    try:
        # 获取全量数据
        query_result = CaseService.get_case_list_services(query_db, page_query, is_page=False)
        export_result = CaseService.export_case_list_services(query_result)
        logger.info('导出成功')
        return ResponseUtil.streaming(data=bytes2file_response(export_result))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
