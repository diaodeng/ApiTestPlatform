# 2026-07-07 工单处理口径、统计与相似问题治理实施方案

## 结论

本方案在 2026-07-08 讨论后修订：当前阶段不新增“已处理”主流程状态，也不把“是否已发版”塞进 `status`。推荐把统计主时间、首次响应、首次处理结论、处置完成、关闭归档、发布验证拆成独立时间字段。

第一阶段优先落地：

1. 新增 `submit_time` 到工单主表，作为统一业务提交时间；外部同步取外部 `createTime`，手工创建取本地 `create_time`。
2. 新增 `processed_at`，表示“首次形成有效排查结论时间”；它不能用 `first_response_at` 替代。
3. 保留现有 `resolved_at` 终态写入逻辑，但把语义明确为“处置完成时间”，不是只代表真实 Bug 修复完成。
4. 保留 `first_response_at`，继续表达首次响应/接手时间，用于响应 SLA。
5. 新增版本治理字段：`affected_version`、`planned_fix_version`、`fixed_version`；发布验证字段 `released_version/released_at/verified_at` 可同步做，也可作为第一阶段后半段。

第二阶段再考虑 Issue 归因层。当前根因、根因分类、细分问题字段已经能做分类统计；Issue 层解决的是“多张 Ticket 是否属于同一个真实问题实例”，不是替代根因字段。

## 当前项目现状

### 已具备能力

1. `Ticket` 主表已有 `status`、`started_at`、`resolved_at`、`closed_at`、`first_response_at`、`total_process_seconds`。
2. `first_response_at` 当前在指派、状态流转自动切换处理人时写入，用于表达首次响应/接手。
3. 状态流转统一走 `TicketService.change_ticket_status`，工作流状态由 `workflow_status` 和 `workflow_transition` 动态配置。
4. 状态历史由 `ticket_status_history` 记录，事件由 `ticket_event` 记录，事件类型已包含 `DEPLOYED`、`VERIFIED`、`RESOLVED`、`CLOSED`。
5. 统计页已有 `/ticket/statistics/overview` 和 `/ticket/statistics/trend`，当前趋势已统计新增、解决、关闭、净增、周期末未关闭存量、Bug/非 Bug、Top 模块和 Top 细分问题。
6. 细分问题类型、根因分类、解决方式、关闭结果已结构化落在工单主表，统计枚举由 `ticket.sync.automation.statClassification` 配置。
7. 相似工单检索已存在，支持 `local_hash`、外部 `embedding` 和 `qdrant` Provider，并在工单详情和自然语言搜索中展示相似结果。

### 当前缺口

1. 统计主时间仍从 `extra_data.external_sync.externalCreateTime` 等 JSON 字段实时解析，缺少主表结构化 `submit_time`，不利于索引、排序和趋势统计。
2. 没有 `processed_at`，无法稳定统计“首次形成排查结论”的时间。
3. 前端当前“处理状态”字段 `processStatus` 实际表示日志拉取/AI 分析进度，如 `log_pull_success`、`ai_success`，不等于业务上的“是否已处理”。
4. `extra_data.version_key` 当前用于 AI 仓库映射，更像“问题发生/分析版本”，不适合作为计划修复版本。
5. 当前有根因、根因分类和细分问题字段，但没有“问题实例归因层”。因此能统计根因分布，却不能稳定统计“几张工单属于同一个真实问题”“一个问题影响多少工单”。
6. `ticket_statistics_daily` 和 `user_statistics_daily` 目前是预留表，实时统计没有快照口径，历史周报会受后续分类变更影响。

## 字段语义推荐

| 字段 | 推荐语义 | 是否第一阶段做 |
|---|---|---|
| `submit_time` | 工单业务提交时间，统计新增和趋势的主时间 | 必做 |
| `first_response_at` | 首次响应/接手时间，当前已有，用于响应 SLA | 保留 |
| `processed_at` | 首次形成有效排查结论时间，非空即已处理 | 必做 |
| `resolved_at` | 工单处置完成时间，所有终态均可写入 | 保留当前逻辑 |
| `closed_at` | 工单正式关闭归档时间 | 保留 |
| `released_at` | 实际发布修复版本时间 | 建议做 |
| `verified_at` | 验证完成时间 | 建议做 |
| `affected_version` | 问题发生/分析版本，兼容 `extra_data.version_key` | 必做 |
| `planned_fix_version` | 计划修复版本，治理和排期字段 | 必做 |
| `fixed_version` | 实际修复版本 | 必做 |
| `released_version` | 实际发版版本 | 建议做 |

