---
title: 操作日志
type: log
source_type: mixed
created: 2026-05-20
updated: 2026-07-17
---

# 操作日志

## [2026-07-17] INGEST-CODE | 工单发生版本权威字段与日志提取修复

- 触发：用户反馈编辑页保存发生版本后再次打开显示 `version`，要求统一版本字段语义，并避免日志下载后重复或错误提取版本号。
- 架构层：工单域 / 版本治理 / 日志拉取后处理 / 外部同步入库 / AI 仓库映射。
- 创建的页面：`web/public/docs/2026-07-17-ticket-version-authority-and-log-extract-fix.md`
- 更新的页面：`server/modules/ticket/util/ticket_common_util.py`、`server/modules/ticket/service/log_pull/ticket_log_post_process_service.py`、`server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/modules/ticket/service/sync/ticket_sync_payload_service.py`、`server/modules/ticket/service/sync/ticket_sync_automation_service.py`、`server/modules/ticket/service/ai/ticket_ai_analysis_service.py`、`server/modules/ticket/service/ai/ticket_light_ai_service.py`、`server/modules/ticket/service/core/ticket_processing_metric_service.py`、`server/modules/ticket/service/core/ticket_service.py`、`web/src/views/ticket/index.vue`、`server/tests/test_ticket_version_key_normalization.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`
- 变更传播链：版本号归一化工具 -> 详情返回与统计字段解析过滤无效版本 -> 编辑页保存以当前发生版本覆盖旧值 -> 同步入库/自动化/轻量 AI 统一过滤 -> 日志下载后处理先检查 `affected_version` 再提取 -> 提取成功写入 `affected_version` 并保留 `extra_data.version_key` 兼容。
- 关键结论：`affected_version` 是 bug 首发/提单版本的权威字段；`versionKey` 和 `extra_data.version_key` 不删除，但只作为历史接口、旧数据和 AI 仓库映射兜底。日志中出现的字段名 `version` 不再被当作有效版本号。

## [2026-07-17] INGEST-CODE | 工单详情弹窗组件化

- 触发：用户要求按最终方案拆分工单详情组件，不保留 `ticketDetailContext` 过渡依赖，父页删除不再使用的详情状态和函数。
- 架构层：Web 控制台 / 工单详情组件
- 创建的页面：`web/public/docs/2026-07-17-ticket-detail-dialog-component.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/components/TicketDetailWithList.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailOverviewTab.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailLogPullTab.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailCollabTab.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailCommentsTab.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailHistoryTab.vue`、`web/src/views/ticket/logPull.shared.js`、`web/src/views/ticket/hooks/useLogViewer.js`、`entities/services/ticket-domain.md`、`entities/services/web-feature-domains.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/views/ticket/index.vue` 只保留 `ticketId/open` 入口 -> `web/src/views/ticket/components/TicketDetailWithList.vue` 自行拉取详情和管理 AI/日志/归因弹窗 -> 恢复描述/AI 翻译和详情 tabs -> tabs 拆分为概览、日志拉取、协同、评论、历史 5 个内部子组件 -> `web/src/views/ticket/logPull.shared.js` 下沉日志拉取表单默认值与清洗逻辑。
- 关键结论：详情弹窗对工单列表页的契约收敛为 `ticketId/open`，详情页主体、描述和 tabs 都由详情组件内部闭环，不再依赖父页 `ticketDetailContext`。拆出的 tab 子组件若使用局部组件，必须在子组件内自行注册，例如日志拉取 tab 的 `LogPullConfigFields` 和 `LogPullNotifyConfigFields`。
- 总共涉及页面：12

## [2026-07-17] INGEST-CODE | 工单详情 tab 自闭环收口

- 触发：用户要求已拆分的工单详情 tab 不再依赖详情页上下文，并删除列表页和详情页中无用数据。
- 架构层：Web 控制台 / 工单详情 tab 组件
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/components/TicketDetailWithList.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailOverviewTab.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailLogPullTab.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailCollabTab.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailCommentsTab.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailHistoryTab.vue`、`web/public/docs/2026-07-17-ticket-detail-dialog-component.md`、`web/public/docs/update_history.md`、`wiki/entities/services/web-feature-domains.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：详情父组件传参收敛为 tab `ticketId/active` -> 概览/日志拉取/协同/评论/历史 tab 内部自行拉取数据和维护表单/弹窗/样式 -> tab 变更后通过 `changed` 通知详情父组件刷新顶部详情和列表 -> 列表页删除旧详情同步函数和详情 tab 样式残留。
- 关键结论：tab 组件不是临时模板拆分，而是各自围绕工单 ID 闭环；详情父组件只保留顶部详情、描述翻译、AI 分析/任务历史、仓库映射、商家映射和新建问题绑定等跨 tab 弹窗。

## [2026-07-16] INGEST-CODE | 工单日志选区候选词与非侵入高亮

- 触发：用户要求工单详情页日志搜索结果详情中，选中文本同时作为高亮候选词并立即高亮，取消选中时对应高亮也取消，并评估 CSS Highlight API。
- 架构层：Web 前端 / 工单日志查看器 / 日志上下文高亮。
- 创建的页面：`web/public/docs/2026-07-16-ticket-log-selection-native-highlight.md`
- 更新的页面：`web/src/views/ticket/hooks/useLogViewer.js`、`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/web-feature-domains.md`、`wiki/flows/ticket-log-record-isolated-view.md`
- 变更传播链：日志上下文浏览器选区 -> `captureLogViewerHighlight` 记录临时选区高亮词 -> `logViewerHighlightKeywords`/文本框候选词 -> 支持 CSS Highlight API 时注册 `Range` 到 `CSS.highlights`，否则回退 `<mark>` 片段渲染；`selectionchange` 折叠或移出上下文 -> `clearLogViewerSelectionHighlight` 移除本次临时高亮。
- 关键结论：非侵入高亮不改写日志文本 DOM，正常路径减少 Vue 节点拆分和选区干扰；不支持该 API 的浏览器仍按原方案只高亮当前上下文块。

## [2026-07-16] INGEST-CODE | 工单日志搜索耗时观测补充

- 触发：用户反馈工单详情日志搜索感觉较慢，要求准备接口记录压缩包位置和解压目录，搜索接口记录工具、参数、目录和耗时。
- 架构层：工单域 / 日志查看服务 / 日志搜索观测 / 日志拉取后处理。
- 创建的页面：`web/public/docs/2026-07-16-ticket-log-search-observability.md`、`web/public/docs/2026-07-16-ticket-log-post-download-processing.md`
- 更新的页面：`server/modules/ticket/service/log_pull/ticket_log_service.py`、`server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/modules/ticket/service/log_pull/ticket_log_post_process_service.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`server/modules/ticket/controller/ticket_log_pull_controller.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/src/views/ticket/syncAutomation/hooks/useSyncConfig.js`、`web/public/docs/update_history.md`
- 变更传播链：`/ticket/logs/prepare` -> `LogService.prepare` 记录 `archive_path/source_path/extract_path/elapsed_ms`；`/ticket/logs/search` -> `LogService.search_keywords/search` 记录 `tool/extract_dir/file/target_file_count/args/hit_count/elapsed_ms`；`all` 多关键字 -> `rg` 管道链流式过滤；`/ticket/log-pull/post-process-config` -> `ticket.logPull.storage.postDownload*` -> `TicketLogPostProcessService` -> 下载完成后按配置解压、版本提取、行索引。
- 关键结论：2026-07-15 的按文件 `rg` 会在文件数多时放大进程启动成本；当前改为 `maxSearchFileCount` 限制内一次性交给 `rg`，中文和 `all` 不再默认走 Python。日志下载完成后的版本提取和索引生成均建立在自动解压开关之上，关闭解压时不会执行。

## [2026-07-15] INGEST-CODE | 工单大数据量内存水位优化

- 触发：用户反馈部署后执行飞书主动拉取、日志拉取/查看和工单统计后内存水位持续升高，要求按有限改动改成分批、yield 和流式处理。
- 架构层：工单域 / 统计服务 / 日志拉取服务 / 飞书多维表格主动拉取。
- 创建的页面：`web/public/docs/2026-07-15-ticket-memory-watermark-optimization.md`
- 更新的页面：`server/modules/ticket/dao/ticket_processing_stats_dao.py`、`server/modules/ticket/service/stats/ticket_processing_stats_service.py`、`server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/modules/ticket/service/sync/ticket_sync_notify_service.py`、`server/modules/ticket/service/sync/ticket_sync_config_service.py`、`server/modules/ticket/service/sync/ticket_bitable_pull_service.py`、`web/public/docs/update_history.md`
- 变更传播链：统计接口 -> 轻量字段行和单次遍历计算；飞书主动拉取 -> records/search 分页迭代 -> 主动拉取循环逐条处理；日志实时查看 -> 归档截取 `StringIO` 顺序写入 -> 直接返回文本。
- 关键结论：本次不改变接口响应契约；RSS 不立即回落仍可能来自 Python 内存池高水位，但大对象峰值和全量 ORM/飞书记录列表已收敛。

## [2026-07-11] INGEST-CODE | 工单业务周周期快照与精确统计

- 触发：用户要求实现业务周快照新表和快照业务周精确统计。
- 架构层：工单域 / 统计服务 / 数据模型 / 定时任务 / Web 统计页。
- 创建的页面：`server/modules/ticket/dao/ticket_statistics_period_snapshot_dao.py`、`server/sql/20260711_ticket_statistics_period_snapshot.sql`、`web/public/docs/2026-07-11-ticket-business-week-period-snapshot.md`
- 更新的页面：`server/modules/ticket/entity/do/ticket_do.py`、`server/modules/ticket/service/stats/ticket_statistics_snapshot_service.py`、`server/modules/ticket/service/stats/ticket_processing_stats_service.py`、`server/modules/ticket/controller/ticket_config_controller.py`、`server/modules/ticket/util/ticket_statistics_time_util.py`、`server/module_task/scheduler_maintenance.py`、`server/tests/test_ticket_processing_metrics.py`、`web/src/views/ticket/statistics/index.vue`、`web/public/docs/2026-07-10-ticket-statistics-usage-guide.md`、`web/public/docs/2026-07-11-ticket-statistics-similarity-phase1-2.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`
- 变更传播链：`ticket_statistics_period_snapshot` -> `TicketStatisticsPeriodSnapshotDao` -> `TicketStatisticsSnapshotService.build_business_week_snapshot` -> `ticket_business_week_statistics_snapshot` -> `TicketProcessingStatsService.get_business_week_snapshot_statistics/get_business_week_snapshot_trend` -> 统计页快照业务周读取精确周期快照。
- 关键结论：自然日、自然周和自然月快照继续读取 `ticket_statistics_daily`；快照口径业务周读取周期表，不再返回 `snapshot_business_week_not_supported`。

## [2026-07-10] INGEST-CODE | 工单统计第三阶段维度快照补齐

- 触发：用户要求继续实现方案第三阶段未实现部分，并按项目、模块、问题类型分维度冻结快照。
- 架构层：工单域 / 统计服务 / 数据模型 / Web 统计页。
- 创建的页面：`server/sql/20260710_ticket_statistics_dimensional_snapshot.sql`
- 更新的页面：`server/modules/ticket/entity/do/ticket_do.py`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/dao/ticket_statistics_daily_dao.py`、`server/modules/ticket/dao/ticket_processing_stats_dao.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/modules/ticket/service/stats/ticket_statistics_snapshot_service.py`、`server/modules/ticket/service/stats/ticket_processing_stats_service.py`、`server/modules/ticket/controller/ticket_config_controller.py`、`web/src/views/ticket/statistics/index.vue`、`web/public/docs/2026-07-10-ticket-statistics-snapshot-phase3.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`
- 变更传播链：`ticket_statistics_daily.snapshot_scope` 与维度字段 -> 每日快照任务生成全局行和叶子维度行 -> 快照统计服务按筛选聚合叶子行 -> 统计页新增工单类型筛选并修正快照提示。
- 关键结论：本次默认“问题类型”为 `issue_type_id/issue_type_name`；`problem_pattern_code` 细分问题暂不冻结，仍只参与实时口径筛选。

## [2026-07-10] INGEST-CODE | 工单统计第三阶段快照口径落地

- 触发：用户要求继续根据方案文档实现第三阶段，补齐统计快照和周报稳定口径。
- 架构层：工单域 / 统计服务 / 定时任务 / Web 统计页。
- 创建的页面：`web/public/docs/2026-07-10-ticket-statistics-snapshot-phase3.md`
- 更新的页面：`server/modules/ticket/entity/do/ticket_do.py`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/dao/ticket_statistics_daily_dao.py`、`server/modules/ticket/service/stats/ticket_statistics_snapshot_service.py`、`server/modules/ticket/service/stats/ticket_processing_stats_service.py`、`server/modules/ticket/controller/ticket_config_controller.py`、`server/module_task/scheduler_maintenance.py`、`server/modules/ticket/service/sync/ticket_sync_config_service.py`、`server/modules/ticket/service/sync/ticket_sync_notification_job_service.py`、`web/src/views/ticket/statistics/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：`ticket_statistics_daily` 扩表 -> 每日快照任务 -> `TicketStatisticsSnapshotService` 冻结自然日统计 -> `TicketProcessingStatsService` 按 `statisticsMode` 切换实时/快照 -> 统计页口径切换 -> 汇总通知默认快照。
- 关键结论：当前快照先按自然日整体冻结，不做项目/模块维度拆分；快照模式下统计页提示筛选维度暂不参与快照聚合，避免误读。

## [2026-07-10] INGEST-CODE | 工单第二阶段 Issue 前端入口补齐

- 触发：用户要求继续实现第二阶段未完成部分，补齐工单真实问题实例归因层的可用入口。
- 架构层：工单域 / Web 控制台 / 问题实例归因页面入口。
- 创建的页面：`web/public/docs/2026-07-10-ticket-issue-ui-entry-completion.md`
- 更新的页面：`web/src/views/ticket/issue/index.vue`、`web/src/views/ticket/index.vue`、`web/src/router/index.js`、`web/public/docs/update_history.md`
- 变更传播链：`ticket_issue` / `ticket_relation` 后端能力 -> 独立 Issue 管理页 -> 工单列表入口 -> 工单详情内嵌归因入口保持不变。
- 关键结论：第二阶段后端能力已经具备，这次补齐的是“独立管理视图 + 统一跳转入口”，不新增 Issue 统计看板。

## [2026-07-08] INGEST-CODE | 工单统计汇总块同名行合并修复

- 触发：用户反馈工单统计汇总块中“解决方式”“关闭结果”“细分问题”存在重复展示行，例如两个“未填写”和两个“POS客户端支付”。
- 架构层：Web 工单统计页 / 汇总统计块展示规则。
- 创建的页面：`web/public/docs/2026-07-08-ticket-statistics-summary-row-dedup.md`
- 更新的页面：`server/modules/ticket/service/stats/ticket_processing_stats_service.py`、`server/tests/test_ticket_processing_metrics.py`、`web/src/views/ticket/statistics/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：`overview[*Counts]` 原始统计数组 -> 后端按空值归一和稳定 code 合并 -> 前端统计块 `block.format(row)` 生成最终展示标签 -> 前端按展示标签兜底合并 `count` -> 表格只显示一行。
- 关键结论：重复行来自同一业务含义在历史数据中以空值、占位值或 code/name 混用保存；统计口径应以后端稳定 key 汇总为主，前端合并只作为展示兜底。

## [2026-07-08] INGEST-CODE | 工单统计嵌套字段小驼峰转换修复

- 触发：用户反馈认证检查工单统计中所有趋势数据为 0，工单类型、是否真实问题、根因分类都显示未填写，但实际数据有不同值。
- 架构层：工单域 / 统计响应契约 / Web 统计页字段读取。
- 更新的页面：`server/modules/ticket/service/stats/ticket_processing_stats_service.py`、`server/tests/test_ticket_processing_metrics.py`、`web/public/docs/2026-07-08-ticket-submit-processed-stats-implementation.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：`TicketDao.get_ticket_statistics/get_statistics_trend` 返回 snake_case 嵌套字段 -> `TicketProcessingStatsService` 递归小驼峰转换 -> 前端统计页读取 `newCount/problemCount/moduleCounts/issueTypeName/isProblem/rootCauseType`。
- 关键结论：根因不是统计 SQL 聚合为 0，而是新统计服务只转换了响应最外层字段，嵌套数组字段仍是下划线命名，前端按小驼峰读取时全部落入 0 或“未填写”兜底。

## [2026-07-08] INGEST-CODE | 工单问题实例归因层第二阶段落地

