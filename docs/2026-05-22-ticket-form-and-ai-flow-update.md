# 工单表单与 AI 流程更新记录

## 本次更新

- 工单新增/编辑表单增加 `工单号` 和 `版本号`，其中工单号要求手动输入且唯一，版本号作为 AI 分析前置条件。
- 工单新增页的项目和模块下拉联动，模块仅在选择项目后可选，切换项目会清空已选模块；模块选项同时兼容 HRM 的项目字段和项目-模块关联表，避免因数据来源不同导致空列表。
- 工单 AI 分析提交改为按工单所属项目 + 版本号自动匹配仓库映射。
- 仓库映射管理拆分为独立菜单页面，路由与菜单路径统一为 `aiRepoMapping`，便于稳定挂载到侧边栏。
- 工单事件写入前增加 JSON 安全序列化与兜底字符串化，避免 `TicketStatusHistory` 等 ORM 对象直接进入 `event_data`。
- AI 分析任务执行过程会在系统日志中输出阶段日志、命令信息和异常堆栈；数据库侧只保留最终失败原因和状态描述，便于定位 Worker 卡点而不污染业务表。
- Windows 开发环境下会优先解析 `codex` 的绝对路径执行，避免服务进程 PATH 与交互终端不一致导致的 `WinError 2`。
- AI 分析 Worker 使用任务级独立 `CODEX_HOME`，并复制当前 Codex 配置后再执行，避免复用用户目录下的临时状态导致的 app-server 初始化失败。
- AI 分析 Worker 的环境变量优先从 Codex 配置目录 `.env` 读取，再回退到当前进程环境变量，避免开发机认证信息只写在 Codex 目录时无法读取。
- AI 分析 Worker 会把 stdout/stderr 写到任务工作区，同时在系统日志里输出环境快照，便于排查后端线程与手工终端的差异。
- AI 分析 Worker 的 `--output-schema` 生成结果已按 Codex 要求补齐根对象 `additionalProperties: false`，避免 `invalid_request_error`。
- 当前线上执行链路调整为：服务端只负责任务编排和结果入库，AI 分析通过 WebSocket 下发给本地 `client_new` agent，由 agent 在本地调用 Codex 并回传结果；服务端增加 `ticket.ai.agent.code` 以便显式指定执行 Agent，未配置时自动取在线 Agent。
- Agent 侧会在执行过程中通过 `ai_analysis_step` / `ai_analysis_status` / `ai_analysis_error` / `ai_analysis_finished` 事件回传阶段日志，服务端只记录系统日志，不落业务表。
- 工单新增时可以勾选是否自动拉取日志，以及是否在日志成功后自动发起 AI 分析；自动化配置会随工单和日志拉取记录一起保存，日志后自动 AI 会携带选定 Agent 编码。
- 日志拉取任务创建后会在成功阶段自动检查 `_automation` 配置并按需发起 AI 分析，避免人工重复提交。
- 工单详情页改为按需加载下方数据，时间线、日志拉取、RCA 和 AI 分析不会在打开详情时一次性全部拉取。

## 影响范围

- 后端：`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/service/ticket_ai_analysis_service.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/modules/ticket/dao/ticket_ai_dao.py`
- 前端：`web/src/views/ticket/index.vue`、`web/src/views/ticket/ai-repo-mapping/index.vue`、`web/src/router/index.js`
- 权限与菜单：`server/modules/ticket/perms.py`

## 验证

- 后端 `compileall` 通过。
- 后端 `ruff check` 通过。
- 前端 `npm run build:prod` 通过。
