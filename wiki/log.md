---
title: 操作日志
type: log
source_type: mixed
created: 2026-05-20
updated: 2026-05-20
---

# 操作日志

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
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

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