- 触发：用户要求按第二阶段计划实现真实问题实例归因层，并提供前端人工确认入口。
- 架构层：工单域 / 工单核心数据模型 / Web 控制台 / 问题实例归因。
- 创建的页面：`web/public/docs/2026-07-08-ticket-issue-attribution-implementation.md`
- 更新的页面：`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`
- 变更传播链：`ticket_issue` / `ticket.issue_id` / `ticket_relation` -> `TicketIssueDao` -> `TicketIssueService` / `TicketRelationService` -> `ticket_issue_controller` API -> 工单详情相似工单人工确认入口和列表 Issue 列。
- 关键结论：`ticket.issue_id` 是主归因，`ticket_relation` 只保存补充关系；相似工单不会自动强绑定，只在用户点击“归入同一问题”后确认。

## [2026-07-08] INGEST-CODE | 工单提交时间、处理结论和版本治理第一阶段落地

- 触发：用户要求按方案文件实现第一阶段内容，并强调项目分层、不要揉大文件。
- 架构层：工单域 / 工单核心数据模型 / 处理统计 / 外部同步 / Web 控制台。
- 创建的页面：`web/public/docs/2026-07-08-ticket-submit-processed-stats-implementation.md`
- 更新的页面：`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`
- 变更传播链：`Ticket` 主表字段 -> `TicketProcessingMetricService` 写入提交/处理/发布验证时间 -> 手动创建/编辑、状态流转、事件、RCA、Excel 导入、外部同步 payload -> `TicketProcessingStatsService` 统计处理率和存量 -> 工单列表与统计页展示。
- 关键结论：`first_response_at` 继续只表示首次响应/接手，`processed_at` 才表示首次形成有效排查结论；`resolved_at` 保留终态处置完成口径；Issue 归因层仍是第二阶段。
- 2026-07-08 补充：统计页必须保留旧的整体趋势、问题性质趋势、Top模块趋势和Top细分问题趋势；处理率与未处理存量只作为新增独立趋势图，趋势明细也同时保留旧列和新增处理列。历史用户显示配置缺少 `processingTrend` 时，前端按配置版本自动补齐一次，保存后尊重用户手动勾选结果。

## [2026-07-07] QUERY | 工单处理口径、统计与相似问题治理方案

- 触发：用户要求结合当前项目情况，分析 `D:\xj\Documents\工单状态和统计相关.txt` 中需求和实现建议，并整理完整方案供后续实现。
- 检索路径：`wiki/purpose.md`、`wiki/index.md`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`、`wiki/entities/enums/ticket-enums.md`、`wiki/flows/ticket-workflow-routing.md`、需求原文、`server/modules/ticket/entity/do/ticket_do.py`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/dao/ticket_dao.py`、`web/src/views/ticket/statistics/index.vue`。
- 创建的页面：`web/public/docs/2026-07-07-ticket-status-statistics-and-issue-plan.md`
- 更新的页面：`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`
- 关键结论：不新增“已处理”主流程状态；计划以 `processed_at` 承接首次形成排查结论时间；版本治理字段从 `extra_data.version_key` 中拆出；相似/重复工单后续以 `ticket_issue + ticket.issue_id` 承接真实问题归因，`ticket_relation` 只做补充关系。
- 2026-07-08 讨论后修订：第一阶段新增 `submit_time` 作为统计主时间；`first_response_at` 保留首次响应/接手语义，不替代 `processed_at`；`resolved_at` 保留终态写入逻辑并定义为“工单处置完成时间”；Issue 归因层降为第二阶段增强，现有根因/根因分类/细分问题字段继续承担分类统计。

## [2026-07-07] INGEST-CODE | 工单 AI hybrid 日志模式强制检索原始目录

- 触发：用户反馈选择“摘要 + 完整目录”后 Agent 仍主要读取摘要，遗漏完整日志目录中的异常，怀疑与 Provider 生效和上下文长度限制有关。
- 架构层：工单域 / AI 分析 / Agent 日志目录读取 / Provider 执行上下文
- 创建的页面：`web/public/docs/2026-07-07-ticket-ai-hybrid-log-source-search.md`
- 更新的页面：`server/modules/ticket/service/ai/ticket_ai_analysis_service.py`、`client_new/services/ticket_ai_analysis_service.py`、`server/tests/test_ticket_ai_analysis_prompt.py`、`web/public/docs/update_history.md`
- 变更传播链：前端 `logAnalysisMode=hybrid` -> 服务端任务上下文 `logAnalysisMode` -> Agent 工作区 `logs_ai_digest.txt/source_logs_manifest.json/source_logs/` -> prompt 要求摘要仅作索引并必须 `rg` 检索原始目录。
- 关键结论：Provider 生效会影响实际模型和上游上下文窗口，但项目代码没有 200K 的 AI 日志目录限制；当前日志正文快照上限是 800000 字符，摘要上限是 300000 字符，`source_logs/` 原始目录仍应解压保留。hybrid 漏日志的直接风险来自指令允许模型停在摘要层，已改为必须检索原始目录。

## [2026-07-06] INGEST-CODE | 相似工单主动拉取场景与 Embedding 自定义参数

- 触发：用户反馈关闭自动刷新场景开关后，飞书多维表格主动拉取仍会向量化；同时部分 Embedding 模型不支持默认 `dimensions` 参数。
- 架构层：工单域 / 相似工单 / 自动向量刷新 / Embedding 请求参数
- 更新的页面：`server/modules/ticket/service/ai/ticket_embedding_service.py`、`server/modules/ticket/service/sync/ticket_bitable_pull_service.py`、`server/modules/ticket/service/sync/ticket_sync_post_process_service.py`、`server/tests/test_ticket_embedding_service.py`、`web/src/views/ticket/similarityConfig/index.vue`、`web/public/docs/2026-07-06-ticket-similarity-bitable-pull-embedding-params.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：相似工单配置 `sceneTriggers.bitablePull` -> 主动拉取 `sync_scene=bitable_pull` -> 延后后处理映射 `bitablePull` -> `vectorize_ticket_for_scene` 独立判断；旧配置缺少 `bitablePull` 时继承 `externalSync`；Embedding 配置 `requestParams` -> `_embed_text_openai_compatible` 合并请求体 -> `embedding.dimension` 只校验返回维度。
- 关键结论：`enabled` 是相似检索总开关，不是某个入库入口开关；多维主动拉取入库现在有独立自动向量化开关。外部 Embedding 默认不再传 `dimensions`，需要时在自定义 JSON 中显式添加。

## [2026-07-06] INGEST-CODE | 工单同步项目映射拆分前逻辑对齐

- 触发：用户要求对照备份分支 `master_params_ticket_back` 梳理入库项目映射逻辑，实际行为必须和拆分前提交 `a69c82a259f3105c90526c097255c8e1cdcbf47a` 一致。
- 架构层：工单域 / 外部同步入库 / 同步字段映射
- 创建的页面：`web/public/docs/2026-07-06-ticket-sync-project-mapping-backup-parity.md`
- 更新的页面：`server/modules/ticket/service/sync/ticket_sync_field_mapping_service.py`、`server/modules/ticket/service/sync/ticket_sync_automation_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`、`web/public/docs/update_history.md`
- 变更传播链：`TicketSyncAutomationService.detect_fields` -> `ticketVender/ticketModle` 映射优先 -> `projectCode/moduleCode` 业务码兜底 -> `TicketSyncPayloadService.build_upsert_payload` -> 工单 `project_id/module_id` 入库。

## [2026-07-05] INGEST-CODE | 相似工单严格 Provider 与 Collection 维度预览

- 触发：用户要求重新处理向量化和相似查询逻辑，不要兜底；配置 hash 就用 hash，配置 embedding 就只用 embedding，配置 qdrant 就只用 qdrant；配置页需要显示 Qdrant collection 列表和维度。
- 架构层：工单域 / 相似工单 / 严格 Provider / Qdrant 配置页
- 更新的页面：`server/modules/ticket/service/ai/ticket_embedding_service.py`、`server/modules/ticket/controller/ticket_config_controller.py`、`server/tests/test_ticket_embedding_service.py`、`web/src/api/ticket/ticket.js`、`web/src/api/ticket/config.js`、`web/src/views/ticket/similarityConfig/index.vue`、`web/public/docs/2026-06-17-ticket-similarity-qdrant-provider.md`、`web/public/docs/2026-07-05-ticket-qdrant-rebuild-400-diagnosis.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-automation-flow.md`
- 变更传播链：相似工单配置页 Provider -> `TicketEmbeddingService._normalize_provider` -> `vectorize_ticket/search_tickets` -> `local_hash` 只生成/查询数据库 `embedding_record` 本地 hash，`embedding` 只调用外部 Embedding 并查询数据库向量，`qdrant` 只调用外部 Embedding 和 Qdrant；失败不再回退。配置页刷新 collection -> `POST /ticket/similarity/qdrant/collections` -> `list_qdrant_collections` -> Qdrant `/collections` 与 `/collections/{name}` -> 返回维度并和配置维度比较。
- 关键结论：不使用 Qdrant 时，向量数据存储在数据库 `embedding_record.embedding` JSON 字段，不是本地文件。Qdrant collection 维度与配置维度不一致时页面会提示并阻止保存。
- 2026-07-05 补充：配置页改为按检索 Provider 联动展示，`local_hash` 隐藏外部接口和 Qdrant 配置，`embedding` 只显示外部 Embedding 配置，`qdrant` 才显示 Qdrant 配置；隐藏字段保留原值，手动重建 Provider 下拉只允许跟随配置或当前 Provider。

## [2026-07-05] INGEST-CODE | 工单向量重建幂等与强制重建

- 触发：用户询问本地 hash 是否适合写入 Qdrant、与真实 Embedding 相似度差异、搜索是否一定使用 Qdrant，并要求手动重建、入库和更新时已生成过的 Embedding 不要重复调用外部接口。
- 架构层：工单域 / 相似工单 / Embedding 幂等 / Qdrant 同步
- 更新的页面：`server/modules/ticket/service/ai/ticket_embedding_service.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/modules/ticket/entity/vo/ticket_vo.py`、`web/src/views/ticket/similarityConfig/index.vue`、`server/tests/test_ticket_embedding_service.py`、`web/public/docs/2026-06-17-ticket-similarity-qdrant-provider.md`、`web/public/docs/2026-07-05-ticket-qdrant-rebuild-400-diagnosis.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-automation-flow.md`
- 变更传播链：相似工单配置页“强制重建” -> `TicketEmbeddingRebuildRequestModel.force_rebuild` -> `TicketEmbeddingService.rebuild_ticket_embeddings(force_rebuild)` -> `vectorize_ticket` -> `TicketDao.get_embedding_record` -> 比较模型、版本、配置维度、向量长度和包含 `fields + text` 的 `content_hash` -> 命中时跳过外部 Embedding；若本次要求同步 Qdrant，则复用本地向量写入 Qdrant。
- 关键结论：当前严格 Provider 模式下本地 hash 不写 Qdrant；`local_hash` 只用数据库 `embedding_record`，`embedding` 只用外部 Embedding + 数据库 `embedding_record`，`qdrant` 只用外部 Embedding + Qdrant，失败不回退其他 Provider。手动重建默认幂等跳过，`forceRebuild=true` 才强制重新消耗外部 token。

## [2026-07-05] INGEST-CODE | 工单向量重建 Qdrant 400 诊断增强

- 触发：用户反馈手动重建工单 `INC00001699695` 时 Qdrant `/collections/ticket_similarity/points` 返回 400，日志只显示 `400 Client Error`，无法判断根因。
- 架构层：工单域 / 相似工单 / Qdrant Provider / 后端诊断
- 创建的页面：`web/public/docs/2026-07-05-ticket-qdrant-rebuild-400-diagnosis.md`
- 更新的页面：`server/modules/ticket/service/ai/ticket_embedding_service.py`、`server/tests/test_ticket_embedding_service.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-automation-flow.md`
- 变更传播链：`TicketEmbeddingService.rebuild_ticket_embeddings` -> 批次日志/熔断状态 -> `vectorize_ticket` -> 判断是否同步 Qdrant -> `embed_text(allow_local_fallback=False)` -> `_embed_text_openai_compatible(dimensions=配置维度)` -> `_upsert_qdrant_ticket` -> `_ensure_qdrant_collection(expected_dimension, allow_recreate=True)`；配置允许覆盖时删除并重建 collection；Qdrant 4xx/5xx -> `_raise_for_qdrant_status` -> 异常信息保留响应体。
- 关键结论：既有 `ticket_similarity` collection 维度与当前 Embedding 实际返回维度不一致会导致 400；外部 Embedding 521 时不允许回退 hash 写 Qdrant，否则会在 2560 和 1024 等维度之间反复删建。重建是一条工单一次 Embedding 请求，批量只是在服务端循环；外部异常会熔断后续请求并返回 `abortReason/skipped`。若确认旧 Qdrant 向量可丢弃，可开启 `recreateCollectionOnDimensionMismatch` 后全量重建。

## [2026-07-05] INGEST-CODE | 相似工单手动重建改用 ticketNo

- 触发：用户要求相似工单配置中的手动重建功能使用工单 `ticketNo`，并询问本地 hash 与 Embedding 的差异。
- 架构层：工单域 / 相似工单 / Web 配置页 / API 契约
- 创建的页面：`web/public/docs/2026-07-05-ticket-similarity-rebuild-ticket-no.md`
- 更新的页面：`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/modules/ticket/service/ai/ticket_embedding_service.py`、`server/modules/ticket/controller/ticket_config_controller.py`、`web/src/views/ticket/similarityConfig/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-automation-flow.md`
- 变更传播链：相似工单配置页手动输入 `ticketNosText` -> `POST /ticket/similarity/rebuild.ticketNos` -> `TicketEmbeddingService.resolve_ticket_ids_for_rebuild` -> `TicketDao.list_tickets_by_nos` -> 现有向量重建流程按系统 `ticket_id` 执行。
- 关键结论：页面不再要求用户输入内部 `ticketId`；后端保留 `ticketIds` 兼容但优先按 `ticketNos` 解析。指定工单号全部不存在时返回 0 条，不误触发全量重建。本地 hash 适合兜底和开发，真实 Embedding + Qdrant 的语义召回能力明显更强但有服务稳定性和配置成本。

## [2026-07-04] INGEST-CODE | 工单日志查看器文件范围搜索与高亮

- 触发：用户要求日志查看页换行开关放到日志详细信息块标题上，日志搜索支持先全局再按文件搜索，并评估选中文案相同内容高亮是否可实现。
- 架构层：工单域 / 日志查看 / Web 控制台
- 创建的页面：`web/public/docs/2026-07-04-ticket-log-viewer-file-scope-highlight.md`
- 更新的页面：`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`server/modules/ticket/controller/ticket_log_pull_controller.py`、`server/modules/ticket/service/log_pull/ticket_log_service.py`、`server/tests/test_ticket_log_service.py`、`web/src/views/ticket/hooks/useLogViewer.js`、`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`、`wiki/flows/ticket-log-record-isolated-view.md`、`wiki/entities/services/web-feature-domains.md`
- 变更传播链：前端全局关键字搜索结果 `file` -> 文件范围下拉/在此文件搜索 -> `/ticket/logs/search.file` -> `LogService.search` 限定单文件扫描；日志详细信息块选中文案 -> `logViewerHighlightText` -> 当前上下文行片段高亮并在翻页后复用。
- 关键结论：按文件搜索复用原搜索接口和日志相对路径校验；高亮只处理当前上下文块，不扫描整份日志，默认性能风险可控。打开查看器时必须先重置旧状态再写入当前记录，避免 `recordId` 被清空后搜索回落到工单级目录。

## [2026-07-04] INGEST-CODE | 工单日志链接与 AI 前端偏好

