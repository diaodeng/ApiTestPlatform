from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.dao.push_dao import PushDao
from module_hrm.entity.vo.push_vo import DeletePushModel, PushPageQueryModel, PushModel
from module_hrm.service.push_service import PushService
from utils.common_util import CamelCaseUtil
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

pushController = APIRouter(prefix='/hrm/pushManager', dependencies=[Depends(LoginService.get_current_user)])


@pushController.get("/list",
                    response_model=PageResponseModel,
                    dependencies=[Depends(CheckUserInterfaceAuth(['hrm:push:list']))])
async def push_list(request: Request,
                    query_info: PushPageQueryModel = Depends(PushPageQueryModel.as_query),
                    query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                    data_scope_sql: str = Depends(GetDataScope('PushTarget', user_alias='manager'))

                    ):
    query_info.manager = current_user.user.user_id
    result = await PushService.get_push_list(query_db, query_info, data_scope_sql)
    return ResponseUtil.success(model_content=result)


@pushController.get("/all",
                    response_model=PageResponseModel,
                    dependencies=[Depends(CheckUserInterfaceAuth(['hrm:push:all']))])
async def push_list(request: Request,
                    query_info: PushPageQueryModel = Depends(PushPageQueryModel.as_query),
                    query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                    data_scope_sql: str = Depends(GetDataScope('PushTarget', user_alias='manager'))

                    ):
    query_info.manager = current_user.user.user_id
    result = await PushService.get_all(query_db, query_info, data_scope_sql)
    return ResponseUtil.success(data=result)


@pushController.get("/{push_id}",
                    response_model=PageResponseModel,
                    dependencies=[Depends(CheckUserInterfaceAuth(['hrm:push:detail']))])
def push_detail(request: Request,
                push_id: int,
                query_db: Session = Depends(get_db),
                # data_scope_sql: str = Depends(GetDataScope('HrmRunDetail', user_alias='manager')),
                ):
    result = PushService.get_detail(query_db, push_id)
    return ResponseUtil.success(data=result)


@pushController.delete("",
                       response_model=PageResponseModel,
                       dependencies=[Depends(CheckUserInterfaceAuth(['hrm:push:delete']))])
def push_del(request: Request, query_info: DeletePushModel, query_db: Session = Depends(get_db)):
    PushDao.delete(query_db, query_info.push_ids)
    return ResponseUtil.success(dict_content={"msg": "删除成功"})


@pushController.put("",
                    response_model=PageResponseModel,
                    dependencies=[Depends(CheckUserInterfaceAuth(['hrm:push:edite']))])
def push_edite(request: Request,
               query_info: PushModel,
               query_db: Session = Depends(get_db)):
    PushDao.update(query_db, query_info)
    return ResponseUtil.success(dict_content={"msg": "修改成功"})


@pushController.post("",
                     response_model=PageResponseModel,
                     dependencies=[Depends(CheckUserInterfaceAuth(['hrm:push:add']))])
def push_add(request: Request,
             query_info: PushModel,
             query_db: Session = Depends(get_db),
             current_user: CurrentUserModel = Depends(LoginService.get_current_user)
             ):
    query_info.manager = current_user.user.user_id
    query_info.create_by = current_user.user.user_name
    query_info.update_by = current_user.user.user_name
    query_info.dept_id = current_user.user.dept_id
    PushDao.add(query_db, query_info)
    return ResponseUtil.success(dict_content={"msg": "新增成功"})
