"""
工单导出服务，负责导出列定义、数据查询、格式化与 Excel 生成。

职责边界：
- 不直接操作 HTTP 请求/响应。
- 查询逻辑委托 DAO，装饰逻辑复用已有 service。
- Excel 字节生成委托 ticket_excel_export_util。
"""
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.dao.ticket_issue_dao import TicketIssueDao
from modules.ticket.entity.vo.ticket_export_vo import (
    TicketExportRequestModel,
    TicketIssueTicketExportRequestModel,
)
from modules.ticket.entity.vo.ticket_vo import TicketQueryModel
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.core.ticket_version_service import TicketVersionService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.util.ticket_excel_export_util import (
    MAX_EXPORT_ROWS,
    ExportColumn,
    generate_excel_bytes,
)
from utils.common_util import CamelCaseUtil
from utils.log_util import logger

# =============================================================================
# 工单导出列定义（与 Web 页面列名保持一致）
# =============================================================================
TICKET_EXPORT_COLUMNS: list[ExportColumn] = [
    ExportColumn(key="index", label="序号"),
    ExportColumn(key="ticketNo", label="工单编号"),
    ExportColumn(key="title", label="标题"),
    ExportColumn(key="similarityScore", label="相似度"),
    ExportColumn(key="issueNo", label="问题编号"),
    ExportColumn(key="issueConfirmed", label="归因确认"),
    ExportColumn(key="issueTitle", label="问题标题"),
    ExportColumn(key="issueRelationType", label="归因类型"),
    ExportColumn(key="status", label="状态"),
    ExportColumn(key="processStatus", label="日志/AI进度"),
    ExportColumn(key="processingConclusionStatus", label="处理结论"),
    ExportColumn(key="project", label="项目"),
    ExportColumn(key="moduleName", label="模块"),
    ExportColumn(key="issueType", label="工单类型"),
    ExportColumn(key="isProblem", label="问题性质"),
    ExportColumn(key="rootCauseType", label="根因分类"),
    ExportColumn(key="solutionType", label="解决方式"),
    ExportColumn(key="resolution", label="关闭结果"),
    ExportColumn(key="problemPattern", label="细分问题"),
    ExportColumn(key="customerPriority", label="对方优先级"),
    ExportColumn(key="internalPriority", label="内部优先级"),
    ExportColumn(key="source", label="来源"),
    ExportColumn(key="firstLineAssigneeName", label="1线人员"),
    ExportColumn(key="internalOwnerName", label="内部负责人"),
    ExportColumn(key="currentAssigneeName", label="当前处理人"),
    ExportColumn(key="submitTime", label="工单提交时间"),
    ExportColumn(key="firstResponseAt", label="首次响应时间"),
    ExportColumn(key="processedAt", label="处理完成时间"),
    ExportColumn(key="affectedVersion", label="影响版本"),
    ExportColumn(key="plannedFixVersion", label="计划修复版本"),
    ExportColumn(key="fixedVersion", label="实际修复版本"),
    ExportColumn(key="releasedVersion", label="实际发版版本"),
    ExportColumn(key="createTime", label="创建时间"),
]

# =============================================================================
# 问题实例导出工单列定义（必须包含问题编号、问题名）
# =============================================================================
ISSUE_TICKET_EXPORT_COLUMNS: list[ExportColumn] = [
    ExportColumn(key="issueNo", label="问题编号", required=True),
    ExportColumn(key="issueTitle", label="问题名", required=True),
    ExportColumn(key="ticketNo", label="工单编号"),
    ExportColumn(key="title", label="标题"),
    ExportColumn(key="status", label="状态"),
    ExportColumn(key="project", label="项目"),
    ExportColumn(key="moduleName", label="模块"),
    ExportColumn(key="issueType", label="工单类型"),
    ExportColumn(key="isProblem", label="问题性质"),
    ExportColumn(key="rootCauseType", label="根因分类"),
    ExportColumn(key="solutionType", label="解决方式"),
    ExportColumn(key="resolution", label="关闭结果"),
    ExportColumn(key="problemPattern", label="细分问题"),
    ExportColumn(key="customerPriority", label="对方优先级"),
    ExportColumn(key="internalPriority", label="内部优先级"),
    ExportColumn(key="source", label="来源"),
    ExportColumn(key="firstLineAssigneeName", label="1线人员"),
    ExportColumn(key="internalOwnerName", label="内部负责人"),
    ExportColumn(key="currentAssigneeName", label="当前处理人"),
    ExportColumn(key="submitTime", label="工单提交时间"),
    ExportColumn(key="firstResponseAt", label="首次响应时间"),
    ExportColumn(key="processedAt", label="处理完成时间"),
    ExportColumn(key="createTime", label="创建时间"),
]