- 触发：用户反馈工单日志拉取列表缺少时间/路径参数，归档地址和压缩包需要像外部链接一样左键打开、右键复制；发起 AI 分析和协同/AI 的 Agent、Provider、追加提示词默认选择和手动记忆失效。
- 架构层：Web 前端 / 工单详情 / 日志拉取管理 / AI 表单偏好
- 创建的页面：`web/public/docs/2026-07-04-ticket-log-link-and-ai-preference.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/logPullRecord/index.vue`、`web/src/views/ticket/logPull.shared.js`、`web/src/views/ticket/hooks/useLogViewer.js`、`web/src/views/ticket/hooks/useTicketAiPreference.js`、`web/public/docs/update_history.md`、`wiki/entities/services/web-feature-domains.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：日志拉取记录行数据 `commandDataType/modifyTime/path/storagePath/commandResultUrl` -> 共享链接解析与参数格式化工具 -> 工单详情页日志拉取列表和独立日志拉取管理页统一展示；AI 表单配置、最近任务和用户手动选择 -> `useTicketAiPreference` -> 发起 AI 分析弹窗与协同/AI 消息表单默认值。
- 关键结论：日志拉取列表现在可直接看出本次拉取用的是时间还是路径，归档/原始包链接左键执行原下载策略、右键复制目标链接；AI 表单默认值优先使用用户手动记忆，其次才使用工单配置和最近任务。

## [2026-07-04] INGEST-CODE | 清理 TicketSyncService 已迁移常量副本

- 触发：用户要求清理 `TicketSyncService` 未使用常量。
- 架构层：工单域 / 同步服务 / 常量归属 / 主编排瘦身
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/sync/ticket_sync_service.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：`TicketSyncService` 中配置默认值、外部字段模型、统计枚举、Celery 分发模式、消费者交付、群推送锁和 AI 任务状态常量副本 -> 对应子服务 `TicketSyncConfigService`、`TicketSyncPayloadService`、`TicketSyncPostProcessService`、`TicketSyncGroupPushService`、`TicketSyncDeliveryService` 已维护权威常量 -> 主同步服务仅保留当前入库延后发布需要的 `PUBLISH_STATUS_PROCESSING_AI`。
- 关键结论：`TicketSyncService` 不再携带已迁移职责的默认配置和状态常量副本；后续新增常量应放入对应职责子服务，不应为了调用方便复制到主编排服务。

## [2026-07-04] INGEST-CODE | 拆分 TicketSyncService 外部请求归一化边界

- 触发：用户要求继续拆分；批量重归类已迁移后，本次继续迁移剩余的外部请求归一化边界。
- 架构层：工单域 / 外部同步接口 / 请求体读取 / 字段归一化 / 同步入库前置契约
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/sync/ticket_external_sync_request_service.py`、`server/modules/ticket/service/sync/ticket_sync_service.py`、`server/modules/ticket/controller/ticket_sync_controller.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/2026-07-04-project-implementation-boundary-rules.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`TicketSyncService.load_external_sync_payload/normalize_external_sync_payload` -> `TicketExternalSyncRequestService.load_external_sync_payload/normalize_external_sync_payload` -> `/ticket/sync/external` 控制器直接调用新服务并继续使用 `TicketExternalSyncUpsertModel` 校验。
- 关键结论：JSON/表单请求读取、外部字段必填校验、人员字段拆分、`extraData.external_field_mapping` 和 `raw_payload` 构造不再属于 `TicketSyncService`；后续调整外部请求契约应优先修改 `TicketExternalSyncRequestService`。

## [2026-07-04] INGEST-CODE | 拆分 TicketSyncService 批量重归类边界

- 触发：用户建议继续拆批量重归类或外部请求归一化，并优先选择不影响入库事务主路径的部分；本次选择手动批量重归类边界。
- 架构层：工单域 / 同步服务 / 批量重归类 / 未归类统计 / 手动管理接口
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/sync/ticket_batch_reclassification_service.py`、`server/modules/ticket/service/sync/ticket_sync_service.py`、`server/modules/ticket/controller/ticket_sync_controller.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/2026-07-04-project-implementation-boundary-rules.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`TicketSyncService._run_auto_ticket_category_classification/batch_reclassify_ticket_categories_services/get_uncategorized_ticket_statistics_services` -> `TicketBatchReclassificationService.run_auto_ticket_category_classification/batch_reclassify_ticket_categories_services/get_uncategorized_ticket_statistics_services` -> `/ticket/sync/auto-category/reclassify` 与 `/ticket/sync/auto-category/stats` 控制器直接调用新服务。
- 关键结论：批量重归类、正则批量分类和未归类统计不再属于外部同步入库主服务；后续手动重归类规则应优先修改 `TicketBatchReclassificationService`，外部入库主路径仍留在 `TicketSyncService`。

## [2026-07-04] INGEST-CODE | 拆分 TicketSyncService 同步交付边界

- 触发：用户要求继续拆分工单同步服务，当前优先迁移边界清晰的 pending/ack 交付状态能力。
- 架构层：工单域 / 外部同步 / 内网 pending 拉取 / 同步 ack 回执 / 同步元数据摘要
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/sync/ticket_sync_delivery_service.py`、`server/modules/ticket/service/sync/ticket_sync_service.py`、`server/modules/ticket/controller/ticket_sync_controller.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/2026-07-04-project-implementation-boundary-rules.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`TicketSyncService.extract_sync_summary/_update_consumer_state/pull_pending_tickets/ack_sync_delivery` -> `TicketSyncDeliveryService.extract_sync_summary/update_consumer_state/pull_pending_tickets/ack_sync_delivery` -> `/ticket/sync/pending` 与 `/ticket/sync/ack` 控制器直接调用新服务；主同步入库链路仅通过新服务读取 `syncSummary`。
- 关键结论：消费者交付状态、`delivered_revision` 推进、pending 租约和 `syncSummary` 构造不再属于 `TicketSyncService`；后续修改内网同步交付规则应优先改 `TicketSyncDeliveryService`。

## [2026-07-04] INGEST-CODE | 工单服务按依赖关系组织为子包

- 触发：用户要求将已经拆出的工单服务按照依赖关系组织成独立模块或子包，不要全部放在同一个 service 包中，后续再继续细拆。
- 架构层：工单域 / 服务包结构 / 同步服务 / AI 服务 / 日志拉取 / 协作 / 通知 / 统计
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/sync/*`、`server/modules/ticket/service/ai/*`、`server/modules/ticket/service/log_pull/*`、`server/modules/ticket/service/core/*`、`server/modules/ticket/service/collaboration/*`、`server/modules/ticket/service/notification/*`、`server/modules/ticket/service/stats/*`、`server/modules/ticket/controller/*`、`server/module_task/celery_tasks.py`、`server/module_task/scheduler_maintenance.py`、`server/server.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`server/tests/test_ticket_topic_stats_service.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/2026-07-04-project-implementation-boundary-rules.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：旧 `modules.ticket.service.ticket_*` 顶层服务文件 -> 按职责移动到 `service/sync`、`service/ai`、`service/log_pull`、`service/core`、`service/collaboration`、`service/notification`、`service/stats` -> 控制器、定时任务、应用启动、测试和运行时 `patch()` 字符串同步改为新路径 -> 删除旧顶层服务入口且不保留 re-export shim。
- 关键结论：本次只做包结构收敛，不继续扩大业务拆分；工单同步主服务仍在 `service/sync` 内，后续可继续拆分该子包内部职责。新增调用方必须直接引用新子包路径，禁止恢复 `modules.ticket.service.ticket_*` 旧入口。

## [2026-07-04] INGEST-CODE | 拆分 TicketSyncService 延后后处理与同步自动化

- 触发：用户确认继续拆分，要求继续处理 `TicketSyncService` 的延后后处理边界。
- 架构层：工单域 / 外部同步入库 / 延后后处理 / 字段识别 / 同步自动化 / Celery 后台任务
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/ticket_sync_post_process_service.py`、`server/modules/ticket/service/ticket_sync_automation_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/controller/ticket_sync_controller.py`、`server/modules/ticket/service/ticket_bitable_pull_service.py`、`server/module_task/celery_tasks.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/2026-07-04-project-implementation-boundary-rules.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`TicketSyncService.dispatch_deferred_sync_post_process_task/run_deferred_sync_post_process/_execute_deferred_sync_post_process` -> `TicketSyncPostProcessService` -> 控制器、主动拉取和 Celery 任务直接调用新服务；`TicketSyncService._detect_fields/run_sync_automation/_mark_automation_step/_collect_text/_extract_pattern` -> `TicketSyncAutomationService` -> 主入库链路与延后后处理共用同一字段识别和自动化执行服务。
- 关键结论：延后后处理不再挂在 `TicketSyncService` 上；Celery 分发、本地后台回退、系统用户 payload 归一化、AI 提取/翻译/分类、向量刷新和发布状态收敛由 `TicketSyncPostProcessService` 编排。字段识别、相似工单、自动拉日志和自动 AI 提交由 `TicketSyncAutomationService` 承接，避免后处理服务反向依赖主同步服务。

## [2026-07-04] INGEST-CODE | 拆分 TicketSyncService 外部入库 payload 构造

- 触发：用户要求继续拆 `TicketSyncService` 的延后后处理或外部入库 payload 构造；本次优先迁移边界更清晰的外部入库 payload 构造。
- 架构层：工单域 / 外部同步入库 / 同步元数据 / 自动拉日志参数提示
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/ticket_sync_payload_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/2026-07-04-project-implementation-boundary-rules.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`TicketSyncService._build_upsert_payload/_build_meta/_attach_meta/_resolve_external_create_time/_merge_external_text_fields/_resolve_auto_log_pull_modify_time` -> `TicketSyncPayloadService.build_upsert_payload/build_meta/attach_meta/resolve_external_create_time/merge_external_text_fields/resolve_auto_log_pull_modify_time` -> 外部同步入库、延后后处理、pending 拉取、ack 和自动化链路直接调用新服务公开方法。
- 关键结论：`TicketSyncService` 不再负责拼装 Ticket 持久化 payload 和同步 meta；项目/模块兜底、来源快照、外部创建时间、revision、`log_pull_hints` 与自动拉日志日期解析集中在 `TicketSyncPayloadService`，且没有保留旧私有入口转发 shim。

## [2026-07-04] INGEST-CODE | 清理 TicketSyncService 兼容门面并评估继续拆包

- 触发：用户指出 `TicketSyncService` 历史兼容门面仍属于为了兼容拆分而存在的内容，也需要清理；同时要求分析当前拆分是否合理、是否可以继续拆成独立包或子包。
- 架构层：工单域 / 同步服务 / 配置服务 / 评论同步 / AI 分类统计 / 群推送
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：`TicketSyncService` 兼容门面 -> 调用方直接依赖 `TicketSyncConfigService`、`TicketSyncCommentService`、`TicketSyncGroupPushService`、`TicketAutoClassificationService` -> 删除旧门面方法和源码目录 `.bak/.bak2` 备份文件 -> 文档记录后续子包拆分边界。
- 关键结论：`TicketSyncService` 不再保留仅转发到子服务的拆分兼容入口；当前拆分方向正确但同步主服务仍偏大，后续应按 `sync/config/comment/notification/ai/log_pull/core` 子包边界渐进迁移，迁移时不要留下只 re-export 或只转发的旧文件。

## [2026-07-04] INGEST-CODE | 工单拆分依赖方向重构

- 触发：用户指出函数内导入和延迟代理不是合理优雅的解法，要求把相关能力抽成子模块，不要相互依赖，并与拆分前逻辑保持一致。
- 架构层：工单域 / 服务拆分 / 评论同步 / AI 分类统计 / 公共工具
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/service/ticket_message_sync_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_sync_comment_service.py`、`server/modules/ticket/service/ticket_sync_group_push_service.py`、`server/modules/ticket/service/ticket_auto_classification_service.py`、`server/modules/ticket/service/ticket_comment_core_service.py`、`server/modules/ticket/util/ticket_common_util.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：`TicketService` 本地导入同步服务 / `TicketMessageSyncService` 延迟代理主服务 / 同步评论反向依赖主服务 -> 下沉为 `TicketAutoClassificationService`、`TicketCommentCoreService`、`ticket_common_util` -> 高层服务不再通过函数内导入或代理互相调用。
- 关键结论：保留拆分结构时，共享能力必须处在更低层；不能继续把旧大服务作为跨模块共享实现。

## [2026-07-04] INGEST-CODE | 工单拆分循环引用与功能兼容修复

- 触发：用户反馈工单系统大文件拆分重构后出现功能问题和回环引用，要求参考 `master_params_ticket_new` 分支，在保留拆分的前提下恢复功能。
- 架构层：工单域 / 拆分控制器 / 同步服务兼容门面 / 消息同步 / 飞书多维表格主动拉取
- 创建的页面：`web/public/docs/2026-07-04-ticket-split-compat-fix.md`
- 更新的页面：`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/service/ticket_message_sync_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_sync_config_service.py`、`server/modules/ticket/service/ticket_sync_field_mapping_service.py`、`server/modules/ticket/controller/ticket_crud_controller.py`、`server/modules/ticket/controller/ticket_config_controller.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：拆分后顶层互相 import -> 启动期循环引用 -> 改为延迟导入/代理；拆分后旧私有入口缺失 -> 测试与历史调用失败 -> 曾短期由 `TicketSyncService` 兼容门面委托子服务；控制器拆分遗漏 RCA 路由 -> `PUT /ticket/{ticket_id:int}/rca` 补回。
- 关键结论：保留拆分结构时，主同步服务曾短期承接历史调用；后续已清理兼容门面，新增代码应直接调用拆出的 `TicketSyncConfigService`、`TicketSyncCommentService`、`TicketSyncGroupPushService`、`TicketAutoClassificationService`，且不要在服务模块顶层形成反向依赖。

## [2026-07-02] INGEST-CODE | 修复工单列表多选查询类型导致查不到数据和报错

- 触发：用户反馈多选单个选项正常，选多个就查不到数据，人员多选直接报 Pydantic 验证错误 `Input should be a valid string` / `unable to parse string as an integer`，input 为 `['3,2']`。
- 架构层：Web 控制台 / 工单列表 / VO 查询模型 / DAO 归一化
- 更新的页面：`server/modules/ticket/entity/vo/ticket_vo.py`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：`TicketQueryModel` / `TicketStatisticsQueryModel` 多选字段类型 `str | list[X] | None` → `str | None`；FastAPI `Query()` 检测到类型含 `list[...]` 会自动包装标量值 → Pydantic 收到 `["3,2"]` 而非 `"3,2"` → DAO 的 `_normalize_*_list` 判断已是 list 不拆分 → `.in_(["open,closed"])` 查不到数据 / `.in_([int("3,2")])` 报错。
- 关键结论：DAO 的三类归一化函数（`_normalize_text_list` / `_normalize_int_list` / `_normalize_bool_list`）已支持逗号分隔字符串拆分，VO 层只需声明 `str | None` 接收逗号分隔字符串即可，不需要联合 `list[...]` 类型。
- 总共涉及页面：2

## [2026-07-02] INGEST-CODE | 工单列表多选筛选与索引模型同步
- 触发：用户要求工单列表页面各种下拉筛选项改为多选，并结合数据库结构和索引评估性能；数据库索引已手动创建，要求同步落到数据库模型。
- 架构层：Web 控制台 / 工单列表 / Ticket 查询 DAO / Ticket 数据模型
- 创建的页面：`web/public/docs/2026-07-02-ticket-list-multi-filter.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/components/UserSelect.vue`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/modules/ticket/entity/do/ticket_do.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：列表多选控件 -> 逗号分隔查询参数 -> `TicketQueryModel` 多值字段 -> DAO 归一化 -> `IN` / OR 过滤 -> `Ticket.__table_args__` 索引声明。
- 关键结论：多选使用单次分页查询，不拆分多次请求；主要性能风险仍在关键字模糊查询、JSON 提交时间表达式和最新状态子查询。后续如数据量继续增长，应考虑将提交时间落为实体列并建立 `(del_flag, submit_time, ticket_id)` 索引。
- 总共涉及页面：8

## [2026-07-02] INGEST-CODE | 工单同步项目模块变更覆盖修复
- 触发：用户反馈工单系统中外部推送、内部拉取、多维表格自动拉取入库或更新时，外部项目变化会导致映射项目和商家变化，但内部数据没有同步更新；要求外部给的数据任何变化都要同步到内部数据。
- 架构层：工单域 / 外部同步 / 飞书多维表格主动拉取 / 内网拉取
- 创建的页面：`web/public/docs/2026-07-02-ticket-sync-project-module-overwrite.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：外部字段 `ticketVender/projectName/merchantName/ticketModle/moduleName` -> `_detect_fields` -> `_build_upsert_payload` -> `ticket.project_id/merchant_name/module_id/module_name` 与 `extra_data.log_pull_hints.vendorId`。
- 总共涉及页面：5

