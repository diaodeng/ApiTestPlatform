"""
周报脚本：读取 2026-07-17 ~ 2026-07-23 的工单数据并生成分类统计报告。
使用 .env.prod 数据库配置。
"""

import os
import sys
from datetime import datetime, timedelta
from urllib.parse import quote_plus

# 将 server 目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path

# 强制加载 .env.prod 配置
BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / '.env.prod'
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✅ 已加载配置: {env_file}")
else:
    print(f"❌ 找不到配置文件: {env_file}")
    sys.exit(1)

from sqlalchemy import create_engine, func, and_, or_, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, JSON, Text, Index
from sqlalchemy.dialects.mysql import LONGTEXT


# ─────────────────────────────────────────
# 轻量级工单 ORM（避免完整项目依赖）
# ─────────────────────────────────────────
class Base(DeclarativeBase):
    pass


def long_text_type():
    return LONGTEXT


class Ticket(Base):
    __tablename__ = "ticket"
    __table_args__ = {"extend_existing": True}

    ticket_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(long_text_type(), nullable=True)
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    merchant_name: Mapped[str] = mapped_column(String(128), nullable=True, default="")
    module_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    module_name: Mapped[str] = mapped_column(String(128), nullable=True, default="")
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    category_name: Mapped[str] = mapped_column(String(128), nullable=True, default="")
    issue_type_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default="")
    issue_type_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_priority: Mapped[str] = mapped_column(String(20), nullable=True, default="P3")
    internal_priority: Mapped[str] = mapped_column(String(20), nullable=True, default="P3")
    severity: Mapped[str] = mapped_column(String(50), nullable=True, default="")
    source: Mapped[str] = mapped_column(String(50), nullable=True, default="")
    reporter_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reporter_name: Mapped[str] = mapped_column(String(100), nullable=True, default="")
    current_assignee_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_assignee_name: Mapped[str] = mapped_column(String(100), nullable=True, default="")
    first_line_assignee_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    first_line_assignee_name: Mapped[str] = mapped_column(String(100), nullable=True, default="")
    internal_owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    internal_owner_name: Mapped[str] = mapped_column(String(100), nullable=True, default="")
    is_problem: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    root_cause_type: Mapped[str | None] = mapped_column(String(128), nullable=True, default="")
    solution_type: Mapped[str | None] = mapped_column(String(128), nullable=True, default="")
    resolution_code: Mapped[str | None] = mapped_column(String(64), nullable=True, default="")
    resolution_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="")
    problem_pattern_code: Mapped[str | None] = mapped_column(String(128), nullable=True, default="")
    problem_pattern_name: Mapped[str | None] = mapped_column(String(256), nullable=True, default="")
    affected_version: Mapped[str | None] = mapped_column(String(100), nullable=True, default="")
    planned_fix_version: Mapped[str | None] = mapped_column(String(100), nullable=True, default="")
    fixed_version: Mapped[str | None] = mapped_column(String(100), nullable=True, default="")
    released_version: Mapped[str | None] = mapped_column(String(100), nullable=True, default="")
    root_cause: Mapped[str] = mapped_column(long_text_type(), nullable=True)
    solution: Mapped[str] = mapped_column(long_text_type(), nullable=True)
    submit_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_process_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    del_flag: Mapped[str] = mapped_column(String(1), nullable=False, default="0")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ─────────────────────────────────────────
# 数据库连接
# ─────────────────────────────────────────
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USERNAME = os.environ.get("DB_USERNAME", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_DATABASE = os.environ.get("DB_DATABASE", "autotest")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USERNAME}:{quote_plus(DB_PASSWORD)}@"
    f"{DB_HOST}:{DB_PORT}/{DB_DATABASE}?charset=utf8mb4"
)

print(f"🔗 连接数据库: {DB_HOST}:{DB_PORT}/{DB_DATABASE}")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ─────────────────────────────────────────
# 时间范围
# ─────────────────────────────────────────
BEGIN_TIME = datetime(2026, 7, 17, 0, 0, 0)
END_TIME = datetime(2026, 7, 23, 23, 59, 59)

