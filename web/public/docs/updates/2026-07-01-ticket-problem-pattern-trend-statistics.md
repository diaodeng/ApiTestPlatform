# 工单细分问题类型与趋势统计（2026-07-01）

## 背景

工单治理需要长期观察支持类、Bug、非 Bug、模块和具体问题类型随时间的变化。自由标签适合检索，但不适合作为领导看板的稳定统计口径，因此本次把“内存泄露”“280开头券为纸质券规则说明”等细分原因沉淀为固定枚举。

## 本次调整

1. 工单主表新增细分问题类型字段：
   - `problem_pattern_code`
   - `problem_pattern_name`
   - `problem_pattern_confidence`
   - `problem_pattern_source`
   - `problem_pattern_verified`
   - `problem_pattern_verified_by`
   - `problem_pattern_verified_at`
2. `ticket.sync.automation.statClassification` 新增 `problemPatterns` 枚举组，和工单类型、根因分类、解决方式、关闭结果共用同一配置入口。
3. AI 分类统计输出新增 `problemPatternCode/problemPatternName/problemPatternConfidence`，服务端只接受候选枚举中的细分问题；停用的细分问题不会传给 AI。
4. 人工确认的细分问题不会被后续 AI 分类覆盖。
5. 工单列表新增细分问题筛选、表格列、编辑字段和状态流转字段。
6. 工单统计页新增细分问题分布和趋势曲线，趋势明细表保留用于查看每个周期的明细数据。
7. 新增接口 `GET /ticket/statistics/trend`，支持 `day/week/month` 粒度，返回新增、关闭、净增、估算存量、Bug、非 Bug、支持类、Top 模块和 Top 细分问题。

## 前端展示位置

- 菜单入口仍为工单统计页。
- 筛选区选择时间范围、项目、模块、模块 Code、细分问题和趋势粒度后，点击查询会同时刷新汇总统计和趋势统计。
- 趋势曲线位于统计块下方、趋势明细表上方，包含：
  - 整体趋势：新增、关闭、净增、周期末未关闭存量。
  - 问题性质趋势：Bug、非 Bug、未判断、支持类。
  - Top 模块趋势：按查询结果自动取总量最高的模块绘制曲线。
  - Top 细分问题趋势：按查询结果自动取总量最高的细分问题绘制曲线。
- 趋势明细表继续保留，用于在日、周、月粒度切换后查看每个周期的具体数值。
- “显示配置”分为“汇总统计块”和“趋势展示”两组，趋势展示可单独控制整体趋势曲线、问题性质趋势曲线、Top 模块趋势曲线、Top 细分问题趋势曲线和趋势明细表。

## 统计口径

- 汇总统计仍使用 `GET /ticket/statistics/overview`，按查询时间范围内工单创建时间汇总当前结构化字段。
- 趋势统计使用 `GET /ticket/statistics/trend`，按工单创建时间分桶。
- 趋势中的 `openBacklog` 是每个周期末仍未关闭的存量，会包含查询窗口开始前已经存在且未关闭的历史工单。
- 正式周报/月报如果要求历史报表不随后续分类修正变化，后续应增加统计快照任务；当前实现以实时查询当前分类为准。

## 兼容性影响

- 旧库启动时会自动补齐新增列；也可手工执行 `server/sql/20260701_ticket_problem_pattern_columns.sql`。
- 旧工单的细分问题字段为空，需要通过批量重归类或人工维护补齐。
- AI 自动分类完整性判断现在要求细分问题编码和名称也完整；历史已分类但没有细分问题的工单会被视为可继续补齐。
- `tags` 仍保留为辅助检索字段，但不作为细分问题统计主口径。