## [2026-07-01] INGEST-CODE | 修正工单AI分类提示词优先级：DB模板优先于旧版内联提示词
- 触发：生产环境手动强制重新归类始终使用旧提示词，DB 模板表 `SysAiPromptTemplate` 中的新版提示词不生效。
- 架构层：工单域 / 轻量 AI 分类统计 / 提示词解析
- 创建的页面：无
- 更新的页面：`server/modules/ticket/service/ticket_light_ai_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`wiki/entities/services/ticket-domain.md`、`wiki/log.md`
- 创建的双向链接：0 对（本次仅更新已有页面内容）
- 变更传播链：`classify_ticket_statistics` 提示词优先级（override > DB模板 > 默认）→ 改为（DB模板 > override兜底 > 默认）→ 生产环境旧 `promptContent` 不再覆盖新版模板；`_merge_legacy_ai_classification_prompt_content` 保存时改为检查字段是否显式提交，前端提交空字符串时不再强制恢复旧值。
- 关键结论：根因不是缓存，而是同步配置 JSON 中残留的旧版 `promptContent` 优先级高于 DB 模板表；修正后 DB 模板始终优先，旧版仅作兜底。
- 总共涉及页面：4

## [2026-07-01] INGEST-CODE | 工单统计页趋势明细滚动截断修复
- 触发：用户反馈工单统计页只能滚动到趋势图，趋势明细表虽然存在但无法继续滚动显示。
- 架构层：Web 控制台 / 工单统计页 / 页面布局滚动容器
- 创建的页面：无
- 更新的页面：`web/src/views/ticket/statistics/index.vue`、`web/public/docs/update_history.md`、`wiki/log.md`
- 变更传播链：`AppMain` 滚动容器 + 统计页根节点继承全局 `app-container flex: 1` -> 页面内容被压缩为一屏高度 -> 趋势明细表不可达；本次改为统计页局部按内容自然撑高。
- 关键结论：问题是页面布局样式冲突，不是趋势接口或表格数据异常；统计页作为长内容页面不应继续继承全局 `flex: 1` 高度占位。

## [2026-07-01] INGEST-CODE | 工单统计时间口径改为提交时间
- 触发：用户确认工单统计应关注用户提交时间，外部同步工单的提交时间可能早于本地入库时间。
- 架构层：Ticket 统计 DAO / 统计服务接口 / Web 统计页
- 创建的页面：`web/public/docs/2026-07-01-ticket-statistics-submit-time.md`
- 更新的页面：`server/modules/ticket/dao/ticket_dao.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/controller/ticket_controller.py`、`web/src/views/ticket/statistics/index.vue`、`web/public/docs/update_history.md`、`wiki/log.md`
- 变更传播链：统计概览时间过滤和趋势新增/存量分桶统一使用工单提交时间，优先 `extra_data.external_sync.externalCreateTime`，其次 `extra_data.external_sync.source.externalCreateTime`，最后回退 `ticket.create_time`；关闭/解决趋势仍使用 `closed_at`、`resolved_at`。
- 关键结论：当前统计页原口径确实使用本地 `Ticket.create_time`；本次改为用户提交时间后，外部同步历史工单会归属到真实提交日期。

## [2026-07-01] INGEST-CODE | 工单细分问题类型与趋势统计
- 触发：用户希望固定枚举化“内存泄露”“280开头券为纸质券规则说明”等细分原因，并按时间趋势展示支持类、Bug、非 Bug、模块和具体问题变化。
- 架构层：工单域 / 分类统计 / 轻量 AI 自动分类 / Web 统计页
- 创建的页面：`web/public/docs/2026-07-01-ticket-problem-pattern-trend-statistics.md`、`server/sql/20260701_ticket_problem_pattern_columns.sql`
- 更新的页面：`server/modules/ticket/entity/do/ticket_do.py`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_light_ai_service.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/config/get_db.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/index.vue`、`web/src/views/ticket/statistics/index.vue`、`web/src/views/ticket/syncAutomation/index.vue`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`、`wiki/entities/enums/ticket-enums.md`
- 变更传播链：`ticket.sync.automation.statClassification.problemPatterns` -> AI 分类候选枚举 -> `ticket.problem_pattern_*` 主表字段 -> 工单列表/编辑/状态流转 -> 汇总统计与趋势统计。
- 关键结论：细分原因不再使用自由标签作为主统计口径；AI 只允许从启用的固定 `problemPatterns` 候选中选择。人工确认的细分问题不被后续 AI 覆盖。趋势接口按事件时间实时计算当前分类和周期末未关闭存量，正式周报如需历史不变更，应后续增加统计快照。

## [2026-06-30] INGEST-CODE | 后台任务与定时任务日志 tid 补齐
- 触发：用户反馈 HTTP 请求已有日志 tid，但定时任务触发执行、工单同步延后后台过程仍显示 `[-]`，无法串联一次执行。
- 架构层：日志上下文 / Celery 调度 / 工单同步自动化
- 创建的页面：`web/public/docs/2026-06-30-background-task-trace-id.md`
- 更新的页面：`server/context/request_context.py`、`server/middlewares/cors_middleware.py`、`server/module_task/celery_tasks.py`、`server/module_task/celery_job_service.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/service/ticket_sync_service.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：HTTP `X-Request-Id` / Celery Worker 自动生成 `job-xxxxxxxx` -> `context.request_context` -> loguru patcher -> 定时任务、工单延后后处理、本地后台任务日志统一输出 tid。
- 关键结论：非 HTTP 入口必须显式设置 contextvars；定时任务在 Worker 执行时生成 tid，避免 Beat 同步时生成后被周期复用。工单外部同步延后任务投递 Celery 或回退本地后台时都传递当前 tid，发布后需重启 Celery Worker 以加载新任务签名。

## [2026-06-28] INGEST-CODE | 帮助中心文档自动索引
- 触发：用户反馈 `web/src/views/about/about.vue` 只能查看手写菜单中的少量帮助文档，后续自动增加的业务说明和配置说明无法方便查看。
- 架构层：Web 控制台 / 帮助文档 / 前端构建插件
- 创建的页面：`web/public/docs/2026-06-28-help-docs-auto-index.md`
- 更新的页面：`web/src/views/about/about.vue`、`web/vite/plugins/docs-index.js`、`web/vite/plugins/index.js`、`web/public/docs/update_history.md`、`wiki/entities/components/frontend-bootstrap.md`、`wiki/entities/services/web-feature-domains.md`
- 变更传播链：`web/public/docs/*.md` -> Vite 启动/构建扫描 -> `docs-index.json` -> 帮助中心搜索与分类菜单 -> Markdown 渲染组件展示。
- 关键结论：浏览器不能直接枚举 `public/docs` 目录，因此自动发现必须放在构建期或后端接口；本次选择前端 Vite 插件，避免增加后端接口。后续新增 Markdown 文档只需放入 `web/public/docs`，重新启动开发服务或执行生产构建后即可在帮助中心查看。

## [2026-06-27] INGEST-CODE | 工单排查过程消息同步用户名解析
- 触发：用户反馈最近实现的工单排查过程消息同步中，飞书会话跟帖消息同步到当前系统和飞书多维表格时，用户记录成飞书内部 ID，希望通过飞书接口查询用户名。
- 架构层：工单域 / 飞书话题评论入站 / 工单评论 / 多维表格排查过程
- 创建的页面：`web/public/docs/2026-06-27-ticket-message-sync-user-name.md`
- 更新的页面：`server/modules/ticket/service/ticket_message_sync_service.py`、`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-06-26-ticket-message-sync.md`、`web/public/docs/2026-06-27-ticket-message-sync-user-name.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：飞书消息事件 `sender.open_id` -> 飞书通讯录用户详情查询 -> `sender_display_name` -> `ticket_comment.user_name` 与多维表格 `stepReason` 追加 `{user}`。
- 关键结论：评论同步不是工单主体同步；入站跟帖消息需要在落库和写回多维前统一解析发送人展示名。凭证优先使用 `feishuAuth`，群推送和多维配置只作为兜底；查询失败不阻断同步，只回退事件自带名称或 ID。飞书正文 `@_user_1` 必须结合 `mentions` 解析，系统显示 `@用户名`，附件保留人员 ID；多维 Text 富文本片段中的 `mention_user_id` 也要带入评论附件，才能在系统、飞书群和多维表格之间恢复真实 @ 样式。

## [2026-06-26] INGEST-CODE | 多维表格主动拉取富文本换行保留
- 触发：用户反馈主动拉取多维表格数据时，换行符被处理成 `{"text": "\n", "type": "text"}` 或空文本片段，导致内容格式丢失、描述挤在一起、排查过程评论分割不正确。
- 架构层：工单域 / 飞书多维表格主动拉取 / 字段映射 / 同步评论
- 创建的页面：`web/public/docs/2026-06-26-ticket-bitable-pull-rich-text-newline.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：飞书富文本片段数组 -> `_normalize_bitable_record_scalar` 富文本识别 -> 描述/排查过程保留真实换行 -> `parse_step_reason_segments` 按日期行拆分评论。
- 关键结论：富文本片段数组必须按片段顺序拼接，换行片段保留为真实 `\n`，空文本片段不落为 JSON 文本；普通多选和人员数组继续走原分隔符拼接逻辑。

## [2026-06-25] INGEST-CODE | 日志拉取下载链接复制
- 触发：用户反馈工单详情页日志拉取列表“下载原始包”和日志拉取管理页“下载日志”无法复制原始日志下载链接，需要能粘贴到邮件。
- 架构层：工单域 / 日志拉取 / Web 控制台 / 下载链接
- 创建的页面：`web/public/docs/2026-06-25-ticket-log-pull-copy-download-link.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/logPullRecord/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：日志拉取记录 `commandResultUrl/storagePath` -> 前端下载策略解析 -> “复制链接”入口 -> 邮件或 IM 粘贴。
- 关键结论：原始压缩包优先复制外部 `commandResultUrl`；管理页按“下载日志”实际策略复制 HTTP 归档、原始地址或系统下载接口。本地/FTP 归档复制的是鉴权接口地址，访问者需要系统登录态。

## [2026-06-25] INGEST-CODE | 多维表格主动拉取群消息人员解析与日志
- 触发：用户反馈 `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync` 同步后推送消息有概率获取不到人员信息，并要求发送消息日志记录消息内容。
- 架构层：工单域 / 飞书多维表格主动拉取 / 群消息通知 / 飞书人员 @ 解析
- 创建的页面：`web/public/docs/2026-06-25-ticket-bitable-pull-mention-log-fix.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`
- 变更传播链：`bitablePull.fieldMappings` 人员字段 -> `_build_bitable_pull_field_mapping_from_record` 提取姓名/邮箱 -> `extraData.external_field_mapping` -> `_resolve_ticket_person_email` -> 飞书邮箱查 `open_id` -> 群消息渲染与发送日志。
- 关键结论：人员信息应优先来自拉取到的数据中的人员字段邮箱；本地系统用户只作为姓名兜底。若飞书人员字段没有邮箱且本地也无用户邮箱，则无法解析 `open_id`，但现在日志会记录最终正文和解析明细。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取必填字段模型校验
- 触发：用户确认主动拉取多维表格数据是否按“外部工单字段模型”做必填字段校验，并要求字段不全时不要入库或发群消息。
- 架构层：工单域 / 飞书多维表格主动拉取 / 外部字段模型 / 群消息后处理
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-pull-required-field-model.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`externalFieldModel.fields[].required` -> `run_bitable_pull_services` 必填字段推导 -> `_build_bitable_pull_sync_object` 记录级校验 -> 失败记录不调用 `sync_external_ticket` / `dispatch_deferred_sync_post_process_task`。
- 关键结论：主动拉取现在直接以外部工单字段模型为必填校验口径；字段不全只计入 `failedCount` 和 warning 日志，不入库、不触发自动群消息。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取优先级与人员字段兜底
- 触发：用户反馈多维表格主动拉取中对方优先级和内部优先级反了，且部分内部负责人、当前处理人为空；要求内部优先级无值时使用外部优先级，不影响外部推送逻辑。
- 架构层：工单域 / 飞书多维表格主动拉取 / 外部同步入库字段映射
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-pull-priority-person-fallback.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`bitablePull.fieldMappings` -> `_build_bitable_pull_sync_object` 主动拉取专用归一化 -> `TicketExternalSyncUpsertModel` 顶层字段与 `extraData.external_field_mapping` -> `_detect_fields/_build_upsert_payload` 入库。
- 关键结论：问题位置不在外部推送 controller，而在主动拉取绕过 controller 归一化后直接构造同步模型；本次只补主动拉取转换层，外部推送逻辑不变。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取强制同步与字段保留
- 触发：用户要求主动拉取多维表格数据支持强制同步，并反馈入库项目、模块、内部负责人为空，执行完成后未翻译。
- 架构层：工单域 / 飞书多维表格主动拉取 / 外部同步入库 / 翻译自动化
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-pull-force-sync-field-translate.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/module_task/scheduler_maintenance.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`forceSync/force_sync` -> 主动拉取运行配置 -> 绕过 `snapshotHash` 跳过 -> 重新入库与延后后处理；字段映射 -> `extraData.external_field_mapping` + 顶层 `projectName/moduleName/internalOwnerName` -> 项目/模块/人员识别；`automation.autoTranslate` -> 外部同步翻译决策 -> 主链路与延后后处理一致执行。
- 关键结论：强制同步只绕过去重，不扩大飞书查询范围；历史数据重拉仍需配合 `createdAfter/filterFormula/viewId`。主动拉取来源字段为空时不会凭空补出项目、模块或负责人。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取 Celery 用户上下文修复
- 触发：用户反馈多维表格主动拉取任务入库后，延后后处理 Celery 报 `CurrentUserModel.permissions/roles Field required`，随后记录转换又提示缺少 `ticketModle`。
- 架构层：工单域 / 飞书多维表格主动拉取 / Celery 延后后处理 / 用户上下文
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-pull-celery-user-context.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`run_bitable_pull_services` 定时任务系统用户 -> 完整 `CurrentUserModel` payload -> Celery `run_deferred_sync_post_process` -> 自动 AI、自动化识别、相似工单向量化、群推送等延后动作继续执行；字段映射目标别名 -> `ticketModle` 规范字段 -> 必填校验。
- 关键结论：系统用户 payload 必须包含 `permissions=[]`、`roles=[]`，且用户字段要使用 Pydantic alias `userId/userName/nickName`；历史只包含 `user_id/user_name/nick_name` 的队列任务在入口处转换兼容。`moduleName/module_name/ticketModel/ticket_model` 目标字段会归一为 `ticketModle`，但来源字段为空仍会跳过记录。

## [2026-06-23] INGEST-CODE | 日志拉取参数示例与日期预填
- 触发：用户要求日志拉取弹窗支持从参数示例下拉填入当前参数，并在工单提取门店、POS 编号时同步提取日期预填到 modifyTime。
- 架构层：工单域 / 日志拉取 / 参数配置 / 工单同步 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-23-ticket-log-pull-parameter-examples.md`
- 更新的页面：`server/modules/ticket/dao/ticket_log_pull_dao.py`、`server/modules/ticket/service/ticket_log_pull_service.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`web/src/components/ticket/LogPullConfigFields.vue`、`web/src/views/ticket/index.vue`、`web/src/views/ticket/logPullRecord/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：`ticket.logPull.parameterExamples` -> `/ticket/log-pull/vendor-store-options.parameterExamples` -> `LogPullConfigFields` 参数示例下拉 -> 当前参数写入 `modifyTime/path`；`extra_data.log_pull_hints.modifyTime` -> 添加日志拉取弹窗预填。
- 关键结论：参数示例配置为 `[{name,value}]` 列表；日志类型填入日期参数，数据库类型填入路径参数，工单日期只在存在有效值时覆盖预填。

## [2026-06-23] INGEST-CODE | 工单日志拉取记录独立查看
- 触发：用户反馈同一工单有多条日志拉取记录时，点击某条记录查看日志会显示之前查看过的记录；同时要求明确日志拉取成功后的下载/解压行为，以及 AI 分析使用哪条日志记录。
- 架构层：工单域 / 日志拉取 / 日志查看 / AI 分析任务提交
- 创建的页面：`web/public/docs/2026-06-23-ticket-log-record-isolated-view.md`、`wiki/flows/ticket-log-record-isolated-view.md`
- 更新的页面：`server/modules/ticket/service/ticket_log_service.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：日志拉取记录行 -> `recordId` 传入日志准备 -> `data/logs/ticket_{ticketId}/record_{recordId}` 独立目录 -> 搜索/上下文/异常摘要继续携带 `recordId`；从记录查看器发起 AI 分析 -> 请求携带 `logPullRecordId`
- 关键结论：日志拉取成功会下载压缩包并按记录归档；有时间范围时截取正文入库，无时间范围时只归档整包。AI 分析请求未指定记录时取工单最新日志记录，版本号缺失时再用最近成功记录兜底。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取字段预览元数据化
- 触发：用户反馈飞书多维表格主动拉取中“读取表格字段”失败，日志显示 `records=0`；昨天可读，当前因运行时默认时间窗口/过滤条件下无记录导致样例记录字段推断为空。
- 架构层：工单域 / 飞书多维表格集成 / 同步自动化配置
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-field-preview-metadata.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`fields-preview` -> `TicketSyncNotifyService.query_bitable_fields` -> 飞书字段元数据接口；元数据失败 -> 清空 `filterFormula/createdAfter` 后样例记录兜底；主动拉取定时任务过滤逻辑不变。

## [2026-06-23] INGEST-CODE | 工单多维表格配置保存态与运行态拆分
- 触发：用户反馈填写“多维表格公共配置”后，“飞书多维表格主动拉取”的对应配置项也会被自动填上，要求多维主动拉取有独立配置时用独立配置，没有才用表格公共配置，并梳理外部推送、内部拉取、主动拉取、手动新增/编辑的配置边界和翻译配置关系。
- 架构层：工单域 / 同步自动化配置 / 飞书多维表格集成 / 翻译自动化
- 创建的页面：`web/public/docs/2026-06-23-ticket-bitable-config-scope.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-06-23-ticket-bitable-config-scope.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`ticket.sync.automation.bitableCommon` -> 运行时多维查询配置解析 -> 外部推送邮箱补齐 / 飞书多维表格主动拉取 / 按人催办 / 汇总统计；页面回显不再被公共配置污染。
- 追加：翻译配置边界已写入文档；外部推送、内部拉取、主动拉取、手动新增/编辑分别有自己的场景开关，但共用 AI 配置中心的翻译总开关、Provider 和 Prompt。
- 风险：历史库中已经被旧逻辑写入独立配置段的公共值不会自动清理，避免误删用户真实独立配置；需在页面手动清空一次后保存。

