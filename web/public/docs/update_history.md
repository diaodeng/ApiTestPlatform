## 2026-07-04

1. 修复工单大文件拆分后的启动期循环引用：`TicketService`、`TicketMessageSyncService` 和 `TicketSyncService` 不再互相顶层导入。
2. 补回拆分遗漏的 `PUT /ticket/{ticket_id:int}/rca` 接口，恢复前端保存 RCA 功能。
3. 清理 `TicketSyncService` 中仅为拆分兼容存在的私有入口门面，配置、主动拉取查询、评论同步、发布状态收敛和 AI 分类统计均由调用方直接依赖对应子服务。
4. 修复主动拉取显式 `createdAfter/created_after` 被默认 1 小时时间窗口覆盖的问题，并恢复飞书多维表格时间过滤旧口径。
5. 将函数内导入和延迟代理改为独立子模块：新增 `TicketCommentCoreService`、`TicketAutoClassificationService` 和 `ticket_common_util`，评论幂等、消息流、AI 分类与用户工具均从主服务中下沉，避免重新形成相互依赖。
6. 删除源码目录中的 `.bak/.bak2` 历史备份文件，避免后续检索和 AI 分析误判仍存在旧私有入口；拆分前逻辑统一以 `master_params_ticket_new` 分支为准。
7. 新增说明文档：`web/public/docs/2026-07-04-ticket-split-compat-fix.md`。
8. 新增 `TicketRemoteSyncService` 承接远端 pending 拉取、payload 转换、本地 revision/time 跳过判断和 ack 回写；远端拉取定时任务直接调用该服务，`TicketSyncService` 不再保留远端拉取转发入口。
9. 新增 `TicketSyncPayloadService` 承接外部同步入库 payload 构造、同步 meta、外部创建时间、来源快照、`log_pull_hints` 和自动拉日志日期解析；`TicketSyncService` 删除对应私有方法并直接调用新服务公开方法。
10. 新增 `TicketSyncPostProcessService` 承接外部同步延后后处理投递、运行入口、系统用户 payload 归一化和后处理执行主体；控制器、主动拉取和 Celery 任务不再调用 `TicketSyncService` 的延后入口。
11. 新增 `TicketSyncAutomationService` 承接字段识别、自动化步骤状态、相似工单、自动拉日志和自动 AI 分析提交；`TicketSyncService` 与延后后处理服务都直接调用该服务。
12. 将工单服务按依赖关系组织为 `service/sync`、`service/ai`、`service/log_pull`、`service/core`、`service/collaboration`、`service/notification`、`service/stats` 子包；所有调用方改为新路径，旧顶层 `modules.ticket.service.ticket_*` 服务入口删除且不保留 re-export shim。
13. 新增 `TicketSyncDeliveryService` 承接同步摘要、pending 拉取、ack 回执和消费者交付状态更新；`/ticket/sync/pending` 与 `/ticket/sync/ack` 控制器直接调用该服务，`TicketSyncService` 不再保留交付状态入口。
14. 新增 `TicketBatchReclassificationService` 承接批量重归类、正则归类批处理和未归类统计；`/ticket/sync/auto-category/reclassify` 与 `/ticket/sync/auto-category/stats` 控制器直接调用该服务，`TicketSyncService` 不再保留手动重归类入口。
15. 新增 `TicketExternalSyncRequestService` 承接外部同步请求读取、JSON/表单兼容、必填字段校验、人员字段拆分和外部字段快照构造；`/ticket/sync/external` 控制器直接调用该服务，`TicketSyncService` 不再保留外部请求归一化入口。
16. 清理 `TicketSyncService` 中已迁移到子服务的常量副本，配置默认值、统计枚举、字段模型、群推送锁和交付状态常量继续由对应子服务维护。

## 2026-07-02

1. 修复工单外部推送、内网拉取、多维表格主动拉取复用入库时项目/模块变更未覆盖旧内部归属的问题：本次外部数据携带项目或模块字段时，按本次解析结果更新；解析不到本地 ID 时清空旧 ID 并保留外部文本。
2. 本次项目字段变化但无法解析商家 ID 时，不再沿用旧 `extra_data.log_pull_hints.vendorId`，避免后续自动拉日志继续使用旧商家。
3. 新增说明文档：`web/public/docs/2026-07-02-ticket-sync-project-module-overwrite.md`。
4. 工单列表页下拉筛选改为多选，后端新增多值查询参数并使用 `IN` 条件过滤；`Ticket` 模型补齐常用筛选组合索引声明。
5. 新增说明文档：`web/public/docs/2026-07-02-ticket-list-multi-filter.md`。

## 2026-07-01

1. 工单分类统计新增“细分问题类型”固定枚举 `problemPatterns`，用于统计内存泄露、280开头券为纸质券规则说明等长期治理问题模式。
2. 工单主表新增 `problem_pattern_*` 字段，AI 分类只从启用的固定细分问题枚举中选择，人工确认后的细分问题不会被 AI 覆盖。
3. 工单列表、编辑、状态流转和详情页接入细分问题筛选、展示和人工确认。
4. 工单统计页新增细分问题分布、趋势统计曲线和趋势明细表，显示配置可单独控制趋势图和趋势表，新增接口 `GET /ticket/statistics/trend`。
5. 新增说明文档：`web/public/docs/2026-07-01-ticket-problem-pattern-trend-statistics.md`。
6. 修复工单统计页趋势区域滚动截断：统计页根容器改为按内容自然撑高，趋势明细表可继续向下滚动查看。
7. 工单统计页时间范围和趋势新增/存量口径改为工单提交时间：外部 `externalCreateTime` 优先，缺失时回退本地 `create_time`；新增说明文档 `web/public/docs/2026-07-01-ticket-statistics-submit-time.md`。
8. 修复飞书多维表格主动拉取分页循环：`records/search` 的 `page_size/page_token` 改为 URL 查询参数，并增加重复 `page_token` 熔断保护；新增说明文档 `web/public/docs/2026-07-01-ticket-bitable-pagination-loop-fix.md`。

