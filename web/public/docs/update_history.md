## 2026-06-22

1. 修复飞书多维表格记录详情链接生成错误：主动拉取和按人催办不再把 `record_id` 直接拼成详情页 URL，而是优先使用飞书搜索接口返回的 `record_url/shared_url`。
2. 针对飞书 `records/search` 在实际环境中未返回链接的问题，新增只读补查：搜索结果缺少详情链接时，系统会按 `record_id` 批量调用 `records/batch_get(with_shared_url=true)` 补齐 `shared_url`。
3. 当飞书仍未返回记录详情链接时，系统不再伪造不可访问的 `...?record=record_id` 链接，避免错误链接进入工单详情和催办消息。
4. 新增说明文档：`web/public/docs/2026-06-22-ticket-bitable-record-url-fix.md`。

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

## 2026-06-15

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