## [2026-06-23] INGEST-CODE | 工单 AI Agent 异常反馈修复
- 触发：用户反馈发起工单 AI 分析时 Agent 未连接或连接异常，服务端已有报错但 Web 页面只显示 `{}` 或没有真实失败原因。
- 架构层：工单域 / AI 分析任务 / Agent 连接校验 / Web 错误提示
- 创建的页面：`web/public/docs/2026-06-23-ticket-ai-agent-error-feedback.md`
- 更新的页面：`server/modules/ticket/service/ticket_ai_analysis_service.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/index.vue`、`web/src/utils/request.js`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-automation-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：AI 分析提交 -> 服务端 Agent 在线校验 -> 前端响应错误归一化 -> 提交/重试短轮询任务终态 -> 失败原因弹窗展示
- 验证：`uv run ruff check modules/ticket/service/ticket_ai_analysis_service.py`、`npm run build:prod` 均通过；前端构建仍有既有 `config.js`、`eval` 和 chunk 体积警告。
- 总共涉及页面：8

## [2026-06-22] INGEST-CODE | 工单日志查看器交互与编码兼容优化
- 触发：用户要求工单日志搜索结果和上下文窗口支持全屏/最小化，修复上下文翻页重复、搜索结果数量受限、中文乱码和上下文滚动查看问题。
- 架构层：工单域 / 日志查看 / Web 控制台 / 日志服务
- 创建的页面：`web/public/docs/2026-06-22-ticket-log-viewer-usability.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`server/modules/ticket/service/ticket_log_service.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：日志查看弹窗 -> 搜索结果上限与面板状态 -> 点击命中按需加载上下文 -> 后端非重叠翻页指针 -> 编码兼容读取与中文关键字搜索
- 验证：`uv run ruff check modules/ticket/service/ticket_log_service.py modules/ticket/entity/vo/ticket_log_pull_vo.py`、GB18030 中文日志上下文/搜索小样本、`npm run build:prod` 均通过。
- 总共涉及页面：7

## [2026-06-22] INGEST-CODE | 工单入库原文保留与 AI 分析版本号兜底
- 触发：用户要求项目、模块匹配失败时保留原文；后续数据无版本号时不清空已有版本；手动发起 AI 分析可选版本号，未选时从日志提取并回写后发起分析。
- 架构层：工单域 / 外部同步入库 / 工单编辑 / 日志拉取 / AI 分析任务提交
- 创建的页面：`web/public/docs/2026-06-22-ticket-ingest-version-ai-fallback.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/service/ticket_ai_analysis_service.py`、`server/modules/ticket/service/ticket_log_pull_service.py`、`server/modules/ticket/dao/ticket_log_pull_dao.py`、`server/modules/ticket/entity/vo/ticket_vo.py`、`web/src/views/ticket/index.vue`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：外部同步识别 -> `_build_upsert_payload` 原文保留 -> 工单编辑版本保护 -> `TicketAiAnalysisService._ensure_version_key_for_analysis` 日志提取回填 -> AI 分析任务提交
- 验证：通过本次相关 6 个边界测试；整文件测试仍有既有 `bitableCommon.pageSize` 断言失败，未纳入本次改动范围。
- 总共涉及页面：13

## [2026-06-22] INGEST-CODE | 相似工单支持详情跳转
- 触发：用户要求工单详情页中的相似工单可跳转查看，支持原飞书详情 URL 和当前系统详情页；当前系统详情原为弹窗，需要通过 URL 拼接工单号独立打开。
- 架构层：工单域 / Web 控制台 / 工单详情弹窗 / 相似工单
- 创建的页面：`web/public/docs/2026-06-22-ticket-similar-detail-links.md`
- 更新的页面：`web/src/router/index.js`、`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：相似工单卡片 -> `openSystemTicketDetail` 生成 `#/ticket/detail/:ticketId` -> 隐藏路由复用工单页并自动打开详情弹窗；外部链接继续走 `resolveTicketDetailUrl` -> `openTicketLink`
- 总共涉及页面：5

## [2026-06-22] INGEST-CODE | 多维表格主动拉取创建时间窗口
- 触发：用户要求定时任务 `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync` 默认查询当前时间前 1 小时之后的数据，指定时间时按指定时间之后的数据查询。
- 架构层：工单域 / 飞书多维表格主动拉取 / 任务调度
- 创建的页面：`web/public/docs/2026-06-22-ticket-bitable-pull-created-after.md`
- 更新的页面：`server/module_task/scheduler_maintenance.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`pull_feishu_bitable_ticket_sync` 补齐 `createdAfter` -> `TicketSyncService.run_bitable_pull_services` 按飞书记录创建时间过滤 -> 外部同步入库链路
- 总共涉及页面：5

## [2026-06-22] INGEST-CODE | 修复飞书多维表格记录详情链接
- 触发：用户反馈 `TicketSyncService._build_bitable_record_url` 使用多维表格搜索结果中的 `record_id` 拼接 URL 无法访问，真实可访问地址需要飞书记录详情 URL。
- 架构层：工单域 / 飞书多维表格集成 / 按人催办通知
- 创建的页面：`web/public/docs/2026-06-22-ticket-bitable-record-url-fix.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketSyncNotifyService.query_bitable_records` 搜索记录 -> `records/batch_get(with_shared_url=true)` 批量补齐 `shared_url` -> `TicketSyncService._build_bitable_pull_sync_object` / `TicketSyncNotifyService._collect_person_overdue_data` -> 工单 `ticket_url` / 来源 `recordUrl` / 催办 `detailUrl`
- 追加：已用 dev 环境真实参数只读实测，`records/search` 未返回链接，但 `records/batch_get` 可稳定返回 `https://duodian.feishu.cn/record/...` 形式的 `shared_url`；补查后 31 条记录全部成功补齐。
- 总共涉及页面：7

## [2026-06-18] INGEST-CODE | 工单统计项目模块多选筛选
- 触发：用户要求工单统计页面顶部增加按项目、模块筛选，并支持多选。
- 架构层：工单域 / Web 控制台 / 统计接口
- 创建的页面：`web/public/docs/2026-06-18-ticket-statistics-project-module-multiselect.md`
- 更新的页面：`web/src/views/ticket/statistics/index.vue`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/dao/ticket_dao.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：统计页多选筛选 -> `TicketStatisticsQueryModel.projectIds/moduleIds` -> `TicketService.get_statistics_services` -> `TicketDao.get_ticket_statistics`
- 追加：模块筛选改为未选择项目时展示全部有效模块，选择项目后展示所选项目下模块；工单列表页同步使用该筛选规则。
- 总共涉及页面：8

## [2026-06-21] INGEST-CODE | 工单主动拉取与多维配置统一
- 触发：用户要求根据桌面需求文档实现“工单主动拉取与配置优化”，包括外部字段模型、飞书多维表格主动拉取、字段映射和公共多维配置继承。
- 架构层：工单域 / 飞书多维表格集成 / 任务调度 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-21-ticket-bitable-pull-and-config-unify.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/module_task/scheduler_maintenance.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`bitableCommon/externalFieldModel/bitablePull` 配置 -> `TicketSyncService.run_bitable_pull_services` -> `TicketSyncNotifyService.query_bitable_records` -> `TicketSyncService.sync_external_ticket`
- 追加：主动拉取复用外部同步主链路，但会按 `recordId + snapshotHash` 判断记录是否变化；未变化时跳过，避免周期任务反复递增同步 revision。
- 总共涉及页面：9

## [2026-06-18] INGEST-CODE | 工单 AI Agent 已登记 worktree 分支复用
- 触发：用户反馈工单 AI 分析创建 `wemn_vender_master_1.3.8.41` 分支 worktree 时，目标目录不存在但 Git 提示该分支已被旧工作区路径占用。
- 架构层：工单域 / client_new Agent / Git worktree
- 创建的页面：`web/public/docs/2026-06-18-ticket-ai-worktree-registered-branch-reuse.md`
- 更新的页面：`client_new/services/ticket_ai_analysis_service.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`_ensure_local_worktree_repo` / `_ensure_worktree_repo` -> `_find_registered_worktree_by_branch` -> 复用 Git 已登记且分支校验通过的 worktree
- 总共涉及页面：4

## [2026-06-18] INGEST-CODE | 工单列表处理状态与评论按需加载
- 触发：用户要求工单列表“日志拉取”列改为“处理状态”并补充日志拉取中状态，详情页描述/翻译可收起，评论从历史页移到同级且点击后再异步请求。
- 架构层：工单域 / Web 控制台 / 评论接口 / 日志拉取状态筛选
- 创建的页面：`web/public/docs/2026-06-18-ticket-list-process-status-and-comments-lazy.md`
- 更新的页面：`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/dao/ticket_dao.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/constants.js`、`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`entities/enums/ticket-enums.md`、`flows/ticket-automation-flow.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketDao.list_comments` -> `GET /ticket/{ticket_id}/comments` -> 工单详情评论 tab 按需加载；`ticketProcessStatusOptions` -> `_build_ticket_process_status_filter` -> 工单列表处理状态筛选
- 总共涉及页面：10

## [2026-06-17] INGEST-CODE | 按人催办定时任务支持飞书参数覆盖
- 触发：用户要求按人催办通知的飞书筛选条件、人员字段名、时间字段名、视图、tableId、appToken 可在定时任务中配置；任务未配置时回退原参数配置。
- 架构层：工单域 / 飞书通知 / 任务调度
- 创建的页面：`web/public/docs/2026-06-17-ticket-person-reminder-task-override.md`
- 更新的页面：`server/module_task/scheduler_maintenance.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_sync_notify_service.py`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`scheduler_maintenance.ticket_person_overdue_reminder` -> `TicketSyncService.run_person_reminder_services` -> `TicketSyncNotifyService.query_bitable_records`
- 总共涉及页面：6

## [2026-06-17] INGEST-CODE | 工单分类 AI 配置统一
- 触发：用户反馈工单分类统计配置分散在工单同步配置和 AI 配置中心，要求统一 Provider/提示词管理，并避免修改配置影响现有业务。
- 架构层：工单域 / 同步自动化 / AI Provider / AI 提示词模板 / 分类统计
- 创建的页面：`web/public/docs/2026-06-17-ticket-classification-config-unification.md`
- 更新的页面：`server/module_admin/service/ai_prompt_template_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/src/views/system/aiconfig/index.vue`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：AI 提示词默认模板 -> `ticket.sync.automation.aiClassification` 场景开关与选择项 -> `TicketLightAiService.classify_ticket_statistics` -> 工单分类统计字段回填
- 兼容策略：历史 `aiClassification.promptContent` 保存时保留，只作为旧配置兜底；新页面不再提供正文编辑入口。

## [2026-06-17] INGEST-CODE | 摄入工单自动归类排障日志增强
- 触发：用户反馈工单同步配置中点击统计未归类调用 `/sync/auto-category/stats` 没有自动归类，需要知道为什么没执行、正在执行什么、正在处理什么数据
- 架构层：工单域 / 同步自动化 / 轻量 AI 分类统计
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/2026-06-17-ticket-auto-category-debug-logs.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/service/ticket_light_ai_service.py` / `web/src/views/ticket/syncAutomation/index.vue` -> 工单同步自动归类排障
- 总共涉及页面：4

## [2026-06-17] INGEST-CODE | 工单相似度检索 Qdrant Provider
- 触发：用户反馈相似工单统计不准确，要求按标题和描述智能判断，并将向量库接入做成可配置方式。
- 架构层：工单域 / 相似工单检索 / Embedding / Qdrant / 批量重建任务
- 创建的页面：`web/public/docs/2026-06-17-ticket-similarity-qdrant-provider.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`flows/ticket-automation-flow.md`、`log.md`
- 变更传播链：`TicketEmbeddingService` -> `ticket.similarity.config` Provider 配置 -> `GET /ticket/similarity/config` / `POST /ticket/similarity/rebuild` -> 工单详情、协同追问、AI 分析上下文复用相似工单结果
- 追加：新增 `PUT /ticket/similarity/config`、菜单 `ticket.similarity.config` 和页面 `ticket/similarityConfig/index`；`sceneTriggers` 控制外部同步、远端拉取、手动新增、手动编辑、Excel 导入、关闭知识沉淀六类自动向量刷新场景。

## [2026-06-17] INGEST-CODE | 工单 AI Agent 分支 worktree 隔离
- 触发：用户反馈同一 Agent 并发分析不同工单时可能需要不同分支，并要求不影响原代码；未配置 localRepoPath 时自动创建目录并 checkout。
- 架构层：工单域 / client_new Agent / Codex Worker / Git worktree
- 创建的页面：`web/public/docs/2026-06-17-ticket-ai-agent-worktree-branch-isolation.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` -> 仓库映射 localRepoPath 分支校验、缺省 worktree 创建、Worker 提示词和阶段事件记录实际代码目录
- 追加：当历史映射携带 `localRepoPath` 但该目录当前分支与 `branchName` 不一致时，Agent 会记录原因并优先基于该本地仓库创建分支固定 worktree，复用原项目 Git 配置和凭据；只有无法自动创建 worktree 时才失败。

## [2026-06-16] INGEST-CODE | 工单保存接口非阻塞与按钮防重复提交
- 触发：用户反馈工单编辑弹窗保存响应慢，接口响应前保存按钮仍可重复点击，并要求接口异步化避免阻塞其他接口。
- 架构层：工单域 / Web 控制台 / FastAPI 事件循环 / 工单新增编辑保存链路
- 创建的页面：`web/public/docs/2026-06-16-ticket-save-nonblocking-submit-lock.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` -> 新增编辑保存线程池调度与弹窗提交态说明

## [2026-06-16] INGEST-CODE | 工单多维表格邮箱同步幂等优化
- 触发：用户要求外部推单入库时，如果多维表格邮箱之前已经成功同步过则不要每次重复同步，并确认推送和拉取是否都由配置控制。
- 架构层：工单域 / 外部同步链路 / 多维表格邮箱补齐 / 内网远端拉取
- 创建的页面：`web/public/docs/2026-06-16-ticket-bitable-email-sync-idempotent.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` / `server/tests/test_ticket_sync_mapping_boundary.py` -> 多维邮箱同步成功标记与推拉配置边界说明

## [2026-06-16] INGEST-CODE | 日志下载与工单同步接口非阻塞修复
- 触发：用户反馈日志拉取列表点击归档地址、原始压缩包和重新下载会导致 FastAPI 服务卡住，并要求检查外部推送、内网拉取等高频工单接口。
- 架构层：工单域 / 日志拉取 / 外部同步链路 / FastAPI 事件循环
- 创建的页面：`web/public/docs/2026-06-16-ticket-log-pull-download-nonblocking.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` / `web/src/views/ticket/logPullRecord/index.vue` -> 浏览器直链下载与同步服务线程池边界说明