## 为什么 `processed_at` 不能用 `first_response_at`

`first_response_at` 当前在“指派”或“状态流转自动切换处理人”时写入。它代表有人接手或系统发生响应动作，但此时可能还没有排查结论。

示例：

| 时间 | 动作 | 字段 |
|---|---|---|
| 10:00 | 外部提交工单 | `submit_time=10:00` |
| 10:05 | 指派给内部负责人 | `first_response_at=10:05` |
| 11:30 | 排查确认是配置问题，给出处理方案 | `processed_at=11:30` |
| 14:00 | 工单进入终态 | `resolved_at=14:00` |
| 次日 | 正式关闭 | `closed_at=次日` |

如果用 `first_response_at` 替代 `processed_at`，处理率会被响应动作虚高；领导看到的“已处理”会变成“有人接手”，不是“有排查结果”。

因此推荐：

1. `first_response_at` 继续用于响应率、首次响应耗时。
2. `processed_at` 用于处理率、首次处理耗时、未处理存量。

## `resolved_at` 推荐语义

结合当前系统已有逻辑，推荐保留“进入终态即写 `resolved_at`”的设计。

`resolved_at` 的推荐语义调整为：

> 工单处置完成时间，即工单已经有最终处置结论并进入终态。

它不限定为“真实 Bug 已修复”。非问题、重复、驳回、设计如此、用户误操作等终态也可以写 `resolved_at`。要统计真实 Bug 修复，应结合：

1. `is_problem = true`
2. `solution_type`
3. `resolution_code`
4. `fixed_version`
5. `released_at`
6. `verified_at`

这样可以保留现有代码和历史数据口径，同时避免把 `resolved_at` 误解释为“发布完成”或“真实问题修复完成”。

## 处理完成规则

`processed_at` 表示“已经形成有效排查结论”，不是“已经响应”、不是“已经关闭”、也不是“已经发版”。

满足下列任一条件时，如果 `processed_at` 为空，应写入当前时间：

1. 状态流转时提交了有效 `root_cause`、`solution`、`is_problem`、`root_cause_type`、`solution_type`、`resolution_code`、`problem_pattern_code` 中任意关键结论字段。
2. 状态流转到 `wait_release`、`wait_verify`、`resolved`、`closed`、`rejected`、`non_problem`、`design_as_expected`、`user_misoperation`、`duplicated` 等已具备结论或终态的状态。
3. 保存 RCA 且包含 `root_cause_detail`、`investigation_process`、`fix_solution`、`verify_method` 等有效内容。
4. 新增排查类事件，事件类型为 `ANALYSIS`、`RCA`、`LOG_ANALYSIS`、`DB_CHECK`、`FIX_APPLIED`、`DEPLOYED`、`VERIFIED`、`RESOLVED`、`CLOSED`，且内容或结构化数据不为空。
5. AI 分析结果被人工确认并写回主结论或 RCA 时。AI 任务成功本身只代表有建议，不自动写 `processed_at`。

## 数据模型方案

### 第一阶段新增字段

在 `ticket` 表新增：

| 字段 | 类型建议 | 说明 |
|---|---|---|
| `submit_time` | `DATETIME` | 工单业务提交时间，外部工单取外部 `createTime`，本地工单取 `create_time` |
| `affected_version` | `VARCHAR(100)` | 问题发生/分析版本，兼容迁移自 `extra_data.version_key` |
| `planned_fix_version` | `VARCHAR(100)` | 计划修复版本，治理和排期字段 |
| `fixed_version` | `VARCHAR(100)` | 实际修复版本 |
| `released_version` | `VARCHAR(100)` | 实际发版版本，可与发布事件联动 |
| `processed_at` | `DATETIME` | 首次形成处理结论时间 |
| `released_at` | `DATETIME` | 实际发版时间 |
| `verified_at` | `DATETIME` | 验证完成时间 |

建议索引：

1. `idx_ticket_del_submit_time(del_flag, submit_time, ticket_id)`
2. `idx_ticket_del_processed_time(del_flag, processed_at, ticket_id)`
3. `idx_ticket_del_resolved_time(del_flag, resolved_at, ticket_id)`
4. `idx_ticket_del_closed_time(del_flag, closed_at, ticket_id)`
5. `idx_ticket_del_planned_fix_version(del_flag, planned_fix_version, ticket_id)`

