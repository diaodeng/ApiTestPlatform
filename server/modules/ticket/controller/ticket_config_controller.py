
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from context.request_context import get_current_trace_id
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_vo import (
    KnowledgeArticleModel,
    KnowledgeArticleQueryModel,
    TicketEmbeddingRebuildRequestModel,
    TicketSimilarityConfigModel,
    TicketStatisticsQueryModel,
    WorkflowStatusModel,
    WorkflowTransitionModel,
)
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketConfigController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])

@ticketConfigController.get(
    "/similarity/config",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:similarity:config:list"))],
)
async def get_ticket_similarity_config(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单相似度检索配置接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 当前相似度 Provider、Embedding 和 Qdrant 配置
    """
    try:
        config = await run_in_threadpool(TicketEmbeddingService.ensure_default_config, query_db)
        return ResponseUtil.success(data=config)
    except Exception as e:
        query_db.rollback()
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.put(
    "/similarity/config",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:similarity:config:edit"))],
)
async def save_ticket_similarity_config(
    request: Request,
    config_object: TicketSimilarityConfigModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    保存工单相似度检索配置接口。
    :param request: 请求对象
    :param config_object: Provider、Embedding、Qdrant 和场景触发开关配置
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 保存后的规范化配置
    """
    try:
        data = config_object.model_dump(by_alias=True, exclude_none=False)
        saved_config = await run_in_threadpool(
            TicketEmbeddingService.save_similarity_config,
            query_db,
            data,
            current_user_name=current_user.user.user_name if current_user and current_user.user else "system",
        )
        return ResponseUtil.success(data=saved_config, msg="保存成功")
    except Exception as e:
        query_db.rollback()
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.post(
    "/similarity/rebuild",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:similarity:rebuild"))],
)
async def rebuild_ticket_similarity_embeddings(
    request: Request,
    background_tasks: BackgroundTasks,
    rebuild_object: TicketEmbeddingRebuildRequestModel,
    query_db: Session = Depends(get_db),
):
    """
    重建工单相似度向量接口。
    :param request: 请求对象
    :param background_tasks: FastAPI 后台任务容器
    :param rebuild_object: 重建范围、批大小和 Provider 参数
    :param query_db: 数据库会话
    :return: 后台提交结果或同步重建摘要
    """
    try:
        if rebuild_object.run_in_background:
            trace_id = get_current_trace_id()
            background_tasks.add_task(TicketEmbeddingService.rebuild_with_independent_session, rebuild_object, trace_id)
            return ResponseUtil.success(
                data={
                    "mode": "background",
                    "ticketIds": rebuild_object.ticket_ids,
                    "allTickets": rebuild_object.all_tickets,
                    "pageSize": rebuild_object.page_size,
                    "provider": rebuild_object.provider,
                    "includeQdrant": rebuild_object.include_qdrant,
                },
                msg="工单向量重建任务已提交后台执行",
            )
        result = await run_in_threadpool(TicketEmbeddingService.rebuild_result_with_independent_session, rebuild_object)
        return ResponseUtil.success(data=result, msg="工单向量重建完成")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
@ticketConfigController.get(
    "/workflow/config",
    dependencies=[Depends(CheckUserInterfaceAuth(["ticket:workflow:list", "ticket:ticket:status"], False))],
)
async def get_ticket_workflow(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单工作流配置接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 状态列表和流转配置
    """
    try:
        return ResponseUtil.success(data=TicketService.get_workflow_services(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.post("/workflow/status", dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:edit"))])
async def save_workflow_status(
    request: Request,
    status_object: WorkflowStatusModel,
    query_db: Session = Depends(get_db),
):
    """
    保存工作流状态节点接口。
    :param request: 请求对象
    :param status_object: 状态ID、编码、名称、是否开始状态、是否结束状态和排序
    :param query_db: 数据库会话
    :return: 保存结果
    """
    try:
        result = TicketService.save_workflow_status(query_db, status_object)
        if result.is_success:
            return ResponseUtil.success(data=result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.delete(
    "/workflow/status/{status_id}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:remove"))]
)
async def delete_workflow_status(request: Request, status_id: int, query_db: Session = Depends(get_db)):
    """
    删除工作流状态节点接口。
    :param request: 请求对象
    :param status_id: 状态节点ID
    :param query_db: 数据库会话
    :return: 删除结果；已被工单、历史或流转规则引用时会拒绝删除
    """
    try:
        result = TicketService.delete_workflow_status(query_db, status_id)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.post(
    "/workflow/transition",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:edit"))],
)
async def save_workflow_transition(
    request: Request, transition_object: WorkflowTransitionModel, query_db: Session = Depends(get_db)
):
    """
    保存工作流流转规则接口。
    :param request: 请求对象
    :param transition_object: 流转ID、原状态、目标状态、允许角色、是否需要说明和是否需要解决方案
    :param query_db: 数据库会话
    :return: 保存结果
    """
    try:
        result = TicketService.save_workflow_transition(query_db, transition_object)
        if result.is_success:
            return ResponseUtil.success(data=result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.delete(
    "/workflow/transition/{transition_id}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:remove"))]
)
async def delete_workflow_transition(request: Request, transition_id: int, query_db: Session = Depends(get_db)):
    """
    删除工作流流转规则接口。
    :param request: 请求对象
    :param transition_id: 流转规则ID
    :param query_db: 数据库会话
    :return: 删除结果
    """
    try:
        result = TicketService.delete_workflow_transition(query_db, transition_id)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
@ticketConfigController.get(
    "/stat-classification/options",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))],
)
async def get_ticket_stat_classification_options(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单分类统计枚举选项接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 工单类型、根因分类、解决方式和关闭结果选项
    """
    try:
        return ResponseUtil.success(data=TicketSyncConfigService.get_ticket_stat_classification_options(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.get(
    "/statistics/overview",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:statistics:list"))],
)
async def get_ticket_statistics(
    request: Request,
    query: TicketStatisticsQueryModel = Depends(TicketStatisticsQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取工单统计接口，时间范围按工单提交时间统计。
    :param request: 请求对象
    :param query: 提交时间范围、项目ID、模块ID和模块业务码筛选参数
    :param query_db: 数据库会话
    :return: 总量、平均处理耗时、状态分布、分类分布和人员处理量
    """
    try:
        statistics = await run_in_threadpool(
            TicketService.get_statistics_services,
            query_db,
            query.begin_time,
            query.end_time,
            query.project_ids,
            query.module_ids,
            query.module_codes,
        )
        return ResponseUtil.success(data=statistics)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.get(
    "/statistics/trend",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:statistics:list"))],
)
async def get_ticket_statistics_trend(
    request: Request,
    query: TicketStatisticsQueryModel = Depends(TicketStatisticsQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取工单趋势统计接口，新增和存量按工单提交时间归属趋势桶。
    :param request: 请求对象
    :param query: 提交时间范围、项目、模块、粒度和细分问题筛选参数
    :param query_db: 数据库会话
    :return: 按天、周或月分桶的新增、关闭、存量和分类趋势
    """
    try:
        statistics = await run_in_threadpool(
            TicketService.get_statistics_trend_services,
            query_db,
            query.begin_time,
            query.end_time,
            query.project_ids,
            query.module_ids,
            query.module_codes,
            query.granularity,
            query.problem_pattern_codes,
        )
        return ResponseUtil.success(data=statistics)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
@ticketConfigController.get("/knowledge/list", dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:list"))])
async def get_knowledge_list(
    request: Request,
    query: KnowledgeArticleQueryModel = Depends(KnowledgeArticleQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取知识库文章列表接口。
    :param request: 请求对象
    :param query: 文章标题、分类和关键字查询条件
    :param query_db: 数据库会话
    :return: 知识库文章分页列表
    """
    try:
        query_result = TicketService.get_knowledge_list_services(query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=query_result)
        return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.post("/knowledge", dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:add"))])
async def add_knowledge(
    request: Request,
    article_object: KnowledgeArticleModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增知识库文章接口。
    :param request: 请求对象
    :param article_object: 标题、内容、分类、标签和关联工单ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入创建人
    :return: 新增结果
    """
    try:
        result = TicketService.create_knowledge(query_db, article_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.put("/knowledge", dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:edit"))])
async def edit_knowledge(
    request: Request,
    article_object: KnowledgeArticleModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    编辑知识库文章接口。
    :param request: 请求对象
    :param article_object: 文章ID、标题、内容、分类、标签和关联工单ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 编辑结果
    """
    try:
        result = TicketService.update_knowledge(query_db, article_object, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.get(
    "/knowledge/{article_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:query"))],
)
async def get_knowledge_detail(request: Request, article_id: int, query_db: Session = Depends(get_db)):
    """
    获取知识库文章详情接口。
    :param request: 请求对象
    :param article_id: 文章ID
    :param query_db: 数据库会话
    :return: 文章详情
    """
    try:
        result = TicketService.get_knowledge_detail_services(query_db, article_id)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="知识库文章不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketConfigController.delete(
    "/knowledge/{article_id}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:remove"))]
)
async def delete_knowledge(
    request: Request,
    article_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    删除知识库文章接口。
    :param request: 请求对象
    :param article_id: 文章ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 删除结果
    """
    try:
        result = TicketService.delete_knowledge(query_db, article_id, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
