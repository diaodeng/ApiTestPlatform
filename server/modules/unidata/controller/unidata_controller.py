"""大数据查询控制器：只负责路由、参数模型与鉴权，业务编排下沉到 service。"""
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.service.login_service import LoginService
from modules.unidata.entity.vo.unidata_vo import (
    UnidataColumnQueryModel,
    UnidataQueryRequestModel,
    UnidataTableQueryModel,
)
from modules.unidata.service.unidata_engine_service import UnidataEngineService
from modules.unidata.service.unidata_query_service import UnidataQueryService
from utils.response_util import ResponseUtil

unidataController = APIRouter(prefix="/unidata", dependencies=[Depends(LoginService.get_current_user)])


@unidataController.get("/sources")
async def list_sources(request: Request, query_db: Session = Depends(get_db)):
    """获取启用的大数据查询数据源下拉选项。"""
    return ResponseUtil.success(data=await run_in_threadpool(UnidataQueryService.list_source_options, query_db))


@unidataController.get("/sources/{source_code}/databases")
async def list_databases(request: Request, source_code: str, query_db: Session = Depends(get_db)):
    """获取当前账号有权限的数据库清单（权限驱动，附分层信息）。"""
    try:
        data = await run_in_threadpool(UnidataQueryService.list_databases, query_db, source_code)
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))
    return ResponseUtil.success(data=[item.model_dump(by_alias=True) for item in data])


@unidataController.get("/sources/{source_code}/engines")
async def list_engines(request: Request, source_code: str, refresh: bool = False, query_db: Session = Depends(get_db)):
    """动态探测数据源可用的查询引擎（带缓存，refresh=true 强制重新探测）。"""
    try:
        data = await run_in_threadpool(UnidataEngineService.list_engine_statuses, query_db, source_code, refresh)
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))
    return ResponseUtil.success(data=[item.model_dump(by_alias=True) for item in data])


@unidataController.get("/sources/{source_code}/tables")
async def list_tables(
    request: Request,
    source_code: str,
    query: UnidataTableQueryModel = Depends(UnidataTableQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """获取指定库下的表清单（支持表名/中文名过滤与分页）。"""
    try:
        data = await run_in_threadpool(
            UnidataQueryService.list_tables,
            query_db,
            source_code,
            query.db_name,
            query.keyword,
            query.page_no,
            query.page_size,
        )
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))
    rows = [row.model_dump(by_alias=True) for row in data["rows"]]
    return ResponseUtil.success(data={"total": data["total"], "rows": rows})


@unidataController.get("/sources/{source_code}/table-columns")
async def list_table_columns(
    request: Request,
    source_code: str,
    query: UnidataColumnQueryModel = Depends(UnidataColumnQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """获取表的字段清单（字段名/类型/备注），供左侧树展开表节点使用。"""
    try:
        data = await run_in_threadpool(UnidataQueryService.list_columns, query_db, source_code, query.table_full_name)
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))
    return ResponseUtil.success(data=[item.model_dump(by_alias=True) for item in data])


@unidataController.post("/sources/{source_code}/query")
async def execute_query(
    request: Request,
    source_code: str,
    model: UnidataQueryRequestModel,
    query_db: Session = Depends(get_db),
):
    """执行只读 SQL 查询，返回列结构与数据行。"""
    try:
        result = await run_in_threadpool(UnidataQueryService.execute_query, query_db, source_code, model)
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))
    return ResponseUtil.success(data=result.model_dump(by_alias=True))