## [2026-06-16] INGEST-CODE | 工单详情顶部描述布局优化
- 触发：用户反馈工单详情弹窗顶部详情表格中描述过长会撑变形，灰色关键字列换行会抬高短信息行；随后要求描述自动展示全部内容，并将原文和翻译分开展示、支持手动翻译。
- 架构层：工单域 / Web 控制台 / 工单详情弹窗 / 轻量 AI 翻译
- 创建的页面：`web/public/docs/2026-06-16-ticket-detail-summary-description-layout.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`ticket_controller.py` / `ticket_service.py` / `ticket.js` / `ticket/index.vue` -> 详情顶部基础信息表格、描述独立行和手动翻译入口

## [2026-06-16] INGEST-CODE | 工单 stepReason 排查过程评论同步
- 触发：用户要求将飞书 webhook 的 `stepReason` 大文本拆分为工单评论，并支持幂等、内网同步、本地评论不被覆盖和评论附件预留。
- 架构层：工单域 / 外部同步链路 / 评论模型 / 内网远端拉取
- 创建的页面：`web/public/docs/2026-06-16-ticket-step-reason-comment-sync.md`
- 创建的 SQL：`server/sql/20260616_ticket_comment_sync_source.sql`
- 更新的页面：`web/public/docs/update_history.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 变更传播链：`ticket_controller.py` / `ticket_sync_service.py` / `ticket_service.py` / `ticket_dao.py` / `ticket_do.py` / `ticket_vo.py` -> stepReason 评论幂等同步说明

## [2026-06-16] INGEST-CODE | 工单同步重启恢复与远端拉取重试修复
- 触发：用户反馈服务重新部署/异常重启后同步状态可能不对，远端推送可更新但内部拉取后内部数据未更新。
- 架构层：工单域 / 外部同步链路 / 内网远端拉取 / 发布状态恢复
- 创建的页面：`web/public/docs/2026-06-16-ticket-sync-restart-retry-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`web/public/docs/ticket-sync-automation.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/dao/ticket_dao.py` -> 工单同步发布状态、pending 租约与远端拉取重试说明

## [2026-06-16] INGEST-CODE | 日志拉取下载来源与 POS 列表区分
- 触发：用户要求日志拉取管理页下载优先本服务文件、缺失再走原始路径；工单详情页归档地址与原始压缩包分别下载；详情列表增加商家、门店、POSID。
- 架构层：工单域 / 日志拉取 / 下载来源 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-16-ticket-log-pull-download-source-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`ticket_log_pull_service.py` / `ticket_controller.py` / `ticket.js` / `ticket/index.vue` / `logPullRecord/index.vue` -> 下载来源参数与详情页日志拉取列表展示

## [2026-06-16] INGEST-CODE | 日志拉取弹窗布局与通知修复
- 触发：用户要求日志拉取弹窗商家/门店/POSID 自动铺满整行，按数据类型切换 `modifyTime/path`，时间方式仅切割日志时显示，默认本地保存，并修复通知配置不生效。
- 架构层：工单域 / 日志拉取 / Web 控制台 / 推送通知
- 创建的页面：`web/public/docs/2026-06-16-ticket-log-pull-dialog-layout-notify-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 变更传播链：`LogPullConfigFields.vue` / `LogPullNotifyConfigFields.vue` / `ticket_log_pull_service.py` -> 日志拉取提交参数清洗与结果通知

## [2026-06-16] INGEST-CODE | 工单编辑历史模块与人员名称保留
- 触发：用户反馈编辑页所属模块与当前项目模块不匹配时应原样显示/保存；1线人员和内部负责人不应重复显示 ID 选择与名称输入，无法匹配用户时应保留原始名称。
- 架构层：工单列表 / 工单编辑表单 / 工单关系字段解析
- 更新的页面：`web/public/docs/update_history.md`、`web/public/docs/2026-06-16-ticket-classification-statistics-fields.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`web/src/views/ticket/index.vue` / `UserSelect.vue` / `ticket_service.py` -> 历史模块文本保留 / 人员名称单控件回显与保存

## [2026-06-16] INGEST-CODE | 工单编辑模块回填与工单类型展示修复
- 触发：用户反馈工单列表中编辑保存后模块显示为空，且工单类型编辑前显示像所属模块、编辑后才正确。
- 架构层：工单列表 / 工单编辑表单 / 分类统计字段展示
- 更新的页面：`web/public/docs/update_history.md`、`web/public/docs/2026-06-16-ticket-classification-statistics-fields.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`web/src/views/ticket/index.vue` -> 编辑回填模块保护 / 提交前模块名称补齐 / 工单类型不回退旧分类

## [2026-06-16] INGEST-CODE | 工单分类统计独立字段与可视化枚举配置
- 触发：用户要求按 `D:\xj\Documents\工单分类统计设计.txt` 实现工单分类统计拆维，并将统计状态/枚举设计为可配置且可视化配置。
- 架构层：工单域 / 工单统计 / 同步自动化配置 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-16-ticket-classification-statistics-fields.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`entities/enums/ticket-enums.md`、`log.md`
- 变更传播链：`ticket.sync.automation.statClassification` -> 工单表独立统计字段 -> 工单列表/流转/RCA/统计页展示

## [2026-06-15] INGEST-CODE | 远端拉取状态与内部负责人映射修复
- 触发：用户反馈内网拉取公网工单后状态仍显示公网原始文案，且公网有内部负责人但内网缺失。
- 架构层：工单域 / 外部同步链路 / 远端拉取入库
- 创建的页面：`web/public/docs/2026-06-15-ticket-remote-pull-status-owner-mapping.md`
- 更新的页面：`web/public/docs/update_history.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` -> 远端拉取状态与内部负责人映射说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | 工单协同追问触发 AI 修复
- 触发：用户反馈工单详情页 `协同/AI` 中追问有保存输入内容，但没有发起 AI 分析
- 架构层：工单域 / AI Worker 编排 / 前端详情页
- 创建的页面：`web/public/docs/2026-06-15-ticket-message-run-ai-trigger-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_service.py` / `web/src/views/ticket/index.vue` -> 工单协同追问触发 AI 说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | 工单 AI 整包日志摘要优化
- 触发：用户询问几十 MB 日志是否完整给 AI 分析，担心 token 消耗过高。
- 架构层：client_new Agent / 工单 AI 分析 / 日志整包处理
- 创建的页面：`web/public/docs/2026-06-15-ticket-ai-log-digest-optimization.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单 AI 日志整包摘要说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | Agent Codex CLI 执行链路修复
- 触发：用户反馈 Windows Agent 安装 Codex 桌面应用后，工单 AI 分析误用桌面应用 `codex.exe`、弹出 cmd 窗口，且账号并发限制错误被业务日志污染。
- 架构层：client_new Agent / 工单 AI 分析 / Codex CLI 执行
- 创建的页面：`web/public/docs/2026-06-15-agent-codex-cli-runtime-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` / `client_new/model/config.py` -> Agent Codex CLI 执行修复说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | 日志拉取重新拉取参数恢复兼容
- 触发：用户反馈工单详情页日志拉取记录点击“重新拉取”时报“当前记录缺少可重新拉取的原始参数”。
- 架构层：工单域 / 日志拉取 / 历史记录兼容
- 创建的页面：`web/public/docs/2026-06-15-ticket-log-pull-retry-payload-fallback.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` -> 重新拉取参数恢复说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | API Key 使用审计非阻断处理
- 触发：用户反馈远端推单偶发 MySQL 2013，堆栈显示失败点为 API Key 鉴权阶段更新 `sys_api_key.last_used_ip/last_used_time`。
- 架构层：认证鉴权 / API Key / 工单外部同步入口
- 创建的页面：`web/public/docs/2026-06-15-api-key-usage-audit-nonblocking.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_admin/service/api_key_service.py` -> API Key 使用审计非阻断说明
- 总共涉及页面：3

## [2026-06-15] INGEST-CODE | 工单动态工作流状态与远端模块同步修复
- 触发：用户反馈远端推送 `ticketModle` 变化未正确更新，以及工作流新增/修改状态后工单流转无法选择新增状态。
- 架构层：工单域 / 外部同步链路 / 工作流流转 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-15-ticket-workflow-dynamic-status-and-remote-module.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-workflow-routing.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_sync_service.py` / `web/src/views/ticket/index.vue` -> 工单动态状态与远端模块同步文档
- 总共涉及页面：6

## [2026-06-15] INGEST-CODE | 新增专题工单会话状态统计定时任务
- 触发：用户要求根据 `D:\xj\Downloads\topic_ticket_stats.py` 将内部逻辑实现在当前项目的定时任务中，并通过任务参数配置所需信息。
- 架构层：工单域 / 任务调度 / 飞书群消息统计
- 创建的页面：`web/public/docs/2026-06-15-ticket-topic-stats-scheduler.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_topic_stats_service.py` / `server/module_task/scheduler_maintenance.py` -> 专题统计定时任务文档
- 总共涉及页面：3

## [2026-06-12] INGEST-CODE | 工单群消息@人补强（模板别名 + 人员对象邮箱解析）
- 触发：用户要求外部推单/远端拉取发群时，按模板决定是否 @ 报告人与当前责任人，并通过邮箱查询飞书 `open_id` 稳定 @ 人。
- 架构层：工单域 / 外部同步链路 / 飞书通知
- 创建的页面：`web/public/docs/2026-06-12-ticket-group-mention-template-and-person-email-compat.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_sync_notify_service.py` -> 工单通知链路文档
- 总共涉及页面：3

## [2026-06-12] INGEST-CODE | 自动群推送状态条件改为可视化配置
- 触发：用户要求将自动群推送的状态判断从后端写死逻辑改为可视化配置，并确认外部推单/远端拉取都生效且不影响手动推送。
- 架构层：工单域 / 同步自动化配置 / 群消息通知
- 创建的页面：`web/public/docs/2026-06-12-ticket-group-auto-push-status-condition-config.md`
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` / `web/src/views/ticket/syncAutomation/index.vue` -> 工单同步配置文档
- 总共涉及页面：4

## [2026-06-11] INGEST-CODE | 修复外部推单秒级重复导致群消息重复发送
- 触发：用户反馈外部同工单短时间重复推送时，群消息仍会重复发送，要求“收到后立即判重”。
- 架构层：工单域 / 外部同步链路 / 群消息通知
- 创建的页面：`web/public/docs/2026-06-11-ticket-external-rapid-duplicate-dedup-lock.md`
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` -> 工单同步与群推送幂等文档
- 总共涉及页面：4

## [2026-06-11] INGEST-CODE | 修复按人催办过滤公式导致飞书参数异常
- 触发：用户反馈“按人催办通知”一旦填写过滤公式，调用飞书接口即报参数异常。
- 架构层：工单域 / 飞书通知 / 多维表格查询
- 创建的页面：`web/public/docs/2026-06-11-person-reminder-filter-formula-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_notify_service.py` -> 工单通知链路文档
- 总共涉及页面：3

## [2026-06-10] INGEST-CODE | AI配置中心默认提示词补齐（自动分类/日志参数提取）
- 触发：用户反馈 AI 配置中心“自动分类提示词、日志参数提取提示词”默认无法选择，要求系统默认插入可选模板，内容可为空以便后续填写。
- 架构层：系统管理 / AI配置中心 / 提示词模板
- 创建的页面：`web/public/docs/2026-06-10-ai-config-default-common-prompts.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_admin/service/ai_prompt_template_service.py` / `server/module_admin/service/ai_config_service.py` -> AI配置中心文档
- 总共涉及页面：3

## [2026-06-10] INGEST-CODE | 工单通知补强（优先级分流 + 汇总统计 + 统一飞书凭证）
- 触发：用户提供“工单通知相关”需求，要求补齐优先级分流发群、按人催办、定时汇总统计、统一 app_id/app_secret 与配置可视化。
- 架构层：工单域 / 飞书通知 / 任务调度 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-10-ticket-notify-routing-and-summary.md`
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_notify_service.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/entity/vo/ticket_vo.py` / `server/module_task/scheduler_maintenance.py` / `web/src/views/ticket/syncAutomation/index.vue` / `web/src/api/ticket/ticket.js` -> 工单域知识页
- 总共涉及页面：4

## [2026-06-10] INGEST-CODE | 修复日志拉取列表 modify_time 字段异常
- 触发：用户反馈工单列表页报错 `'TicketLogPullRecord' object has no attribute 'modify_time'`
- 架构层：工单域 / 日志拉取
- 创建的页面：无
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-06-10] INGEST-CODE | 修复日志拉取弹窗关联工单回填缺失
- 触发：用户反馈日志拉取弹窗中关联工单后，商家ID/门店/POS未自动回填。
- 架构层：工单域 / 日志拉取 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/views/ticket/index.vue` / `web/src/views/ticket/logPullRecord/index.vue` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `server/modules/ticket/service/ticket_log_pull_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-06-10] INGEST-CODE | 工单自动拉日志门槛 + 自动分类 + 日志弹窗回填
- 触发：用户要求自动拉日志必须参数齐全才执行，并新增工单自动分类能力（含批量重跑），同时增强日志拉取弹窗回填与“日志成功后版本号自动回填”。
- 架构层：工单域 / 外部同步链路 / 轻量 AI 配置中心 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-10-ticket-auto-logpull-and-auto-category.md`
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_light_ai_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/entity/vo/ticket_vo.py` / `server/module_admin/service/ai_config_service.py` / `server/module_admin/entity/vo/ai_config_vo.py` / `web/src/views/system/aiconfig/index.vue` / `web/src/views/ticket/index.vue` / `web/src/views/ticket/logPullRecord/index.vue` / `web/src/components/ticket/LogPullConfigFields.vue` / `web/src/api/ticket/ticket.js` -> 工单域知识页
- 总共涉及页面：4

## [2026-06-10] INGEST-CODE | 工单通知系统（群消息推送 + 按人催办）落地
- 触发：用户要求基于飞书多维表格按人催办、支持工单群消息推送、并将同步链路翻译开关收敛到清晰配置。
- 架构层：工单域 / 外部同步链路 / 飞书通知 / 任务调度 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_notify_service.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/module_task/scheduler_maintenance.py` / `web/src/views/ticket/syncAutomation/index.vue` / `web/src/views/system/aiconfig/index.vue` -> 工单域知识页
- 总共涉及页面：3

## [2026-06-09] INGEST-CODE | 修复日志拉取弹窗门店联动不重新查询
- 触发：用户反馈在日志拉取弹窗中输入或选择商家后，门店下拉没有只显示对应商家的门店。
- 架构层：工单域 / 日志拉取 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/ticket-log-pull-design.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `web/src/api/ticket/ticket.js` / `web/src/components/ticket/LogPullConfigFields.vue` -> 工单域知识页
- 总共涉及页面：3

## [2026-06-09] INGEST-CODE | 修复门店配置列表分页数据读取层级错误
- 触发：用户反馈门店配置页面查询后后端已返回数据，但前端列表不显示。
- 架构层：工单域 / 日志拉取 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/views/ticket/logPullRecord/index.vue` -> 工单域知识页
- 总共涉及页面：2

## [2026-06-09] INGEST-CODE | 修复门店配置导入误去重与大文件导入卡顿
- 触发：用户反馈 `/ticket/log-pull/store-configs/import` 上传 3K 门店配置后只剩少量记录，同时导入期间影响其他服务可用性。
- 架构层：工单域 / 日志拉取 / 门店配置导入 / 知识库同步
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/ticket-log-pull-design.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/dao/ticket_log_pull_dao.py` -> 工单域知识页
- 总共涉及页面：4

## [2026-06-05] INGEST-CODE | 日志拉取新增门店配置导入与项目商家映射
- 触发：用户要求给日志拉取页面增加门店信息导入入口，支持增量/覆盖导入，并补充项目到商户编号的映射和链路日志。
- 架构层：工单域 / 日志拉取 / Web 控制台 / 知识库同步
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/ticket-log-pull-design.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/entity/do/ticket_log_pull_do.py` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/dao/ticket_log_pull_dao.py` / `web/src/views/ticket/logPullRecord/index.vue` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-31] INGEST-CODE | 工单外部同步与内网拉取链路落地
- 触发：用户需要双环境部署下的工单同步能力，要求知道哪些数据已被某个内网系统拉取过，并在同步后自动识别归属信息、匹配类似工单、按条件串联日志拉取与 AI 分析，同时记录执行失败步骤。
- 架构层：工单域 / 外部系统集成 / 自动化链路 / 系统参数配置
- 创建的页面：`flows/ticket-external-sync-flow.md`
- 更新的页面：`entities/services/ticket-domain.md`、`index.md`、`log.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`
- 创建的双向链接：2 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/dao/ticket_dao.py` / `server/modules/ticket/entity/vo/ticket_vo.py` / `server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/perms.py` -> `wiki/flows/ticket-external-sync-flow.md` -> `wiki/entities/services/ticket-domain.md`
- 总共涉及页面：6

