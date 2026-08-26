"""
POS 历史工单分类补录临时脚本。

使用方式：
1. 先预览：uv run python scripts/backfill_pos_ticket_issue_classification.py preview
2. 再执行：uv run python scripts/backfill_pos_ticket_issue_classification.py apply --issue-confirmed
3. 如需回滚：uv run python scripts/backfill_pos_ticket_issue_classification.py rollback --artifact <回滚工件.json>

说明：
- 读取 server/.env.prod 的生产库连接；
- 默认只做 preview，不改库；
- 只处理 POS 相关、状态到“5. 产研处理完毕”及之后的工单；
- 只对保守白名单里的细分问题自动创建/复用 issue，避免产生泛化垃圾 issue。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pymysql
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from utils.snowflake import snowIdWorker

SCRIPT_OPERATOR = "pos_ticket_backfill_script"
SYNC_CONFIG_KEY = "ticket.sync.automation"
ISSUE_EVENT_TYPE = "ISSUE_ATTRIBUTED"
TICKET_SQL = """
SELECT
    t.ticket_id, t.ticket_no, t.title, t.description,
    t.project_id, t.module_id, t.module_code, t.module_name, t.status,
    t.issue_type_id, t.issue_type_name, t.classification_source,
    t.problem_pattern_code, t.problem_pattern_name, t.problem_pattern_source, t.problem_pattern_verified,
    t.issue_id, t.issue_relation_type, t.issue_confirmed,
    t.severity, t.create_time, t.update_time
FROM ticket t
LEFT JOIN workflow_status ws ON ws.code = t.status
WHERE t.del_flag = '0'
  AND (
    UPPER(COALESCE(t.module_code, '')) LIKE 'POS%%'
    OR UPPER(COALESCE(t.module_name, '')) LIKE '%%POS%%'
  )
  AND (
    COALESCE(ws.order_num, 0) >= 8
    OR (
      COALESCE(t.status, '') REGEXP '^[[:space:]]*[0-9]+'
      AND CAST(SUBSTRING_INDEX(TRIM(t.status), '.', 1) AS UNSIGNED) >= 5
    )
    OR LOWER(COALESCE(t.status, '')) IN ('duplicated record', 'duplicated record-cancelled')
  )
