# 工单每日快照任务增强

**日期**：2026-07-10

**类型**：功能增强

## 背景

`ticket_daily_statistics_snapshot` 定时任务原先默认统计"今天"的数据，且只支持单日模式（`statistics_date`），不支持日期范围批量补跑。统计"今天"在 23:55 执行时会丢失 23:55~24:00 之间的数据。

## 改动内容

### 1. 任务函数参数改造

**文件**：`server/module_task/scheduler_maintenance.py`

新增 `begin_date` 和 `end_date` 参数，支持三种调用模式：

| 模式 | 参数 | 行为 |
|------|------|------|
| 默认 | 不传参 | 统计昨天 |
| 单日 | `statistics_date` | 统计指定单天 |
| 范围 | `begin_date` + `end_date` | 逐日循环统计范围 |

#### 默认模式改为"昨天"

原来默认统计"今天"，改为默认统计"昨天"（`date.today() - timedelta(days=1)`），确保统计完整自然日数据。

#### 范围模式

- 逐日循环 `begin_date` 到 `end_date`（含），每天独立创建数据库会话和 commit
- 某天失败不影响其他天，失败日期记录在 `failed_days` 列表中
- 支持任务终止标记检查，可中途停止
- 返回汇总：`total_days`、`total_leaf_count`、`failed_days`

### 2. 代码拆分

将任务函数拆分为三个职责清晰的方法：

- `ticket_daily_statistics_snapshot()`：入口函数，参数解析和模式路由
- `_run_snapshot_single(date_str)`：单日执行
- `_run_snapshot_range(task_id, begin_date, end_date)`：范围执行

### 3. 导入变更

- 新增 `date` 和 `timedelta` 导入
- 移除不再使用的 `datetime` 导入

### 4. 文档更新

**文件**：`web/public/docs/2026-07-10-ticket-statistics-usage-guide.md`

更新章节：
- 5.1 任务说明：默认统计改为昨天，新增调度时间建议
- 5.3 手动触发快照：三种调用模式说明和示例
- 5.4 快照幂等性：补充 upsert 幂等说明
- 5.5 调度时间建议：新增章节，说明 23:55 和 00:05 的执行策略
- Q3/Q8 FAQ：补充批量补跑建议

## 影响范围

- 定时任务 `ticket_daily_statistics_snapshot` 的参数格式变化（向后兼容，原有 `statistics_date` 参数仍然有效）
- 默认行为变化：从统计"今天"改为统计"昨天"

## 验证结果

- `ruff check` 语法检查通过
- 导入验证通过（`from module_task.scheduler_maintenance import ticket_daily_statistics_snapshot`）

## 调度建议

- 推荐每天 23:55 执行，参数留空（默认统计昨天）
- 或每天 00:05 执行，效果一致

## 无需拆分任务

`TicketStatisticsSnapshotService.build_daily_snapshot()` 已在单次调用中同时生成：
- 1 条全局快照（`snapshot_scope=all`）
- N 条叶子维度快照（`snapshot_scope=leaf`，按 `项目+模块+工单类型` 分组）

只需 1 个定时任务即可。

---

## 补充修复（2026-07-10 14:17）

### 问题

执行统计任务时报错：
```
(pymysql.err.OperationalError) (1364, "Field 'new_count' doesn't have a default value")
```

### 根因

数据库表 `ticket_statistics_daily` 有一个旧字段 `new_count`（等同于 `submitted_count`，表示新增工单数），但 SQLAlchemy 模型 `TicketStatisticsDaily` 中没有定义该字段。

当快照任务创建新记录时，SQLAlchemy 不会在 INSERT 语句中包含 `new_count`，而该字段在数据库中是 `NOT NULL` 且没有默认值，导致 MySQL 报错。

### 修复方案

**1. 模型层：添加 `new_count` 字段**

文件：`server/modules/ticket/entity/do/ticket_do.py`

```python
new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增工单数（兼容旧字段）")
```

**2. 快照服务：在 payload 中包含 `new_count`**

文件：`server/modules/ticket/service/stats/ticket_statistics_snapshot_service.py`

在 `build_metric_payload` 方法中，将 `new_count` 设置为与 `submitted_count` 相同的值：

```python
submitted_count = len(submitted_rows)
payload = {
    "total_count": ...,
    "submitted_count": submitted_count,
    "new_count": submitted_count,  # 兼容旧字段
    ...
}
```

**3. 数据库迁移：添加默认值**

文件：`server/sql/20260710_ticket_statistics_new_count_default.sql`

```sql
ALTER TABLE ticket_statistics_daily
    MODIFY COLUMN new_count INT NOT NULL DEFAULT 0 COMMENT '新增工单数（兼容旧字段，值同 submitted_count）';
```

