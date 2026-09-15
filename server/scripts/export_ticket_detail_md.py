"""
工单详情页数据导出脚本（只读）。

用途：
- 按工单号从数据库导出与前端"工单详情页"一致的完整数据，并渲染为 Markdown 文档，供其他系统使用。
- 覆盖范围（与前端详情页各 Tab 对应）：
  1. 详情接口 GET /ticket/{id} 的全量字段：工单主记录、AI 翻译、同步摘要、版本标签、
     问题实例归属、日志拉取摘要、AI 分析摘要、协同消息、ACR 快照、相似工单、AI 提示词分层。
  2. 时间线接口 GET /ticket/{id}/timeline：状态历史、指派历史、事件、RCA。
  3. 评论列表 GET /ticket/{id}/comments。
  4. 日志拉取记录列表 GET /ticket/log-pulls-by-ticket?ticketId={id}。

副作用控制（重要）：
- 全程只执行 SELECT，不 commit、不写入任何业务表；
- 跳过详情接口中的相似工单向量子链路（TicketSimilarityQueryService 在向量缺失时会生成向量、
  调用外部 Embedding/Qdrant API 并写库），改为只读查询 ticket_relation 相似关系，
  并在文档中标注该差异；
- 其余装饰（项目名称、版本标签、问题实例、日志拉取/AI 分析摘要、提示词分层）均复用生产服务只读方法，
  保证字段口径与详情页一致。

使用方式：
    cd server
    uv run python scripts/export_ticket_detail_md.py INC00001939452 INC00001846424
    # 可选参数 --out-dir 指定输出目录，默认输出到 scripts/output/ticket_detail_export_<时间戳>/
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

# 强制使用 prod 环境配置（与 weekly_ticket_report.py 等脚本惯例一致）
os.environ["APP_ENV"] = "prod"
from dotenv import load_dotenv

env_file = SERVER_ROOT / ".env.prod"
if not env_file.exists():
    print(f"❌ 找不到配置文件: {env_file}")
    sys.exit(1)
load_dotenv(env_file, override=True)

from config.database import SessionLocal
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import (
    TicketRelation,
)
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullQueryModel
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from utils.common_util import CamelCaseUtil


def _json_default(obj):
    """JSON 序列化兜底：datetime/date/Decimal 等转字符串。"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat(sep=" ") if isinstance(obj, datetime) else obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8", errors="replace")
        except Exception:
            return repr(obj)
    return str(obj)


def _dump(obj, max_chars: int | None = None) -> str:
    """把 Python 对象序列化为 JSON 字符串，用于 md 中代码块展示。"""
    text = json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + f"\n...（内容过长已截断，完整长度 {len(text)} 字符）"
    return text