## 2026-06-30

1. 补齐非 HTTP 执行链路日志 tid：Celery 定时任务每次执行会生成 `job-xxxxxxxx`，手动执行任务会继承提交请求的 `X-Request-Id`。
2. 工单外部同步延后后处理无论走 Celery 还是 FastAPI 本地后台任务，都会沿用入库请求 tid，便于串联入库、自动化、AI、群推送日志。
3. 工单相似度向量后台重建也继承提交请求 tid；新增说明文档：`web/public/docs/2026-06-30-background-task-trace-id.md`。

## 2026-06-28

1. 帮助中心改为自动读取 `web/public/docs/docs-index.json` 生成菜单，新增 Markdown 文档不再需要手工修改 `about.vue` 才能查看。
2. 前端 Vite 启动和构建时会自动扫描 `web/public/docs` 下的 Markdown 文件，并按标题、文件名和分类生成搜索入口。
3. 新增说明文档：`web/public/docs/2026-06-28-help-docs-auto-index.md`。

1. 工单 AI 分类统计新增状态变更触发配置：可开启状态变更后归类，并配置一个或多个目标状态。
2. 入库和状态触发分类调整防重复规则：状态变更命中配置时，内容变化或任一核心分类字段缺失会重新归类；只有核心分类字段完整且内容未变化时才跳过。
3. 同步配置页新增“状态变更执行”“状态触发条件”“状态变更强制覆盖”配置项，并在自动分类管理中支持输入指定工单 ID 手动归类。
4. 新增说明文档：`web/public/docs/2026-06-28-ticket-ai-classification-status-trigger.md`。

## 2026-06-27

1. 修复飞书话题评论同步时评论人显示为飞书内部 ID 的问题：现在会通过 `sender.open_id` 查询飞书用户详情并写入用户名。
2. 同一用户名解析结果会同时用于当前系统工单评论和多维表格排查过程追加内容。
3. 飞书消息正文中的 `@_user_1` 会按 `mentions` 映射为 `@用户名` 保存到工单系统，并在附件中保留 open_id/user_id，写回多维表格或飞书群时恢复真实 @ 样式。
4. 多维表格 `stepReason` 富文本片段中的 `mention_user_id` 会归一为 `@用户名` 并随评论附件保留，避免多维回流到系统或飞书群时丢失 @ 人员。
5. 新增说明文档：`web/public/docs/2026-06-27-ticket-message-sync-user-name.md`。

## 2026-06-26

1. 修复飞书多维表格主动拉取富文本字段换行丢失：`{"text": "\n", "type": "text"}` 会保留为真实换行，不再被转成空文本或 JSON 文本片段。
2. `description` 和 `stepReason` 等长文本字段会按富文本片段顺序拼接，避免内容挤在一起，并恢复排查过程按日期行拆分评论的能力。
3. 新增说明文档：`web/public/docs/2026-06-26-ticket-bitable-pull-rich-text-newline.md`。

## 2026-06-25

1. 工单详情页日志拉取列表“原始压缩包”新增“复制链接”，可复制外部原始压缩包地址用于邮件粘贴。
2. 日志拉取管理页“下载日志”旁新增“复制链接”，按当前下载策略复制 HTTP 归档地址、原始压缩包地址或需登录态的系统下载接口地址。
3. 新增说明文档：`web/public/docs/2026-06-25-ticket-log-pull-copy-download-link.md`。

1. 修复飞书多维表格主动拉取后群消息有概率无法 @ 人的问题：主动拉取字段映射会从飞书人员对象/数组中优先提取姓名与邮箱，通知服务也兼容嵌套人员对象提取邮箱。
2. 群消息发送前新增 `群推送消息内容` 日志，记录最终渲染正文、发送目标和 @ 解析明细，方便排查消息变量和人员解析来源。
3. 新增说明文档：`web/public/docs/2026-06-25-ticket-bitable-pull-mention-log-fix.md`。

## 2026-06-24

1. 新增通用用户配置表 `sys_user_config` 和当前用户配置接口，按 `userId + configType + configKey` 保存少量 JSON 偏好。
2. 工单列表新增根因分类、解决方式、关闭结果筛选和表格列；表格列支持“列设置”并按用户保存。
3. 工单统计页新增“显示配置”，可按用户决定哪些统计块展示。
4. 新增说明文档：`web/public/docs/2026-06-24-ticket-user-config-columns-stat-blocks.md`。

1. 多维表格主动拉取必填校验改为直接读取“外部工单字段模型”中 `required=true` 的字段，避免历史 `externalSyncRequiredFields` 与字段模型漂移。
2. 字段不全的主动拉取记录会转换失败并计入 `failedCount`，不会入库，也不会触发延后后处理和自动群消息。
3. 新增说明文档：`web/public/docs/2026-06-24-ticket-bitable-pull-required-field-model.md`。

1. 修复飞书多维表格主动拉取优先级兜底：内部优先级来源字段为空、对方优先级有值时，主动拉取会用对方优先级补齐内部优先级。
2. 主动拉取字段映射新增当前处理人别名兼容，并把当前处理人、内部负责人、优先级同步到顶层模型和 `extraData.external_field_mapping`，避免落库后人员为空。
3. 本次只调整主动拉取转换层，不修改外部推送 `/ticket/sync/external` 的归一化逻辑。
4. 新增说明文档：`web/public/docs/2026-06-24-ticket-bitable-pull-priority-person-fallback.md`。

