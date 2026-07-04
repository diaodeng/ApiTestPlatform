# 2026-07-04 工单前端拆分后备份分支逻辑对齐审计

## 背景

本次检查以备份分支 `master_params_ticket_new` 为业务语义基准，核对当前工单管理前端拆分后的逻辑是否一致。重点范围为：

1. `web/src/api/ticket/*.js` 工单 API 拆分。
2. `web/src/views/ticket/index.vue` 与 `web/src/views/ticket/hooks/*.js`。
3. `web/src/views/ticket/syncAutomation/index.vue` 与 `web/src/views/ticket/syncAutomation/hooks/useSyncConfig.js`。

## 对齐结果

1. 工单 API 拆分后与备份分支一致：旧 `ticket.js` 中 80 个导出函数在拆分 API 文件中均存在，函数名、请求 method 和 url 未发现差异。
2. 工单管理页函数集合与备份分支一致：对照旧 `index.vue` 与当前 `index.vue + hooks`，未发现旧函数遗漏。
3. 恢复日志拉取弹窗和日志查看器逻辑：
   - 表单字段恢复为 `commandDataType/modifyTime/path/cutLogEnabled/logBeginTime/logEndTime/logPointTime/storageMode/autoAiEnabled/notifyConfig` 等备份分支字段。
   - `addTicketLogPull`、`listTicketLogPulls` 恢复按 `ticketId + payload/query` 调用。
   - 恢复工单详情预填商家、门店、POSID、日期，以及按项目映射回填商家编号。
   - 恢复日志拉取提交校验、通知配置归一、自动 AI 参数、记录刷新、重新拉取、重新下载、删除和下载来源策略。
   - 恢复日志查看器 `prepare/search/errors/context` 的请求参数和上下文翻页行为。
4. 恢复工单列表查询逻辑：
   - 多选筛选项继续按逗号分隔提交，避免数组被 GET 序列化成 `field[0]`。
   - 人员筛选字段恢复为 `currentAssigneeIds/firstLineAssigneeIds/internalOwnerIds`。
   - 默认排序恢复为 `submitTime desc`，清空排序时回到该默认值。
   - 列配置恢复使用 `ticket/ticket_list_columns`，保存结构为 `{ visibleColumns: [...] }`。
   - 自然语言搜索恢复使用当前分页大小作为 limit。
   - 外部详情链接解析恢复兼容 `syncSummary`、`extraData.externalSync.source` 等来源。
5. 恢复选项加载逻辑：
   - 版本选项恢复从 `listTicketAiRepoMappings` 获取，不再误用项目商家映射数据。
   - 查询模块选项恢复未选择项目时加载全部模块，选择项目时在前端按项目过滤。
   - 表单模块和版本选项恢复备份分支的数据源和返回行为。
   - 统计分类选项恢复读取 `issueTypes/rootCauseTypes/solutionTypes/resolutions/problemPatterns`。
6. 恢复 AI 分析 Provider 联动：`useOptions` 只解析 Provider 绑定的 Agent，页面层继续写入 `aiAnalysisTaskForm.agentCode`，默认提示词编码继续从当前 `detail` 解析。
7. 同步自动化页函数集合与备份分支一致；同时恢复保存链路中的实际语义：
   - JSON 数组配置非法时抛错并阻止保存，不再静默回退为空数组。
   - `validateElForm` 在表单 ref 缺失时直接返回通过，避免 Promise 不结束。
   - 主动拉取字段映射新增/删除恢复数组保护。
   - 日期时间归一化无法匹配标准格式时保留原文本，不再截断到 19 位。

## 验证

1. 使用脚本对比 `master_params_ticket_new:web/src/api/ticket/ticket.js` 与当前 `web/src/api/ticket/*.js`，确认 `old funcs=80 current split funcs=80 missing=[] added=[] changed=[]`。
2. 使用脚本对比 `master_params_ticket_new:web/src/views/ticket/index.vue` 与当前 `index.vue + hooks`，确认旧函数无遗漏。
3. 使用脚本对比 `master_params_ticket_new:web/src/views/ticket/syncAutomation/index.vue` 与当前 `syncAutomation/index.vue + hooks`，确认旧函数无遗漏。
4. 执行 `cd web; npm run build:prod`，生产构建通过。构建仍存在项目既有警告：`/config.js` 非 module 脚本、`src/utils/tools.js` 使用 `eval`、部分 chunk 超过 500 kB。

## 注意事项

1. `useOptions` 中跨状态能力只保留纯解析结果，实际写入表单状态留在页面层，避免 hook 之间互相持有对方状态。
2. 后续继续拆分前端时，需要同时检查模板事件引用、API 调用签名、表单字段名、保存配置结构和错误处理语义，不能只看函数名是否存在。