`extra_data.version_key` 暂时保留，用于兼容 AI 仓库映射。新增/编辑接口同步维护 `affected_version`，AI 分析取版本时优先使用 `affected_version`，为空再回退 `extra_data.version_key`。

### 提交时间写入规则

1. 手工创建工单：`submit_time = create_time`。
2. 外部同步工单：`submit_time = 外部 createTime`，失败时回退 `create_time`。
3. 主动拉取多维表格：如果映射字段中有外部创建时间，写入 `submit_time`。
4. 历史数据回填：优先从 `extra_data.external_sync.externalCreateTime` 或 `extra_data.external_sync.source.externalCreateTime` 解析，失败时回填 `create_time`。
5. 查询过渡期：统计表达式优先 `submit_time`，为空时继续回退 JSON 外部时间，再回退 `create_time`，避免迁移不完整导致数据丢失。

### 第二阶段 Issue 层

第二阶段是否实施 Issue 层，取决于是否需要从“工单统计”升级为“真实问题实例统计”。

当前已有根因字段可以回答：

1. 根因分类分布是什么。
2. Top 细分问题是什么。
3. 哪些工单是真实问题。
4. 关闭结果是什么。

Issue 层用于回答：

1. 多张工单是不是同一个真实问题实例。
2. 一个真实问题影响了多少门店、用户、工单。
3. 今天新增工单里实际新增了几个真实问题。
4. 哪些工单是重复反馈。
5. 某个修复版本覆盖了哪些真实问题实例。

如果实施，建议新增 `ticket_issue`，并在 `ticket` 表新增 `issue_id`、`issue_relation_type`、`issue_confirmed`。`ticket_relation` 只保存依赖、阻塞、引用等补充关系，不替代 Issue 归因。

## 后端改造方案

### 文件边界

按当前项目拆分规则，不继续膨胀 `TicketService`。建议新增：

1. `server/modules/ticket/service/core/ticket_processing_metric_service.py`
   - 负责 `submit_time/processed_at/released_at/verified_at/resolved_at/closed_at` 的判定和写入。
   - 对外公开方法示例：`resolve_submit_time`、`mark_processed_if_needed`、`apply_status_time_fields`、`apply_event_time_fields`。
2. `server/modules/ticket/service/stats/ticket_processing_stats_service.py`
   - 负责处理率、处理趋势、SLA 指标统计。
   - 控制器直接调用该服务，不通过 `TicketService` 做简单转发。
3. 第二阶段如实施 Issue，再新增 `service/issue/ticket_issue_service.py` 和 `service/issue/ticket_relation_service.py`。

### 状态流转改造

在 `change_ticket_status` 中保留现有工作流校验和历史写入，时间字段判定下沉到 `TicketProcessingMetricService`：

1. 进入 `processing` 或指派时，保持现有 `started_at/first_response_at` 逻辑。
2. 满足处理结论规则时，写 `processed_at`，只写第一次。
3. `wait_release -> wait_verify` 或目标状态 `wait_verify` 且来源是 `wait_release` 时，写 `released_at`。
4. `wait_verify -> resolved` 时，写 `verified_at`。
5. 任意终态仍按当前逻辑写 `resolved_at`，语义为处置完成时间。
6. 进入 `closed` 时写 `closed_at`。
7. `total_process_seconds` 短期保持现有逻辑，文档中说明它当前更接近“处置/闭环耗时”；如果后续要统计首次处理耗时，使用 `processed_at - submit_time`。

### 事件写入改造

新增事件时通过 `TicketProcessingMetricService.apply_event_time_fields`：

1. `DEPLOYED` 写 `released_at` 和 `released_version`。
2. `VERIFIED` 写 `verified_at`。
3. `RESOLVED` 写 `resolved_at`。
4. `CLOSED` 写 `closed_at`。
5. 事件包含有效排查结论时写 `processed_at`。

### RCA 和 AI 写回

1. 保存 RCA 时，如果根因、排查过程、修复方案、验证方式任一字段有效，则写 `processed_at`。
2. AI 分析任务成功不自动写 `processed_at`。
3. 当用户确认 AI 结论并写回 `root_cause/solution/RCA` 时，再写 `processed_at`。