1. 飞书多维表格主动拉取新增 `forceSync` 强制同步参数，开启后忽略本地 `recordId + snapshotHash` 去重，重新入库并触发后处理。
2. 主动拉取字段映射会保留 `ticketVender/ticketModle/internalOwner` 到 `extraData.external_field_mapping`，并同步写入 `projectName/moduleName/internalOwnerName`，避免项目、模块、内部负责人入库为空。
3. 主动拉取自动翻译现在优先读取 `bitablePull.automation.autoTranslate`，不再被全局 `autoTranslateOnSync=false` 误关。
4. 新增说明文档：`web/public/docs/2026-06-24-ticket-bitable-pull-force-sync-field-translate.md`。

1. 修复飞书多维表格主动拉取入库成功后 Celery 延后后处理用户上下文不完整的问题：系统用户载荷补齐 `permissions/roles`，并使用 `userId/userName/nickName` alias，避免 `CurrentUserModel` 校验失败。
2. 延后后处理入口兼容历史只包含 `user` 的任务载荷，旧的 `user_id/user_name/nick_name` 会转换成模型可识别字段。
3. 主动拉取字段映射目标字段兼容 `moduleName/module_name/ticketModel/ticket_model`，统一归一为 `ticketModle`，避免模块字段别名被必填校验误判为缺失。
4. 新增说明文档：`web/public/docs/2026-06-24-ticket-bitable-pull-celery-user-context.md`。

1. 修复“飞书多维表格主动拉取”字段映射区读取表格字段失败的问题：字段预览优先读取飞书字段元数据，不再依赖最近一小时或过滤条件下是否有记录。
2. 字段元数据读取失败时，回退样例记录推断字段，但会清空 `filterFormula` 和 `createdAfter`，避免运行时过滤条件导致 `records=0`。
3. 新增说明文档：`web/public/docs/2026-06-24-ticket-bitable-field-preview-metadata.md`。

1. 修复多维表格主动拉取嵌套 filter 的时间值补齐：嵌套模式在最外层 `children` 追加默认时间窗口，同时递归补齐内部时间字段空值。
2. 扁平 filter 只补齐已有时间字段的空 `value`，不再额外追加默认时间范围。
3. 新增说明文档：`web/public/docs/2026-06-24-ticket-bitable-nested-time-filter.md`。

1. 工单“发起AI分析”弹窗会自动回填 Provider、Agent 和追加提示词；选择绑定 Agent 的 Provider 时自动填入 Agent。
2. AI 分析日志模式默认改为“摘要 + 完整目录”，提交兜底值同步使用 `hybrid`。
3. 手工提交 AI 分析成功后立即关闭弹窗，后台继续短轮询本次任务以保留快速失败提示，不再让弹窗等待轮询结束。
4. 新增说明文档：`web/public/docs/2026-06-24-ticket-ai-analysis-dialog-defaults.md`。

1. 多维表格查询条件文案统一为 `records/search` filter JSON，不再提示填写 `CurrentValue.[字段]` 公式文本。
2. 修正主动拉取配置示例和后端过滤条件错误提示，避免配置人员按旧公式口径填写。
3. 多维表格主动拉取默认时间窗口改为下推到飞书 `records/search` filter：更新时间字段或创建时间字段大于等于当前时间前 1 小时；`createdAfter` 仅作为覆盖窗口下限的兼容入参保留。
4. 新增说明文档：`web/public/docs/2026-06-24-ticket-bitable-filter-json-doc-fix.md`。

## 2026-06-23

1. 日志拉取参数配置新增 `ticket.logPull.parameterExamples`，配置格式为 `[{ "name": "...", "value": "..." }]`。
2. 日志拉取弹窗新增“参数示例”下拉，选择后按当前显示项写入 `modifyTime` 或 `path`。
3. 工单详情和日志拉取管理页打开添加日志拉取弹窗时，会读取 `logPullHints.modifyTime/logDate` 并预填到 `modifyTime`。
4. 新增说明文档：`web/public/docs/2026-06-23-ticket-log-pull-parameter-examples.md`。

1. 修复同一工单多条日志拉取记录查看串记录的问题：指定拉取记录查看时，日志准备、搜索、上下文和异常摘要都按 `recordId` 使用独立目录。
2. 单条日志记录查看目录改为 `data/logs/ticket_{ticketId}/record_{recordId}`；同一记录已准备过时复用，不再重复下载或解压。
3. 从某条日志记录查看器发起 AI 分析时，前端会默认提交该记录的 `logPullRecordId`；未指定时后端仍按当前规则取该工单最新日志记录，版本号缺失时再用最近成功记录兜底。
4. 新增说明文档：`web/public/docs/2026-06-23-ticket-log-record-isolated-view.md`。

1. 发起工单 AI 分析前新增 Agent 在线校验，指定 Agent 未连接服务端时直接返回明确失败原因，不再创建必然失败的后台任务。
2. 工单页提交或重试 AI 分析后会短轮询本次任务终态，后台快速失败时直接弹出任务 `errorMessage`。
3. 全局请求错误提示新增对象归一化，优先读取 `msg/message/errorMessage/detail`，避免页面只显示 `{}`。
4. 新增说明文档：`web/public/docs/2026-06-23-ticket-ai-agent-error-feedback.md`。

## 2026-06-22

1. 外部同步入库时，项目匹配失败会保留 `ticketVender/projectName/merchantName` 原始文本，模块匹配失败继续保留原始模块文本，避免归属展示为空。
2. 手动编辑或后续同步未携带版本号时，不再清空工单已有版本号。
3. 发起 AI 分析时版本号支持可选：手动选择优先；未选择时后端会从工单已有版本号或成功日志记录中提取并回写后再提交分析。
4. 新增说明文档：`web/public/docs/2026-06-22-ticket-ingest-version-ai-fallback.md`。