print(f"📅 统计时间: {BEGIN_TIME.strftime('%Y-%m-%d')} ~ {END_TIME.strftime('%Y-%m-%d')}")
print()

# ─────────────────────────────────────────
# 查询统计
# ─────────────────────────────────────────


def fmt_num(n):
    """格式化数字为千分位"""
    return f"{n:,}"


def fmt_pct(part, total):
    """百分比"""
    if total == 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def run_report():
    db = SessionLocal()
    try:
        # 基础过滤条件
        base_filter = and_(
            Ticket.del_flag == "0",
            Ticket.create_time >= BEGIN_TIME,
            Ticket.create_time <= END_TIME,
        )

        # ── 总体数量 ──
        total = db.query(func.count(Ticket.ticket_id)).filter(base_filter).scalar() or 0
        print("=" * 70)
        print("                    📊 工单周报 (2026-07-17 ~ 2026-07-23)")
        print("=" * 70)
        print(f"\n  📌 本周新增工单总数: {total} 条\n")

        if total == 0:
            print("  (本周无新增工单)")
            return

        # ── 按天分布 ──
        print("─" * 70)
        print("  📅 按天分布")
        print("─" * 70)
        day_rows = (
            db.query(func.date(Ticket.create_time), func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(func.date(Ticket.create_time))
            .order_by(func.date(Ticket.create_time))
            .all()
        )
        for day, cnt in day_rows:
            bar = "█" * max(1, int(cnt / max(1, max(r[1] for r in day_rows)) * 30))
            print(f"     {day}: {fmt_num(cnt):>6} 条  {bar}")

        # ── 按状态分布 ──
        print("\n─" * 70)
        print("  📌 按工单状态分布")
        print("─" * 70)
        status_rows = (
            db.query(Ticket.status, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.status)
            .order_by(func.count(Ticket.ticket_id).desc())
            .all()
        )
        for status, cnt in status_rows:
            print(f"     {status or '(空)':20s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按项目分布 ──
        print("\n─" * 70)
        print("  📁 按项目分布 (Top 15)")
        print("─" * 70)
        project_rows = (
            db.query(Ticket.project_id, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.project_id)
            .order_by(func.count(Ticket.ticket_id).desc())
            .limit(15)
            .all()
        )
        for pid, cnt in project_rows:
            print(f"     project_id={pid}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按模块分布 ──
        print("\n─" * 70)
        print("  📦 按模块分布 (Top 15)")
        print("─" * 70)
        module_rows = (
            db.query(Ticket.module_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.module_name)
            .order_by(func.count(Ticket.ticket_id).desc())
            .limit(15)
            .all()
        )
        for mname, cnt in module_rows:
            label = mname or "(未填写)"
            print(f"     {label:30s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按工单类型分布 ──
        print("\n─" * 70)
        print("  🏷️  按工单类型分布")
        print("─" * 70)
        issue_type_rows = (
            db.query(Ticket.issue_type_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.issue_type_name)
            .order_by(func.count(Ticket.ticket_id).desc())
            .all()
        )
        for itype, cnt in issue_type_rows:
            label = itype or "(未填写)"
            print(f"     {label:30s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按来源分布 ──
        print("\n─" * 70)
        print("  📥 按工单来源分布")
        print("─" * 70)
        source_rows = (
            db.query(Ticket.source, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.source)
            .order_by(func.count(Ticket.ticket_id).desc())
            .all()
        )
        for src, cnt in source_rows:
            label = src or "(未填写)"
            print(f"     {label:30s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按优先级分布 ──
        print("\n─" * 70)
        print("  🔥 按内部优先级分布")
        print("─" * 70)
        priority_rows = (
            db.query(Ticket.internal_priority, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.internal_priority)
            .order_by(Ticket.internal_priority)
            .all()
        )
        for pri, cnt in priority_rows:
            label = pri or "(未填写)"
            print(f"     {label:30s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按处理人分布 (Top 15) ──
        print("\n─" * 70)
        print("  👤 按当前处理人分布 (Top 15)")
        print("─" * 70)
        assignee_rows = (
            db.query(Ticket.current_assignee_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.current_assignee_name)
            .order_by(func.count(Ticket.ticket_id).desc())
            .limit(15)
            .all()
        )
        for aname, cnt in assignee_rows:
            label = aname or "(未指派)"
            print(f"     {label:20s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 是否真实问题 ──
        print("\n─" * 70)
        print("  ✅ 是否真实问题")
        print("─" * 70)
        problem_rows = (
            db.query(Ticket.is_problem, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.is_problem)
            .all()
        )
        for is_p, cnt in problem_rows:
            if is_p is True:
                label = "真实问题"
            elif is_p is False:
                label = "非问题"
            else:
                label = "未填写"
            print(f"     {label:20s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按根因分类 ──
        print("\n─" * 70)
        print("  🔍 按根因分类分布")
        print("─" * 70)
        root_cause_rows = (
            db.query(Ticket.root_cause_type, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.root_cause_type)
            .order_by(func.count(Ticket.ticket_id).desc())
            .all()
        )
        for rct, cnt in root_cause_rows:
            label = rct or "(未填写)"
            print(f"     {label:30s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按解决方式 ──
        print("\n─" * 70)
        print("  🛠️  按解决方式分布")
        print("─" * 70)
        solution_rows = (
            db.query(Ticket.solution_type, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.solution_type)
            .order_by(func.count(Ticket.ticket_id).desc())
            .all()
        )
        for stype, cnt in solution_rows:
            label = stype or "(未填写)"
            print(f"     {label:30s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按关闭结果分布 ──
        print("\n─" * 70)
        print("  🔒 按关闭结果分布")
        print("─" * 70)
        resolution_rows = (
            db.query(Ticket.resolution_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.resolution_name)
            .order_by(func.count(Ticket.ticket_id).desc())
            .all()
        )
        for rname, cnt in resolution_rows:
            label = rname or "(未填写)"
            print(f"     {label:30s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 按问题模式分布 (Top 15) ──
        print("\n─" * 70)
        print("  🎯 按细分问题类型分布 (Top 15)")
        print("─" * 70)
        pattern_rows = (
            db.query(Ticket.problem_pattern_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.problem_pattern_name)
            .order_by(func.count(Ticket.ticket_id).desc())
            .limit(15)
            .all()
        )
        for pname, cnt in pattern_rows:
            label = pname or "(未填写)"
            print(f"     {label:35s}: {fmt_num(cnt):>6} 条  ({fmt_pct(cnt, total)})")

        # ── 平均处理耗时 ──
        avg_seconds = (
            db.query(func.avg(Ticket.total_process_seconds))
            .filter(base_filter, Ticket.total_process_seconds > 0)
            .scalar()
            or 0
        )
        avg_hours = avg_seconds / 3600
        print("\n─" * 70)
        print("  ⏱️  处理耗时")
        print("─" * 70)
        print(f"     平均处理耗时: {avg_hours:.1f} 小时 ({int(avg_seconds)} 秒)")
        print(f"     (仅统计已记录耗时的工单)")

        # ── 按版本分布 ──
        print("\n─" * 70)
        print("  📋 版本相关统计")
        print("─" * 70)
        for version_field, label in [
            (Ticket.affected_version, "受影响版本"),
            (Ticket.planned_fix_version, "计划修复版本"),
            (Ticket.fixed_version, "实际修复版本"),
            (Ticket.released_version, "发版版本"),
        ]:
            ver_rows = (
                db.query(version_field, func.count(Ticket.ticket_id))
                .filter(base_filter, version_field != "", version_field.isnot(None))
                .group_by(version_field)
                .order_by(func.count(Ticket.ticket_id).desc())
                .limit(10)
                .all()
            )
            if ver_rows:
                print(f"\n     [{label}]")
                for ver, cnt in ver_rows:
                    print(f"       {ver:30s}: {fmt_num(cnt):>6} 条")

        print("\n" + "=" * 70)
        print("                         📊 报告结束")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_report()