# =============================================================================
# 状态中文映射（与前端 constants.js 保持一致）
# =============================================================================
STATUS_LABEL_MAP: dict[str, str] = {
    "pending": "待受理",
    "processing": "处理中",
    "wait_user": "待用户反馈",
    "wait_dev": "待开发",
    "wait_release": "待上线",
    "wait_verify": "待验证",
    "resolved": "已解决",
    "closed": "已关闭",
    "rejected": "已驳回",
    "non_problem": "非问题",
    "design_as_expected": "设计如此",
    "user_misoperation": "用户误操作",
    "duplicated": "重复工单",
}

SOURCE_LABEL_MAP: dict[str, str] = {
    "customer": "客户反馈",
    "support": "客服录入",
    "test": "测试发现",
    "monitor": "监控告警",
    "internal": "内部巡检",
}

class TicketExportService:
    """工单导出服务，提供工单列表和问题实例关联工单的导出能力。"""

    # ------------------------------------------------------------------
    # 工单列表导出
    # ------------------------------------------------------------------
    @classmethod
    def export_tickets(
        cls,
        query_db: Session,
        export_request: TicketExportRequestModel,
    ) -> bytes:
        """
        按选中工单或筛选条件导出工单列表为 Excel 字节流。
        :param query_db: 数据库会话
        :param export_request: 导出请求模型（选中工单ID、筛选条件、列配置）
        :return: Excel 文件字节流
        """
        # 解析导出列
        columns = cls._resolve_export_columns(
            TICKET_EXPORT_COLUMNS, export_request.columns
        )
        logger.info(
            f"工单导出: 选中工单数={len(export_request.selected_ticket_ids)}, "
            f"导出列数={len(columns)}"
        )

        # 查询数据
        if export_request.selected_ticket_ids:
            rows = cls._export_tickets_by_ids(query_db, export_request.selected_ticket_ids)
        else:
            # 未选择工单时严格按前端传入的当前筛选条件导出。
            rows = cls._export_tickets_by_query(query_db, export_request.query)

        if not rows:
            logger.info("工单导出: 无匹配数据，生成仅表头的 Excel")
            return generate_excel_bytes(columns, [], sheet_name="工单列表")

        # 格式化行数据
        formatted_rows = cls._format_ticket_rows(query_db, columns, rows)

        logger.info(f"工单导出: 共导出 {len(formatted_rows)} 行")
        return generate_excel_bytes(columns, formatted_rows, sheet_name="工单列表")

    @classmethod
    def _export_tickets_by_ids(
        cls, query_db: Session, ticket_ids: list[int]
    ) -> list[dict[str, Any]]:
        """
        按工单ID列表查询并装饰工单数据。
        :param query_db: 数据库会话
        :param ticket_ids: 工单ID列表
        :return: 装饰后的工单字典列表
        """
        if len(ticket_ids) > MAX_EXPORT_ROWS:
            raise ValueError(
                f"选中的工单超过单次导出上限 {MAX_EXPORT_ROWS} 条，请减少勾选数量后重试。"
            )
        query = TicketQueryModel(
            ticket_ids=",".join(str(tid) for tid in ticket_ids),
            page_num=1,
            page_size=MAX_EXPORT_ROWS + 1,
            is_page=True,
        )
        query = TicketService._build_ticket_list_filter_query(query_db, query)
        result = TicketDao.get_ticket_list(query_db, query)
        rows = cls._extract_ticket_rows(result)
        cls._check_export_row_limit(rows)

        # 复用列表装饰逻辑
        all_ids = [item.get("ticketId") for item in rows if isinstance(item, dict) and item.get("ticketId")]
        summary_map = TicketLogPullService.get_latest_summary_map(query_db, all_ids)
        ai_summary_map = TicketAiAnalysisService.get_latest_summary_map(query_db, all_ids)
        for item in rows:
            if isinstance(item, dict):
                TicketService._decorate_ticket_item(item)
                item["latestLogPull"] = summary_map.get(item.get("ticketId"))
                item["latestAiAnalysis"] = ai_summary_map.get(item.get("ticketId"))
        TicketVersionService.attach_ticket_version_labels(query_db, rows)
        TicketService._attach_issue_summary(query_db, rows)
        return rows

    @classmethod
    def _export_tickets_by_query(
        cls, query_db: Session, query: TicketQueryModel | None = None
    ) -> list[dict[str, Any]]:
        """
        按当前筛选条件全量查询并装饰工单数据（不分页）。
        :param query_db: 数据库会话
        :param query: 当前工单列表筛选条件
        :return: 装饰后的工单字典列表
        """
        # 导出查询不分页，但限制最大行数，避免单次请求读取无限数据。
        export_query = query or TicketQueryModel()
        export_query = export_query.model_copy(
            # 多取 1 行用于判断是否超过上限，同时避免 query.all() 将全部结果加载到内存。
            update={"page_num": 1, "page_size": MAX_EXPORT_ROWS + 1, "is_page": True}
        )
        export_query = TicketService._build_ticket_list_filter_query(query_db, export_query)
        result = TicketDao.get_ticket_list(query_db, export_query)
        rows = cls._extract_ticket_rows(result)
        cls._check_export_row_limit(rows)

        all_ids = [item.get("ticketId") for item in rows if isinstance(item, dict) and item.get("ticketId")]
        summary_map = TicketLogPullService.get_latest_summary_map(query_db, all_ids)
        ai_summary_map = TicketAiAnalysisService.get_latest_summary_map(query_db, all_ids)
        for item in rows:
            if isinstance(item, dict):
                TicketService._decorate_ticket_item(item)
                item["latestLogPull"] = summary_map.get(item.get("ticketId"))
                item["latestAiAnalysis"] = ai_summary_map.get(item.get("ticketId"))
        TicketVersionService.attach_ticket_version_labels(query_db, rows)
        TicketService._attach_issue_summary(query_db, rows)
        return rows

    @staticmethod
    def _extract_ticket_rows(result: Any) -> list[dict[str, Any]]:
        """
        从工单 DAO 返回结果中提取行数据。

        DAO 在分页查询时返回 PageResponseModel，在非分页查询时返回列表；
        Pydantic 模型不能直接用 list(result) 转成行列表，否则会得到
        ('rows', [...]) 这样的字段元组，进而导致格式化阶段调用 tuple.get() 报错。
        :param result: DAO 查询结果
        :return: 工单字典行列表
        """
        if result is None:
            return []
        if hasattr(result, "rows"):
            rows = result.rows or []
        elif isinstance(result, list):
            rows = result
        elif isinstance(result, dict):
            rows = result.get("rows") or []
        else:
            logger.warning(f"工单导出: DAO 返回了不支持的结果类型 {type(result).__name__}")
            return []
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _check_export_row_limit(rows: list[dict[str, Any]]) -> None:
        """
        校验导出行数上限。
        :param rows: 待导出的工单行
        :return: 无返回值，超限时抛出 ValueError
        """
        if len(rows) > MAX_EXPORT_ROWS:
            raise ValueError(
                f"当前匹配 {len(rows)} 条，超过单次导出上限 {MAX_EXPORT_ROWS} 条，请缩小筛选条件后重试。"
            )

    # ------------------------------------------------------------------
    # 问题实例关联工单导出
    # ------------------------------------------------------------------
    @classmethod
    def export_issue_tickets(
        cls,
        query_db: Session,
        export_request: TicketIssueTicketExportRequestModel,
    ) -> bytes:
        """
        按选中的问题实例导出其关联工单为 Excel 字节流。
        :param query_db: 数据库会话
        :param export_request: 导出请求模型（选中问题实例ID、列配置）
        :return: Excel 文件字节流
        """
        if not export_request.selected_issue_ids:
            raise ValueError("请先选择问题实例")

        columns = cls._resolve_export_columns(
            ISSUE_TICKET_EXPORT_COLUMNS, export_request.columns
        )
        logger.info(
            f"问题实例工单导出: 选中问题数={len(export_request.selected_issue_ids)}, "
            f"导出列数={len(columns)}"
        )

        # 查询问题实例及其关联工单
        rows = cls._query_issue_tickets(query_db, export_request.selected_issue_ids)

        if not rows:
            logger.info("问题实例工单导出: 无匹配数据，生成仅表头的 Excel")
            return generate_excel_bytes(columns, [], sheet_name="问题实例关联工单")

        # 格式化行数据
        formatted_rows = cls._format_issue_ticket_rows(query_db, columns, rows)

        logger.info(f"问题实例工单导出: 共导出 {len(formatted_rows)} 行")
        return generate_excel_bytes(columns, formatted_rows, sheet_name="问题实例关联工单")

    @classmethod
    def _query_issue_tickets(
        cls, query_db: Session, issue_ids: list[int]
    ) -> list[dict[str, Any]]:
        """
        查询问题实例及其关联工单，返回组合行列表。
        每行包含问题实例信息和工单信息。
        :param query_db: 数据库会话
        :param issue_ids: 问题实例ID列表
        :return: 问题实例与工单组合字典列表
        """
        # 查询问题实例
        issues = TicketIssueDao.list_issue_summary_by_ids(query_db, issue_ids)
        if not issues:
            return []

        rows = []
        ticket_ids_for_decorate = []

        for issue_id, issue in issues.items():
            issue_dict = CamelCaseUtil.transform_result(issue)
            tickets = TicketIssueDao.list_tickets_by_issue_id(query_db, issue_id)
            if tickets:
                for ticket in tickets:
                    ticket_dict = CamelCaseUtil.transform_result(ticket)
                    ticket_dict["issueNo"] = issue_dict.get("issueNo") or issue.issue_no
                    ticket_dict["issueTitle"] = issue_dict.get("title") or issue.title
                    rows.append(ticket_dict)
                    ticket_ids_for_decorate.append(ticket.ticket_id)
            else:
                # 没有工单的问题实例也生成一行
                row = {
                    "ticketId": None,
                    "issueNo": issue_dict.get("issueNo") or issue.issue_no,
                    "issueTitle": issue_dict.get("title") or issue.title,
                }
                rows.append(row)

        # 装饰工单字段
        if ticket_ids_for_decorate:
            summary_map = TicketLogPullService.get_latest_summary_map(query_db, ticket_ids_for_decorate)
            ai_summary_map = TicketAiAnalysisService.get_latest_summary_map(query_db, ticket_ids_for_decorate)
            for item in rows:
                tid = item.get("ticketId")
                if tid and isinstance(item, dict):
                    TicketService._decorate_ticket_item(item)
                    item["latestLogPull"] = summary_map.get(tid)
                    item["latestAiAnalysis"] = ai_summary_map.get(tid)
            TicketVersionService.attach_ticket_version_labels(query_db, rows)

        return rows

    # ------------------------------------------------------------------
    # 列解析
    # ------------------------------------------------------------------
    @classmethod
    def _resolve_export_columns(
        cls,
        all_columns: list[ExportColumn],
        requested_keys: list[str],
    ) -> list[ExportColumn]:
        """
        按请求的 key 列表解析最终导出列，未指定时使用全部列。
        :param all_columns: 全部可用列定义
        :param requested_keys: 前端传入的列 key 列表
        :return: 最终导出列列表
        """
        if not requested_keys:
            return list(all_columns)
        key_set = set(requested_keys)
        resolved = [col for col in all_columns if col.key in key_set]
        if not resolved:
            return list(all_columns)
        return resolved

    # ------------------------------------------------------------------
    # 行格式化（工单列表导出）
    # ------------------------------------------------------------------
    @classmethod
    def _format_ticket_rows(
        cls,
        query_db: Session,
        columns: list[ExportColumn],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        将装饰后的工单字典列表格式化为导出用行数据。
        :param query_db: 数据库会话
        :param columns: 导出列定义
        :param rows: 装饰后的工单字典列表
        :return: 格式化后的行数据列表
        """
        return [cls._format_ticket_row(query_db, columns, idx, row) for idx, row in enumerate(rows, 1)]

    @classmethod
    def _format_ticket_row(
        cls,
        query_db: Session,
        columns: list[ExportColumn],
        index: int,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        """
        格式化单行工单数据。
        :param query_db: 数据库会话
        :param columns: 导出列定义
        :param index: 行序号
        :param row: 装饰后的工单字典
        :return: 格式化后的行字典
        """
        result: dict[str, Any] = {}
        for col in columns:
            result[col.key] = cls._format_ticket_field(query_db, col.key, row, index)
        return result

    @classmethod
    def _format_ticket_field(
        cls,
        query_db: Session,
        key: str,
        row: dict[str, Any],
        index: int,
    ) -> str:
        """
        格式化单个工单导出字段。
        :param query_db: 数据库会话
        :param key: 列 key
        :param row: 装饰后的工单字典
        :param index: 行序号
        :return: 格式化后的字符串
        """
        if key == "index":
            return str(index)
        if key == "ticketNo":
            return str(row.get("ticketNo") or row.get("ticket_no") or "")
        if key == "title":
            return str(row.get("title") or "")
        if key == "similarityScore":
            score = row.get("similarityScore")
            return f"{float(score):.2f}" if score is not None else "-"
        if key == "issueNo":
            return str(row.get("issueNo") or "")
        if key == "issueConfirmed":
            confirmed = row.get("issueConfirmed")
            if confirmed is True:
                return "已确认"
            if confirmed is False:
                return "待确认"
            return "-"
        if key == "issueTitle":
            return str(row.get("issueTitle") or "")
        if key == "issueRelationType":
            return cls._format_relation_type(row.get("issueRelationType"))
        if key == "status":
            return cls._format_status(row.get("status"))
        if key == "processStatus":
            return cls._format_process_status(row)
        if key == "processingConclusionStatus":
            return "已处理" if row.get("processedAt") else "未处理"
        if key == "project":
            return str(row.get("projectName") or row.get("merchantName") or "")
        if key == "moduleName":
            return str(row.get("moduleName") or row.get("module_name") or "")
        if key == "issueType":
            return str(row.get("issueTypeName") or row.get("issueTypeId") or row.get("issue_type_id") or "")
        if key == "isProblem":
            return cls._format_is_problem(row.get("isProblem"))
        if key == "rootCauseType":
            return str(row.get("rootCauseType") or row.get("root_cause_type") or "")
        if key == "solutionType":
            return str(row.get("solutionType") or row.get("solution_type") or "")
        if key == "resolution":
            return str(row.get("resolutionName") or row.get("resolutionCode") or row.get("resolution_code") or "")
        if key == "problemPattern":
            return str(
                row.get("problemPatternName") or row.get("problemPatternCode") or row.get("problem_pattern_code") or ""
            )
        if key == "customerPriority":
            return str(row.get("customerPriority") or row.get("customer_priority") or "")
        if key == "internalPriority":
            return str(row.get("internalPriority") or row.get("internal_priority") or "")
        if key == "source":
            return cls._format_source(row.get("source"))
        if key == "firstLineAssigneeName":
            return str(row.get("firstLineAssigneeName") or row.get("first_line_assignee_name") or "")
        if key == "internalOwnerName":
            return str(row.get("internalOwnerName") or row.get("internal_owner_name") or "")
        if key == "currentAssigneeName":
            return str(row.get("currentAssigneeName") or row.get("current_assignee_name") or "")
        if key == "submitTime":
            return cls._format_datetime(row.get("submitTime") or row.get("submit_time"))
        if key == "firstResponseAt":
            return cls._format_datetime(row.get("firstResponseAt") or row.get("first_response_at"))
        if key == "processedAt":
            return cls._format_datetime(row.get("processedAt") or row.get("processed_at"))
        if key == "affectedVersion":
            return str(row.get("affectedVersion") or "")
        if key == "plannedFixVersion":
            return str(row.get("plannedFixVersion") or "")
        if key == "fixedVersion":
            return str(row.get("fixedVersion") or "")
        if key == "releasedVersion":
            return str(row.get("releasedVersion") or "")
        if key == "createTime":
            return cls._format_datetime(row.get("createTime") or row.get("create_time"))
        return str(row.get(key, ""))

    # ------------------------------------------------------------------
    # 行格式化（问题实例工单导出）
    # ------------------------------------------------------------------
    @classmethod
    def _format_issue_ticket_rows(
        cls,
        query_db: Session,
        columns: list[ExportColumn],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        将问题实例工单数据格式化为导出用行数据。
        :param query_db: 数据库会话
        :param columns: 导出列定义
        :param rows: 原始数据行
        :return: 格式化后的行数据列表
        """
        return [cls._format_issue_ticket_row(query_db, columns, idx, row) for idx, row in enumerate(rows, 1)]

    @classmethod
    def _format_issue_ticket_row(
        cls,
        query_db: Session,
        columns: list[ExportColumn],
        index: int,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        """
        格式化单行问题实例工单数据。
        :param query_db: 数据库会话
        :param columns: 导出列定义
        :param index: 行序号
        :param row: 原始数据字典
        :return: 格式化后的行字典
        """
        result: dict[str, Any] = {}
        for col in columns:
            result[col.key] = cls._format_ticket_field(query_db, col.key, row, index)
        return result

    # ------------------------------------------------------------------
    # 字段格式化辅助方法
    # ------------------------------------------------------------------
    @classmethod
    def _format_status(cls, value: Any) -> str:
        """格式化工单状态。"""
        if value is None:
            return "-"
        return STATUS_LABEL_MAP.get(str(value), str(value))

    @classmethod
    def _format_process_status(cls, row: dict[str, Any]) -> str:
        """
        格式化日志/AI进度（与前端 resolveTicketProcessStatus 逻辑一致）。
        :param row: 工单字典
        :return: 进度中文描述
        """
        latest_log = row.get("latestLogPull") or {}
        latest_ai = row.get("latestAiAnalysis") or {}
        log_status = str(latest_log.get("status") or "").lower()
        ai_status = str(latest_ai.get("status") or "").lower()

        if ai_status:
            if ai_status in ("running", "created"):
                return "AI分析中"
            if ai_status == "success":
                return "AI分析完成"
            if ai_status in ("failed", "canceled"):
                return "AI分析失败"

        if not latest_log or not log_status:
            return "未拉取"

        if log_status == "success" and not latest_ai:
            return "AI未分析"
        if log_status == "failed":
            return "拉取失败"

        # 日志拉取其他状态
        LOG_STATUS_MAP = {
            "created": "日志待执行",
            "submitting": "提交申请中",
            "polling": "轮询处理中",
            "downloading": "下载中",
            "processing": "解析中",
            "success": "日志拉取成功",
            "exception": "程序异常",
            "cancelled": "已取消",
        }
        return LOG_STATUS_MAP.get(log_status, latest_log.get("statusDesc") or log_status)

    @classmethod
    def _format_relation_type(cls, value: Any) -> str:
        """格式化归因关系类型。"""
        if value is None:
            return "-"
        MAP = {"manual": "人工确认", "similar": "相似归因", "external": "外部关联"}
        return MAP.get(str(value), str(value))

    @classmethod
    def _format_is_problem(cls, value: Any) -> str:
        """格式化问题性质。"""
        if value is True:
            return "真实问题"
        if value is False:
            return "非问题"
        return "-"

    @classmethod
    def _format_source(cls, value: Any) -> str:
        """格式化来源。"""
        if value is None:
            return "-"
        return SOURCE_LABEL_MAP.get(str(value), str(value))

    @staticmethod
    def _format_datetime(value: Any) -> str:
        """格式化时间字段为 YYYY-MM-DD HH:mm:ss。"""
        if value is None:
            return "-"
        from datetime import datetime as dt
        if isinstance(value, dt):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)