1. 优化工单日志查看器：搜索结果列表和上下文窗口支持独立放大全屏、还原和最小化。
2. 搜索结果上限改为页面可配置，默认 500，最大 5000；搜索默认只返回命中列表，点击命中行后再加载上下文，避免大量结果时响应体过大。
3. 修复上下文上一段/下一段重复展示上一段数据的问题：后端按窗口大小返回非重叠分页指针，前端只使用服务端指针翻页。
4. 增强日志中文编码兼容：上下文读取支持 UTF-8、UTF-8 BOM、GB18030/GBK 等常见编码；中文关键字搜索走 Python 编码兼容路径。
5. 新增说明文档：`web/public/docs/2026-06-22-ticket-log-viewer-usability.md`。

1. 工单详情页“相似工单”新增“系统详情”和“飞书详情”跳转入口，便于直接查看相似工单完整内容。
2. 新增隐藏路由 `#/ticket/detail/:ticketId`，支持通过 URL 拼接系统工单 ID 独立打开工单详情弹窗。
3. 新增说明文档：`web/public/docs/2026-06-22-ticket-similar-detail-links.md`。

1. 多维表格主动拉取定时任务 `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync` 增加创建时间窗口：默认处理当前时间前 1 小时之后创建的记录，指定 `createdAfter/created_after/startTime/beginTime` 时按指定时间过滤。
2. 主动拉取结果新增 `queriedRecordCount`、`createdAfter`，便于确认飞书原始查询数量和实际过滤窗口。
3. 新增说明文档：`web/public/docs/2026-06-22-ticket-bitable-pull-created-after.md`。
4. 修复飞书多维表格记录详情链接生成错误：主动拉取和按人催办不再把 `record_id` 直接拼成详情页 URL，而是优先使用飞书搜索接口返回的 `record_url/shared_url`。
5. 针对飞书 `records/search` 在实际环境中未返回链接的问题，新增只读补查：搜索结果缺少详情链接时，系统会按 `record_id` 批量调用 `records/batch_get(with_shared_url=true)` 补齐 `shared_url`。
6. 当飞书仍未返回记录详情链接时，系统不再伪造不可访问的 `...?record=record_id` 链接，避免错误链接进入工单详情和催办消息。
7. 新增说明文档：`web/public/docs/2026-06-22-ticket-bitable-record-url-fix.md`。

## 2026-06-21

1. 新增“飞书多维表格主动拉取”能力：定时任务可按条件查询多维记录，经字段映射后复用外部推单链路入库。
2. 新增“多维表格公共配置”，工单汇总统计、按人催办、外部推送邮箱补全与主动拉取默认继承该配置，局部配置可覆盖。
3. 新增“外部工单字段模型”，外部同步必填字段下拉与主动拉取映射目标字段统一读取该模型。
4. 主动拉取增加 `recordId + snapshotHash` 去重，同一记录内容未变化时跳过，不再反复递增工单同步 revision。
5. 新增说明文档：`web/public/docs/2026-06-21-ticket-bitable-pull-and-config-unify.md`。

1. 工单列表页新增“模块Code”筛选，选项动态从后端模块接口获取；未选项目时显示全部有效模块 code，选中项目后收敛到当前项目下的 code。
2. 工单统计页新增“模块Code”多选筛选，继续支持项目、模块联合过滤；统计接口新增 `moduleCodes` 参数并与现有项目、模块条件共同生效。
3. 工单模块选项接口补充返回 `moduleCode` 字段，前端统一基于后端返回结果生成模块 code 下拉枚举。
4. 模块管理中的 `moduleCode` 唯一性改为“同一项目下唯一”，不同项目允许复用相同模块 code。
5. 新增说明文档：`web/public/docs/2026-06-21-ticket-module-code-filter-and-project-unique.md`。

## 2026-06-18

1. 工单统计页顶部新增项目、模块多选筛选；模块候选按已选项目加载，统计接口支持 `projectIds/moduleIds` 逗号分隔参数。
2. 工单统计页和工单列表页的模块筛选支持未选项目时选择全部模块；选择一个或多个项目后，模块候选收敛为所选项目下的模块。
3. 工单统计接口改为在线程池执行同步聚合查询，避免大统计阻塞 FastAPI 事件循环。
4. 新增说明文档：`web/public/docs/2026-06-18-ticket-statistics-project-module-multiselect.md`。

1. 修复工单 AI Agent 创建分支 worktree 时，目标固定目录不存在但同分支已登记在旧工作区路径下会报 `already used by worktree` 的问题；Agent 现在会先读取 `git worktree list --porcelain` 并复用已登记且分支校验通过的目录。
2. 新增说明文档：`web/public/docs/2026-06-18-ticket-ai-worktree-registered-branch-reuse.md`。

1. 工单列表“日志拉取”列调整为“处理状态”：优先展示最新 AI 分析状态，其次展示最新日志拉取阶段。
2. 处理状态筛选枚举新增日志拉取中间态，支持按待执行、提交申请中、轮询处理中、下载中、解析中以及“日志拉取中”筛选。
3. 工单详情页描述与翻译支持展开/收起，默认展开描述、收起翻译；收起时保留一行内容预览，减少长描述占用且避免误判为空。
4. 评论从历史页二级 tab 提升为详情页一级 tab，位于历史前；新增评论列表接口并改为点击评论 tab 时按需请求。
5. 新增说明文档：`web/public/docs/2026-06-18-ticket-list-process-status-and-comments-lazy.md`。

## 2026-06-17

1. 按人催办定时任务支持任务级覆盖飞书参数：`appToken/tableId/viewId/filterFormula/personField/timeField/dataSource/pageSize`，任务非空值优先，否则继续走全局同步配置。
2. 修复全员催办分支未返回结果、单邮箱字符串不兼容，以及 `filterFormula` 被 JSON 解析导致普通公式文本失败的问题。
3. 新增说明文档：`web/public/docs/2026-06-17-ticket-person-reminder-task-override.md`。

