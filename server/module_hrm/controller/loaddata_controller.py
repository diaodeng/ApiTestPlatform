import json

from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_hrm.dao.api_dao import ApiOperation
from module_hrm.dao.case_dao import CaseDao
from module_hrm.dao.debugtalk_dao import DebugTalkDao
from module_hrm.dao.env_dao import EnvDao
from module_hrm.dao.module_dao import ModuleDao
from module_hrm.dao.project_dao import ProjectDao
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.vo.case_vo import CaseModel
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase
from module_hrm.enums.enums import TstepTypeEnum
from module_hrm.service.load_data_service import OldDatabase, CoverData
from utils.log_util import *
from utils.response_util import *

hrmLoadController = APIRouter(prefix='/hrm/load')


@hrmLoadController.get("/api")
async def api_load(request: Request,
                   query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        old_api_data = OldDatabase().api()
        api_models = CoverData().api(old_api_data)
        for api_model in api_models:
            print(api_model.api_id)
            ApiOperation.add(query_db, api_model)
        return ResponseUtil.success(data="完成")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmLoadController.get("/env")
async def env_load(request: Request,
                   query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        old_api_data = OldDatabase().env()
        api_models = CoverData().env(old_api_data)
        for api_model in api_models:
            print(api_model.env_id)
            EnvDao.add_env_dao(query_db, api_model)
        query_db.commit()
        return ResponseUtil.success(data="完成")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmLoadController.get("/project")
async def project_load(request: Request,
                       query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        old_api_data = OldDatabase().project()
        api_models = CoverData().project(old_api_data)
        for api_model in api_models:
            print(api_model.project_id)
            ProjectDao.add_project_dao(query_db, api_model)
        query_db.commit()
        return ResponseUtil.success(data="完成")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmLoadController.get("/debugtalk")
async def debugtalk_load(request: Request,
                         query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        old_api_data = OldDatabase().debugtalk()
        api_models = CoverData().debugtalk(old_api_data)
        for api_model in api_models:
            print(api_model.debugtalk_id)
            DebugTalkDao.add_debugtalk_dao(query_db, api_model)
        query_db.commit()
        return ResponseUtil.success(data="完成")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmLoadController.get("/module")
async def module_load(request: Request,
                      query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        old_api_data = OldDatabase().module()
        api_models = CoverData().module(old_api_data)
        for api_model in api_models:
            print(api_model.module_id)
            ModuleDao.add_module_dao(query_db, api_model)
        query_db.commit()
        return ResponseUtil.success(data="完成")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@hrmLoadController.get("/case")
async def case_load(request: Request,
                    query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        old_api_data = OldDatabase().case()
        api_models = CoverData().case(old_api_data)
        for api_model in api_models:
            print(api_model.case_id)
            CaseDao.add_case_dao(query_db, api_model)
        query_db.commit()
        return ResponseUtil.success(data="完成")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))



@hrmLoadController.get("/updateCase")
async def update_case(request: Request,
                        query_db: Session = Depends(get_db)
                        ):
    try:
        all_case_orm = query_db.query(HrmCase).all()
        for case in all_case_orm:
            case_request: TestCase = json.loads(case.request)
            for step in case_request["teststeps"]:
                if step["step_type"] == 1:
                    step["step_type"] = TstepTypeEnum.http
                elif step["step_type"] == 2:
                    step["step_type"] = TstepTypeEnum.websocket
            query_db.query(HrmCase).filter(HrmCase.case_id == case.case_id).update({"request": case_request.model_dump(exclude_unset=True)})
            logger.info(f"case_id:{case.case_id}更新成功")
        query_db.commit()
        return ResponseUtil.success(msg="处理成功")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))