## [2026-05-31] INGEST-CODE | 日志拉取页面商家门店改为参数配置联动下拉
- 触发：用户要求日志拉取页面的商家、门店改为可配置并沿用现有服务端参数配置，且商家与门店联动。
- 架构层：工单域 / 日志拉取 / 系统参数配置 / Web 控制台
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/ticket-log-pull-design.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `web/src/api/ticket/ticket.js` / `web/src/views/ticket/logPullRecord/index.vue` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-29] INGEST-CODE | 定时任务新增线程/进程执行方式并拆分 Worker
- 触发：用户要求按任务配置选择线程或进程执行，并落地长期稳定方案，去掉业务层二级 spawn 子进程
- 架构层：任务调度域 / Celery Worker / 任务执行模型
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_job_models.py` / `server/module_task/celery_job_service.py` / `server/config/get_db.py` / `server/supervisord.conf` / `web/src/views/monitor/job/index.vue` / `web/src/views/qtr/job/index.vue` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-29] INGEST-CODE | 临时统一 Celery 任务为线程内直执行
- 触发：用户要求先排除 Linux 下业务子进程 `spawn` 与 IPC 干扰，确认任务逻辑在线程直执行模式下是否正常
- 架构层：任务调度域 / Celery Worker / 任务执行模型
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-29] INGEST-CODE | 修复 Windows 下 Celery 业务子进程导入失败
- 触发：用户在 Windows 开发环境执行定时任务时，Worker 已收到任务，但二级 `spawn` 子进程启动阶段报 `ModuleNotFoundError: No module named 'module_task'`
- 架构层：任务调度域 / Celery Worker / Windows 多进程导入路径
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-29] INGEST-CODE | 修复定时任务子进程结果回传竞态
- 触发：用户反馈定时任务执行记录显示“子进程未返回结果”，但应用日志里没有异常堆栈
- 架构层：任务调度域 / Celery Worker / 子进程 IPC
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` -> 任务调度域知识页
- 总共涉及页面：2

## [2026-05-29] INGEST-CODE | 落地 AI 分析提示词分层设计
- 触发：用户要求直接落地“AI 分析提示词分层设计方案”，希望项目/模块拥有默认提示词，且提交分析时允许额外说明
- 架构层：工单域 / AI 提示词组装 / 前端提交弹窗
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_prompt_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` / `server/modules/ticket/service/ticket_service.py` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：3

## [2026-05-28] INGEST-CODE | 调整工单 AI 仓库映射优先级到 Agent 本地配置
- 触发：用户指出工单 AI 仓库映射里的工作区根目录和本地仓库路径更像 Agent 本地配置，要求服务端改为非必填，并在 Agent 本地配置存在时始终以本地配置为准
- 架构层：工单域 / Agent 编排 / 新版客户端
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` / `client_new/ui/pages/agent_page.py` / `web/src/views/ticket/aiRepoMapping/index.vue` -> 工单域知识页
- 总共涉及页面：3

## [2026-05-27] INGEST-CODE | 修复 Celery 任务长执行锁过期与失联状态恢复
- 触发：用户反馈 Celery Worker 异常后任务状态会一直停留在 running，且无法再次手动执行；另有 2 小时任务在 `lock_ttl_seconds=3600` 下执行到 1 小时后又被自动重复派发
- 架构层：任务调度域 / Redis 锁 / 运行态心跳 / 手动终止
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` / `server/module_task/celery_job_service.py` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-27] INGEST-CODE | 调整 Celery 执行日志为启动写入、结束回填
- 触发：用户怀疑存在其他触发途径，希望能在任务执行中直接看到是谁触发、何时进入 running；现有执行日志只在任务完成后写入，导致运行中缺少数据库记录
- 架构层：任务调度域 / 执行日志生命周期
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` / `server/module_task/celery_job_service.py` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-26] INGEST-CODE | 修复工单 AI 分析 WebSocket loop 归属错误
- 触发：用户先反馈工单 AI 分析失败后重试时任务长期停留在“进行中”，修复后又暴露出发起分析时报 `got Future attached to a different loop`
- 架构层：工单域 / Agent 编排 / 异步事件循环
- 创建的页面：`docs/2026-05-26-ticket-ai-analysis-future-threadsafe-result.md`
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_qtr/service/agent_service.py` / `server/module_qtr/controller/agent_controller.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-26] INGEST-CODE | 修复 AI 分析期间 Agent 事件循环被阻塞导致断连
- 触发：用户反馈启动 AI 分析时 Agent 经常断开，怀疑是大文件占用连接过久，要求在不改数据流前提下定位根因并采用稳定方案处理
- 架构层：工单域 / Agent 编排 / 新版客户端
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-automation-flow.md`、`docs/ticket_system_phase1.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` / `client_new/server/agent_server.py` / `server/module_qtr/controller/agent_controller.py` / `server/module_qtr/service/agent_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-20] INIT-CODE | 初始化 Wiki 基础结构
- 触发：用户执行 `$llm-wiki init`
- 架构层：知识库初始化
- 创建的页面：`overview.md`、`purpose.md`、`concepts/architecture-overview.md`、`entities/services/backend-application.md`、`entities/components/frontend-bootstrap.md`、`flows/http-api-entrypoint.md`、`schema.md`、`index.md`
- 更新的页面：无
- 创建的双向链接：13 对
- 变更传播链：`README.md`/`server/server.py`/`server/config/env.py`/`web/src/main.js` -> Wiki 总览与入口页
- 总共涉及页面：8

## [2026-05-20] INGEST-CODE | 摄入 client 与 client_new 模块
- 触发：用户要求摄入 `client/` 与 `client_new/` 模块
- 架构层：桌面客户端层
- 创建的页面：`concepts/desktop-client-architecture.md`、`entities/services/legacy-flet-client.md`、`entities/services/new-pyside-client.md`、`entities/components/legacy-client-bootstrap.md`、`entities/components/new-client-bootstrap.md`
- 更新的页面：`index.md`
- 创建的双向链接：10 对
- 变更传播链：`client/src/main.py`/`client/src/navigationMenu.py`/`client_new/main.py`/`client_new/ui/main_window.py` -> 客户端知识页
- 总共涉及页面：6

## [2026-05-20] INGEST-CODE | 摄入项目其余模块知识库
- 触发：用户要求完成项目中所有模块知识库创建
- 架构层：后端平台 / Web 控制台 / 旧版客户端 / 新版客户端
- 创建的页面：`concepts/module-landscape.md`、`entities/components/server-infrastructure.md`、`entities/services/admin-domain.md`、`entities/services/hrm-domain.md`、`entities/services/qtr-domain.md`、`entities/services/task-scheduler-domain.md`、`entities/services/ticket-domain.md`、`entities/components/web-shell.md`、`entities/services/web-feature-domains.md`、`entities/components/legacy-client-shell.md`、`entities/components/legacy-client-runtime.md`、`entities/services/legacy-client-features.md`、`entities/components/new-client-shell.md`、`entities/components/new-client-runtime.md`、`entities/services/new-client-services.md`、`entities/data-models/admin-core-models.md`、`entities/data-models/hrm-core-models.md`、`entities/data-models/task-core-models.md`、`entities/data-models/ticket-core-models.md`、`entities/enums/hrm-enums.md`、`entities/enums/ticket-enums.md`
- 更新的页面：`index.md`、`overview.md`、`purpose.md`
- 创建的双向链接：28 对
- 变更传播链：`server/` / `web/src/` / `client/src/` / `client_new/` -> 模块全景图与各域页面
- 总共涉及页面：24

## [2026-05-20] INGEST-CODE | 摄入工单项目/参数配置/流转路由改造
- 触发：用户要求将日志拉取地址与 Cookie 迁移到参数配置、工单归属改为测试项目/模块、状态流转支持默认处理人与通知预留
- 架构层：工单域 / HRM 测试管理域 / 系统参数配置
- 创建的页面：`flows/ticket-workflow-routing.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`entities/enums/ticket-enums.md`、`index.md`
- 创建的双向链接：7 对
- 变更传播链：`server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` / `web/src/views/ticket/workflow/index.vue` -> 工单域知识页与流转流程页
- 总共涉及页面：5

## [2026-05-20] INGEST-CODE | 摄入工单日志弹窗与时间范围收紧改造
- 触发：用户要求将日志展示改为弹窗，日志时间范围必填，并且只读取 `*_pos.log*` 日志
- 架构层：工单域 / Web 控制台
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：1

## [2026-05-21] INGEST-CODE | 摄入工单日志实时重截查看改造
- 触发：用户要求在日志弹窗里默认查看入库内容，仅在查看原始文档时联动显示本次截取范围并支持按调整后的时间实时重截查看
- 架构层：工单域 / Web 控制台
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：1

## [2026-05-21] INGEST-CODE | 摄入工单日志提交弹窗与提示按钮改造
- 触发：用户要求把日志拉取提交区域改为弹窗，参数配置入口改为通用提示按钮，日志页只保留记录列表
- 架构层：工单域 / Web 控制台 / 通用组件
- 创建的页面：`docs/2026-05-21-ticket-log-submit-dialog-prompt-button.md`
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/components/PromptButton/index.vue` / `web/src/views/ticket/index.vue` / `web/src/main.js` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-21] INGEST-CODE | 摄入工单项目选项状态修复与公共项目管理说明
- 触发：用户反馈新增工单时项目/模块下拉为空，需要确认是否复用公共项目管理
- 架构层：工单域 / HRM 测试管理域
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-20-ticket-param-config-workflow-change.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_import_service.py` -> 工单域知识页
- 总共涉及页面：3

## [2026-05-21] INGEST-CODE | 摄入工单事件JSON安全序列化修复
- 触发：用户在按时间点提交日志时，工单事件写入因包含 datetime 导致 JSON 序列化失败
- 架构层：工单域
- 创建的页面：`docs/2026-05-21-ticket-event-data-json-safe.md`
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/dao/ticket_dao.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-21] INGEST-CODE | 修复日志拉取事件写入绕过 JSON 安全转换的问题
- 触发：用户反馈提交日志拉取任务仍然因 datetime 进入 event_data 而报错
- 架构层：工单域
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-21-ticket-event-data-json-safe.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-21] INGEST-CODE | 摄入日志按时间范围完整入库与换行开关改造
- 触发：用户要求日志按时间范围完整入库，不要静默截断，并支持默认不换行查看
- 架构层：工单域 / Web 控制台
- 创建的页面：`docs/2026-05-21-ticket-event-data-json-safe.md`
- 更新的页面：`entities/services/ticket-domain.md`、`docs/ticket-log-pull-design.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `web/src/views/ticket/index.vue` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-21] INGEST-CODE | 摄入工单日志前端解压展示改造
- 触发：用户说明后端仅返回压缩结果，要求前端在显示时自行解压
- 架构层：工单域 / Web 控制台
- 创建的页面：`docs/2026-05-21-ticket-log-content-decompress.md`
- 更新的页面：`entities/services/ticket-domain.md`、`docs/ticket-log-pull-design.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-21] INGEST-CODE | 摄入工单日志记录级重拉重下重截改造
- 触发：用户要求在日志拉取列表和详情页增加重新拉取、重新下载、重新截取功能
- 架构层：工单域 / Web 控制台
- 创建的页面：`docs/2026-05-21-ticket-log-retry-redownload-reextract.md`
- 更新的页面：`entities/services/ticket-domain.md`、`docs/ticket-log-pull-design.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` / `web/src/api/ticket/ticket.js` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-22] INGEST-CODE | 摄入工单AI分析任务与仓库映射能力
- 触发：用户要求根据最终方案实现工单自动分析、调用 Codex Worker 回写结果，并增加版本/仓库/分支映射管理
- 架构层：工单域 / AI Worker 编排 / Web 控制台
- 创建的页面：`docs/2026-05-22-ticket-ai-analysis-final-solution.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`entities/enums/ticket-enums.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` / `server/modules/ticket/dao/ticket_ai_dao.py` / `server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` / `web/src/api/ticket/ticket.js` -> 工单域知识页
- 总共涉及页面：5

## [2026-05-22] INGEST-CODE | 摄入工单表单与 AI 流程联动调整
- 触发：用户要求修复 TicketStatusHistory 序列化报错，并将工单号、版本号、仓库映射菜单和项目/模块联动纳入最终业务流程
- 架构层：工单域 / AI Worker 编排 / Web 控制台
- 创建的页面：`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/dao/ticket_dao.py` / `server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` / `web/src/views/ticket/index.vue` / `web/src/views/ticket/ai-repo-mapping/index.vue` -> 工单域知识页
- 总共涉及页面：5

## [2026-05-22] INGEST-CODE | 修复工单分析序列化与模块/路由联动兜底
- 触发：用户反馈提交分析仍报 `TicketStatusHistory` 序列化错误，且模块列表为空、AI 仓库映射路由需要改为驼峰路径
- 架构层：工单域 / HRM 测试管理域 / Web 控制台
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/dao/ticket_dao.py` / `server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` / `server/modules/ticket/perms.py` / `web/src/router/index.js` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI分析阶段日志与失败原因回写
- 触发：用户要求 AI 分析失败时能在系统日志里看到具体执行到哪一步、哪一步失败以及异常堆栈，数据库仅保留最后失败原因
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
## [2026-07-01] INGEST-CODE | 工单列表表头排序
- 触发：用户要求工单列表从创建时间排序改为默认按提交时间倒序，并在表头增加按字段排序能力，同时确认当前可排序字段范围。
- 架构层：工单域 / Web 控制台 / 列表分页查询
- 创建的页面：`web/public/docs/2026-07-01-ticket-list-header-sort.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/dao/ticket_dao.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：工单列表表头 `sort-change` -> `sortField/sortOrder` 查询参数 -> DAO 排序白名单 -> 服务端分页排序。
- 热修：排序表达式选择改为显式 `None` 判断，避免 SQLAlchemy 表达式进入 Python 布尔判断时报 `Boolean value of this clause is not defined`。
- 总共涉及页面：6

- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-06-16] INGEST-CODE | 修复工单 pending 候选窗口导致内网拉取为空
- 触发：用户反馈 2026-06-16 上午 10 点后公网能接收推送，但内网拉不到新增数据
- 架构层：工单域 / 外部同步 / 内网远端拉取
- 创建的页面：无
- 更新的页面：`docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/dao/ticket_dao.py` -> 工单外部同步与内网拉取流程
- 总共涉及页面：2

## [2026-06-21] INGEST-CODE | 工单模块 code 筛选与项目内唯一
- 触发：用户要求工单列表和工单统计增加按模块 code 搜索，模块 code 改为项目下唯一，并且筛选下拉枚举动态从后端获取。
- 架构层：工单域 / HRM 模块管理 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-21-ticket-module-code-filter-and-project-unique.md`
- 更新的页面：`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/module_hrm/service/module_service.py`、`web/src/views/ticket/index.vue`、`web/src/views/ticket/statistics/index.vue`、`web/src/views/hrm/module/index.vue`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`/ticket/modules/options` 返回 `moduleCode` -> 工单列表/统计页动态生成模块 code 下拉 -> `/ticket/list` 与 `/ticket/statistics/overview` 增加 `moduleCode/moduleCodes` 过滤；`module_service.py` -> HRM 模块 code 唯一性改为项目内校验

## [2026-05-22] INGEST-CODE | 修复 Windows 下 codex Worker 路径解析问题
- 触发：用户在 Windows 开发环境提交 AI 分析时，日志显示 `WinError 2`，服务进程找不到 `codex` 可执行文件
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Worker 独立 CODEX_HOME 兜底
- 触发：用户继续反馈 AI 分析在 Windows 下因 Codex app-server 初始化和临时目录状态导致失败
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Worker .env 优先加载规则
- 触发：用户要求 AI 分析优先读取 Codex 配置目录中的 `.env`，再回退到系统环境变量
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Worker 排障日志增强
- 触发：用户继续排查 Windows 下 AI Worker 返回 `invalid_request_error`，需要对比终端与后台线程的运行差异
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Worker 输出 schema 约束修复
- 触发：用户提供最新 stderr，确认 Codex 返回 `Invalid schema for response_format 'codex_output_schema'`
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Agent 远程执行链路
- 触发：用户确认短期方案改为本地启动 agent，由服务端通过 WebSocket 调 agent 调用 Codex 并回传结果
- 架构层：工单域 / Agent 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` / `server/module_qtr/service/agent_service.py` / `server/module_qtr/controller/agent_controller.py` / `client_new/services/ticket_ai_analysis_service.py` / `client_new/server/agent_server.py` -> 工单域知识页
- 总共涉及页面：3