1. 统一工单分类 AI 配置职责：Provider 和提示词正文统一在系统管理的 AI Provider / AI 提示词中维护，工单同步配置页只选择 Provider 编码、提示词编码和场景开关。
2. 清理旧默认模板 `ticket_category_classify_default`，分类统计默认值统一使用 `ticket_stat_classify_default`；历史 `aiClassification.promptContent` 不再作为新编辑入口，但保存配置时会保留并作为旧环境兜底，避免现有业务因配置保存突变。
3. 工单同步配置页按基础配置、拉取配置、推送配置、手动配置标识区块，批量重归类提示词改为模板下拉选择。
4. 分类统计自动处理标题、描述、最近评论和当前字段，并回填 `category_name`、`issue_type_id/issue_type_name`、`module_name`、`severity`、`root_cause_type`、`solution_type`、`resolution_code/resolution_name`、`root_cause`、`solution`、`is_problem`。
5. 新增说明文档：`web/public/docs/2026-06-17-ticket-classification-config-unification.md`。

1. 工单同步配置页“统计未归类工单”明确为只统计不自动归类；执行归类仍使用“按当前配置重归类”或“强制重归类全部”。
2. 自动归类链路补充详细服务日志：入口参数、筛选结果、逐条处理、跳过原因、AI 配置、模型执行、字段回填和汇总结果均可从日志排查。
3. 新增说明文档：`web/public/docs/2026-06-17-ticket-auto-category-debug-logs.md`。

1. 工单相似度检索改为配置化 Provider：默认保留 `local_hash`，新增 `qdrant` Provider 和兼容 OpenAI Embedding 的配置入口。
2. 相似工单文本扩展为标题、描述、AI 摘要、根因、解决方案和 RCA；关键词命中改为弱加分，不再直接给 100% 相似度。
3. 新增 `GET /ticket/similarity/config` 和 `POST /ticket/similarity/rebuild`，支持初始化配置和批量重建历史工单向量。
4. 新增 `PUT /ticket/similarity/config` 和相似工单配置菜单页，可视化维护 Provider、Embedding、Qdrant、参与字段和 `sceneTriggers` 场景开关。
5. 外部同步、远端拉取、手动新增、手动编辑、Excel 导入和关闭知识沉淀链路会按 `sceneTriggers` 自动刷新工单向量。
6. 新增说明文档：`web/public/docs/2026-06-17-ticket-similarity-qdrant-provider.md`。

1. 工单 AI Agent 执行代码分析改为按仓库映射分支隔离：优先校验 `localRepoPath` 当前分支，未配置时按 `repoUrl + branchName` 自动创建固定 Git worktree。
2. Agent 不再在已有目录上自动 checkout；提示词、请求快照和阶段事件会记录实际分析代码目录和当前分支，分支不匹配时明确失败。
3. 当历史映射的 `localRepoPath` 指向普通 clone 且当前分支不等于 `branchName` 时，Agent 会优先基于该本地仓库创建分支固定 worktree，复用原项目 `.git/config`、remote 和本地 Git 凭据，不再直接在原项目中失败。
4. 新增说明文档：`web/public/docs/2026-06-17-ticket-ai-agent-worktree-branch-isolation.md`。

1. 工单专题信息统计任务 `module_task.scheduler_maintenance.ticket_topic_stats_report` 改为直接调用飞书开放 API：用任务参数 `appId/appSecret` 获取 tenant token，拉取群消息和线程回复后统计专题工单信息，并通过飞书应用发送交互卡片。
2. 移除该任务对 `lark-cli`、`larkCliBin` 和机器人 `webhook` 的依赖；新增 `receiveChatIds/appChatIds` 作为发送目标，未配置时默认发送到 `sources` 中的群。
3. 新增说明文档：`web/public/docs/2026-06-17-ticket-topic-stats-feishu-api.md`。

1. `ticket.sync.automation` 新增 `aiClassification` 可视化配置，支持分别控制外部同步入库、远端拉取入库、手动创建入库是否执行 AI 分类统计。
2. AI 分类统计回填 `ticket` 主表结构化字段，执行摘要写入 `extra_data.ai_classification`；同文本成功结果会自动防重，手动强制重归类仍可覆盖。
3. 新增说明文档：`web/public/docs/2026-06-17-ticket-ai-classification-statistics.md`。
4. AI 分类统计上下文纳入最近评论，防重 hash 同步包含评论内容；默认 prompt 分工调整为 system 放规则、user 放业务上下文。
5. `aiClassification` 新增 `promptContent`，未配置自定义提示词时后端自动回填内置默认提示词，配置页进入后可直接基于默认内容编辑；AI 执行时该内容只作为 system prompt，工单标题、描述和评论仍放入 user prompt。

## 2026-06-16

1. 修复工单新增/编辑保存慢时阻塞其他接口的问题：`POST /ticket`、`PUT /ticket` 在 `async def` 内使用 `run_in_threadpool` 执行业务保存，并在线程内创建独立数据库会话。
2. 工单编辑弹窗保存按钮增加提交中状态，接口响应前“确定”和“取消”按钮不可再次点击，避免重复提交。
3. 新增说明文档：`web/public/docs/2026-06-16-ticket-save-nonblocking-submit-lock.md`。

1. 优化外部推单多维表格邮箱补齐：同一工单已成功同步过同一个 `recordId` 时，不再重复请求飞书多维表格。
2. 成功补齐状态写入 `extra_data.external_sync.bitableEmailSync`；推送侧仍由 `externalSyncBitable.enabled` 控制，拉取侧由 `remoteSync.enabled` 控制且不会重复查多维，只消费远端已携带邮箱。
3. 新增说明文档：`web/public/docs/2026-06-16-ticket-bitable-email-sync-idempotent.md`。

