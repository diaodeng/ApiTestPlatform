# 2026-07-08 工单提交时间、处理结论和版本治理第一阶段实现记录

## 结论

已按第一阶段方案落地：工单主表新增结构化提交时间、处理结论时间、发布验证时间和版本治理字段；统计接口切换为处理口径统计服务；前端列表和统计页展示“处理结论/处理率/未处理存量”。本次不新增 Issue 归因层。

## 后端实现

1. `ticket` 主表模型新增：
   - `submit_time`
   - `processed_at`
   - `released_at`
   - `verified_at`
   - `affected_version`
   - `planned_fix_version`
   - `fixed_version`
   - `released_version`
2. 新增 `TicketProcessingMetricService`：
   - 解析 `submit_time`，优先显式字段，再兼容 `extra_data.external_sync.externalCreateTime`，最后回退 `create_time`。
   - 维护 `affected_version` 与历史 `version_key` 的兼容关系。
   - 根据状态流转、结论字段、RCA 和事件写入 `processed_at/released_at/verified_at`。
   - 保留 `resolved_at` 终态即写入的处置完成口径。
3. 新增 `TicketProcessingStatsDao` 和 `TicketProcessingStatsService`：
   - 统计新增、已响应、已处理、处理率、处置完成、关闭、未处理存量。
   - 控制器直接调用统计服务，不再通过 `TicketService` 做统计转发。
4. 外部同步 payload 写入 `submit_time`、版本治理字段和处理时间字段。
5. Excel 导入模板和导入落库新增提交时间、处理完成时间、发版/验证时间和版本字段。
6. SQL 脚本：`server/sql/20260708_ticket_submit_processed_version_columns.sql`。

## 前端实现

1. 工单列表：
   - 原 `processStatus` 文案改为“日志/AI进度”。
   - 新增“处理结论”筛选，支持已处理/未处理。
   - 新增处理时间范围筛选。
   - 新增列：处理结论、首次响应时间、处理完成时间、计划修复版本、实际修复版本、实际发版版本。
2. 新增/编辑工单：
   - “版本号”文案调整为“发生版本”。
   - 新增计划修复版本、实际修复版本、实际发版版本字段。
   - 保存时 `affectedVersion` 优先沿用发生版本。
3. 统计页：
   - 顶部指标调整为总数、新增、已处理、处理率。
   - 保留原有“整体趋势、问题性质趋势、Top模块趋势、Top细分问题趋势”曲线。
   - 新增独立“处理率与存量趋势”曲线，不替换或删除原有趋势图。
   - 历史用户的 `ticket_statistics_blocks.visibleTrendBlocks` 配置中没有 `processingTrend` 时，页面会按配置版本自动补齐一次，避免新增曲线不在页面和显示配置中出现。
   - 趋势明细保留原有新增、处置完成、关闭、净增、未关闭存量、Bug、非Bug、支持类、Top细分问题和Top模块列，并新增已响应、已处理、新增已处理、处理率、未处理存量、平均响应/处理耗时。

## 验证结果

1. 后端 ruff 针对本次改动文件已通过。
2. 前端 `npm run build:prod` 已通过。
3. `uv run python -m pytest ...` 当前失败原因是 uv 虚拟环境未安装 pytest；裸 `uv run pytest` 会命中系统旧 pytest 脚本，不代表项目 Python 版本。项目 `server/.python-version` 为 3.10，`uv run python --version` 为 3.10.19。

## 注意事项

1. 执行 SQL 前需确认目标库字段和索引不存在。
2. 历史数据回填使用保守策略：不重写已有非空时间字段，不批量修改历史 `resolved_at`。
3. `processed_at` 不由 AI 任务成功自动写入，只在人工确认写回主结论、RCA、状态流转或排查事件时写入。