def _clean(value):
    """把数据库/JSON 值转为适合表格展示的单行字符串。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    text = str(value)
    # 压缩换行，避免破坏 md 表格结构
    return text.replace("\r\n", "\\n").replace("\n", "\\n").strip()


# 详情接口主记录中排除的字段（大 JSON 单独成节展示，避免表格里塞超长文本）
MAIN_TABLE_SECTIONS = {
    "extraData": "扩展字段（extra_data）",
    "aiAnalysis": "AI 分析预留字段（ai_analysis）",
    "tags": "标签（tags）",
    "aiPromptLayers": "AI 提示词分层（aiPromptLayers）",
    "syncSummary": "外部同步摘要（syncSummary）",
    "latestLogPull": "最新日志拉取摘要（latestLogPull）",
    "latestAiAnalysis": "最新 AI 分析摘要（latestAiAnalysis）",
    "issue": "归属问题实例（issue）",
}

# 相似工单/消息/快照等由详情接口附加的列表字段，单独成节
LIST_SECTIONS = {
    "messages": "协同消息流（messages）",
    "snapshots": "ACR 快照列表（snapshots）",
}


def render_ticket_md(ticket_no: str, bundle: dict) -> str:
    """把单个工单的完整数据渲染为 Markdown 文档。"""
    detail = bundle["detail"]
    lines: list[str] = []
    lines.append(f"# 工单详情导出：{ticket_no}")
    lines.append("")
    lines.append(f"> 导出时间：{datetime.now().isoformat(sep=' ', timespec='seconds')}")
    lines.append(
        "> 数据来源：api-test-platform 生产库（.env.prod），"
        "口径与前端工单详情页一致（详情 + 时间线 + 评论 + 日志拉取记录）。"
    )
    lines.append(
        "> 差异说明：详情页的“相似工单推荐”依赖向量化与外部 Embedding/Qdrant 服务且有写库副作用，"
        "本导出改为只读查询 ticket_relation 相似工单关系。"
    )
    lines.append("")

    # ── 一、工单主信息 ──
    lines.append("## 一、工单主信息")
    lines.append("")
    lines.append("| 字段 | 值 |")
    lines.append("| --- | --- |")
    skip = set(MAIN_TABLE_SECTIONS) | set(LIST_SECTIONS) | {
        "similarTickets", "symptomTickets", "caseTickets",
        "similarEmbeddingStatus", "similarEmbeddingMessage",
        "latestSnapshot",
    }
    for key in detail.keys():
        if key in skip:
            continue
        lines.append(f"| {key} | {_clean(detail.get(key))} |")
    lines.append("")

    # ── 二、大字段单独展示 ──
    lines.append("## 二、扩展与大字段")
    lines.append("")
    for key, title in MAIN_TABLE_SECTIONS.items():
        lines.append(f"### 2.{list(MAIN_TABLE_SECTIONS).index(key) + 1} {title}")
        lines.append("")
        value = detail.get(key)
        if value in (None, "", [], {}):
            lines.append("（空）")
        else:
            lines.append("```json")
            lines.append(_dump(value, max_chars=30000))
            lines.append("```")
        lines.append("")

    # ── 三、协同消息流与快照 ──
    lines.append("## 三、协同消息流与 ACR 快照")
    lines.append("")
    for key, title in LIST_SECTIONS.items():
        lines.append(f"### 3.{list(LIST_SECTIONS).index(key) + 1} {title}")
        lines.append("")
        items = detail.get(key) or []
        if not items:
            lines.append("（无记录）")
        else:
            for idx, item in enumerate(items, 1):
                head = ""
                if isinstance(item, dict):
                    head = " | ".join(
                        f"{k}: {_clean(v)}" for k, v in item.items()
                        if k in ("id", "role", "messageType", "version", "snapshotType", "createTime", "createBy") and v
                    )
                lines.append(f"**[{idx}]** {head}")
                lines.append("")
                lines.append("```json")
                lines.append(_dump(item, max_chars=20000))
                lines.append("```")
                lines.append("")

    # ── 四、相似工单（只读关系） ──
    lines.append("## 四、相似/关联工单（ticket_relation 只读口径）")
    lines.append("")
    relations = bundle["relations"]
    if not relations:
        lines.append("（无记录）")
    else:
        lines.append("| 关系类型 | 对端工单号 | 对端标题 | 置信度 | 来源 | 是否人工确认 | 备注 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for rel in relations:
            rel_row = (
                f"| {_clean(rel['relation_type'])} | {_clean(rel['peer_ticket_no'])} "
                f"| {_clean(rel['peer_title'])} | {_clean(rel['confidence'])} "
                f"| {_clean(rel['source'])} | {_clean(rel['confirmed'])} | {_clean(rel['remark'])} |"
            )
            lines.append(rel_row)
    lines.append("")

    # ── 五、时间线 ──
    timeline = bundle["timeline"]
    lines.append("## 五、时间线（状态/指派历史、事件、RCA）")
    lines.append("")

    status_history = timeline.get("statusHistory") or []
    lines.append("### 5.1 状态历史")
    lines.append("")
    if status_history:
        lines.append("| 状态变化 | 操作人 | 开始时间 | 结束时间 | 停留秒数 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in status_history:
            change = f"{_clean(row.get('fromStatus'))} → {_clean(row.get('toStatus'))}"
            status_row = (
                f"| {change} | {_clean(row.get('operatorName'))} | {_clean(row.get('startedAt'))} "
                f"| {_clean(row.get('endedAt'))} | {_clean(row.get('durationSeconds'))} "
                f"| {_clean(row.get('comment'))} |"
            )
            lines.append(status_row)
    else:
        lines.append("（无记录）")
    lines.append("")

    assign_history = timeline.get("assignHistory") or []
    lines.append("### 5.2 指派历史")
    lines.append("")
    if assign_history:
        lines.append("| 原处理人 | 新处理人 | 指派人 | 指派时间 | 原因 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in assign_history:
            assign_row = (
                f"| {_clean(row.get('fromUserName'))} | {_clean(row.get('toUserName'))} "
                f"| {_clean(row.get('assignedByName'))} | {_clean(row.get('assignedAt'))} "
                f"| {_clean(row.get('reason'))} |"
            )
            lines.append(assign_row)
    else:
        lines.append("（无记录）")
    lines.append("")

    events = timeline.get("events") or []
    lines.append("### 5.3 事件")
    lines.append("")
    if events:
        lines.append("| 事件类型 | 操作人 | 时间 | 内容 | 事件数据 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in events:
            event_row = (
                f"| {_clean(row.get('eventType'))} | {_clean(row.get('operatorName'))} "
                f"| {_clean(row.get('createTime'))} | {_clean(row.get('content'))} "
                f"| {_clean(row.get('eventData'))} |"
            )
            lines.append(event_row)
    else:
        lines.append("（无记录）")
    lines.append("")

    rca = timeline.get("rca")
    lines.append("### 5.4 RCA")
    lines.append("")
    if rca:
        lines.append("```json")
        lines.append(_dump(rca, max_chars=20000))
        lines.append("```")
    else:
        lines.append("（无记录）")
    lines.append("")

    # ── 六、评论 ──
    comments = bundle["comments"]
    lines.append("## 六、评论")
    lines.append("")
    if comments:
        for idx, row in enumerate(comments, 1):
            comment_head = (
                f"**[{idx}]** {_clean(row.get('userName'))} | {_clean(row.get('createTime'))} "
                f"| 内部评论: {_clean(row.get('isInternal'))} "
                f"| 来源: {_clean(row.get('sourceType'))}/{_clean(row.get('sourceSystem'))}"
            )
            lines.append(comment_head)
            lines.append("")
            content = str(row.get("content") or "").replace("\r\n", "\n")
            lines.append("```text")
            lines.append(content if content.strip() else "（空）")
            lines.append("```")
            attachments = row.get("attachments")
            if attachments:
                lines.append("附件/引用信息：")
                lines.append("```json")
                lines.append(_dump(attachments, max_chars=10000))
                lines.append("```")
            lines.append("")
    else:
        lines.append("（无评论）")
        lines.append("")

    # ── 七、日志拉取记录 ──
    log_pulls = bundle["logPulls"]
    lines.append("## 七、日志拉取记录")
    lines.append("")
    if log_pulls:
        rows = log_pulls if isinstance(log_pulls, list) else (log_pulls.get("rows") or [])
        lines.append(f"共 {len(rows)} 条记录。")
        lines.append("")
        for idx, row in enumerate(rows, 1):
            head_keys = (
                "recordId", "recordNo", "status", "applyStatus",
                "storeName", "instanceName", "logDate", "createTime",
            )
            head = " | ".join(
                f"{k}: {_clean(v)}" for k, v in row.items() if k in head_keys and v
            )
            lines.append(f"**[{idx}]** {head}")
            lines.append("")
            lines.append("```json")
            lines.append(_dump(row, max_chars=20000))
            lines.append("```")
            lines.append("")
    else:
        lines.append("（无记录）")
        lines.append("")

    return "\n".join(lines) + "\n"


# 简化版主信息字段：只保留详情页基本信息区实际展示的字段（中文标签 → 详情数据键）
BRIEF_MAIN_FIELDS: list[tuple[str, str]] = [
    ("编号", "ticketNo"),
    ("标题", "title"),
    ("状态", "status"),
    ("当前处理人", "currentAssigneeName"),
    ("所属项目", "projectName"),
    ("所属模块", "moduleName"),
    ("外部链接", "ticketUrl"),
    ("工单类型", "issueTypeName"),
    ("根因分类", "rootCauseType"),
    ("内部优先级", "internalPriority"),
    ("对方优先级", "customerPriority"),
    ("严重等级", "severity"),
    ("来源", "source"),
    ("提单人", "reporterName"),
    ("提交时间", "submitTime"),
    ("1线人员", "firstLineAssigneeName"),
    ("内部负责人", "internalOwnerName"),
    ("问题性质", "isProblem"),
    ("解决方式", "solutionType"),
    ("关闭结果", "resolutionName"),
    ("细分问题", "problemPatternName"),
    ("细分确认", "problemPatternVerified"),
    ("所属问题", "issueTitle"),
    ("归因类型", "issueRelationType"),
    ("归因确认", "issueConfirmed"),
    ("问题发生版本", "affectedVersion"),
    ("计划修复版本", "plannedFixVersion"),
    ("实际修复版本", "fixedVersion"),
    ("实际发版版本", "releasedVersion"),
    ("总耗时秒", "totalProcessSeconds"),
    ("首次响应时间", "firstResponseAt"),
    ("处置完成时间", "processedAt"),
    ("关闭时间", "closedAt"),
    ("日志拉取状态", "latestLogPull"),
]


def render_ticket_brief_md(ticket_no: str, bundle: dict) -> str:
    """
    渲染简化版 Markdown：只保留详情页各 Tab 实际展示的数据，不含原始 JSON 大字段。
    :param ticket_no: 工单号
    :param bundle: export_one 产出的数据包
    :return: 简化版 md 文本
    """
    detail = bundle["detail"]
    timeline = bundle["timeline"]
    lines: list[str] = []
    lines.append(f"# 工单摘要：{ticket_no}")
    lines.append("")
    lines.append(f"> 导出时间：{datetime.now().isoformat(sep=' ', timespec='seconds')}")
    lines.append("> 说明：仅保留工单详情页实际展示的数据；完整原始数据见同名完整版文档。")
    lines.append("")

    # ── 一、基本信息 ──
    lines.append("## 一、基本信息")
    lines.append("")
    lines.append("| 字段 | 值 |")
    lines.append("| --- | --- |")
    for label, key in BRIEF_MAIN_FIELDS:
        value = detail.get(key)
        if key == "latestLogPull":
            # 日志拉取状态只展示页面上的状态描述
            pull = value if isinstance(value, dict) else {}
            status = _clean(pull.get("statusDesc") or pull.get("status"))
            value = status or None
        if value in (None, ""):
            lines.append(f"| {label} | - |")
        else:
            lines.append(f"| {label} | {_clean(value)} |")
    lines.append("")

    # ── 二、工单描述 ──
    lines.append("## 二、工单描述")
    lines.append("")
    lines.append("**原文**")
    lines.append("")
    lines.append("```text")
    lines.append(str(detail.get("originalDescription") or "（空）"))
    lines.append("```")
    ai_translation = str(detail.get("aiTranslation") or "").strip()
    if ai_translation:
        lines.append("**AI 翻译**")
        lines.append("")
        lines.append("```text")
        lines.append(ai_translation)
        lines.append("```")
    lines.append("")

    # ── 三、最终处理 ──
    lines.append("## 三、最终处理")
    lines.append("")
    lines.append(f"- 根因：{_clean(detail.get('rootCause')) or '-'}")
    lines.append(f"- 解决方案：{_clean(detail.get('solution')) or '-'}")
    lines.append("")

    # ── 四、最新 AI 结论（页面概览 Tab 展示口径） ──
    snapshot = detail.get("latestSnapshot") or {}
    ai_task = detail.get("latestAiAnalysis") or {}
    lines.append("## 四、最新 AI 结论")
    lines.append("")
    snapshot_head = (
        f"- 快照版本：{_clean(snapshot.get('version')) or '-'}"
        f"｜快照时间：{_clean(snapshot.get('createTime')) or '-'}"
        f"｜创建人：{_clean(snapshot.get('createdByName')) or '-'}"
    )
    lines.append(snapshot_head)
    lines.append(f"- 摘要：{_clean(snapshot.get('summary')) or _clean(ai_task.get('analysisSummary')) or '-'}")
    lines.append(f"- 根因：{_clean(snapshot.get('rootCause')) or _clean(ai_task.get('rootCause')) or '-'}")
    lines.append(f"- 解决方案：{_clean(snapshot.get('solution')) or _clean(ai_task.get('fixSuggestion')) or '-'}")
    lines.append(f"- 预防建议：{_clean(snapshot.get('prevention')) or '-'}")
    lines.append(f"- 风险说明：{_clean(snapshot.get('risk')) or '-'}")
    lines.append(f"- 负责人：{_clean(snapshot.get('owner')) or '-'}")
    lines.append("")

    # ── 五、历史（状态流转 + 指派 + 排查事件，只保留页面展示的要素） ──
    lines.append("## 五、历史")
    lines.append("")
    status_history = timeline.get("statusHistory") or []
    if status_history:
        lines.append("### 状态流转")
        lines.append("")
        lines.append("| 状态变化 | 操作人 | 时间 | 说明 |")
        lines.append("| --- | --- | --- | --- |")
        for row in status_history:
            change = f"{_clean(row.get('fromStatus'))} → {_clean(row.get('toStatus'))}"
            ended = _clean(row.get("endedAt"))
            lines.append(
                f"| {change} | {_clean(row.get('operatorName'))} | {ended or _clean(row.get('startedAt'))} "
                f"| {_clean(row.get('comment'))} |"
            )
        lines.append("")
    assign_history = timeline.get("assignHistory") or []
    if assign_history:
        lines.append("### 指派记录")
        lines.append("")
        lines.append("| 原处理人 → 新处理人 | 指派人 | 时间 | 原因 |")
        lines.append("| --- | --- | --- | --- |")
        for row in assign_history:
            lines.append(
                f"| {_clean(row.get('fromUserName'))} → {_clean(row.get('toUserName'))} "
                f"| {_clean(row.get('assignedByName'))} | {_clean(row.get('assignedAt'))} "
                f"| {_clean(row.get('reason'))} |"
            )
        lines.append("")
    events = timeline.get("events") or []
    if events:
        lines.append("### 排查事件")
        lines.append("")
        lines.append("| 时间 | 操作人 | 事件说明 |")
        lines.append("| --- | --- | --- |")
        for row in events:
            lines.append(
                f"| {_clean(row.get('createTime'))} | {_clean(row.get('operatorName'))} "
                f"| {_clean(row.get('content'))} |"
            )
        lines.append("")
    if not status_history and not assign_history and not events:
        lines.append("（无记录）")
        lines.append("")
    rca = timeline.get("rca")
    if rca:
        lines.append("### RCA（页面历史 Tab 展示字段）")
        lines.append("")
        for label, key in [
            ("问题现象", "symptom"),
            ("影响范围", "impactScope"),
            ("复现步骤", "reproduceSteps"),
            ("排查过程", "investigationProcess"),
            ("根因分类", "rootCauseCategory"),
            ("根因详情", "rootCauseDetail"),
            ("修复方案", "fixSolution"),
            ("预防建议", "preventionSolution"),
        ]:
            text = _clean(rca.get(key))
            if text:
                lines.append(f"**{label}**：{text}")
                lines.append("")
    lines.append("")

    # ── 六、评论 ──
    comments = bundle["comments"]
    lines.append("## 六、评论")
    lines.append("")
    if comments:
        for idx, row in enumerate(comments, 1):
            lines.append(
                f"**[{idx}]** {_clean(row.get('userName'))}｜{_clean(row.get('createTime'))}"
            )
            lines.append("")
            lines.append("```text")
            lines.append(str(row.get("content") or "（空）").replace("\r\n", "\n"))
            lines.append("```")
            lines.append("")
    else:
        lines.append("（无评论）")
        lines.append("")

    # ── 七、相似/关联工单 ──
    relations = bundle["relations"]
    lines.append("## 七、相似/关联工单")
    lines.append("")
    if relations:
        lines.append("| 关系类型 | 对端工单号 | 对端标题 | 是否人工确认 |")
        lines.append("| --- | --- | --- | --- |")
        for rel in relations:
            lines.append(
                f"| {_clean(rel['relation_type'])} | {_clean(rel['peer_ticket_no'])} "
                f"| {_clean(rel['peer_title'])} | {_clean(rel['confirmed'])} |"
            )
    else:
        lines.append("（无记录）")
    lines.append("")

    # ── 八、日志拉取记录（只保留页面列表展示字段） ──
    log_pulls = bundle["logPulls"]
    rows = log_pulls if isinstance(log_pulls, list) else (log_pulls.get("rows") or [])
    lines.append("## 八、日志拉取记录")
    lines.append("")
    if rows:
        lines.append("| 记录ID | 状态 | 状态说明 | 环境 | 门店 | POS | 拉取方式 | 拉取人 | 时间 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in rows:
            lines.append(
                f"| {_clean(row.get('id'))} | {_clean(row.get('status'))} "
                f"| {_clean(row.get('statusDesc'))} | {_clean(row.get('environment'))} "
                f"| {_clean(row.get('storeId'))} | {_clean(row.get('posNo'))} "
                f"| {_clean(row.get('pullMethod'))} | {_clean(row.get('puller'))} "
                f"| {_clean(row.get('createTime'))} |"
            )
    else:
        lines.append("（无记录）")
    lines.append("")

    return "\n".join(lines) + "\n"


def export_one(ticket_no: str) -> tuple[str, dict]:
    """
    导出单个工单的详情页全量数据。
    :param ticket_no: 工单号
    :return: (工单号, 数据包 dict)
    """
    db = SessionLocal()
    try:
        ticket = TicketDao.get_ticket_by_no(db, ticket_no)
        if not ticket:
            raise ValueError(f"工单不存在: {ticket_no}")

        # 1) 详情接口主链路（与 TicketService.get_ticket_detail_services 一致，仅跳过向量化相似工单）
        result = CamelCaseUtil.transform_result(ticket)
        TicketService._decorate_ticket_item(result)
        from modules.ticket.service.core.ticket_version_service import TicketVersionService
        TicketVersionService.attach_ticket_version_labels(db, [result])
        TicketService._attach_issue_summary(db, [result])
        TicketService._attach_relation_codes(db, result)
        result["latestLogPull"] = TicketLogPullService.get_latest_summary(db, ticket.ticket_id)
        result["latestAiAnalysis"] = TicketAiAnalysisSummary.get_summary(db, ticket.ticket_id)

        # 消息与快照（跳过相似工单向量化，直接读 DAO）
        result["messages"] = CamelCaseUtil.transform_result(TicketDao.list_messages(db, ticket.ticket_id))
        snapshots = TicketDao.list_snapshots(db, ticket.ticket_id)
        result["snapshots"] = CamelCaseUtil.transform_result(snapshots)
        result["latestSnapshot"] = CamelCaseUtil.transform_result(snapshots[0]) if snapshots else None

        # AI 提示词分层（只读）
        result["aiPromptLayers"] = TicketPromptServiceResolver.resolve(db, ticket)

        bundle: dict = {"detail": result}

        # 2) 时间线（状态/指派历史、事件、RCA；评论单独拉取避免重复大块）
        timeline = TicketDao.get_timeline(db, ticket.ticket_id, include_comments=False)
        bundle["timeline"] = {k: CamelCaseUtil.transform_result(v) for k, v in timeline.items()}

        # 3) 评论
        bundle["comments"] = CamelCaseUtil.transform_result(TicketDao.list_comments(db, ticket.ticket_id))

        # 4) 相似/关联工单（只读 ticket_relation，双向查询）
        rel_rows = db.query(TicketRelation).filter(
            (TicketRelation.source_ticket_id == ticket.ticket_id)
            | (TicketRelation.target_ticket_id == ticket.ticket_id)
        ).all()
        relations = []
        for rel in rel_rows:
            peer_id = (
                rel.target_ticket_id
                if rel.source_ticket_id == ticket.ticket_id
                else rel.source_ticket_id
            )
            peer = TicketDao.get_ticket_by_id(db, peer_id)
            relations.append(
                {
                    "relation_type": rel.relation_type,
                    "peer_ticket_no": peer.ticket_no if peer else str(peer_id),
                    "peer_title": peer.title if peer else "",
                    "confidence": rel.confidence,
                    "source": rel.source,
                    "confirmed": rel.confirmed,
                    "remark": rel.remark,
                }
            )
        bundle["relations"] = relations

        # 5) 日志拉取记录列表（与详情页"日志拉取"Tab 一致，非分页全量）
        # 注意：QueryModel 配置了 alias_generator=to_camel 且未开启 populate_by_name，
        # 按字段名 ticket_id 构造会被静默忽略导致查询 ticket_id IS NULL，必须按别名构造。
        query_model = TicketLogPullQueryModel.model_validate(
            {"ticketId": ticket.ticket_id, "isPage": False}
        )
        service_result = TicketLogPullService.list_log_pull_records_services(db, query_model)
        # is_page=False 时 DAO 返回列表；防御性兼容分页对象
        if isinstance(service_result, list):
            bundle["logPulls"] = service_result
        else:
            bundle["logPulls"] = getattr(service_result, "rows", []) or []

        return ticket_no, bundle
    finally:
        # 只读会话直接关闭即可，不 commit
        db.close()


# 延迟导入包装，避免模块导入顺序问题
class TicketAiAnalysisSummary:
    """AI 分析摘要的轻量包装。"""

    @staticmethod
    def get_summary(db, ticket_id: int):
        from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService

        return TicketAiAnalysisService.get_latest_summary(db, ticket_id)


class TicketPromptServiceResolver:
    """提示词分层的轻量包装。"""

    @staticmethod
    def resolve(db, ticket):
        from modules.ticket.service.ai.ticket_prompt_service import TicketPromptService

        return TicketPromptService.resolve_prompt_layers(db, ticket)


def main() -> None:
    # 解析 --out-dir 及其值后，其余位置参数视为工单号
    argv = list(sys.argv[1:])
    out_dir_arg = None
    if "--out-dir" in argv:
        idx = argv.index("--out-dir")
        if idx + 1 < len(argv):
            out_dir_arg = argv[idx + 1]
        # 移除 --out-dir 与其值，避免目录路径被误认成工单号
        del argv[idx : idx + 2]
    ticket_nos = [a for a in argv if not a.startswith("-")] or ["INC00001939452", "INC00001846424"]
    if out_dir_arg:
        out_dir = Path(out_dir_arg)
    else:
        default_dir_name = f"ticket_detail_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir = SERVER_ROOT / "scripts" / "output" / default_dir_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"== 工单详情导出（只读）== 目标工单: {ticket_nos}")
    print(f"输出目录: {out_dir}")

    for ticket_no in ticket_nos:
        try:
            resolved_no, bundle = export_one(ticket_no)
        except ValueError as exc:
            print(f"❌ {ticket_no}: {exc}")
            continue
        md_text = render_ticket_md(resolved_no, bundle)
        out_path = out_dir / f"ticket_{resolved_no}.md"
        out_path.write_text(md_text, encoding="utf-8")
        # 同时产出简化版：仅保留详情页各 Tab 实际展示的数据
        brief_text = render_ticket_brief_md(resolved_no, bundle)
        brief_path = out_dir / f"ticket_{resolved_no}_brief.md"
        brief_path.write_text(brief_text, encoding="utf-8")
        detail = bundle["detail"]
        print(
            f"✅ {resolved_no}: 已导出 -> {out_path} + {brief_path.name} "
            f"(消息 {len(detail.get('messages') or [])} 条, "
            f"快照 {len(detail.get('snapshots') or [])} 条, "
            f"事件 {len(bundle['timeline'].get('events') or [])} 条, "
            f"评论 {len(bundle['comments'])} 条, "
            f"日志拉取记录 {len(bundle['logPulls']) if isinstance(bundle['logPulls'], list) else '未知'} 条)"
        )


if __name__ == "__main__":
    main()