### 导入和同步改造

1. Excel 导入模板新增：`工单提交时间`、`问题发生版本`、`计划修复版本`、`实际修复版本`、`实际发版版本`、`处理完成时间`、`发版时间`、`验证时间`。
2. 外部同步字段模型 `externalFieldModel` 新增可映射目标字段，允许从飞书多维表格同步上述字段。
3. `extra_data.version_key` 迁移到 `affected_version`，但不删除原字段。
4. 外部同步入库 payload 统一写 `submit_time`，后续统计不再重复解析 JSON。

## 统计接口方案

### 统计口径
新增下面的统计口径，不要删除原来已有的统计口径

| 指标 | 计算方式 |
|---|---|
| 新增工单数 | `submit_time` 在范围内的工单数量 |
| 已响应数 | `first_response_at` 在范围内的工单数量 |
| 已处理数 | `processed_at` 在范围内的工单数量 |
| 新增工单已处理数 | `submit_time` 在范围内且 `processed_at IS NOT NULL` 的工单数量 |
| 新增工单处理率 | 新增工单已处理数 / 新增工单数 |
| 处置完成数 | `resolved_at` 在范围内的工单数量 |
| 关闭数 | `closed_at` 在范围内的工单数量 |
| 平均首次响应耗时 | `first_response_at - submit_time`，仅统计 `first_response_at IS NOT NULL` |
| 平均首次处理耗时 | `processed_at - submit_time`，仅统计 `processed_at IS NOT NULL` |
| 平均处置完成耗时 | `resolved_at - submit_time`，仅统计 `resolved_at IS NOT NULL` |
| 平均关闭耗时 | `closed_at - submit_time`，仅统计 `closed_at IS NOT NULL` |
| 周期末未处理存量 | 周期末前已提交且 `processed_at` 为空或晚于周期末 |
| 周期末未关闭存量 | 周期末前已提交且 `closed_at` 为空或晚于周期末 |

### overview 返回建议

在现有 `/ticket/statistics/overview` 中追加字段，保持兼容：

```json
{
  "total": 100,
  "newCount": 100,
  "firstRespondedCount": 80,
  "processedCount": 70,
  "processedInNewCount": 60,
  "processRate": 0.6,
  "resolvedCount": 50,
  "closedCount": 30,
  "avgFirstResponseSeconds": 600,
  "avgFirstProcessSeconds": 3600,
  "avgResolveSeconds": 86400,
  "avgCloseSeconds": 172800,
  "unprocessedCount": 40,
  "processedStatusCounts": [
    {"status": "processed", "label": "已处理", "count": 60},
    {"status": "unprocessed", "label": "未处理", "count": 40}
  ]
}
```

注意：`processedCount` 表示处理动作发生在查询时间范围内；`processedInNewCount` 表示查询范围内新增的工单里已处理的数量。页面文案必须区分。

### trend 返回建议

在现有 `/ticket/statistics/trend` 的每个 bucket 追加：

```json
{
  "newCount": 10,
  "firstRespondedCount": 8,
  "processedCount": 7,
  "processedInNewCount": 6,
  "processRate": 0.6,
  "resolvedCount": 5,
  "closedCount": 3,
  "unprocessedBacklog": 12,
  "avgFirstResponseSeconds": 600,
  "avgFirstProcessSeconds": 3600
}
```

整体趋势图新增曲线：

1. 新增
2. 已响应
3. 已处理
4. 处理率
5. 处置完成
6. 关闭
7. 未处理存量

## 前端改造方案

### 工单列表

1. 新增列：
   - `submitTime`：直接来自主表 `submit_time`。
   - `firstResponseAt`：首次响应时间。
   - `processedAt`：处理完成/首次结论时间。
   - `processingConclusionStatus`：处理结论状态，展示“已处理/未处理”。
   - `plannedFixVersion`、`fixedVersion`、`releasedVersion`。
2. 保留当前 `processStatus` 筛选和列，但建议显示名调整为“日志/AI进度”，避免和处理结论混淆。
3. 新增筛选：
   - 处理结论：全部/未处理/已处理。
   - 提交时间范围，改为主表 `submit_time`。
   - 处理完成时间范围。
   - 计划修复版本、实际修复版本、发版版本。
4. 列设置继续复用当前用户配置 `ticket/ticket_list_columns`。