1. 修复日志拉取下载入口阻塞服务的问题：工单详情页“原始压缩包”改为浏览器直接打开 `commandResultUrl`，不再由后端代理下载外部大文件。
2. 工单详情页“归档地址”和日志拉取管理页“下载”在目标为 HTTP 地址或仅存在原始地址时直接走浏览器下载；本地/FTP 归档仍保留后端鉴权下载。
3. 外部推送、pending 拉取、ack、日志内容读取、日志列表、重新下载等 `async def` 内的同步服务调用改为 `run_in_threadpool`，避免同步 SQLAlchemy、requests、文件/FTP 操作阻塞事件循环。
4. 新增说明文档：`web/public/docs/2026-06-16-ticket-log-pull-download-nonblocking.md`。

1. 新增飞书 `stepReason` 排查过程评论同步：按 `20260616 人员：` 或 `20260616：` 拆分为外部评论，并按 `segmentIndex` 生成幂等键避免重复追加。
2. 评论表扩展来源和附件字段，区分本地评论与同步评论；本地评论不会被外部同步覆盖，内网拉取会同步公网外部评论。
1. 修复公网 pending 拉取候选窗口过小导致内网 10 点后拉不到新工单的问题：`get_tickets_for_sync` 改为分批扫描候选数据，避免旧工单占满前 200 条后新数据无法进入同步判断。
2. 排查确认 `dev` 为公网、`prod` 为内网；公网数据已入库且可发布，内网定时任务正常每分钟执行，根因在公网 `/ticket/sync/pending` 返回为空。
3. 新增说明文档：`web/public/docs/2026-06-16-ticket-sync-pending-scan-window-fix.md`。

3. 新增说明文档：`web/public/docs/2026-06-16-ticket-step-reason-comment-sync.md`，新增迁移 SQL：`server/sql/20260616_ticket_comment_sync_source.sql`。

## 2026-07-01

1. 修复工单列表排序接口报错 `Boolean value of this clause is not defined`：后端排序表达式不再使用 Python `or` 判断 SQLAlchemy 表达式，改为显式 `None` 判断。
1. 工单列表新增表头排序：点击表头会按对应字段做服务端分页排序，默认按工单提交时间倒序。
2. 当前列表展示列均可排序：工单编号、标题、状态、处理状态、项目、模块、工单类型、问题性质、根因分类、解决方式、关闭结果、细分问题、优先级、来源、三类负责人、提交时间、创建时间。
3. 新增说明文档：`web/public/docs/2026-07-01-ticket-list-header-sort.md`。

1. 修复工单同步在服务重启后可能卡在 `processing_ai/publish_ready=false` 导致内网拉不到新版本的问题：pending 拉取前会在无活动 AI 任务时自动恢复发布状态。
2. 修复内网远端拉取失败后远端 revision 被永久标记已交付的问题：failed 回执不再推进 `delivered_revision`，下次拉取可继续重试同一版本。
3. 新增说明文档：`web/public/docs/2026-06-16-ticket-sync-restart-retry-fix.md`。

1. 优化工单详情弹窗顶部基础信息布局：描述改为表格下方独立整行显示，避免长描述撑变形。
2. 工单详情顶部基础信息表格的灰色标签列不再换行，避免短信息行被标签换行抬高。
3. 新增说明文档：`web/public/docs/2026-06-16-ticket-detail-summary-description-layout.md`。
4. 调整描述区域为自动展示全部内容，不再限制高度滚动。
5. 工单详情描述区新增“翻译”按钮，复用自动翻译 Provider 和提示词配置；已保存的原文与 AI 翻译在详情页分开展示，缺配置时点击翻译会提示先配置翻译能力。

1. 修复日志拉取下载来源语义：后端下载接口新增 `source=auto/service/original`，管理页“下载日志”优先本服务归档文件，缺失时回退外部原始地址。
2. 工单详情页日志拉取列表新增商家、门店、POSID 三列，便于同一工单区分不同 POS 的拉取记录。
3. 工单详情页“归档地址”改为从本服务下载归档文件，“原始压缩包”改为从外部原始路径下载。
4. 新增说明文档：`web/public/docs/2026-06-16-ticket-log-pull-download-source-fix.md`。

1. 优化日志拉取弹窗：商家、门店、POSID 改为整行铺满；日志类型只显示 `modifyTime`，数据库类型只显示 `path`；文件上限和压缩包上限移动到时间方式之前。
2. 日志切割改为显式开关：只有开启“切割日志”才显示时间方式和时间字段，关闭时按整包下载处理且不提交时间范围。
3. 保存方式默认本地；自动 AI 关闭时隐藏 Agent/Provider；通知配置默认关闭，开启后才显示推送项与成功/失败开关。
4. 修复工单详情页手工日志拉取未提交 `notifyConfig` 导致配置后不通知的问题；后端在日志拉取成功、失败和异常时按记录通知配置推送。
5. 新增说明文档：`web/public/docs/2026-06-16-ticket-log-pull-dialog-layout-notify-fix.md`。

1. 优化工单编辑回填：所属模块不在当前项目模块选项中时，编辑弹窗会原样显示模块文案，保存时继续保存该文案；只有手动选择现有模块后才改为标准模块 ID 与名称。
2. 优化工单编辑人员展示：`1线人员` 与 `内部负责人` 不再额外展示重复的名称输入框；无法匹配现有用户时在人员选择框内直接显示原始用户名文案，保存时保留原文，手动改选后按用户信息保存。
1. 修复工单列表编辑后模块显示为空的问题：编辑弹窗回填项目时不再误触发项目切换清空模块，模块下拉变更和提交前都会按 `moduleId` 补齐 `moduleName`。
2. 修复工单类型列编辑前显示成旧分类/模块文案的问题：工单类型展示只读取 `issue_type_name` 或命中的 `issue_type_id` 枚举，不再回退历史 `category_name`。
1. 工单分类统计维度拆分为独立字段：新增 `issue_type_id/issue_type_name/root_cause_type/solution_type/resolution_code/resolution_name`，并继续复用 `status` 表示流程状态、`module_name` 表示业务域、`is_problem` 表示是否真实问题。
2. `ticket.sync.automation` 新增 `statClassification` 可视化配置，支持维护工单类型、根因分类、解决方式和关闭结果枚举，默认值按本次设计初始化。
3. 工单列表、表单、状态流转、RCA 和统计页接入新枚举配置；统计页新增工单类型、是否真实问题、根因分类、解决方式、关闭结果统计，旧分类统计保留兼容。
4. 新增说明文档：`web/public/docs/2026-06-16-ticket-classification-statistics-fields.md`。