**执行顺序**：
1. 先执行 SQL 迁移脚本，为 `new_count` 添加默认值
2. 重启后端服务，使模型变更生效

### 验证结果

- `ruff check` 语法检查通过
- 导入验证通过（`new_count` 字段已添加到模型）

---

## 补充修复：遗留字段默认值问题（2026-07-10 15:05）

### 问题

执行快照任务时连续报错：
```
(pymysql.err.OperationalError) (1364, "Field 'new_count' doesn't have a default value")
(pymysql.err.OperationalError) (1364, "Field 'avg_process_seconds' doesn't have a default value")
```

### 根因分析

通过 git 历史对比发现，`ticket_statistics_daily` 表在最初创建时有以下字段：
- id, statistics_date, **new_count**, resolved_count, closed_count, **avg_process_seconds**, create_time

第三阶段改造（phase3）时，模型重构移除了 `new_count` 和 `avg_process_seconds` 两个旧字段，新增了 `submitted_count` 和更细粒度的 avg 字段。但数据库表中这两个列仍然存在，且是 `NOT NULL` 无默认值。

当快照任务 INSERT 新记录时，SQLAlchemy 不会为模型中不存在的字段生成 INSERT 语句，MySQL 因此报错。

### 修复方案

**1. 模型层：重新添加两个旧字段**

文件：`server/modules/ticket/entity/do/ticket_do.py`

```python
new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增工单数（兼容旧字段）")
avg_process_seconds: Mapped[int] = mapped_column(
    BigInteger, nullable=False, default=0, comment="平均处理秒数（旧字段，兼容保留）"
)
```

**2. 快照服务：在 payload 中包含这两个字段**

文件：`server/modules/ticket/service/stats/ticket_statistics_snapshot_service.py`

- `new_count` = `submitted_count`（值相同，兼容旧字段）
- `avg_process_seconds` = `avg_first_process_seconds`（语义相近，向后兼容）

**3. 数据库迁移：为两个字段添加 DEFAULT**

文件：`server/sql/20260710_ticket_statistics_new_count_default.sql`

```sql
ALTER TABLE ticket_statistics_daily
    MODIFY COLUMN new_count INT NOT NULL DEFAULT 0 COMMENT '新增工单数（兼容旧字段）';

ALTER TABLE ticket_statistics_daily
    MODIFY COLUMN avg_process_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均处理秒数（兼容旧字段）';
```

### 排查方法

通过 git 历史对比找到问题：

```bash
# 查看最初创建时的模型定义
git show babc492:modules/ticket/entity/do/ticket_do.py | grep -A 20 "class TicketStatisticsDaily"

# 查看最新版本
git show HEAD:modules/ticket/entity/do/ticket_do.py | grep -A 60 "class TicketStatisticsDaily"

# 对比发现移除了 new_count 和 avg_process_seconds
```

### 验证结果

- `ruff check` 语法检查通过
- 导入验证通过（两个字段都已添加到模型）
- 等待用户重新执行快照任务验证

---

## 补充修复：旧唯一索引导致重复键冲突（2026-07-10 15:10）

### 问题

```
sqlalchemy.exc.IntegrityError: (pymysql.err.IntegrityError)
(1062, "Duplicate entry '2026-07-09' for key 'ticket_statistics_daily.statistics_date'")
```

### 根因

原始表定义中 `statistics_date` 使用了 `unique=True`，MySQL 自动生成了一个名为 `statistics_date` 的**单列唯一索引**。

第三阶段改造时：
- `phase3.sql` 创建了 `uk_ticket_statistics_daily_date`（另一个唯一索引）
- `dimensional.sql` 只删除了 `uk_ticket_statistics_daily_date` 和 `idx_ticket_statistics_daily_date`
- **遗漏了原始的 `statistics_date` 唯一索引**

结果：同一日期只能有一条记录，无法同时写入全局快照（scope=all）和叶子维度快照（scope=leaf）。

### 修复方案

**文件**：`server/sql/20260710_ticket_statistics_fix_all.sql`

核心操作：
```sql
ALTER TABLE ticket_statistics_daily DROP INDEX `statistics_date`;
```

同时包含：
- 删除旧唯一索引
- 为 `new_count` 和 `avg_process_seconds` 添加 DEFAULT 值（合并之前的修复）

### 执行步骤

1. 先执行确认：
   ```sql
   SHOW INDEX FROM ticket_statistics_daily WHERE Key_name = 'statistics_date';
   ```
2. 执行修复脚本
3. 验证：
   ```sql
   SHOW INDEX FROM ticket_statistics_daily;
   ```
   确认不再有 `statistics_date` 单列唯一索引，只剩 `uk_ticket_statistics_daily_scope` 复合唯一索引。
4. 重启后端，重新执行快照任务