### 新增/编辑工单

1. 新增版本字段：
   - 问题发生版本 `affectedVersion`。
   - 计划修复版本 `plannedFixVersion`。
   - 实际修复版本 `fixedVersion`。
   - 实际发版版本 `releasedVersion`。
2. 当前 `versionKey` 字段保留但文案调整为“分析版本/发生版本”，落库优先写 `affectedVersion`，同时兼容 `extra_data.version_key`。
3. 保存时不因隐藏字段清空原值，符合当前配置页联动显示原则。

### 状态流转弹窗

1. 当目标状态进入 `wait_release/resolved/closed` 等关键阶段时，按规则展示建议字段：
   - `wait_release`：建议要求根因、解决方案、计划修复版本或实际修复版本。
   - `wait_verify`：建议要求实际发版版本或发版说明。
   - `resolved` 或其他终态：建议要求关闭结果、是否真实问题、根因分类、解决方式。
2. 不建议一次性强制全部字段必填，先通过配置或状态规则逐步收紧。

### 统计页

1. 顶部指标卡改为：
   - 工单总数
   - 新增工单
   - 已响应数
   - 已处理数
   - 处理率
   - 平均首次处理耗时
   - 未处理存量
2. 趋势图新增“处理趋势/处理率趋势”。
3. 趋势明细新增“已响应”“已处理”“处理率”“未处理存量”“平均首次响应耗时”“平均首次处理耗时”列。
4. 显示配置继续复用 `ticket_statistics_blocks`，新增块默认展示。

## AI 和相似工单联动

第一阶段不强制做 Issue 层，只保留当前相似工单推荐。

第二阶段如实施 Issue：

1. 新工单入库后，继续执行相似检索。
2. 若相似度超过配置阈值，例如 95%，生成归因推荐，不自动强绑定。
3. 工程师在详情页确认后，将当前工单 `issue_id` 指向已有 Issue。
4. 如果判断是新问题，则创建新 Issue 并绑定当前工单。
5. AI 分析上下文继续包含相似工单，同时增加所属 Issue 和同 Issue 工单摘要。
6. 工单列表仍展示所有工单，不因重复归因隐藏任何 Ticket。

## 迁移脚本建议

第一阶段 SQL 建议命名：

`server/sql/20260708_ticket_submit_processed_version_columns.sql`

包含：

1. `ticket` 表新增 `submit_time`、版本字段、`processed_at/released_at/verified_at`。
2. 新增索引。
3. 从 `extra_data.external_sync.externalCreateTime`、`extra_data.external_sync.source.externalCreateTime` 或 `create_time` 回填 `submit_time`。
4. 从 `extra_data.version_key` 回填 `affected_version`。
5. 从状态历史、事件历史保守回填 `processed_at/released_at/verified_at`。
6. 不批量重写历史 `resolved_at`，保留现有终态处置完成口径。

第二阶段 SQL 如确认实施再新增：

`server/sql/20260708_ticket_issue_relation_tables.sql`

包含：

1. 创建 `ticket_issue`。
2. `ticket` 表新增 `issue_id/issue_relation_type/issue_confirmed`。
3. 创建 `ticket_relation`。

## 验证计划

### 后端单元测试

1. 手工创建工单写入 `submit_time=create_time`。
2. 外部同步工单按外部 `createTime` 写入 `submit_time`。
3. `first_response_at` 在指派/接手时写入，但不等于 `processed_at`。
4. `processed_at` 首次写入后不被重复覆盖。
5. `processing -> wait_release` 写 `processed_at`，不影响 `first_response_at`。
6. 任意终态继续写 `resolved_at`，语义为处置完成时间。
7. `resolved -> closed` 写 `closed_at`，不覆盖 `resolved_at`。
8. 保存 RCA 写 `processed_at`。
9. AI 任务成功不写 `processed_at`，人工确认写回才写。
10. 统计接口返回新增、响应、处理、处理率、未处理存量。
11. 历史回填脚本可重复执行，不覆盖已有非空时间。

### 前端验证

1. 工单列表展示主表提交时间、首次响应时间、处理结论状态和处理时间。
2. 旧“处理状态”文案调整为“日志/AI进度”后仍可筛选日志/AI进度。
3. 新增/编辑工单保存版本字段，不影响历史 `versionKey`。
4. 状态流转弹窗在不同目标状态下显示对应字段。
5. 统计页处理率和趋势图显示正确。
6. 显示配置保存后刷新仍保留。