ORDER BY t.create_time ASC, t.ticket_id ASC
"""
ISSUE_SQL = "SELECT * FROM ticket_issue WHERE del_flag='0'"
PROJECT_SQL = "SELECT project_id, project_name FROM hrm_project WHERE del_flag='0'"


@dataclass(frozen=True)
class PatternRule:
    """细分问题识别规则。"""

    code: str
    label: str
    issue_type_id: str
    is_problem: bool
    root_cause_type: str
    keywords: tuple[str, ...]
    negative: tuple[str, ...] = ()
    bucket_key: str = ""
    bucket_title: str = ""
    create_issue: bool = False
    min_group: int = 2


RULES: tuple[PatternRule, ...] = (
    PatternRule("sco_account_freeze", "SCO账号冻结/需人工解冻", "user_operation", False, "operation_mistake", ("sco account freeze", "sco冻结", "账号冻结", "需要解冻", "unlock sco")),
    PatternRule("new_store_setup", "新店开业/基础配置申请", "support_consulting", False, "requirement_design", ("新店", "开业", "new store", "store setup", "基础配置申请", "门店初始化")),
    PatternRule("vms_declaration_permission", "礼券申报/员工账号权限异常", "config_issue", True, "config_error", ("vms", "voucher declaration", "gv declaration", "gift voucher", "礼券申报", "vms declaration", "voucher claim", "gift voucher declaration"), ("cashier declaration", "cash drop", "eod declaration"), "vms_declaration_permission", "POS 礼券申报或账号权限异常", True, 2),
    PatternRule("promo_coupon_not_sync", "促销/优惠券不可用或未下发", "config_issue", True, "config_error", ("coupon", "優惠券", "优惠券", "會員券", "会员券", "yuu coupon", "food coupon", "dcr", "coupon redemption", "redeem coupon"), ("voucher declaration", "vms", "gift voucher", "open request", "flat key", "wogi setup", "new store"), "promo_coupon_not_sync", "POS 促销或优惠券未同步/不可用", True, 2),
    PatternRule("payment_voucher_mismatch", "支付/礼券/YUU状态异常", "system_bug", True, "code_defect", ("yuu", "voucher", "礼券", "double payment", "duplicate payment", "支付状态", "积分", "payment mismatch", "支付回滚"), ("voucher declaration", "vms", "coupon")),
    PatternRule("smartsafe_reconciliation", "日结/SmartSafe/Partner对账差异", "data_error", True, "data_exception", ("smartsafe", "partner", "日结", "对账", "reconciliation", "settlement", "差异", "收大数")),
    PatternRule("report_no_data_or_missing", "报表无数据/缺文件", "data_error", True, "data_exception", ("report no data", "报表无数据", "missing file", "缺文件", "missing report", "报表缺失", "no report", "未生成报表", "report missing", "sales report issue"), ("price", "价签", "ils", "s21", "v21", "data8", "tlog", "regenerate", "补数", "回传"), "report_no_data_or_missing", "POS 报表无数据或缺文件", True, 2),
    PatternRule("sales_discrepancy", "销售数据/实时销售差异", "data_error", True, "data_exception", ("sales discrepancy", "sales mismatch", "实时销售差异", "销售数据差异", "销售不准")),
    PatternRule("tlog_regeneration", "Tlog/销售回传补数修复", "data_error", True, "data_exception", ("tlog", "回传", "补数", "重传", "regeneration", "销售回传", "ils", "s21", "v21", "data8")),
    PatternRule("price_sync_abnormal", "价格/价签同步异常", "data_error", True, "data_exception", ("price", "价签", "价格", "shelf label", "price tag", "价格不对", "价签不同步"), ("coupon", "promo", "report"), "price_sync_abnormal", "POS 价格或价签同步异常", True, 2),
    PatternRule("barcode_scan_issue", "扫码/条码识别异常", "system_bug", True, "code_defect", ("barcode", "scan", "cannot scan", "unable to scan", "扫码", "条码", "扫描", "scan item", "截断"), ("promotion", "coupon", "report"), "barcode_scan_issue", "POS 扫码或条码识别异常", True, 2),
    PatternRule("save_pause_residue", "取单挂单残留/取消后仍存在", "system_bug", True, "code_defect", ("挂单", "取单", "save pause", "suspend", "取消后仍存在", "cancel order still exists")),
    PatternRule("memory_leak", "内存泄露", "performance_issue", True, "code_defect", ("内存泄露", "内存泄漏", "memory leak", "oom", "内存溢出", "卡死")),
    PatternRule("pos_payment_enjoy", "enjoy支付异常导致促销信息被删", "system_bug", True, "code_defect", ("enjoy", "促销信息被删", "promotion deleted")),
    PatternRule("offline_data_error", "离线服务数据处理异常", "data_error", True, "data_exception", ("offline", "离线", "离线服务", "offline data")),
    PatternRule("user_config_ware", "用户未维护数据", "config_issue", True, "config_error", ("未维护", "missing config", "master data", "没有配置", "未配置", "资料未维护")),
    PatternRule("pos_payment", "POS客户端支付", "api_exception", True, "third_party", ("payment", "支付", "settlement failed", "upos", "rta", "支付失败", "rollback"), ("coupon", "promotion")),
    PatternRule("pos_client", "POS客户端问题", "system_bug", True, "code_defect", ("pos client", "客户端", "crash", "卡顿", "无法操作", "按钮无响应")),
    PatternRule("optimization", "优化项", "support_consulting", False, "requirement_design", ("优化", "improve", "improvement", "优化项")),
    PatternRule("demand_so", "设计如此", "requirement_consulting", False, "requirement_design", ("设计如此", "as designed", "expected behavior", "正常业务逻辑", "需求如此")),
)
RULE_MAP = {rule.code: rule for rule in RULES}


def s(v):
    return str(v or "").strip()


def i(v):
    if v in (None, ""):
        return None
    try:
        return int(v)
    except Exception:
        return None


def b(v):
    if isinstance(v, bool):
        return v
    return v not in (None, "", 0, "0", "false", "False")


def norm(v: str | None) -> str:
    text = s(v).lower().replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text


def key(v: str | None) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", norm(v))


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def issue_no() -> str:
    return f"ISS{datetime.now().strftime('%Y%m%d')}{snowIdWorker.get_id()}"


def parse_args():
    parser = argparse.ArgumentParser(description="POS 历史工单分类补录临时脚本")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--env-file", default=str(BASE_DIR / ".env.prod"))
        p.add_argument("--output-dir", default=str(BASE_DIR / "scripts" / "output" / "pos_ticket_backfill"))
        p.add_argument("--limit", type=int, default=0)
        if name == "apply":
            p.add_argument("--issue-confirmed", action="store_true")
            p.add_argument("--skip-issue-binding", action="store_true")
    rb = sub.add_parser("rollback")
    rb.add_argument("--env-file", default=str(BASE_DIR / ".env.prod"))
    rb.add_argument("--artifact", required=True)
    return parser.parse_args()


def load_env(path: str):
    env = Path(path)
    if not env.exists():
        raise FileNotFoundError(f"找不到数据库配置文件: {env}")
    load_dotenv(env, override=True)


def db(read_only=False):
    conn = pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT") or 3306),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_DATABASE"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    if read_only:
        with conn.cursor() as cur:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
    return conn


def qall(cur, sql, params=()):
    cur.execute(sql, params)
    return list(cur.fetchall())


def qone(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def chunks(items, size=500):
    for idx in range(0, len(items), size):
        yield items[idx: idx + size]


def load_sync_config(cur):
    row = qone(cur, "SELECT config_value FROM sys_config WHERE config_key=%s", (SYNC_CONFIG_KEY,))
    if not row:
        raise RuntimeError(f"未找到 sys_config: {SYNC_CONFIG_KEY}")
    cfg = json.loads(row["config_value"] or "{}")
    stat = cfg.get("statClassification") or {}
    issue_rows = stat.get("issueTypes") or []
    pattern_rows = stat.get("problemPatterns") or []
    issue_by_value = {s(item.get('value')): item for item in issue_rows if s(item.get('value'))}
    issue_by_label = {s(item.get('label')): item for item in issue_rows if s(item.get('label'))}
    pattern_by_value = {s(item.get('value')): item for item in pattern_rows if s(item.get('value'))}
    pattern_by_label = {s(item.get('label')): item for item in pattern_rows if s(item.get('label'))}
    return cfg, stat, issue_by_value, issue_by_label, pattern_by_value, pattern_by_label


def ensure_pattern_options(cfg, stat, pattern_by_value):
    rows = stat.get("problemPatterns")
    if rows is None:
        rows = []
        stat["problemPatterns"] = rows
    added = []
    for rule in RULES:
        if rule.code in pattern_by_value:
            continue
        item = {
            "value": rule.code,
            "label": rule.label,
            "moduleCode": "POS",
            "issueTypeId": rule.issue_type_id,
            "isProblem": rule.is_problem,
            "rootCauseType": rule.root_cause_type,
            "resolutionCode": "fixed" if rule.is_problem else "non_problem",
            "description": f"POS 历史工单补录规则：{rule.label}",
            "positiveExamples": list(rule.keywords[:6]),
            "negativeExamples": list(rule.negative[:4]),
            "enabled": True,
        }
        rows.append(item)
        pattern_by_value[rule.code] = item
        added.append(item)
    cfg["statClassification"] = stat
    return added


def load_tickets(cur, limit=0):
    projects = {i(row['project_id']): s(row['project_name']) for row in qall(cur, PROJECT_SQL)}
    sql = TICKET_SQL + (f"\nLIMIT {int(limit)}" if limit and limit > 0 else "")
    rows = qall(cur, sql)
    ids = [i(row['ticket_id']) for row in rows if i(row['ticket_id'])]
    comment_map = defaultdict(list)
    for batch in chunks(ids):
        marks = ",".join(["%s"] * len(batch))
        for row in qall(cur, f"SELECT ticket_id, content FROM ticket_comment WHERE ticket_id IN ({marks}) ORDER BY create_time ASC, id ASC", batch):
            if s(row.get('content')):
                comment_map[i(row['ticket_id'])].append(s(row['content']))
    items = []
    for row in rows:
        ticket_id = i(row['ticket_id'])
        project_id = i(row.get('project_id'))
        items.append({
            'ticket_id': ticket_id,
            'ticket_no': s(row.get('ticket_no')),
            'title': s(row.get('title')),
            'description': s(row.get('description')),
            'comments': comment_map.get(ticket_id, []),
            'project_id': project_id,
            'project_name': projects.get(project_id, ''),
            'module_id': i(row.get('module_id')),
            'module_code': s(row.get('module_code')),
            'module_name': s(row.get('module_name')),
            'status': s(row.get('status')),
            'issue_type_id': s(row.get('issue_type_id')),
            'issue_type_name': s(row.get('issue_type_name')),
            'classification_source': s(row.get('classification_source')),
            'problem_pattern_code': s(row.get('problem_pattern_code')),
            'problem_pattern_name': s(row.get('problem_pattern_name')),
            'problem_pattern_source': s(row.get('problem_pattern_source')),
            'problem_pattern_verified': b(row.get('problem_pattern_verified')),
            'issue_id': i(row.get('issue_id')),
            'issue_relation_type': s(row.get('issue_relation_type')),
            'issue_confirmed': b(row.get('issue_confirmed')),
            'severity': s(row.get('severity')),
            'create_time': str(row.get('create_time') or ''),
            'update_time': str(row.get('update_time') or ''),
        })
    return items


def load_issues(cur):
    return qall(cur, ISSUE_SQL)


def resolve_issue_type(issue_type_id, issue_type_name, by_value, by_label):
    if issue_type_id and issue_type_name:
        return issue_type_id, issue_type_name
    if issue_type_id and issue_type_id in by_value:
        return issue_type_id, s(by_value[issue_type_id].get('label'))
    if issue_type_name and issue_type_name in by_label:
        return s(by_label[issue_type_name].get('value')), issue_type_name
    return issue_type_id, issue_type_name


def resolve_pattern(pattern_code, pattern_name, by_value, by_label):
    if pattern_code and pattern_name:
        return pattern_code, pattern_name
    if pattern_code and pattern_code in by_value:
        return pattern_code, s(by_value[pattern_code].get('label'))
    if pattern_name and pattern_name in by_label:
        return s(by_label[pattern_name].get('value')), pattern_name
    return pattern_code, pattern_name


def infer_issue_type(text: str) -> str:
    x = norm(text)
    if any(k in x for k in ("咨询", "how to", "请问", "使用方法", "需要确认")):
        return "support_consulting"
    if any(k in x for k in ("需求", "是否支持", "requirement")):
        return "requirement_consulting"
    if any(k in x for k in ("误操作", "忘记", "操作问题", "使用错误")):
        return "user_operation"
    if any(k in x for k in ("slow", "慢", "卡顿", "卡死", "oom", "memory leak")):
        return "performance_issue"
    if any(k in x for k in ("api", "接口", "http", "timeout", "401", "403", "500", "rta", "upos")):
        return "api_exception"
    if any(k in x for k in ("配置", "权限", "参数", "未配置", "master data", "setup")):
        return "config_issue"
    if any(k in x for k in ("数据", "差异", "无数据", "补数", "report", "对账")):
        return "data_error"
    if any(k in x for k in ("bug", "异常", "无法", "failed", "错误")):
        return "system_bug"
    return ""


def issue_type_is_problem(issue_type_id, by_value):
    row = by_value.get(s(issue_type_id))
    return None if row is None or row.get('isProblem') is None else b(row.get('isProblem'))


def build_example(ticket):
    text = " | ".join([s(ticket['title']), s(ticket['description']), *(s(x) for x in ticket['comments'][:2])]).strip(" |")
    text = re.sub(r"\s+", " ", text)
    return text[:180] + ("..." if len(text) > 180 else "")


@lru_cache(maxsize=512)
def compile_keyword_pattern(keyword: str):
    """为英文/数字关键词编译精确边界匹配，避免 details/reported 这类子串误命中。"""
    x = norm(keyword)
    if not x:
        return re.compile(r"$^")
    escaped = re.escape(x).replace(r"\ ", r"\s+")
    if re.search(r"[a-z0-9]", x):
        return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")
    return re.compile(escaped)


def collect_hits(text, keywords, precise=False):
    """收集命中的关键词；precise=True 时对英文/数字词使用单词边界匹配。"""
    target = norm(text)
    hits = []
    for keyword in keywords:
        x = norm(keyword)
        if not x:
            continue
        matched = bool(compile_keyword_pattern(x).search(target)) if precise else x in target
        if matched:
            hits.append(keyword)
    return hits


def match_coupon_rule(text):
    direct_terms = ("yuu coupon", "food coupon", "coupon redemption", "redeem coupon")
    coupon_terms = ("coupon", "優惠券", "优惠券", "會員券", "会员券", "dcr")
    action_terms = ("redeem", "redeemed", "兌換", "兑换", "cannot be redeemed", "unable to use", "不可使用", "未同步", "not sync", "not updated", "cannot validate")
    negative_terms = ("vms", "voucher declaration", "gift voucher", "open request", "flat key", "wogi setup", "new store", "cashier declaration", "closure store")
    if collect_hits(text, negative_terms, precise=True):
        return []
    direct_hits = collect_hits(text, direct_terms, precise=True)
    coupon_hits = collect_hits(text, coupon_terms, precise=True)
    action_hits = collect_hits(text, action_terms, precise=True)
    if direct_hits:
        return (direct_hits + action_hits)[:8]
    if any(norm(hit) == "dcr" for hit in coupon_hits):
        return (coupon_hits + action_hits)[:8]
    if coupon_hits and action_hits:
        return (coupon_hits + action_hits)[:8]
    return []


def match_vms_rule(text):
    direct_terms = ("voucher declaration", "gv declaration", "礼券申报", "vms declaration", "voucher claim", "gift voucher declaration")
    signal_terms = ("vms", "hkvms", "gift voucher", "礼券")
    context_terms = ("declaration", "declare", "申报", "permission", "权限", "no permission", "unable to declare", "claim")
    negative_terms = ("cashier declaration", "cash drop", "eod declaration", "open request", "wogi setup", "closure store", "store closure")
    direct_hits = collect_hits(text, direct_terms, precise=True)
    if direct_hits:
        return (direct_hits + collect_hits(text, context_terms, precise=True))[:8]
    signal_hits = collect_hits(text, signal_terms, precise=True)
    context_hits = collect_hits(text, context_terms, precise=True)
    if not signal_hits or not context_hits:
        return []
    if collect_hits(text, negative_terms, precise=True):
        return []
    return (signal_hits + context_hits)[:8]


def match_tlog_rule(text):
    direct_terms = ("sales upload", "上传销售", "销售回传", "daily redemption status file", "sales file", "redemption file", "file transmission")
    file_terms = ("ils", "s21", "v21", "data8", "tlog")
    action_terms = ("regenerate", "regeneration", "回传", "补数", "重传", "re-upload", "upload", "incomplete sales", "not received", "missing data", "missing file")
    context_terms = ("sales transaction", "daily sales", "daily redemption", "transaction file", "交易文件", "销售文件", "数据文件", "rta system")
    direct_hits = collect_hits(text, direct_terms, precise=True)
    if direct_hits:
        return (direct_hits + collect_hits(text, action_terms, precise=True))[:8]
    file_hits = collect_hits(text, file_terms, precise=True)
    if file_hits:
        return (file_hits + collect_hits(text, action_terms, precise=True) + collect_hits(text, context_terms, precise=True))[:8]
    action_hits = collect_hits(text, action_terms, precise=True)
    context_hits = collect_hits(text, context_terms, precise=True)
    if action_hits and context_hits:
        return (action_hits + context_hits)[:8]
    return []


def match_report_rule(text):
    direct_terms = ("report no data", "报表无数据", "missing file", "缺文件", "missing report", "报表缺失", "no report", "未生成报表", "report missing", "blank report")
    report_terms = ("sales report", "finance report", "eod report", "report", "报表")
    missing_terms = ("missing", "missing record", "无数据", "no data", "找不到", "未生成", "not generated")
    negative_terms = ("ils", "s21", "v21", "data8", "tlog", "regenerate", "补数", "回传", "重传", "flat key", "item not found", "cashier declaration", "hkvms", "gv discrepancy", "stamp report", "transaction id")
    if collect_hits(text, negative_terms, precise=True):
        return []
    direct_hits = collect_hits(text, direct_terms, precise=True)
    if direct_hits:
        return direct_hits[:8]
    report_hits = collect_hits(text, report_terms, precise=True)
    missing_hits = collect_hits(text, missing_terms, precise=True)
    if report_hits and missing_hits:
        return (report_hits + missing_hits)[:8]
    return []


def match_rule(text):
    x = norm(text)
    for rule in RULES:
        if rule.code == "promo_coupon_not_sync":
            hits = match_coupon_rule(x)
        elif rule.code == "vms_declaration_permission":
            hits = match_vms_rule(x)
        elif rule.code == "tlog_regeneration":
            hits = match_tlog_rule(x)
        elif rule.code == "report_no_data_or_missing":
            hits = match_report_rule(x)
        else:
            hits = [k for k in rule.keywords if k in x]
            if hits and any(k in x for k in rule.negative):
                hits = []
        if hits:
            return rule, hits[:8]
    return None, []


def classify(ticket, issue_by_value, issue_by_label, pattern_by_value, pattern_by_label):
    issue_type_id, issue_type_name = resolve_issue_type(ticket['issue_type_id'], ticket['issue_type_name'], issue_by_value, issue_by_label)
    pattern_code, pattern_name = resolve_pattern(ticket['problem_pattern_code'], ticket['problem_pattern_name'], pattern_by_value, pattern_by_label)
    text = "\n".join([ticket['title'], ticket['description'], *ticket['comments']])
    rule, hits = (None, [])
    if not ticket['problem_pattern_verified'] and not (pattern_code and pattern_name):
        rule, hits = match_rule(text)
        if rule:
            pattern_code, pattern_name = rule.code, rule.label
    if not (issue_type_id and issue_type_name):
        use_id = rule.issue_type_id if rule else infer_issue_type(text)
        if use_id and use_id in issue_by_value:
            issue_type_id = use_id
            issue_type_name = s(issue_by_value[use_id].get('label'))
    current_rule = RULE_MAP.get(pattern_code)
    is_problem = issue_type_is_problem(issue_type_id, issue_by_value)
    if is_problem is None and current_rule:
        is_problem = current_rule.is_problem
    skip = ""
    bucket_key = bucket_title = ""
    should_bind_issue = False
    if ticket['issue_id']:
        skip = "已绑定 issue_id，按约定跳过"
    elif not pattern_code:
        skip = "未识别到细分问题，暂不归并 issue"
    elif is_problem is False:
        skip = "当前判定为非问题类，仅统计不建 issue"
    elif is_problem is None:
        skip = "问题大类无法稳定判断是否为真实问题，暂不建 issue"
    elif not ticket['project_id']:
        skip = "工单缺少 project_id，暂不自动建 issue"
    elif not current_rule or not current_rule.bucket_key:
        skip = "当前细分问题未纳入本轮自动建 issue 白名单"
    else:
        bucket_key = current_rule.bucket_key
        bucket_title = current_rule.bucket_title
        should_bind_issue = True
    return {
        'ticket_id': ticket['ticket_id'],
        'ticket_no': ticket['ticket_no'],
        'project_id': ticket['project_id'],
        'project_name': ticket['project_name'],
        'current_issue_type_id': ticket['issue_type_id'],
        'current_issue_type_name': ticket['issue_type_name'],
        'current_pattern_code': ticket['problem_pattern_code'],
        'current_pattern_name': ticket['problem_pattern_name'],
        'current_issue_id': ticket['issue_id'],
        'issue_type_id': issue_type_id,
        'issue_type_name': issue_type_name,
        'pattern_code': pattern_code,
        'pattern_name': pattern_name,
        'issue_type_should_update': bool((not ticket['issue_id']) and issue_type_id and issue_type_name and (issue_type_id != ticket['issue_type_id'] or issue_type_name != ticket['issue_type_name'])),
        'pattern_should_update': bool((not ticket['issue_id']) and pattern_code and pattern_name and (pattern_code != ticket['problem_pattern_code'] or pattern_name != ticket['problem_pattern_name'])),
        'rule_code': rule.code if rule else (current_rule.code if current_rule else ''),
        'matched_keywords': hits,
        'issue_bucket_key': bucket_key,
        'issue_bucket_title': bucket_title,
        'should_bind_issue': should_bind_issue,
        'skip_reason': skip,
        'example': build_example(ticket),
    }


def build_issue_summary(group):
    lines = [f"本问题实例由 POS 历史工单补录脚本归并生成。归并工单数：{len(group)}。", "代表性工单："]
    for item in group[:5]:
        lines.append(f"- {item['ticket_no']}: {item['example']}")
    return "\n".join(lines)


def build_issue_plans(tickets, decisions, issues, skip_binding=False):
    if skip_binding:
        return [], {}, []
    issue_lookup = {(i(row.get('project_id')), s(row.get('problem_pattern_code')), key(row.get('title'))): row for row in issues if key(row.get('title'))}
    ticket_map = {row['ticket_id']: row for row in tickets}
    groups = defaultdict(list)
    for row in decisions:
        if row['should_bind_issue'] and row['project_id']:
            groups[(row['issue_bucket_key'], row['project_id'])].append(row)
    plans, assign_map, new_issues = [], {}, []
    for (bucket_key, project_id), group in groups.items():
        rule = RULE_MAP[group[0]['pattern_code']]
        lookup_key = (project_id, rule.code, key(rule.bucket_title))
        existing = issue_lookup.get(lookup_key)
        payload = {
            'bucket_key': bucket_key,
            'project_id': project_id,
            'project_name': group[0]['project_name'],
            'pattern_code': rule.code,
            'title': rule.bucket_title,
            'ticket_count': len(group),
            'ticket_ids': [x['ticket_id'] for x in group],
            'ticket_nos': [x['ticket_no'] for x in group],
        }
        if existing:
            payload.update({'issue_action': 'reuse', 'issue_id': i(existing.get('issue_id')), 'issue_no': s(existing.get('issue_no'))})
        elif len(group) < rule.min_group:
            payload.update({'issue_action': 'skip_small_group', 'issue_id': None, 'issue_no': ''})
        else:
            first = sorted([ticket_map[x['ticket_id']] for x in group], key=lambda x: (x['create_time'], x['ticket_id']))[0]
            module_pair = Counter((x['module_id'], x['module_name']) for x in [ticket_map[y['ticket_id']] for y in group] if x['module_id'] or x['module_name']).most_common(1)
            module_id, module_name = module_pair[0][0] if module_pair else (None, 'POS')
            new_issue = {
                'issue_id': snowIdWorker.get_id(),
                'issue_no': issue_no(),
                'title': rule.bucket_title,
                'summary': build_issue_summary(group),
                'status': 'open',
                'severity': Counter(s(ticket_map[x['ticket_id']].get('severity')) for x in group if s(ticket_map[x['ticket_id']].get('severity'))).most_common(1)[0][0] if any(s(ticket_map[x['ticket_id']].get('severity')) for x in group) else '',
                'project_id': project_id,
                'project_name': group[0]['project_name'],
                'module_id': module_id,
                'module_name': s(module_name) or 'POS',
                'root_cause_type': rule.root_cause_type,
                'problem_pattern_code': rule.code,
                'problem_pattern_name': rule.label,
                'owner_id': None,
                'owner_name': '',
                'first_ticket_id': first['ticket_id'],
                'affected_ticket_count': len(group),
                'del_flag': '0',
                'create_by': SCRIPT_OPERATOR,
                'update_by': SCRIPT_OPERATOR,
                'create_time': now_text(),
                'update_time': now_text(),
            }
            payload.update({'issue_action': 'create', 'issue_id': new_issue['issue_id'], 'issue_no': new_issue['issue_no']})
            new_issues.append(new_issue)
        plans.append(payload)
        if payload['issue_action'] in {'reuse', 'create'}:
            for ticket_id in payload['ticket_ids']:
                assign_map[ticket_id] = payload
    return plans, assign_map, new_issues


def build_summary(tickets, decisions, plans):
    total = len(tickets)
    comments = sum(1 for x in tickets if x['comments'])
    return {
        'scope_total': total,
        'comment_coverage_rate': round(comments * 100 / total, 2) if total else 0,
        'missing_issue_type_before': sum(1 for x in tickets if not (x['issue_type_id'] and x['issue_type_name'])),
        'missing_pattern_before': sum(1 for x in tickets if not (x['problem_pattern_code'] and x['problem_pattern_name'])),
        'missing_issue_before': sum(1 for x in tickets if not x['issue_id']),
        'issue_type_updates_planned': sum(1 for x in decisions if x['issue_type_should_update']),
        'pattern_updates_planned': sum(1 for x in decisions if x['pattern_should_update']),
        'issue_bind_candidates': sum(1 for x in decisions if x['should_bind_issue']),
        'issue_type_distribution': dict(Counter(x['issue_type_name'] for x in decisions if x['issue_type_name']).most_common()),
        'pattern_distribution_top20': dict(Counter(x['pattern_code'] for x in decisions if x['pattern_code']).most_common(20)),
        'issue_bucket_distribution': dict(Counter(x['bucket_key'] for x in plans if x['issue_action'] in {'reuse', 'create'}).most_common()),
    }


def write_reports(output_dir, mode, summary, added_patterns, decisions, plans):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = output / f"{ts}_{mode}_summary.json"
    csv_path = output / f"{ts}_{mode}_ticket_decisions.csv"
    plan_path = output / f"{ts}_{mode}_issue_plans.csv"
    json_path.write_text(json.dumps({'generated_at': now_text(), 'mode': mode, 'summary': summary, 'added_problem_patterns': added_patterns}, ensure_ascii=False, indent=2), encoding='utf-8')
    with csv_path.open('w', encoding='utf-8-sig', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=['ticket_id','ticket_no','project_id','project_name','current_issue_type_id','current_issue_type_name','current_pattern_code','current_pattern_name','current_issue_id','issue_type_id','issue_type_name','pattern_code','pattern_name','issue_type_should_update','pattern_should_update','rule_code','matched_keywords','issue_bucket_key','issue_bucket_title','should_bind_issue','skip_reason','example'])
        writer.writeheader()
        for row in decisions:
            item = dict(row)
            item['matched_keywords'] = ' | '.join(row['matched_keywords'])
            writer.writerow(item)
    with plan_path.open('w', encoding='utf-8-sig', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=['bucket_key','project_id','project_name','pattern_code','issue_action','issue_id','issue_no','title','ticket_count','ticket_nos'])
        writer.writeheader()
        for row in plans:
            item = {k: row.get(k) for k in ['bucket_key','project_id','project_name','pattern_code','issue_action','issue_id','issue_no','title','ticket_count']}
            item['ticket_nos'] = ', '.join(row['ticket_nos'])
            writer.writerow(item)
    return {'summary': str(json_path), 'ticket_decisions': str(csv_path), 'issue_plans': str(plan_path)}


def build_apply_updates(tickets, decisions, assign_map, issue_confirmed=False):
    ticket_map = {x['ticket_id']: x for x in tickets}
    updates = []
    for row in decisions:
        ticket = ticket_map[row['ticket_id']]
        touched = row['issue_type_should_update'] or row['pattern_should_update'] or row['ticket_id'] in assign_map
        if not touched:
            continue
        issue_plan = assign_map.get(row['ticket_id'])
        issue_binding_applied = bool(issue_plan and issue_plan['issue_action'] in {'reuse', 'create'})
        updates.append({
            'ticket_id': row['ticket_id'],
            'issue_type_id': row['issue_type_id'],
            'issue_type_name': row['issue_type_name'],
            'classification_source': 'manual' if row['issue_type_should_update'] else ticket['classification_source'],
            'classification_updated_at': now_text() if row['issue_type_should_update'] else None,
            'problem_pattern_code': row['pattern_code'],
            'problem_pattern_name': row['pattern_name'],
            'problem_pattern_source': 'manual' if row['pattern_should_update'] else ticket['problem_pattern_source'],
            'issue_id': issue_plan['issue_id'] if issue_binding_applied else ticket['issue_id'],
            'issue_relation_type': 'primary' if issue_binding_applied else ticket['issue_relation_type'],
            'issue_confirmed': bool(issue_confirmed) if issue_binding_applied else ticket['issue_confirmed'],
            'issue_binding_applied': issue_binding_applied,
            'update_by': SCRIPT_OPERATOR,
        })
    return updates


def snapshot_before(tickets, updates, cfg_before, plans, issues, new_issues):
    update_ids = {x['ticket_id'] for x in updates}
    reuse_issue_ids = {x['issue_id'] for x in plans if x['issue_action'] == 'reuse' and x['issue_id']}
    return {
        'created_at': now_text(),
        'operator': SCRIPT_OPERATOR,
        'config_before': cfg_before,
        'ticket_before': [
            {
                'ticket_id': x['ticket_id'], 'issue_type_id': x['issue_type_id'], 'issue_type_name': x['issue_type_name'],
                'classification_source': x['classification_source'], 'problem_pattern_code': x['problem_pattern_code'],
                'problem_pattern_name': x['problem_pattern_name'], 'problem_pattern_source': x['problem_pattern_source'],
                'issue_id': x['issue_id'], 'issue_relation_type': x['issue_relation_type'], 'issue_confirmed': x['issue_confirmed']
            }
            for x in tickets if x['ticket_id'] in update_ids
        ],
        'existing_issue_before': [x for x in issues if i(x.get('issue_id')) in reuse_issue_ids],
        'inserted_issue_rows': new_issues,
        'inserted_event_ids': [],
    }


def insert_issues(cur, rows):
    if not rows:
        return
    cur.executemany("""
    INSERT INTO ticket_issue (
        issue_id, issue_no, title, summary, status, severity, project_id, project_name,
        module_id, module_name, root_cause_type, problem_pattern_code, problem_pattern_name,
        owner_id, owner_name, first_ticket_id, affected_ticket_count, del_flag,
        create_by, update_by, create_time, update_time
    ) VALUES (
        %(issue_id)s, %(issue_no)s, %(title)s, %(summary)s, %(status)s, %(severity)s, %(project_id)s, %(project_name)s,
        %(module_id)s, %(module_name)s, %(root_cause_type)s, %(problem_pattern_code)s, %(problem_pattern_name)s,
        %(owner_id)s, %(owner_name)s, %(first_ticket_id)s, %(affected_ticket_count)s, %(del_flag)s,
        %(create_by)s, %(update_by)s, %(create_time)s, %(update_time)s
    )""", rows)


def apply_ticket_updates(cur, updates):
    event_ids = []
    sql = """
    UPDATE ticket
    SET issue_type_id=%(issue_type_id)s,
        issue_type_name=%(issue_type_name)s,
        classification_source=%(classification_source)s,
        classification_updated_at=CASE WHEN %(classification_updated_at)s IS NULL THEN classification_updated_at ELSE %(classification_updated_at)s END,
        problem_pattern_code=%(problem_pattern_code)s,
        problem_pattern_name=%(problem_pattern_name)s,
        problem_pattern_source=%(problem_pattern_source)s,
        issue_id=%(issue_id)s,
        issue_relation_type=%(issue_relation_type)s,
        issue_confirmed=%(issue_confirmed)s,
        update_by=%(update_by)s,
        update_time=CURRENT_TIMESTAMP
    WHERE ticket_id=%(ticket_id)s
    """
    event_sql = "INSERT INTO ticket_event (id, ticket_id, event_type, operator_id, operator_name, content, event_data, create_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
    for row in updates:
        cur.execute(sql, row)
        if row.get('issue_binding_applied'):
            eid = snowIdWorker.get_id()
            event_ids.append(eid)
            cur.execute(event_sql, (eid, row['ticket_id'], ISSUE_EVENT_TYPE, None, SCRIPT_OPERATOR, f"脚本补录工单归因到问题实例 {row['issue_id']}", json.dumps({'action':'bind','issue_id':row['issue_id'],'relation_type':row['issue_relation_type'],'confirmed':bool(row['issue_confirmed']),'source':SCRIPT_OPERATOR}, ensure_ascii=False), now_text()))
    return event_ids


def save_config(cur, cfg):
    cur.execute("UPDATE sys_config SET config_value=%s, update_by=%s, update_time=CURRENT_TIMESTAMP WHERE config_key=%s", (json.dumps(cfg, ensure_ascii=False), SCRIPT_OPERATOR, SYNC_CONFIG_KEY))


def refresh_issue_counts(cur, issue_ids):
    for issue_id in sorted({int(x) for x in issue_ids if x}):
        cur.execute("UPDATE ticket_issue SET affected_ticket_count=(SELECT COUNT(1) FROM ticket t WHERE t.del_flag='0' AND t.issue_id=%s), update_by=%s, update_time=CURRENT_TIMESTAMP WHERE issue_id=%s", (issue_id, SCRIPT_OPERATOR, issue_id))


def run_preview(args):
    load_env(args.env_file)
    with db(read_only=True) as conn:
        with conn.cursor() as cur:
            cfg, stat, issue_by_value, issue_by_label, pattern_by_value, pattern_by_label = load_sync_config(cur)
            tickets = load_tickets(cur, args.limit)
            issues = load_issues(cur)
            added = ensure_pattern_options(cfg, stat, pattern_by_value)
            decisions = [classify(x, issue_by_value, issue_by_label, pattern_by_value, pattern_by_label) for x in tickets]
            plans, _, _ = build_issue_plans(tickets, decisions, issues, False)
            summary = build_summary(tickets, decisions, plans)
            files = write_reports(args.output_dir, 'preview', summary, added, decisions, plans)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print(json.dumps(files, ensure_ascii=False, indent=2))


def run_apply(args):
    load_env(args.env_file)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    conn = db(read_only=False)
    try:
        with conn.cursor() as cur:
            cfg, stat, issue_by_value, issue_by_label, pattern_by_value, pattern_by_label = load_sync_config(cur)
            cfg_before = json.loads(json.dumps(cfg, ensure_ascii=False))
            tickets = load_tickets(cur, args.limit)
            issues = load_issues(cur)
            added = ensure_pattern_options(cfg, stat, pattern_by_value)
            decisions = [classify(x, issue_by_value, issue_by_label, pattern_by_value, pattern_by_label) for x in tickets]
            plans, assign_map, new_issues = build_issue_plans(tickets, decisions, issues, bool(args.skip_issue_binding))
            summary = build_summary(tickets, decisions, plans)
            files = write_reports(args.output_dir, 'apply_preview', summary, added, decisions, plans)
            updates = build_apply_updates(tickets, decisions, assign_map, bool(args.issue_confirmed))
            artifact = snapshot_before(tickets, updates, cfg_before, plans, issues, new_issues)
            artifact_path = Path(args.output_dir) / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_apply_rollback.json"
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding='utf-8')
            save_config(cur, cfg)
            insert_issues(cur, new_issues)
            artifact['inserted_event_ids'] = apply_ticket_updates(cur, updates)
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding='utf-8')
            refresh_issue_counts(cur, [x['issue_id'] for x in plans if x['issue_action'] in {'reuse', 'create'}])
            conn.commit()
            print("写库完成。")
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print(json.dumps(files, ensure_ascii=False, indent=2))
            print(str(artifact_path))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_rollback(args):
    load_env(args.env_file)
    artifact = json.loads(Path(args.artifact).read_text(encoding='utf-8'))
    conn = db(read_only=False)
    try:
        with conn.cursor() as cur:
            ids = [int(x) for x in artifact.get('inserted_event_ids') or [] if x]
            if ids:
                cur.execute(f"DELETE FROM ticket_event WHERE id IN ({','.join(['%s'] * len(ids))})", ids)
            for row in artifact.get('ticket_before') or []:
                cur.execute("""
                    UPDATE ticket
                    SET issue_type_id=%s, issue_type_name=%s, classification_source=%s,
                        problem_pattern_code=%s, problem_pattern_name=%s, problem_pattern_source=%s,
                        issue_id=%s, issue_relation_type=%s, issue_confirmed=%s,
                        update_by=%s, update_time=CURRENT_TIMESTAMP
                    WHERE ticket_id=%s
                """, (row['issue_type_id'], row['issue_type_name'], row['classification_source'], row['problem_pattern_code'], row['problem_pattern_name'], row['problem_pattern_source'], row['issue_id'], row['issue_relation_type'], row['issue_confirmed'], SCRIPT_OPERATOR, row['ticket_id']))
            issue_ids = [i(x.get('issue_id')) for x in artifact.get('inserted_issue_rows') or [] if i(x.get('issue_id'))]
            if issue_ids:
                cur.execute(f"DELETE FROM ticket_issue WHERE issue_id IN ({','.join(['%s'] * len(issue_ids))})", issue_ids)
            for row in artifact.get('existing_issue_before') or []:
                cur.execute("UPDATE ticket_issue SET affected_ticket_count=%s, update_by=%s, update_time=CURRENT_TIMESTAMP WHERE issue_id=%s", (row.get('affected_ticket_count'), SCRIPT_OPERATOR, row.get('issue_id')))
            save_config(cur, artifact.get('config_before') or {})
            conn.commit()
            print(f"已按工件回滚完成：{args.artifact}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    args = parse_args()
    if args.cmd == 'preview':
        run_preview(args)
    elif args.cmd == 'apply':
        run_apply(args)
    else:
        run_rollback(args)


if __name__ == '__main__':
    main()