## 2026-07-04

1. 继续拆分工单同步服务：新增 `TicketBitablePullService` 承接飞书多维表格主动拉取字段预览、记录转换、快照去重和调度执行。
2. `TicketSyncService` 删除主动拉取相关方法，不保留转发 shim；同步配置页字段预览和主动拉取定时任务改为直接调用新服务。
3. 对照 `master_params_ticket_new` 保留主动拉取业务语义，字段映射、富文本换行、必填校验、快照去重、强制同步和延后后处理行为不变。
4. 新增 `TicketSyncNotificationJobService` 承接人员催办和汇总统计通知任务编排，控制器和定时任务直接调用该服务，`TicketSyncService` 不再保留通知任务门面。
5. 固化项目实现边界规则到 `AGENTS.md` 和 `web/public/docs/2026-07-04-project-implementation-boundary-rules.md`，明确 controller/service/dao/util/scheduler 的职责边界和禁止转发 shim。
6. 约束拆分后子服务的公开方法命名：外部调用的方法不再使用 `_` 开头；主动拉取子服务和通知工具公开方法已按该规则调整。
7. 新增 `TicketExternalBitableEmailService` 承接外部推送多维表格邮箱补齐逻辑，保留 `recordId` 幂等跳过、字段查询、邮箱脱敏日志和 `external_field_mapping` 写入语义。
8. 新增 `TicketRemoteSyncService` 承接远端拉取同步，保留 `remoteSync` 配置归一、字段别名兼容、本地版本跳过和远端 ack 结构；调度器直接调用新服务。
9. 补充说明文档：`web/public/docs/2026-07-04-ticket-split-compat-fix.md`。
10. 对照备份分支 `master_params_ticket_new` 审计拆分后逻辑：恢复主动拉取自动时间窗口、filter 连接符和嵌套 filter 追加语义；删除拆分 controller 中的重复路由注册，当前工单路由集合与备份分支一致。
11. 新增说明文档：`web/public/docs/2026-07-04-ticket-split-backup-branch-logic-audit.md`。
12. 对照备份分支 `master_params_ticket_new` 审计工单管理前端拆分逻辑：恢复日志拉取提交/预填/下载/查看器、列表查询参数、选项加载、AI Provider 联动和同步自动化保存校验语义。
13. 新增说明文档：`web/public/docs/2026-07-04-ticket-frontend-split-backup-branch-logic-audit.md`。

## 2026-06-15

1. 专题工单会话状态统计任务 `module_task.scheduler_maintenance.ticket_topic_stats_report` 新增分类与状态关键词补充参数：`couponKeywords/stampKeywords/memberKeywords/promoKeywords/closedKeywords/conclusionKeywords`，任务参数未传时继续使用代码内置关键词，传入时与内置关键词合并后参与专题分类和状态判断。
2. 补充说明文档 `web/public/docs/2026-06-15-ticket-topic-stats-scheduler.md`，新增任务参数示例和关键词合并说明。
1. 修复内网远端拉取公网工单后状态和内部负责人未按内网配置生效的问题：`remote_pull` 入库时会使用内网 `statusMappings` 映射远端状态文本，并通过 `assigneeMappings`、邮箱或姓名解析内部负责人。
2. 远端 pending 工单转换模型时补齐 `internalOwnerName/internalOwnerEmail`，兼容公网 `extraData.external_field_mapping` 快照，避免外部推送进入公网后的内部负责人跨环境丢失。
3. 新增说明文档：`web/public/docs/2026-06-15-ticket-remote-pull-status-owner-mapping.md`。
1. 修复工单详情页 `协同/AI` 追问只保存消息、不明显触发 AI 分析的问题：后端将追问正文作为 `extraInstruction` 下发给 AI 任务，前端按 `aiSuccess/aiMessage` 展示触发结果并刷新任务历史。
2. 新增说明文档：`web/public/docs/2026-06-15-ticket-message-run-ai-trigger-fix.md`。
1. 优化工单 AI 整包日志分析：Agent 解压完整日志包后先生成 `logs_ai_digest.txt`，prompt 默认只要求优先读取摘要，避免 Codex 无目标通读几十 MB 原始日志导致 token 消耗过高。
2. 摘要保留命中片段的文件名和行号，必要时仍可让 Codex 定点读取 `source_logs/` 原始日志，不影响完整日志复核能力。
3. 新增说明文档：`web/public/docs/2026-06-15-ticket-ai-log-digest-optimization.md`。
1. 修复 `client_new` Agent 调用 Codex 执行工单 AI 分析时误用 Codex 桌面应用的问题：解析 Worker 时跳过桌面应用目录，新增 `ticket_ai_codex_cli_path` 显式 CLI 路径配置，并在 Windows 下隐藏子进程 cmd 窗口。
2. 优化 Agent Worker 失败返回：只返回错误摘要与 stdout/stderr 文件路径；Codex 账号并发限制会明确提示 `Concurrency limit exceeded`，不再把整段业务日志内容回传为错误消息。
3. 新增说明文档：`web/public/docs/2026-06-15-agent-codex-cli-runtime-fix.md`。
1. 修复工单详情页和日志拉取记录页点击“重新拉取”时，历史记录因 `command_content` 格式或空时间范围字段导致恢复参数失败的问题。
2. 重新拉取参数恢复兼容 JSON 字符串、驼峰/下划线字段名和历史空时间范围；仍要求至少可恢复 `modifyTime` 或 `path`，避免提交不完整外部命令。
3. 新增说明文档：`web/public/docs/2026-06-15-ticket-log-pull-retry-payload-fallback.md`。
1. 将 API Key 最后使用时间/IP 审计更新改为非阻断操作：鉴权仍校验 API Key 有效性，`last_used_ip/last_used_time` 使用独立会话尝试更新，失败只记录 warning，不再影响远端推单入库。
2. 新增说明文档：`web/public/docs/2026-06-15-api-key-usage-audit-nonblocking.md`。
1. 修复工单状态流转候选项不随工作流配置变化的问题：工单列表页加载 `/ticket/workflow/config`，状态筛选、列表展示、详情展示和时间线优先使用动态工作流状态节点。
2. 状态流转弹窗改为按当前状态过滤已配置流转规则，只展示可达目标状态；新增状态节点后必须配置对应流转规则才会出现。
3. `/ticket/workflow/config` 读取权限兼容 `ticket:ticket:status`，保证只有流转权限但没有工作流配置权限的用户也能获取流转候选项。
4. 修复公网外部推单更新已有工单时 `ticketModle` 变化不覆盖旧模块的问题：新模块文本未命中有效 HRM 模块 ID 时会清空旧 `module_id` 并覆盖 `module_name`；远端 pending 工单拉取再入库也会从 `ticketModle/ticketModel/ticket_model` 或 `extraData.external_field_mapping.ticketModle` 回填本地模块名称。
5. 新增说明文档：`web/public/docs/2026-06-15-ticket-workflow-dynamic-status-and-remote-module.md`。
1. 新增专题工单会话状态统计定时任务：`module_task.scheduler_maintenance.ticket_topic_stats_report`，将外部脚本的飞书群拉取、Ticket 提取、专题分类、会话状态判断和飞书卡片发送逻辑迁入项目。
2. 专题统计任务支持通过定时任务参数配置日期范围、飞书群来源、`lark-cli` 路径、webhook、关键字和分页大小；日志按步骤记录来源处理、分页拉取、命中/跳过原因、汇总结果和发送返回。
3. 补充专题统计定时任务说明文档：`web/public/docs/2026-06-15-ticket-topic-stats-scheduler.md`，包含完整任务参数示例和验证记录。
1. 修复已有工单重复外部推送时所属模块名称为空的问题：当外部 `ticketModle` 已解析出模块文本，但本地模块 ID 无效或映射未命中时，入库会兜底写入 `module_name`，不会写入错误的 `module_id`。
2. 同步元数据 `extra_data.external_sync.source.moduleName` 同步记录识别到的模块文本，便于排查外部推送、群消息和统计链路。
3. 补充外部推送按 `recordId` 查询飞书多维表格邮箱的诊断日志：记录是否调用飞书、返回字段名、三类邮箱字段提取结果、失败原因和最终写入状态；日志不输出飞书密钥，邮箱脱敏展示。