### 回归命令

1. 后端：`cd server && uv run ruff check .`
2. 后端测试：`cd server && uv run pytest tests/test_ticket_topic_stats_service.py`
3. 前端：`cd web && npm run build:prod`

如后续实现只改后端统计，可先执行 ruff 和对应 pytest；如改统计页或列表页，需要执行前端构建。

## 分阶段实施计划

### 第一阶段：提交时间、处理口径和版本治理

目标：解决统计主时间、处理率、处理趋势和版本治理字段。

1. 新增数据库字段和模型字段。
2. 新增 `TicketProcessingMetricService`。
3. 改造创建、外部同步、主动拉取和导入链路，统一写 `submit_time`。
4. 改造状态流转、事件、RCA 保存逻辑，写入 `processed_at/released_at/verified_at`。
5. 保留 `resolved_at` 终态处置完成逻辑。
6. 改造统计 overview/trend。
7. 改造列表、新增/编辑、状态流转弹窗、统计页。
8. 补充迁移脚本和测试。

### 第二阶段：问题实例归因层

目标：在确实需要“真实问题数、重复工单数、影响工单数”时，再解决相似/重复工单治理。

1. 新增 `ticket_issue`、`ticket.issue_id` 和 `ticket_relation`。
2. 新增 Issue 服务、DAO、VO、控制器。
3. 工单详情页支持从相似推荐归入 Issue。
4. 工单列表和详情展示 Issue 信息。
5. 新增 Issue 统计。

### 第三阶段：快照和周报稳定口径

目标：解决历史统计口径随实时字段变化的问题。

1. 扩展 `ticket_statistics_daily`，增加 `submitted_count/first_responded_count/processed_count/process_rate/unprocessed_backlog`。
2. 新增每日快照任务，按自然日冻结统计。
3. 统计页支持“实时口径/快照口径”切换。
4. 周报、汇总通知优先使用快照口径。

## 风险和取舍

1. `first_response_at` 不能替代 `processed_at`，否则处理率会被接手动作虚高。
2. `resolved_at` 保留现有终态写入逻辑，但必须在页面和文档中定义为“处置完成时间”，不要解释成“真实 Bug 修复时间”。
3. `submit_time` 是统计主口径，建议第一阶段必须结构化到主表，否则后续统计仍长期依赖 JSON 表达式。
4. `processStatus` 已被日志/AI进度占用，新增业务处理口径不要复用该字段名，建议使用 `processingConclusionStatus` 或直接以 `processedAt` 推导。
5. 现有根因字段已经能满足分类统计，不应为了“相似工单”立即上 Issue 层；Issue 层只在需要真实问题实例统计时实施。
6. 统计口径必须在页面文案中区分“查询范围内处理数”和“查询范围新增工单中的已处理数”，否则处理率会被误读。

## 后续实现入口清单

第一阶段优先修改文件：

1. `server/modules/ticket/entity/do/ticket_do.py`
2. `server/modules/ticket/entity/vo/ticket_vo.py`
3. `server/modules/ticket/service/core/ticket_processing_metric_service.py`
4. `server/modules/ticket/service/core/ticket_service.py`
5. `server/modules/ticket/service/sync/ticket_sync_payload_service.py`
6. `server/modules/ticket/service/core/ticket_import_service.py`
7. `server/modules/ticket/dao/ticket_dao.py`
8. `server/modules/ticket/service/stats/ticket_processing_stats_service.py`
9. `server/modules/ticket/controller/ticket_config_controller.py`
10. `web/src/views/ticket/index.vue`
11. `web/src/views/ticket/hooks/useTicketList.js`
12. `web/src/views/ticket/constants.js`
13. `web/src/views/ticket/statistics/index.vue`
14. `server/sql/20260708_ticket_submit_processed_version_columns.sql`

第二阶段确认后再新增：

1. `server/modules/ticket/entity/vo/ticket_issue_vo.py`
2. `server/modules/ticket/dao/ticket_issue_dao.py`
3. `server/modules/ticket/service/issue/ticket_issue_service.py`
4. `server/modules/ticket/service/issue/ticket_relation_service.py`
5. `server/modules/ticket/controller/ticket_issue_controller.py`
6. `web/src/views/ticket/issue/index.vue`