## [2026-05-22] INGEST-CODE | 摄入工单自动拉日志与自动AI联动
- 触发：用户要求新增工单时可同时配置是否拉日志、日志成功后是否自动AI，以及在日志拉取页补充自动AI Agent 选择
- 架构层：工单域 / 日志拉取 / Agent 编排 / 前端按需加载
- 创建的页面：`flows/ticket-automation-flow.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`、`wiki/index.md`
- 创建的双向链接：1 对
- 变更传播链：`server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` / `web/src/views/ticket/index.vue` -> 工单自动化链路流程
- 总共涉及页面：5

## [2026-06-09] INGEST-CODE | 摄入日志拉取门店下拉的 org_no 语义
- 触发：用户反馈日志拉取弹窗里的门店下拉不友好，需要支持按 `org_no`、`sap_org_no` 和门店名称搜索，并且实际提交值应使用 `org_no`
- 架构层：工单域 / 日志拉取 / 前端联动选择
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/ticket-log-pull-design.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `server/modules/ticket/entity/do/ticket_log_pull_do.py` / `web/src/components/ticket/LogPullConfigFields.vue` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：5

## [2026-06-10] INGEST-CODE | 摄入工单同步“统一提取 + 半合并AI调用”链路
- 触发：用户要求将工单同步中的标题总结、分类整理、日志参数提取尽量合并为一次轻量 AI 调用，翻译保留独立调用；并新增日志参数提取配置能力
- 架构层：工单域 / 轻量AI配置中心 / 同步自动化
- 创建的页面：无
- 更新的页面：`docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_light_ai_service.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/module_admin/service/ai_config_service.py` / `server/module_admin/entity/vo/ai_config_vo.py` / `web/src/views/system/aiconfig/index.vue` -> 工单域知识页
- 总共涉及页面：5
## [2026-06-24] INGEST-DOC | 多维表格过滤条件 JSON 文案修正
- 触发：用户确认多维表格查询条件配置已经改为 JSON，但页面和文档仍提示填写公式文本；随后要求主动拉取默认按更新时间或创建时间最近 1 小时在飞书请求参数中过滤，不能先全量拉取后本地过滤。
- 架构层：工单域 / 飞书多维表格集成 / 同步自动化配置
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-filter-json-doc-fix.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/public/docs/2026-06-21-ticket-bitable-pull-and-config-unify.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`
- 变更传播链：`ticket.sync.automation.*.filterFormula` 文案 -> 飞书 `records/search` filter JSON 配置提示 -> 后端错误提示；`createdAfter/updatedAtField/fieldMappings.createTime` -> 主动拉取云端时间窗口 filter；`externalSyncRequiredFields` -> 多维主动拉取记录级必填校验。

## [2026-07-08] INGEST-CODE | 工单统计趋势合并归零修复
- 触发：用户反馈昨晚修改后工单统计中趋势曲线和趋势明细数据都变成 0，而昨天正常。
- 架构层：工单域 / 统计趋势 / 处理口径合并
- 更新的页面：`server/modules/ticket/service/stats/ticket_processing_stats_service.py`、`server/tests/test_ticket_processing_metrics.py`、`web/public/docs/2026-07-08-ticket-submit-processed-stats-implementation.md`、`web/public/docs/update_history.md`
- 变更传播链：`TicketDao.get_statistics_trend` 原趋势字段 + `TicketProcessingStatsService.build_trend_metrics` 新处理字段 -> `merge_trend_series` 白名单合并 -> 趋势曲线和趋势明细继续保留旧字段真实数据。
- 关键结论：处理趋势桶也包含 `newCount/closedCount/resolvedCount/openBacklog/netIncrease` 等同名字段，不能整行覆盖原趋势桶；只允许覆盖新增处理字段。

## [2026-07-08] INGEST-CODE | 工单 Issue 归因迁移脚本 OceanBase 兼容修正
- 触发：用户反馈执行 `server/sql/20260708_ticket_issue_relation_tables.sql` 时 OceanBase 报 `(1149) SQL syntax`，并连带出现 `(1243) Unknown prepared statement handle`。
- 架构层：工单域 / 数据库迁移 / Issue 归因层
- 更新的页面：`server/sql/20260708_ticket_issue_relation_tables.sql`、`web/public/docs/2026-07-08-ticket-issue-attribution-implementation.md`、`web/public/docs/update_history.md`
- 变更传播链：迁移脚本 `PREPARE/EXECUTE` 动态 DDL -> OceanBase 一次性直写 DDL -> 已部分执行场景通过 `information_schema` 检查后跳过重复字段或索引。

## [2026-06-24] INGEST-CODE | 工单 AI 分析弹窗默认值与提交体验修正
- 触发：用户要求发起 AI 分析时自动填入 Provider、Agent、追加提示词，日志模式默认摘要 + 完整目录，并排查 2026-06-23 改动导致提交后弹窗不关闭且继续 loading 的等待点。
- 架构层：工单域 / AI 分析 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-24-ticket-ai-analysis-dialog-defaults.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：AI 分析弹窗默认值 -> Provider 绑定 Agent 前端联动 -> 提交成功立即关闭弹窗 -> 后台短轮询保留快速失败提示。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取嵌套时间过滤修复
- 触发：用户反馈 `TicketSyncService._build_bitable_pull_time_filters` 支持嵌套 filter 后，内部时间字段值无法替换；期望嵌套模式在最外层 `children` 追加时间范围，同时递归补齐内部时间字段值，扁平模式只补齐已有字段。
- 架构层：工单域 / 飞书多维表格集成 / 同步自动化配置
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-nested-time-filter.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-06-22-ticket-bitable-pull-created-after.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`bitablePull.filterFormula` 嵌套 filter -> `_fill_dynamic_time_filter_values` 递归补值 -> `_build_bitable_pull_time_filters` 顶层 children 追加默认时间窗口 -> 飞书 `records/search` 请求过滤。
## [2026-06-24] code | 工单用户配置、列表列与统计块显示
- 更新页面：web/src/views/ticket/index.vue, web/src/views/ticket/statistics/index.vue
- 新增后端：module_admin 用户配置模型、DAO、Service、Controller
- 文档：web/public/docs/2026-06-24-ticket-user-config-columns-stat-blocks.md

## [2026-07-01] INGEST-CODE | 飞书多维表格主动拉取分页循环修复
- 触发：用户反馈主动拉取实际 4K 多记录但分页日志超过 100 页，且 `page_token` 固定不变，存在无限循环风险。
- 架构层：工单域 / 飞书多维表格集成 / 同步自动化配置
- 创建的页面：`web/public/docs/2026-07-01-ticket-bitable-pagination-loop-fix.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketSyncNotifyService.query_bitable_records` -> 飞书 `records/search` 分页参数位置 -> 主动拉取 / 按人催办 / 汇总统计多维表格数据源。
- 总共涉及页面：6

## [2026-07-04] INGEST-CODE | 工单主动拉取服务拆分
- 触发：继续进行工单系统拆分，要求对照 `master_params_ticket_new` 原始逻辑并避免破坏业务逻辑。
- 架构层：工单域 / 飞书多维表格主动拉取 / 同步编排拆分
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_bitable_pull_service.py` -> `server/modules/ticket/controller/ticket_sync_controller.py` / `server/module_task/scheduler_maintenance.py` -> 工单外部同步与内网拉取流程。
- 总共涉及页面：3

## [2026-07-04] INGEST-CODE | 工单通知任务拆分与实现规则固化
- 触发：用户要求继续拆分，并将项目实现规则固化，避免后续新增内容再次导致文件过大或不按作用域拆分。
- 架构层：工单域 / 通知任务编排 / 项目工程规范
- 创建的页面：`web/public/docs/2026-07-04-project-implementation-boundary-rules.md`
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/update_history.md`、`AGENTS.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_notification_job_service.py` -> `server/modules/ticket/controller/ticket_sync_controller.py` / `server/module_task/scheduler_maintenance.py` -> 工单外部同步与内网拉取流程；`AGENTS.md` -> 后续 AI 实现边界规则。
- 总共涉及页面：6

## [2026-07-04] INGEST-CODE | 工单外部多维邮箱补齐拆分与公开方法命名
- 触发：用户要求继续拆分，并要求拆分后的子服务对外方法不要以 `_` 开头。
- 架构层：工单域 / 外部推送多维表格邮箱补齐 / 子服务 API 命名规范
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/2026-07-04-project-implementation-boundary-rules.md`、`web/public/docs/update_history.md`、`AGENTS.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_external_bitable_email_service.py` -> `server/modules/ticket/service/ticket_sync_service.py` -> 工单外部同步与内网拉取流程；`TicketBitablePullService` 公开方法改名 -> 主动拉取测试和定时任务边界。
- 总共涉及页面：6

## [2026-07-04] INGEST-CODE | 工单远端拉取服务拆分
- 触发：用户要求继续拆分工单系统，并保持拆分后子服务公开方法不使用 `_` 前缀。
- 架构层：工单域 / 内网远端拉取 / 同步编排拆分
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_remote_sync_service.py` -> `server/module_task/scheduler_maintenance.py` -> 工单外部同步与内网拉取流程；`TicketSyncService` 删除远端拉取方法，继续保留外部同步入库主链路。
- 总共涉及页面：4

## [2026-07-04] INGEST-CODE | 工单拆分后备份分支逻辑审计
- 触发：用户要求检查拆分后后端逻辑是否与备份分支 `master_params_ticket_new` 一致。
- 架构层：工单域 / 同步拆分兼容 / 路由边界
- 创建的页面：`web/public/docs/2026-07-04-ticket-split-backup-branch-logic-audit.md`
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/2026-07-04-ticket-split-compat-fix.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketBitablePullService.run_bitable_pull_services` / `TicketSyncConfigService.build_bitable_pull_time_filters` / 拆分 controller 路由集合 -> 工单域知识页。
- 总共涉及页面：4

## [2026-07-04] INGEST-CODE | 工单前端拆分后备份分支逻辑审计
- 触发：用户要求检查工单管理下面拆分后的前端逻辑是否与备份分支 `master_params_ticket_new` 一致。
- 架构层：工单域 / 工单管理前端拆分 / 同步自动化配置页
- 创建的页面：`web/public/docs/2026-07-04-ticket-frontend-split-backup-branch-logic-audit.md`
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/views/ticket/hooks/useLogViewer.js` / `useTicketList.js` / `useOptions.js` / `syncAutomation/hooks/useSyncConfig.js` -> 工单详情日志拉取、列表查询、AI 分析 Provider 联动、同步自动化保存校验。
- 总共涉及页面：3
## [2026-07-11] INGEST-CODE | 工单统计默认时间、业务周趋势与相似查询缓存化
- 触发：用户要求按既定计划实现工单统计与相似工单第一、二阶段，并同步文档和 wiki。
- 架构层：工单域 / 统计服务 / 相似度服务 / 独立详情页
- 创建的页面：`web/public/docs/2026-07-11-ticket-statistics-similarity-phase1-2.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`flows/ticket-automation-flow.md`、`web/public/docs/2026-07-10-ticket-statistics-usage-guide.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`ticket_statistics_time_util.py` -> `/ticket/statistics/time-config` -> 统计页默认范围；`TicketProcessingStatsService/TicketDao.get_statistics_trend` -> 业务周分桶；`TicketEmbeddingService.get_ticket_embedding_context/vectorize_ticket/search_tickets_by_vector` -> `TicketSimilarityQueryService.search_similar_tickets_by_ticket` -> `TicketService.get_messages_services` -> 详情相似推荐优先复用缓存向量，缺失或过期时刷新向量；`TicketDetailView.vue` -> `ticket/detail/index.vue` -> 独立详情路由不加载列表。
- 总共涉及页面：5

## [2026-07-11] INGEST-CODE | 工单版本治理批量维护与版本统计
- 触发：用户要求按计划继续处理剩余项，当前剩余为版本批量维护和版本统计。
- 架构层：工单域 / 版本治理 / 实时统计聚合
- 创建的页面：`web/public/docs/2026-07-11-ticket-version-governance.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`web/public/docs/2026-07-10-ticket-statistics-usage-guide.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketReleaseBatchUpdateModel/TicketVersionStatisticsQueryModel` -> `TicketReleaseService` -> `ticket_release_controller.py` -> `/ticket/release/batch` 与 `/ticket/release/statistics` -> 工单列表页版本批量维护和版本统计弹窗。
- 总共涉及页面：5

## [2026-07-12] INGEST-CODE | 相似工单系统详情纯净页面
- 触发：用户要求相似工单跳转本地服务详情页后不显示左侧菜单和顶部多余内容，并保留工单描述收起能力。
- 架构层：Web 壳层 / 工单独立详情页
- 创建的页面：无
- 更新的页面：`entities/components/web-shell.md`、`entities/services/ticket-domain.md`、`web/public/docs/2026-07-11-ticket-statistics-similarity-phase1-2.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/router/index.js` 顶层 `TicketDetail` 路由 -> `web/src/views/ticket/detail/index.vue` 纯页面容器 -> `TicketDetailView.vue` 描述/翻译展开状态。
- 总共涉及页面：4

## [2026-07-15] INGEST-CODE | 工单日志查看与搜索资源保护
- 触发：用户要求优先解决日志拉取解压和搜索可能导致卡顿甚至重启的问题，并且不在页面额外展示文件数量。
- 架构层：工单域 / 日志拉取 / 日志搜索配置
- 创建的页面：`web/public/docs/2026-07-15-ticket-log-resource-guard.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`ticket.logPull.storage` 运行保护阈值 -> `TicketLogPullService.get_storage_config_dict` -> `LogService.prepare/search/errors` -> `/ticket/logs/prepare`、`/ticket/logs/search`、`/ticket/logs/errors`。
- 总共涉及页面：4

## [2026-07-15] INGEST-CODE | 工单日志搜索面板与多关键字高亮
- 触发：用户要求继续处理日志搜索面板布局、多关键字搜索、多高亮和日志拉取记录表格横向滚动问题。
- 架构层：工单域 / 日志搜索契约 / Web 控制台
- 创建的页面：`web/public/docs/2026-07-15-ticket-log-search-ui-multikeyword.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/services/web-feature-domains.md`、`entities/data-models/ticket-core-models.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketLogSearchRequestModel.keywords/searchMode` -> `LogService.search_keywords` -> `/ticket/logs/search` -> `useLogViewer` 多关键字表单和多高亮状态 -> `web/src/views/ticket/index.vue` 日志查看器布局与表格滚动；`web/src/views/ticket/logPullRecord/index.vue` 日志拉取记录横向滚动。
- 总共涉及页面：5

## [2026-07-15] INGEST-CODE | 工单日志搜索文本框化与详情区配置
- 触发：用户要求工单详情页日志搜索关键字和高亮文本输入不要使用下拉列表，改为文本框；多个文本用英文逗号或换行分隔；高亮词输入和上下文数量配置移动到日志详情显示区域顶部；顶部高亮摘要过长时省略。
- 架构层：Web 控制台 / 工单日志查看器
- 创建的页面：`web/public/docs/2026-07-15-ticket-log-search-text-input-layout.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/hooks/useLogViewer.js`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`entities/services/web-feature-domains.md`
- 创建的双向链接：0 对
- 变更传播链：日志搜索文本框输入 -> `normalizeLogViewerKeywords` 归一化 -> `/ticket/logs/search` 多关键字契约；详情区高亮文本框 -> `logViewerHighlightKeywords` -> 上下文行高亮渲染。
- 总共涉及页面：5

## [2026-07-15] INGEST-CODE | 工单日志内容流式读取与统计回收
- 触发：用户反馈飞书主动拉取、日志拉取/查看和工单统计后进程内存水位持续升高，要求按有限改动把大数据量链路改为分批、yield 和流式处理，并尽量主动释放内存。
- 架构层：工单域 / 日志拉取 / 统计服务 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/2026-07-15-ticket-memory-watermark-optimization.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketLogPullService.iter_log_pull_content_stream` -> `/ticket/log-pulls/{record_id}/content/stream` -> `streamTicketLogPullContent` -> `web/src/views/ticket/logPullRecord/index.vue` 边接收边显示；`TicketProcessingStatsService` overview/trend 计算结束后删除临时对象并触发 GC。
- 总共涉及页面：2

## [2026-07-16] INGEST-CODE | 工单列表统计枚举筛选编码标签兼容
- 触发：用户反馈工单列表中能看到对应根因分类和解决方式，但按条件搜索查不到数据。
- 架构层：工单域 / 列表筛选 / AI 自动分类归一化
- 创建的页面：`web/public/docs/2026-07-16-ticket-list-stat-filter-code-label-fix.md`
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketLightAiService._normalize_structured_classification_result` -> `ticket.root_cause_type/solution_type` 新数据写编码；`TicketService._build_ticket_list_filter_query` -> `TicketDao.get_ticket_list` 根因分类和解决方式筛选同时匹配编码与历史中文标签。
- 总共涉及页面：3