## 2026-06-14

1. 梳理并收敛工单同步映射边界：第三方直推 `/ticket/sync/external` 仍按外部字段契约执行项目、模块、商家、状态、人员和门店映射；远端拉取入库不再执行外部映射，改为使用远端返回的内部字段、业务码、版本号和日志拉取提示字段。
2. 外部推送入口明确字段契约，只接受约定字段的驼峰/下划线写法；字段不符合契约时不再猜测，缺少必填字段直接 422。
3. 外部推送入库时继续完整保留原始请求到 `extraData.raw_payload`，并生成 `extraData.external_field_mapping`，供通知模板、人员邮箱解析和问题排查复用。
4. 保留既有后处理能力：外部推送和远端拉取仍支持翻译、标题/分类、自动日志拉取、自动 AI 分析、群推送、发布就绪状态和回执。
5. 修复外部同步入库时系统模块识别兼容性问题：`ticketModle` 现在同时兼容 `moduleName/module_name/moduleCode/module_code`，避免外部系统字段改名后模块丢失。
6. 修复工单群消息默认模板缺少门店信息的问题：默认群消息模板新增 `门店：${store_info}`，同步后发群可直接看到门店。
7. 收紧远端拉取的跨环境 ID 边界：`remote_pull` 下项目/模块只通过 `projectCode/moduleCode` 关联本地 ID，人员只通过邮箱或名称关联本地用户；未命中时只保留文本，不使用远端 ID。
8. 外部推送人员字段语义调整：`reporterName` 写入报告人/1线处理人，`currentAssigneeName` 写入当前处理人，`internalOwner` 写入内部负责人；三类人员均按 `assigneeMappings` 和多维邮箱解析本地用户，失败时只保留名称。
9. 外部推送新增 `externalSyncBitable` 配置，可按 `recordId` 查询飞书多维表格固定字段邮箱，并保存到 `extraData.external_field_mapping` 供群消息 @ 人复用。

## 2026-06-13

1. 工单群消息新增模板内显式 `@` 变量：`sync_external_ticket` 场景会补齐 `report_at`、`reporter_at`、`assignee_at`、`mention_at` 等变量，模板中可直接控制提单人、当前处理人或汇总 `@` 内容；若模板未显式输出 `@` 标签，发送链路仍会自动回退追加解析出的人员 `@`。
2. 工单同步自动化新增 `ticket.sync.automation.externalSyncRequiredFields` 配置，用于控制 `/ticket/sync/external` 的必填字段校验列表，支持按当前对接阶段动态收紧或放宽校验要求。
3. 修复工单同步配置页与通知模板中文乱码：恢复“远端同步链接”“工单汇总统计通知”等页面文案，修正汇总统计模板绑定；“外部同步必填字段”补齐可见候选项并保留自由输入能力。
4. 恢复误删的“飞书统一凭证”“工单群消息推送”配置块；`syncAutomation` 页面相对稳定版本仅保留新增字段配置与模板变量相关差异，不再包含额外区块删除。
