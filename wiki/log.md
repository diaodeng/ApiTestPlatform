## [2026-09-07] FIX | 相似工单检索内存优化与监控缺陷修复（生产 OOM 重启排查落地）

- 触发：2026-09-07 12:31 生产 fastapi 进程被 cgroup 内存上限（1400MB）内核 OOM Kill，supervisor 自动拉起。VM 指标 + 日志 + 数据库交叉排查确认：直接诱因为 12:31:49 Agent 返回工单 AI 分析结果（raw_output 约 7.5MB）处理时瞬时越限；内存放大点包括相似工单检索全量加载向量（2664 条 × 1024 维 JSON，yield_per 迭代下 session 身份映射累积、GC 后单次 +31MB 不回落）、fastapi 09:51 一次 +309MB 未归因阶跃；排查过程还暴露三个观测缺陷（详见下）。
- P1 修复（相似检索内存）：`ticket_embedding_service` 三处向量扫描入口（`_search_embedding`、`search_embedding_records_by_vector`、`_search_local_hash`）统一收敛到新方法 `_score_embedding_pages`——按 `EMBEDDING_SCAN_PAGE_SIZE=500` 分页（`TicketDao.iter_ticket_embedding_pages`，独立 LIMIT/OFFSET 查询 + `object_ids` 白名单），每页处理完 `expire_all` 释放 session 实体；新增信号预筛 `_resolve_signal_prescreen_ids`：检索文本提取到错误码/Trace ID/Request ID（复用画像服务新增的 `TicketSimilarityProfileService.extract_signal_values`）时按 `ticket_similarity_signal` 索引筛候选，仅对候选做向量比对，可通过相似度配置 `signalPrescreenEnabled: false` 关闭（默认开启），无信号自动退回全量分页扫描。生产库只读实测：结果与旧逻辑完全一致；全量分页 11.45s / GC 后 +11MB（旧 yield_per 10.82s / +17MB，历史多次累积至 +31MB）；带错误码预筛 0.14s / +1MB。
- P2 修复（观测缺陷）：① `utils/metrics/process.py` cgroup v1 分支 `oom/oom_kill` 事件计数此前硬编码 0（本次排查无法用指标证明 OOM 的原因），现从 `memory.oom_control` 读真实 `oom_kill`（新增 `_read_v1_oom_kill`）；② `ticket_ai_analysis_service`/`ticket_log_pull_service`/`runner_service` 三处 `get_task_memory_observer("api")` 硬编码把 Worker 进程任务观测器改成 role=api，导致 `qtr_task_*` 指标与 fastapi 进程混在同一序列、`event=task_memory_*` 日志 pid 与 role 不符，全部改为无参调用按 `QTR_METRICS_ROLE` 环境变量判定（`task_memory.get_task_memory_observer` 文档注明业务代码不得传值）；③ `_peek_agent_result_cache` 在 lifespan 事件循环内调用 `asyncio.run` 必然报错（after 日志 12:31:59 可见），重启后 Agent 已回传结果的 AI 任务被误标失败——改为检测到运行中循环时借独立线程驱动协程。
- 新增（诊断能力）：`utils/metrics/memory_snapshot.py` RSS 阈值诊断快照——`QTR_MEMORY_SNAPSHOT_ENABLED`（默认 false）开启后采集线程每 10 秒检查自身 RSS，超过 `QTR_MEMORY_SNAPSHOT_RSS_MB`（默认 900）时临时开启 tracemalloc 追踪 5 秒、top 分配源（`QTR_MEMORY_SNAPSHOT_TOP_LINES`，默认 50）写入 `logs/<日期>/memory_snapshot_<role>_<时间戳>` 后自动关闭；冷却 `QTR_MEMORY_SNAPSHOT_COOLDOWN_SEC`（默认 3600s）。挂在 `collect.PushDataToServer` 主循环节拍上，不新增线程。用于归因 09:51 那类未解释的内存阶跃。
- 文档：`web/public/docs/ticket_similarity.md`（性能章节补两项优化）、`web/public/docs/memory-monitoring.md`（新增 2026-09-07 治理小节 + 诊断快照配置表 + v1 oom 计数/role 历史数据不可信提示）、更新记录 `web/public/docs/updates/2026-09-07-ticket-similarity-scan-memory-optimization.md`（history.md 已加条目）、wiki 本流程文档同步。
- 验证：新增测试 8 个（分页扫描/会话释放/预筛启用关闭/信号提取/cgroup v1 oom 读取/快照开关与冷却），更新 1 个旧 mock（`list_ticket_embedding_records` → `iter_ticket_embedding_pages`）；相关 6 个测试文件 66 用例全通过，`test_ticket_processing_metrics.py` 3 失败经 git stash 基线对比确认为存量问题；改动文件 ruff 通过；生产库只读端到端验证见上。
- 遗留：fastapi 09:51 +309MB 阶跃未归因（建议部署后开启诊断快照观察）；容器内存 1.4GB→2GB 与 Grafana `memory_pressure>0.85` 告警为运维操作未落地；分页 OFFSET 深翻页在向量数万条后退化，届时接入 Qdrant（代码已支持）。

## [2026-09-07] FEAT | 日志版本号提取正则收紧并支持可视化配置

- 触发：用户反馈日志中 `launcher_version:1.0.6.8`（启动器版本）被误提取为工单版本，正确版本应为 `ms_h:1, ms_l:1, ls_h:6, ls_l:8, version:1.1.6.8` 行的 `1.1.6.8`；`OpenGL parsed version: 4, 6` 也存在误提取风险。
- 根因：原正则 `(?:版本号|版本|version|...)\s*[:：=]\s*(...)` 对 `version` 无左边界（`launcher_version` 子串命中）、版本值无形态约束（单数字 `4` 命中），且"首个命中即返回"，误报行先出现即抢占结果；该正则在 3 个服务文件中重复硬编码，不可配置。
- 修复：新增 `modules/ticket/util/ticket_log_version_extract_util.py` 收敛全部版本提取逻辑——日志链路默认正则锚定 `ms_h/ms_l/ls_h/ls_l` 特征行并要求 `x.y.z` 起步版本形态；工单标题/描述文本链路用独立兜底正则（`version` 前禁止字母/下划线 + 同样版本形态约束）。正则列表接入日志拉取存储配置 `versionExtractPatterns`（`TicketLogPullStorageConfigModel`/`TicketLogPullPostProcessConfigModel` 新增字段，归一化时非法项过滤、全空回退默认），两条日志链路（正文回填 `ensure_ticket_version_id_from_log`、下载后处理 `extract_and_update_version_key`）均按配置读取；3 处旧 `VERSION_PATTERN` 类属性全部删除，调用方改走 util 公开函数。
- 前端：同步自动化页「来源与拉取」→「存储与资源限制」卡片「下载完成后处理」区块下方新增「版本提取正则」JSON 数组 textarea，随存储配置一起保存；`useLogPullStorageConfig.js` 负责 JSON 校验（非法时阻断保存并提示）。
- 效果：三行混合日志（OpenGL 行、launcher 行在前，ms_h 行在后）整段与逐行提取均只返回 `1.1.6.8`；自定义正则（如改提取 launcher 版本）与回退默认正则路径均验证可用。
- 文档：`web/public/docs/ticket_log_pull.md` 存储配置表新增 `versionExtractPatterns` 行及专节说明；更新记录 `web/public/docs/updates/2026-09-07-log-version-extract-pattern-config.md`；wiki `flows/ticket-automation-flow.md` 第 8 步已更新。
- 验证：新增 `tests/test_ticket_log_version_extract.py` 7 个用例 + 更新 `tests/test_ticket_version_key_normalization.py` 1 个用例，9 个全通过；改动文件 ruff 通过；`test_ticket_sync_mapping_boundary.py` 13 个失败经 git stash 基线对比确认为存量问题（`detected_version_key` 属性缺失，与本次无关）；前端 `vite build` 通过。


- 触发：用户反馈 `.env.dev` 环境部署最新代码、已在「资源采集服务」页面配置启用采集服务后，Grafana 仍搜不到 `memory_pressure{instance="TEST_ENV", machine="home", job="QTR"}` 等任何当前链路指标。
- 根因：采集线程 `PushDataToServer` 启动时 `_profiles` 为空，`_collect_tick` 无通道直接 return；而本应周期注入配置的 `replace_profiles` 全仓库无任何调用方——`PROFILE_POLL_SECONDS = 5` 只有定义无使用，`poll_and_apply()` 无调用方，三个进程（server.py role=api、celery_app.py role=celery_worker、celery_scheduler.py role=celery_beat）启动后无人喂配置。数据库配置行本身正确（machine=home），只是从未进入线程；wiki 此前描述"周期加载"与实际代码不符。
- 修复：`collect.py` 新增 `PROFILE_REFRESH_SECONDS = 5` 与 `profile_provider` 回调（保持线程不直接访问数据库边界），主循环每秒节拍先执行 `_refresh_profiles_if_due()`：首轮立即加载、之后每 5 秒刷新，回调异常记日志并保留现有通道；`MetricsCollectorRuntimeService.start(role)` 启动时注入 `profile_provider = lambda: load_active_profiles(role)`；`load_active_profiles` 数据库异常语义从"返回空列表"改为"向上抛出"（空列表会令线程误清空通道，抛出由线程捕获保留通道）。
- 效果：api/celery_worker/celery_beat 三进程统一自驱动轮询，页面启用采集服务后最迟 5 秒开始推送，配置增删改/启停 5 秒热生效（与既有文档描述一致，此前实际不生效）；观察点：状态接口 `activeProfileIds` 从空数组变为已加载配置 ID，日志出现"采集通道启动: profileId=…"。
- 文档：更新记录 `web/public/docs/updates/2026-09-06-metrics-collector-profile-polling-fix.md`（history.md 已加条目）、wiki 流程文档 `flows/memory-growth-monitoring.md` 采集链路描述已修正。
- 验证：`tests/test_memory_metrics.py` 新增 3 个回归用例（轮询回调热生效+异常保留通道、无 provider 保持空通道、运行时服务必须注入回调），10 用例全通过；改动文件 ruff 通过；全量 pytest 27 失败/11 错误经 git stash 基线对比确认为存量问题（ticket/ast 模块），与本次无关。未做真实推送端到端验证（需 dev 环境重启进程后看 VM 数据）。

- 触发：用户反馈①新增/编辑凭证不填登录账号会报错，登录接口 JSON 请求体默认填入账号密码占位符，手动清除后下次编辑又自动填回，每次都要手动删；②`.env.prod` 环境 UAT 凭证能登录、定时刷新任务也开着，但凭证仍会过期。
- 根因①：`CredentialDialog.vue` 的 `ensureLoginRequestDefaults()` 无法区分"未初始化"和"用户显式清空"，每次打开编辑框/切换认证方式都把 `{}` 请求体改写为账号密码模板，保存时 `validateRequestTemplateVariables()` 因 secret 缺 username/password 报错；且后端 `update_credential` 对 secret 做合并式更新（只增不删），编辑页明文回填机制下清空账号保存后旧值仍留在密文里，下次编辑又被回填。
- 根因②（生产库只读核实）：定时任务 `refresh_credentials` 正常（interval 30min、run_count=1102、每 30 分钟成功刷新 erp-prod）；UAT 三凭证（erp-uat-gray02/06/08，http_login 模式）`auto_refresh_enabled=0`，8-17 起再无刷新记录且无任何跳过提示；`expire_time` 全为 NULL（前端无到期时间入口），临期刷新路径不可达。
- 修复：默认模板仅新增注入（编辑不再改写）、登录接口加"恢复默认模板"按钮、编辑保存时已回填主字段清空即从密文删除（`_drop_empty_secret_fields`，替代"留空保留原值"）、变量校验报错文案指引化。可见性：凭证列表加"自动刷新"+"最近刷新"列；`refresh_due_credentials` 跳过原因细分（auto_refresh_off/not_due/invalid_config/lease_conflict）并写任务日志，未开启自动刷新的 HTTP 凭证每天最多一条 `auto_refresh_off` 审计日志；编辑页补"到期时间"字段（`expire_time` 后端本已支持）。
- 数据操作：UAT 三凭证 2026-09-06 00:09 用户已自行在页面开启自动刷新（7200 秒，留有 update 审计日志）；本次幂等脚本检测到后跳过，未重复写入。
- 清理：`credential_refresh_service.py` 删除 4d3a4794 引入的重复方法（`_execute_http_auth_step`/`_execute_http_refresh_with_login_fallback` 各定义两次）与死代码 `_apply_response_mapping`。
- 文档：`web/public/docs/credential_management.md`（清空即删除、默认模板、跳过原因、到期时间）、更新记录 `2026-09-06-credential-edit-semantics-and-auto-refresh-visibility.md`、本 wiki 流程文档同步。
- 验证：见当日会话验证记录（pytest/ruff/前端构建）。

## [2026-09-05] FIX | 工单页面表格横向滚动条拖拽不灵敏修复

- 触发：用户反馈工单相关页面凡有表格处，底部横向滚动条鼠标拖动不灵敏（鼠标移动很远表格只动一点），shift+滚轮正常，要求分析原因并按方案 A（升级依赖）处理。
- 根因：Element Plus 2.10.0 官方缺陷。el-table 滚动由 el-scrollbar 接管且原生滚动条被 CSS 隐藏（`scrollbar-width:none` + `::-webkit-scrollbar{display:none}`），拖动的是自绘 thumb，坐标换算在 `scrollbar/src/thumb2.js`：`startDrag` 只记录 `baseScrollHeight`（漏了水平方向应有的 `baseScrollWidth`），`mouseMoveDocumentHandler` 横向也误用 `scrollLeft = 百分比 × baseScrollHeight / 100`，横向拖动灵敏度被压缩为约 scrollHeight/scrollWidth 倍（日志表格内容极宽，600/4000≈0.15，即移 100px 动 15px）。纵向恰好用 scrollHeight 误打误撞正常；shift+滚轮走 wrap 层原生滚动（1:1 像素）不经换算所以正常。官方 changelog 2.10.2（2025-06-13）"Components [scrollbar] horizontal scroll drag invalid"（PR #20953，关联 issue #20951 及 #20957/#20960/#20969/#20984 等一串 el-table 反馈）。项目在 c4f80eac（2025-12-16）恰好升到 2.10.0 落入坏区间。此 bug 影响全站所有 el-scrollbar 横向拖拽（含下拉框），工单页感受最明显。
- 修复：`web/package.json` element-plus 2.10.0 → 2.10.7（同 minor 最新补丁，含 2.10.2 拖拽修复 + 2.10.5/2.10.6 滚动条 resize 修复；核对 2.10.3~2.10.7 changelog 无破坏性变更，2.10.5 另修表格隐藏时宽度计算错误、dropdown hover 异常滚动）。零业务代码改动。
- 验证：安装后检查 `node_modules/element-plus/lib|es/components/scrollbar/src/thumb2.js` 已含 `baseScrollWidth` 且横向分支改用它；`npm run build:prod` 两次通过（36.9s 无 error）。未验证：真实浏览器手动拖拽（需连库环境登录后抽查工单列表/日志拉取记录/详情页，注意确认 `:deep(.el-scrollbar__bar)` 加高、thumb `min-width:48px` 覆盖仍生效）。
- 文档：新增 `web/public/docs/updates/2026-09-05-table-horizontal-scrollbar-drag-fix.md`（重建后 docs-index.json 已收录）；本 wiki 记录。
- 追加（同日晚）：Jenkins docker 构建报 `npm ci` 50 条 Missing rollup@4.63.1。根因：当日 `npm install element-plus` 时 npm 顺带删除 lockfile 中 unimport/unplugin-auto-import 下两条嵌套 rollup@4.63.0 条目且未正确写回（顶层 rollup 被 0.25.8 古老传递依赖占位，4.x 只剩 vite/node_modules/rollup），`npm ci` 校验对缺失位置重解析出 4.63.1 与残留 4.63.0 全对不上；本地 build 正常是 node_modules 已就位不依赖 lockfile 重建。本地 `npm ci --dry-run` 完整重现 50 条 Missing。修复：重跑 `npm install` 生成一致 lockfile（850 插入/263 删除），补齐 rollup 4.63.1 全平台二进制 50 条；再用 `--registry=https://registry.npmmirror.com` 重装并把 51 条 `resolved`（element-plus 本体 + rollup 系列）从 npmjs.org 统一 sed 改写为 npmmirror（仓库 HEAD 约定全量镜像源），避免依赖 npm ci 的域名回退行为。验证：`npm ci --dry-run` Missing 0 条、JSON 解析合法、`npm run build:prod` 通过（36.96s）。教训：npm install 的"顺带去重"会产生 lockfile 与实际依赖树不同步的状态，改动依赖后交付前应跑一次 `npm ci --dry-run` 验证 CI 兼容性。
- 追加二轮（同日 22 时）：Jenkins 复跑仍报 `npm ci` Missing，但收敛为 2 条 `Missing: rollup@4.63.1` 主包条目（平台二进制已齐）。真正根因：本机 node v25/npm 11.6.2 生成的 lockfile 自家 `ci` 校验通过，但 Jenkins node:22-alpine 自带 **npm 10.9.8** 校验不认——npm 11 写 lockfile 时把 `unimport/node_modules/rollup`、`unplugin-auto-import/node_modules/rollup` 两条嵌套主包条目省略（仅保留 53 条 `@rollup/rollup-*` 平台二进制），npm 10 的校验逻辑要求主包条目必须存在。教训：**lockfile 必须用与 CI 相同的 npm 大版本生成**（Dockerfile 基镜像 node:22-alpine → npm 10.x；本机 node 25/npm 11 不行）。修复：`npx --yes npm@10.9.8 install --registry=https://registry.npmmirror.com` 重新生成，两条嵌套主包条目（rollup 4.63.1，resolved 均为 npmmirror）恢复，全文件 0 条 npmjs.org URL；再用 `npx npm@10.9.8 ci --dry-run` 验证 Missing 0 条（与 Jenkins 同版本校验，非本机 npm 11 自验）；`npm run build:prod` 通过（38.19s）。另：用户在二轮前已自行提交 d1264a4f（lockfile 850 行版）与 c5d0eea2（审计依赖），本轮修复基于 d1264a4f 之上。
- 备查：当时考虑过 patch-package 修补（方案 B，锁版本维护负担）和运行时拦截 thumb 自实现拖拽（方案 C，侵入大），均不如升级；后续若升 2.11.x，2.11.1 还会优化 thumb 尺寸计算。

## [2026-09-04] REFACTOR | 工单同步配置页面按入库执行顺序重组

- 三轮（同日）：用户反馈底部"保存配置"按钮悬在半空。根因是二轮为治横向滚动给页面根加的 `overflow-x: hidden`——CSS 规定 overflow-x:hidden 会把 overflow-y 连带从 visible 变 auto，页面根自己变成滚动容器，`position:sticky` 的吸附参照从外层主内容区变成这个不滚动的根元素，吸底失效、按钮退回文档流末尾。修复：改为 `overflow-x: clip`（只裁剪、不产生滚动容器），横向滚动防护与 sticky 吸底兼容。浏览器验证：滚动到内容中部时按钮 bottom 恒等于视口高（900/900），页面无横向溢出。此坑已写入 wiki 流程文档的自适应约束（新增裁剪需求一律用 clip 不用 hidden）。

- 二轮（同日）：按用户反馈做自适应与弹窗收敛。① `el-container` 换块级 `config-tabs-wrap` + 全链路 `min-width:0` + 表格 `width:100%!important`（超宽列在表格内部滚动）+ 页面根 `overflow-x:hidden`，根治横向滚动；② ①字段识别与映射卡片改摘要+「设置」弹窗（6 组映射+3 正则，跟随主保存）；③ 删除"日志拉取配置"页签，三块配置移入"⑦ 同步后自动化"卡片「日志拉取设置」弹窗——拉日志默认值跟随主保存（弹窗底部按钮直调 `handleSave`），存储与资源限制、日志拉取外部接口配置保留各自独立保存按钮立即生效，弹窗顶部 alert 说明保存方式，回应"独立保存按钮弄成弹窗不友好"的顾虑；④ 紧凑化（卡片 padding 14/16、表单 margin 12、mt16→12、卡片头 wrap）；⑤ 弹窗内 el-col 在 ≤768px 降单列——坑点：Element Plus 百分比列宽是 `width:50%` 而非 flex，媒体查询只覆盖 flex 不生效，必须同时覆盖 `width:100%`（浏览器实测 700px 视口两列堆叠后才修正）；⑥ 页签加 `lazy`。
- 验证：`npm run build:prod` 通过；浏览器静态渲染验证三项全过（页面 scrollWidth==clientWidth 无横向滚动、5×400px 列只在表格内部出现滚动条、窄屏弹窗单列堆叠）。dev 后端 MySQL（192.168.100.12）网络不可达无法登录真实系统，视觉走查待用户在可连库环境确认。
- 文档：用户说明页签表改 6 个并补两个弹窗入口说明，changelog 补二轮记录，wiki 流程文档同步。
- 一轮改动见下方原始记录。

### 一轮原始记录

- 触发：用户反馈工单同步配置页面配置太多太乱，要求按实际执行顺序调整和聚合，且同一配置不要出现在多个地方。
- 分析：延后后处理 `execute_deferred_sync_post_process` 真实执行顺序为 自动化范围闸门 → AI 提取 → 标题 → 翻译 → AI 分类 → 自动化（识别/拉日志/AI）→ 向量 → 发布收敛+群推送；旧页面按存储结构分组，场景开关在 5 张卡片重复出现（4 种命名风格 ×4 场景共 31 个），连接凭据在 6 处平铺。
- 改动（仅 `web/src/views/ticket/syncAutomation/index.vue`，零后端改动）：页签重组为 入库流程/来源与拉取/日志拉取配置/评论同步/通知任务/统计与分类/操作 7 个；入库流程卡片按执行顺序编号 ⓪~⑧；新增"场景 × 步骤 开关总表"聚合全部 31 个场景开关（动态绑定 `form[section][field]`，路径与原静态绑定逐一核对一致；翻译/AI分类/群推送行带与后端语义一致的总开关）；移除卡片内重复的 31 个静态开关列；识别规则+映射配置合并为"① 字段识别与映射"卡；主动拉取/邮箱补全/汇总统计/按人催办的连接字段收入"连接与凭证覆盖"折叠区（留空继承 bitableCommon/feishuAuth，隐藏不清空）；"来源与拉取"新增只读"连接解析预览"（模拟 `resolve_bitable_runtime_config` 继承顺序）；远端同步 `credentialBindingId/origin` 从飞书凭证卡迁回远端同步卡；"指定工单手动自动化"从主动拉取卡拆出为独立卡移入"操作"页签。
- 坑点：① 折叠区把 `el-col` 直接搬进 `el-collapse-item` 违反 el-row/el-col 嵌套结构，4 处均补包 `el-row`；② 飞书凭证卡里原本混放了 remoteSync 的两个字段（视觉分组错误，非存储错误），迁移时严格保持 v-model 路径不变；③ Windows 下无独立 python，用 `server` 的 `uv run python` 执行重排脚本，脚本执行后删除。
- 验证：`npm run build:prod` 通过（35.8s 无 error）；新旧 v-model 绑定 diff 确认零字段丢失（31 个开关由静态转总表动态绑定）；后端未改动，ruff 805 存量告警与本次无关。
- 文档：重写 `web/public/docs/ticket-sync-automation.md`（按新页签结构、补执行顺序章节与开关总表键位对照）；新增 `web/public/docs/changelog/2026-09-04-sync-automation-page-reorg.md`；wiki `flows/ticket-external-sync-flow.md` 补"配置页面分组"章节。
- 明确不做（P5 备选）：不改配置键命名、不抽独立 `sceneMatrix` 存储结构——需要迁移与兼容读取，待展示层稳定后评估。

## [2026-09-04] FIX+PERF | 新版客户端 Agent 连接服务器点击卡死修复

- 触发：用户反馈新版客户端 Agent 菜单点击"连接服务器"后页面卡住直到连接成功或失败。
- 根因：点击在 UI 线程同步执行两类阻塞操作——① `AgentClientService.start()` 在启动连接线程前首次导入 `server.agent_server`（级联 playwright.async_api、pyautogui、cv2、py7zr 等，`-X importtime` 实测 1458ms：httpx 754ms、ticket_ai_analysis_service 674ms、pyautogui 415ms、cv2 209ms）；② `AgentController.start()` 同步调用 `get_active_mac()`（UDP socket 连 8.8.8.8 探测出口 IP + psutil 枚举网卡，网络不佳秒级阻塞）与 `AgentConfig.read_config()` 磁盘 IO。事件循环被占死导致界面假死。
- 修复（`client_new/services/agent_client_service.py`）：`start()` 不再在调用线程导入重模块，首次导入与 `MAX_MESSAGE_SIZE` 设置全部移入 `_thread_main` 后台线程；`_agent_server_module()` 双重检查锁（`_AGENT_SERVER_LOCK`）保证只导入一次且仅在后台线程；新增 `is_running()` 区分"准备中/已启动"；`update_runtime_config()` 增加模块已加载守卫，避免保存配置在 UI 线程误触发导入。
- 修复（`client_new/controller/agent_controller.py`）：新增 `_ConnectPrepareThread` 把 `get_active_mac()` 与配置读取移出 UI 线程；`start()` 两段式——UI 线程仅状态校验+置灰（同步 0.4ms，实测），`starting` 即时生效，准备完成后主线程回调 `_on_connect_prepared` 再发起连接；`stop()` 补连接准备阶段取消分支；`shutdown()` 等待准备线程退出。
- 坑点：重写 `_agent_server_module()` 时丢失 `global` 声明触发 ruff F823（函数内既有读取又有赋值），运行即 UnboundLocalError，靠 ruff 对照基线发现修复。
- 验证：新增 `client_new/tests/test_agent_start_nonblocking.py`（FakeWidget+QCoreApplication 事件循环模拟 UI 线程，卡顿监控 >200ms 零记录；update_runtime_config 不触发导入；连接被拒后正确落回 stopped）；ruff 改动文件 4 告警与基线完全一致零新增；既有 test_ticket_ai_task_cancel 3 用例通过。未验证：真实 GUI 手写连点场景（需人工确认），逻辑上状态机已防重入。
- 文档：新增 `web/public/docs/updates/2026-09-04-client-agent-connect-nonblocking.md`，history.md 同步，wiki `entities/services/new-client-services.md` 补线程边界约束。

## [2026-09-03] FIX | 工单AI分析结果schema清洗与失败分支崩溃修复

- 触发：INC00001920244（task_2046322511408128，prod，Provider shuidi / ai-router / deepseek-v4-flash-0731）AI 分析失败。Worker 正常退出且 result.json 内容完整，但 Agent 报 `AI_WORKER_RESULT_INVALID`（`ticket_no`/`merchant_name`/`version`/`root_cause_type` 为 schema 外额外字段、`$.evidence[0..5]` 期望 string 实际 object），随后又抛 `UnboundLocalError: invalid_result_token_usage` 把真实失败原因覆盖为 `AI_WORKER_EXECUTION_ERROR`。
- 根因一（schema 违规）：deepseek-v4-flash 经 ai-router 中转时 codex `--output-schema` 未真正约束模型输出，模型自行附加 schema 外字段并把 evidence 写成 `{source, content}` 对象数组；结果内容质量完好仅结构不符。根因二（崩溃）：`client_new/services/ticket_ai_analysis_service.py` 结果无效分支中 `invalid_result_token_usage` 在 `report_task_span` 使用之后才赋值，任何走该分支的任务必然二次崩溃。
- 清洗修复：新增两端同规则的纯函数清洗（schema 校验前的保守归一化）：①剔除 `additionalProperties=False` 时的 schema 外字段；②evidence 元素为 `{source, content}` 对象时拼接为 `"source: content"` 字符串；③其他非字符串元素 JSON 序列化保留信息。清洗动作写日志可审计；清洗后仍走完整 schema 校验，防线未绕过；明显非法结果依旧按原逻辑失败上报。服务端 `server/modules/ticket/util/ticket_ai_result_schema_util.py`（`TicketAiResultSchemaUtil`），Agent 端 `client_new/services/ticket_ai_result_schema_service.py`（`TicketAiResultSchemaService`）。
- 接入点：服务端在 Agent 回传解析后、`_normalize_analysis_result` 与 `_validate_analysis_result_schema` 之前清洗；Agent 端在 `_parse_worker_output.accept_candidate` 与 `_load_cached_result`（缓存复用路径）清洗后再校验。清洗只影响内存结果，不回写工作区 `result.json` 原始文件。
- 崩溃修复：结果无效分支改为先提取 `invalid_result_token_usage` 再上报 span 再返回。
- 提示词加固（两端）：第 6 条明确"禁止输出 schema 外字段（点名 ticket_no/merchant_name/version/root_cause_type）；evidence 必须字符串数组、格式 `来源文件路径:行号: 证据内容摘要`，禁止 `{source, content}` 对象"。注意 f-string 内 `{source, content}` 必须写成 `{{source, content}}`，否则 ruff F821。
- 变更传播链：`server/modules/ticket/service/ai/ticket_ai_analysis_service.py` / `server/modules/ticket/util/ticket_ai_result_schema_util.py` / `client_new/services/ticket_ai_analysis_service.py` / `client_new/services/ticket_ai_result_schema_service.py` -> 工单域知识页。
- 验证：用真实失败 result.json 验证清洗前 12 条违规（与线上日志一致）、清洗后 0 条，`_parse_worker_output` 完整链路解析成功；边界用例（仅 content、数字/None 元素、合规结果零动作、schema 要求对象时不误清洗）通过。client_new 新增 6 回归用例（`tests/test_ticket_ai_result_schema_sanitize.py`）+ 既有 AI 测试（引号修复/失败契约/鉴权诊断/token 用量/可观测/Codex 配置/取消/锁心跳）全部通过；server ruff + 提示词测试 5 用例通过。未验证项：真实 Agent 重跑该工单（需重启 Agent 后重新提交分析）。
- 文档：新增 `web/public/docs/updates/2026-09-03-ticket-ai-schema-sanitize-and-unbound-fix.md`，history.md 同步。

## [2026-09-03] FIX+PERF | 相似召回精确信号缺陷修复与相似结果 Redis 缓存

- 触发：量化分析（生产库只读查询：2109 工单、1647 条 bge-m3 symptom 向量、覆盖率 85.5%、外部同步/导入/远端拉取场景开关为 false 为缺口主因——用户确认为故意配置）后确认后台任务化在当前量级不必要，改为修召回缺陷 + 结果缓存。
- 缺陷修复：`ticket_hybrid_similarity_service.search_by_vector` 精确信号候选扩展的 `for ticket_id in signal_hits` 缩进在 `for signal_type` 循环外，`signal_hits` 逐轮覆盖导致只消费最后一种信号（error_code）命中，Trace ID/Request ID 命中候选全部丢失；修复后三类信号命中均进入候选池（`setdefault(0.0)` 进重排加分：trace 0.55/request 0.45/error_code 0.35）。
- 结果缓存：新增 `ticket_similar_result_cache_service.py`。缓存对象为 `TicketReadService.get_similar_tickets` 最终结果（symptom+case 两路，非向量）；键 `ticket:similar-result:{ticketId}:{limit}:{配置指纹}`（指纹=sys_config `ticket.similarity.config` 原文 SHA-256 前 16 位，配置变更自然换键）；TTL 5 分钟；后端跟随 `CACHE_BACKEND`（dev/prod 均 redis）：redis 时用**同步客户端**独立建池（相似链路在 run_in_threadpool 同步线程内，不能复用 app.state asyncio 客户端；key 前缀隔离共用实例），memory 时降级进程内 TTL 字典（上限 500 条）；连接失败自动降级直查不抛异常；error 状态结果不缓存。
- 失效点：① `vectorize_ticket_for_scene` 向量刷新成功后（覆盖 manualCreate/manualUpdate/bitablePull/closeKnowledge 全部自动场景）；② `POST /ticket/{id}/similarity-case/status` 案例状态变更提交后。
- 坑点记录：`_build_similar_cache_key` 指纹构建用 `str(config_value)` 时，Mock/非字符串对象会生成含内存地址的不稳定指纹（pytest 下预写键与读取键不一致导致缓存测试失败）；已改为仅接受字符串类型原文，否则回退 default。
- 验证：ruff（5 个改动文件）通过；pytest 相关 3 套件 36 passed（新增 6 用例：三类信号查询/候选集进入/memory 读写失效过期/缓存命中不触发完整链路/error 不缓存）。本机到 dev(192.168.100.12:6633)/prod(10.56.130.136:7218) Redis 均超时不可达（网络隔离），降级路径已验证，**真实 Redis 读写待部署环境验证**。
- 文档：`server/docs/ticket_read_api.md` 补缓存契约说明，新增 `web/public/docs/updates/2026-09-03-ticket-similarity-signal-fix-and-result-cache.md`，history.md 同步。



- 触发：用户确认第二阶段方案——将列表详情弹窗与独立详情页内部组件合逻辑复用，仅去掉独立页可编辑功能。
- 新增共享组件 `web/src/views/ticket/components/detail-shared/`：`TicketSimilarPanel.vue`（工单内容相似+处理案例相似统一面板，含向量状态提示、系统/飞书详情跳转；"归入同一问题"由 `allowBindIssue` 控制并经 `bind-issue` 事件回传宿主）、`TicketDescriptionBlock.vue`（描述+AI翻译展示块，独立折叠；"翻译"按钮由 `allowTranslate` 控制并经 `translate` 事件回传，权限仍走 `v-hasPermi`）。跳转/链接解析逻辑收敛进共享面板，删除 OverviewTab 与独立页各自重复的 `resolveTicketDetailUrl/openSystemTicketDetail` 等实现。
- 共享 Tab 只读能力：`TicketDetailCollabTab`、`TicketDetailCommentsTab` 新增 `readOnly` prop（默认 false，弹窗侧不传行为不变），为 true 时分别隐藏追问编辑区+分析结果操作、评论提交区。
- 独立详情页 `TicketDetailView.vue` 重写为纯只读：移除问题实例关联按钮与整个绑定弹窗（含搜索/归因表单逻辑）、移除相似案例确认（`updateTicketSimilarityCaseStatus` 不再被引用）、相似/描述区接入共享组件、Collab/Comments 标签传 `read-only`；顶部仅保留"刷新"。保留阶段一的轻量链路（summary+相似懒加载+generation 保护）。
- 弹窗侧 `TicketDetailWithList.vue`：描述/翻译区替换为 `TicketDescriptionBlock`（allow-translate: true），删除旧网格布局样式与 `descriptionExpanded/translationExpanded` 死状态；`TicketDetailOverviewTab.vue` 相似两卡片替换为 `TicketSimilarPanel`（allow-bind-issue: true，归因仍走原 `bindTicketIssueFromSimilar`），相似度统一为一位小数百分比展示。
- 后端无改动；接口、权限码、写操作全部保留在列表弹窗。
- 验证：`npm run build:prod` 通过（37.15s，仅 chunk 体积常规提示）。残留检查：独立页无写 API 引用、弹窗/概览 Tab 无死样式死状态。未做浏览器端双入口回归（需运行环境），剩余风险：弹窗描述区视觉布局变化（网格改上下结构）与概览相似按钮样式变化，用户可感知但行为一致。
- 文档：更新 `web/public/docs/ticket_detail.md`（独立页只读边界、评论只读说明、独立页关联问题实例章节改写为跳转指引），新增 `web/public/docs/updates/2026-09-02-ticket-detail-shared-components-readonly.md`，history.md 同步。

## [2026-09-02] PERF | 独立工单详情页改用轻量读取链路，相似工单懒加载

- 触发：用户反馈独立工单详情页 `/ticket/detail/{ticketId}` 打开慢，怀疑被相似工单查询拖住；经分析确认主因是独立页仍调用旧完整详情接口 `GET /ticket/{id}`（`TicketService.get_ticket_detail_services` 串行组装主单+消息+全部快照+相似+提示词层，消息/快照 DAO 无 limit），相似查询（可能触发同步向量生成、外部 Embedding、MySQL 分批扫描与重排）也被串在其中。列表弹窗此前已走 `summary + similar-tickets` 并行轻量链路。
- 前端 `TicketDetailView.vue`：`loadDetail` 从 `getTicket` 切换为 `getTicketSummary`（首屏只含基础信息/描述/翻译/版本/Issue/最新AI摘要/提示词层）；相似工单拆为独立 `loadSimilarTickets`（`GET /ticket/{id}/similar-tickets`），首次切换"相似工单"标签时懒加载（`ensureSimilarLoaded` + `similarLoadedTicketId` 去重），重复切换不重查；新增 `requestGeneration` 代次校验 + `isCurrentRequest`，快速切单/刷新丢弃旧响应，切单时清空相似状态；顶部"刷新"改为 `refreshDetailData`（summary+similar 并行强制重查），CollabTab changed 事件同样联动；概览"最新AI结论"取值去掉 `latestSnapshot.summary` 兜底（summary 契约不含快照），保留 `latestAiAnalysis.analysisSummary/summary`；相似区域 alert/列表按 `similarError/similarLoading` 独立展示，样式新增 `.similar-loading-wrap` 最小高度。
- 后端无改动；轻量接口（summary/similar-tickets/messages/page/snapshots/page）与 Pydantic 契约此前已存在（`server/docs/ticket_read_api.md`），权限不变（summary/similar 均 `ticket:ticket:query`）。
- 验证：`npm run build:prod` 构建通过（36.98s）。未做浏览器端实际打开耗时对比（需运行环境），剩余风险：概览卡片不再展示最新快照摘要（以最新 AI 分析结论为准，快照仍在 AI 标签按需加载）。
- 遗留（后续单独处理）：完整详情接口 `/ticket/{id}` 仍被其他调用方使用、契约保持不变；`TicketHybridSimilarityService.search_by_vector` 精确信号循环缩进疑似缺陷（只消费最后一种信号命中，影响召回质量非首屏耗时）；相似服务与 controller/read service 重复查询源工单；相似 missing/stale 向量后台化（第二阶段）未启动。
- 文档：更新 `web/public/docs/ticket_detail.md`（独立详情页加载规则、FAQ），新增 `web/public/docs/updates/2026-09-02-ticket-standalone-detail-light-load.md`，history.md 同步。

## [2026-09-02] FEAT | 问题实例绑定工单操作列新增外部地址按钮

- 触发：用户要求问题实例详情中已绑定工单列表右侧操作按钮增加外部地址按钮，点击打开外部链接。
- 后端 `ticket_issue_service.get_issue_detail_services`：绑定工单行查询后逐行调用 `TicketService._decorate_ticket_item` 补同步摘要装饰——此前该列表未装饰，`ticketUrl` 为空的工单无法按 extraData 同步摘要兜底出链接（已验证 `ticket_service.py` 不反向依赖 issue 服务，无循环导入）。
- 前端：链接解析函数 `resolveTicketDetailUrl` 从 `useTicketList.js` 下沉到 `views/ticket/constants.js` 共享（useTicketList 改为导入并原样返回，对外契约不变；`TicketDetailView.vue`/`TicketDetailWithList.vue` 内部另有同逻辑实现，本次不动以控制改动范围）；`issue/index.vue` 绑定工单操作列新增"外部地址"按钮（v-if 有链接才显示，与工单列表"跳转"交互一致）+ `openExternalTicketLink` 处理函数，操作列宽 200→260。
- 文档：更新 `web/public/docs/ticket_issue.md`（操作列说明），新增 `web/public/docs/updates/2026-09-02-issue-bound-ticket-external-link.md`，history.md 同步。

## [2026-09-02] FEAT | 工单导出与问题实例导出新增 URL 列（ticket_url）

- 触发：用户要求问题实例管理和工单列表的导出列增加 URL 选项，用于导出 ticket_url。
- 后端 `ticket_export_service.py`：`TICKET_EXPORT_COLUMNS` 与 `ISSUE_TICKET_EXPORT_COLUMNS` 在"标题"后新增 `ExportColumn(key="ticketUrl", label="URL")`；`_format_ticket_field` 新增 ticketUrl 分支（camelCase `ticketUrl` → snake_case `ticket_url` 兜底 → 空值输出空字符串，避免落入通用兜底产生 "None"）。数据无需额外查询：两条导出路径均已调用 `TicketService._decorate_ticket_item`，行内已有装饰后的 ticketUrl（含 extraData 同步摘要 ticketUrl/sourceRecordUrl 兜底，与详情页展示一致）。
- 前端：`useTicketList.js` 新增 `ticketExportColumnOptions`（复制显示列配置后在 title 后插入 URL 项），与表格显示列 `ticketColumnOptions` 拆分——此前工单导出对话框直接复用 `ticketColumnOptions`，若直接加 URL 会混入表格"列设置"；`index.vue` 导出对话框复选框改用导出列配置并从 hook 解构（修复了原先未被模板使用的死代码 computed）；`issue/index.vue` 的 `issueTicketExportColumnOptions` 插入 URL 项。
- 测试：`test_ticket_export_service.py` 新增 2 用例（两处列定义含 ticketUrl/URL；格式化 camelCase/snake_case/空值分支），3 用例全部通过；ruff 通过。
- 文档：新增 `web/public/docs/updates/2026-09-02-ticket-export-url-column.md`，更新 `web/public/docs/ticket/ticket-list-export.md`、`issue-ticket-export.md` 导出列说明表，history.md 同步。

## [2026-09-02] FEAT | AI分析任务协作式取消、outcome 提交类型与锁冲突标识（第三阶段）

- 触发：按确认方案完成第三阶段——取消端点、attached 等待语义（outcome 标识）、锁冲突携带任务标识。
- 取消链路：新增 `POST /ticket/{ticketId}/ai-analysis/tasks/{taskId}/cancel`（权限同 retry）→ `cancel_analysis_task_services`：仅 created/running 可取消（终态幂等返回），先 `_mark_task_status(canceled)`（活跃锁随终态自动释放）+ 审计 canceled + 工单事件 + commit，再 `_notify_agent_task_canceled` fire-and-forget（直发 `cancel_task` request_chunk 分片、`cancel-{task_id}` 作为 request_id、不建 Future 等待；Agent 离线仅告警）。
- Agent 端：`AI_TASK_CANCEL_FLAGS` 取消标记表（asyncio.Lock 保护）；`handle_message_chunk` 攒齐请求后识别 `requestType=cancel_task` 注册标记并 return（不进 forward_by_rules，避免未知类型误入业务链路）；`TicketAiAnalysisService` Worker 执行前/后双检查点 `_check_task_canceled`（执行前取消→结构化 canceled 返回零消耗；执行后取消→丢弃结果不回传、`_parse_failure_token_usage` 提取已耗 token 随 canceled 返回）；handle_request finally 清理标记；`AI_TASK_ALREADY_RUNNING` 返回携带 `running_task_id`/`running_ticket_id`（锁 payload 中的 taskId）。
- 服务端回传后重读状态：`_process_task` 拿到 Agent 响应后重新 `get_task_by_id`，status=canceled 时 rollback 后仅把迟到结果中的 token 补进审计（不覆盖取消态、不写回工单）、走 canceled 同步收尾后 return。
- outcome：`CrudResponseModel` 加可选 `outcome` 字段；创建/retry 的 created、retried、attached（含 IntegrityError 并发分支）、reused（含重试自身已成功分支）全部标注；前端 `showOutcomeMessage` 按 outcome 提示（"已为您关联原任务"/"已返回历史结果"等），任务历史新增"取消"按钮（created/running 可见，二次确认，取消后刷新）。
- 验证：服务端新增 `test_ticket_ai_task_cancel_service.py` 4 用例（不存在/终态幂等/running 取消带通知/created 取消无通知）+ 相关 47 测试全通过、ruff 通过；客户端新增 `test_ticket_ai_task_cancel.py` 3 用例（注册查询清除/无效taskId/清除缺失标记）+ 全量 39 测试通过；`npm run build:prod` 通过。取消通知的 WebSocket 实际投递与 Worker 中断为协作式设计，需部署环境联调验证。
- 边界：旧版 Agent 不识别 cancel_task（服务端取消仍生效，Worker 跑完由回传后重读状态丢弃）；检查点之间无法立即打断（协作式）；两端需同版本部署才完整。
- 文档：新增 `web/public/docs/updates/2026-09-02-ticket-ai-cancel-and-outcome.md`，history.md 同步。

## [2026-09-02] FEAT | AI分析并发防重、重试独立审计与Agent锁心跳续租（第二阶段）

- 触发：第一阶段完成后按确认方案继续第二阶段——并发竞态防重、审计尝试拆分、心跳锁。
- 活跃锁：`ticket_ai_analysis_task` 新增 `active_lock`（VARCHAR 64，created/running 时等于请求指纹，终态置 NULL）+ 唯一索引 `uk_ticket_ai_task_active_lock`（NULL 可重复实现"活跃指纹唯一"）；`_mark_task_status` 增加 `active_lock_fingerprint` 参数统一维护；创建任务直接占锁，`IntegrityError` 翻译为幂等返回原活跃任务；启动迁移 `_ensure_ticket_ai_analysis_active_lock` 补列+清存量+建索引（MySQL information_schema / sqlite PRAGMA 双后端）。force_refresh 指纹混入 task_id，天然不命中活跃锁，强制刷新行为不变。
- 执行白名单：`_process_task` 从"仅跳过 SUCCESS"改为仅允许 created/running 进入执行，堵住 canceled 败者任务被误 queue 后重复消耗模型调用的通道。
- 重试独立审计：`retry_analysis_task_services` 为 failed/canceled 任务新建审计记录（payload 带 `attempt_of_task_id`/`attempt_no`/`attempt_source=retry`/`prior_audit_execution_id`），任务切换到新 audit_execution_id，原审计终态不可变；新增 `_resolve_task_attempt_no`（按审计链回溯序号）/`_resolve_task_provider_code`/`_resolve_task_model_name`；重试入口补 ticket 查询（复用事件需要 ticket_no）。
- 复用事件：`_record_reuse_event` 独立事务写 `status=reused`、`usage_state=not_called` 审计（创建幂等命中、重试成功指纹命中、重试任务自身已成功三处接入），失败仅告警；token 聚合 DAO 按 SUM 天然忽略 reused 行（其 token 列为 NULL/0），不重复计费。
- 心跳锁：Agent 端 `_acquire_task_lock` 锁内容增加 `lastHeartbeatAt`；新增 `_run_lock_heartbeat`（asyncio 后台任务 15s 间隔 `asyncio.to_thread` 刷新）；`_is_stale_lock` 心跳优先（停止 >60s 过期）旧锁回退时间窗兼容；Worker 执行段 try/finally 启动并取消心跳任务（先停心跳再释放锁）。
- 前端：AI 执行审计页 statusOptions 补 `canceled`（已取消（重复请求））/`reused`（复用历史结果），statusTagType 同步。
- 验证：服务端新增 `test_ticket_ai_active_lock.py` 3 用例（终态释放/占锁/无指纹释放）+ 相关 43 测试全部通过；ruff 通过；客户端新增 `test_ticket_ai_lock_heartbeat.py` 4 用例（心跳判活/停止过期/旧锁回退/心跳刷新）+ 全量 36 测试通过；`npm run build:prod` 通过。未做真实并发双请求联调（唯一索引冲突路径为代码推演+IntegrityError 兜底）。
- 文档：新增 `web/public/docs/updates/2026-09-02-ticket-ai-concurrency-guard-and-audit-attempts.md`，history.md 同步。

## [2026-09-02] FEAT | AI分析断链恢复链路与失败路径Token真实消耗

- 触发：用户确认方案——失败但已发生的模型调用必须记录真实 token；服务重启不应导致 Agent 已完成的执行结果丢失；Agent 重连配置增加永续重连开关。
- Agent 端（client_new）：`WebSocketClient` 新增 `retry_forever`/`retry_forever_interval` 永续重连（窗口高频用尽后降级低频重连直到手动停止，config/UI/agent_client_service 全链路接线，默认关闭不改变现网行为）；新增断连待补交清单 `storage/data/pending_response_deliveries.json`——响应回传失败自动入清单（按 request_id 去重、上限 200 条），连接建立成功后自动补交（单批 10 条），`handle_message_chunk` 的回传改走 `_send_response_with_recovery`；token 补齐：新增 `_parse_failure_token_usage`（失败路径统一提取，Claude 解析新增 `accept_error_result` 参数仅失败路径接受 is_error 报文）、`_recover_token_usage_from_workspace`（超时/异常分支从工作区落盘 stdout/stderr/result.json 恢复），缓存命中路径恢复 token（此前固定 None）。
- 服务端：`agent_controller` 孤儿响应分片不再丢弃——新注册表 `orphan_response_chunks` 内存攒齐后经 `HandleResponse.validate_transport_payload` 校验写入 Redis 结果缓存（key 与调度侧 `_result_key` 一致、TTL 同为 24h），等待方存在时路径不变；`resume_pending_tasks` 启动恢复前按审计 payload 中的 requestId `_peek_agent_result_cache` 检测迟到结果，命中任务重新排队（不再标 AI_TASK_INTERRUPTED），`_process_task` 开头 `_load_recovered_agent_response` 读缓存、`_process_recovered_success` 走成功写回（任务描述"恢复服务重启前的执行结果"，command_line=agent:recovered）；业务失败/结果不可解析路径补 token 提取计入审计；request_id 写入审计 request_payload；`_persist_success_result` 改传 `_submission_user_placeholder(task)`（SimpleNamespace 占位），成功消息/RCA/快照创建者归属提交人。
- 边界：只有传输成功且业务成功的迟到响应才恢复写回；存量任务（审计无 requestId）无法自动恢复仍按中断；缓存命中/失败提取均为"尽力而为"，无凭据返回 None（语义为未知，非 0）；attempt 拆分审计、心跳锁、任务接管等待为后续阶段，本次未做。
- 验证：服务端相关 40 测试（token/dispatch/chunk_registry/transport/task_status）全部通过，ruff 通过；客户端 32 测试（含新增 `test_ticket_ai_failure_token_usage.py` 失败提取/工作区恢复/缓存提取 7 组）全部通过；全部存量失败项经 git stash 对照确认为与本改动无关的既有问题。两端均未做真实 WebSocket 链路联调（需部署环境）。
- 文档：新增更新记录 `web/public/docs/updates/2026-09-02-ticket-ai-reconnect-recovery-and-token-usage.md`，history.md 同步。

## [2026-09-01] FIX | 内存分析图表联动与闪烁修复（时间轴/zr 点击/contextLoading）

- 触发：用户反馈两个问题——图表只有点到极小的数据点符号才跳日志（`showSymbol:false`+lttb 下几乎点不到，点时间轴/空白无效）；点击搜索结果行时页面闪烁（分栏布局后全局 v-loading 遮罩 + 结果面板高度类 `log-view-panel-fill` 依赖 context 是否存在，加载期间来回切换 + 虚拟表格高度级联重算）。
- 图表修复：横轴从 category（降采样后点间距不均导致时间失真）改为 time 真实时间轴（数据用 epoch 毫秒）；点击改用 `chart.getZr().on('click')` + `convertFromPixel` 换算时间 + 二分 `findNearestIndex` 就近匹配数据点，点曲线/时间轴/空白均可跳日志，命中 legend/dataZoom 组件元素时忽略；反向联动 markLine 同步改为毫秒定位；数据点毫秒缓存渲染时构建一次复用。
- 闪烁修复：`loadContext` 拆出独立 `contextLoading`，loading 遮罩就地显示在日志明细块内，不再触发全局遮罩与面板高度类切换；高亮刷新 watch 去 `deep:true`（context 整体替换、highlightKeywords 整体赋值，引用监听即可）。
- 体验补强：`loadContext` 成功后调用新增 `scrollToContextLine()`，按行号文本就近 `scrollIntoView` 定位目标行。
- 解析兼容：`MEMORY_LOG_PATTERN` 毫秒分隔符 `[,.]` 兼容（此前点号格式行被静默跳过），time 捕获组改秒级、strptime 同步 `"%Y-%m-%d %H:%M:%S"`。
- 资源优化：内存分析逐文件扫描时仅首个文件向 `LogService.search` 传 db 读取保护配置，后续文件传 `db=None` 走默认值——实测单次配置读取约 100ms（含 ensure 两次 SELECT + JSON 解析 + 线程池校准），200 文件累计省 20s+ 查库。
- 验证：ruff 通过；parse_hit_line 六组用例（逗号/点号毫秒、无小数、无时间戳、非法日期、非法数值）全部通过；`npm run build:prod` 通过。
- 文档：更新 `web/public/docs/ticket_log_viewer.md` 图表交互与注意事项，更新记录追加至 `2026-09-01-ticket-log-resource-curve-linkage.md`。

## [2026-09-01] UI | 日志拉取列表操作按钮常显与操作列溢出修复

- 触发：工单详情页日志拉取列表的重新拉取按钮依赖行悬浮；日志拉取管理列表的资源曲线、重新拉取按钮也依赖悬浮，且固定右侧操作列宽度不足导致按钮显示不全、部分按钮跑出页面。
- 实现：移除两处 `.hover-only-action` 的显隐样式和模板类名，详情页重新拉取、管理页资源曲线与重新拉取均常显；管理页操作列宽度从 170px 调整为 270px，详情页调整为 220px，保留 fixed right 与原有权限、禁用态和操作逻辑。
- 文档：同步更新 `web/public/docs/ticket_log_viewer.md`、两份操作列更新记录及更新历史。


## [2026-09-01] FIX | 内存分析图表空白修复（成功态引入的挂载时序问题）

- 触发：完成态改动上线后，分析完成只显示汇总标签、三张曲线图空白。
- 根因：onResult 设置 metrics 时图表组件因成功态停留尚未挂载，watch 触发时 refs 为空渲染被跳过；1.5 秒后组件挂载不再触发 watch。
- 修复：`LogMemoryChartPanel` 增加 `onMounted` 时数据已就绪则主动 `renderCharts()`，覆盖"数据先到、组件后挂载"场景。
- 验证：`npm run build:prod` 构建通过。

## [2026-09-01] UX | 日志查看器图表-日志分栏联动布局

- 触发：点曲线点后自动最小化图表的交互不佳，联动时看不到曲线，需手动反复展开。
- 实现：`LogViewerDialog` 布局重构为 CSS Grid 分栏——`memoryPanelVisible` 时进入分栏：宽屏左右（图表列默认 40%，min 300px）、窄屏（<1280px）上下；分隔条 mousedown 拖拽改 `--split-ratio`（0.15~0.7，会话内记忆），拖拽结束 resize 曲线；点曲线点/日志行不再折叠图表，双方同屏联动；面板 header"收起图表"回单栏，工具栏"内存分析"按钮随时重开；结果表格宽度改按内容区实测宽度（ResizeObserver，弹窗打开后补挂监听适配 destroy-on-close）计算。
- 验证：`npm run build:prod` 通过。

## [2026-09-01] FEAT | 日志内存分析搜索管道引擎升级与图表日志双向联动

- 触发：内存分析展开后日志详情被顶出可视区看不到；用户要求曲线点与日志联动跳转，并确认按"完全版"实施（复用 rg 搜索管道 + 双向联动 + 列表页独立入口）。
- 后端：`TicketLogMemoryMetricsService` 扫描层切换为逐文件调用 `LogService.search`（关键字 `Process cpu:`、with_context=False、rg 优先/Python 降级、并发与字节保护复用）；Util 数据点新增 line/epoch 与 `parse_hit_line`；VO 新增 total_hits/parsed_count/skipped_line_count；解析失败跳过计数，2 万点硬上限截断；NDJSON 流式进度保留（文件粒度）。
- 前端：弹窗内容区可滚动 + 工具栏吸顶；内存面板最小化/展开、点日志行自动最小化；`LogMemoryChartPanel` 曲线点 click 回抛 file/line、暴露 highlightTime 画 markLine、lttb 采样；点曲线跳日志上下文、点日志行画标记线；内存分析透传当前文件范围过滤；新增 `LogResourceCurveDialog.vue`（曲线+数据点分页列表，点击打开完整日志查看器 jumpToContext 跳行）；列表页操作列新增"曲线"入口。
- 验证：后端 ruff 通过 + 打桩冒烟（多文件命中、解析失败跳过、统计与行号正确）；前端 `npm run build:prod` 通过。
- 文档：更新 `web/public/docs/ticket_log_viewer.md`，新增更新记录 `web/public/docs/updates/2026-09-01-ticket-log-resource-curve-linkage.md`。

## [2026-09-01] FIX | 日志查看器内存分析完成态图标与扫描性能优化

- 触发：内存分析进度条到 100% 后不展示成功图标（完成瞬间进度区直接隐藏）；用户询问是否应改用 rg/grep 外部进程过滤日志。
- 实现：前端 `LogViewerDialog.vue` 新增完成态——onResult 后进度条定格 100%、`el-progress` 切 `success` 状态显示对勾图标，并提示总耗时与提取点数，1.5 秒后自动切换图表；进行中仍封顶 99% 避免中间文件提前出图标。后端 `TicketLogMemoryMetricsUtil.iter_parse_file` 新增 `Process cpu` ASCII 字节锚点预过滤，无关行跳过解码与正则匹配，解析语义不变。
- 决策：未引入 rg/grep 子进程过滤。当前瓶颈是逐行解码+正则，锚点预过滤已消除主要开销；外部进程会引入二进制部署依赖、丢失行内进度粒度，且违背 util 无副作用边界（若未来引入只允许在 service 层做并带降级）。
- 文档：更新 `web/public/docs/ticket_log_viewer.md` 2.5 节进度描述，新增更新记录 `web/public/docs/updates/2026-09-01-ticket-log-viewer-memory-progress-and-scan-perf.md`。

## [2026-09-01] UI | 日志拉取记录管理页操作列主次分离

- 触发：操作列 6 个彩色圆形按钮平铺（270px 宽）视觉散乱，不符合中后台主流的主次分离规范。
- 实现：`logPullRecord/index.vue` 操作列改为「查看、资源曲线、重新拉取常显 + 更多下拉常显收纳（复制/停止/重新拉取/重新下载/删除）」；删除在下拉内红字置底并用分隔线隔离；保留禁用态语义与下载进度环替换逻辑；列宽固定 270px 并 fixed right。原单行操作函数全部复用，新增 `handleRowCommand` 统一分发。
- 边界：仅改动日志拉取记录管理页；工单详情日志拉取 Tab 的重新拉取按钮同步改为常显，列宽固定 220px。
- 文档：更新 `web/public/docs/ticket_log_viewer.md` 管理页操作说明与准备进度章节，新增更新记录 `2026-09-01-ticket-log-pull-action-column.md`。


## [2026-09-01] FEAT | 日志查看器内置内存分析图表

- 触发：排查工单内存问题时需要先拉取日志，再在本地用 plot_memory.py 脚本生成内存曲线图片，链路割裂且结果不便留存。
- 实现：后端新增 `POST /ticket/logs/memory-metrics`（权限 `ticket:logpull:query`），由新子服务 `TicketLogMemoryMetricsService` 定位解压目录、筛选日志文件并调用新工具 `TicketLogMemoryMetricsUtil` 解析 `Process cpu/mem/threads` 监控行，返回数据点与汇总；前端在 `LogViewerDialog` 工具栏新增"内存分析"按钮，展开新组件 `LogMemoryChartPanel` 用 ECharts 绘制内存（Mb/%）、CPU、线程三张曲线，支持降采样（默认上限 2000 点）与汇总展示。
- 边界：不改变既有日志准备/搜索链路；文件数量超过 `maxSearchFileCount` 保护阈值时要求指定文件范围；无监控行时返回明确提示而不是兜底伪造数据。
- 追加流式进度（同日）：新增 `GET /ticket/logs/memory-metrics/stream` NDJSON 事件流（start/progress/result/error），解析工具改为生成器逐块产出数据点与进度，前端展示进度条、当前文件、已提取点数、已耗时与 ETA 线性估算；关闭面板/刷新中止请求；POST 接口保留并复用同一套解析逻辑。
- 文档：更新 `web/public/docs/ticket_log_viewer.md`（新增 2.5 内存分析、FAQ），新增更新记录 `web/public/docs/updates/2026-09-01-ticket-log-viewer-memory-chart.md`。
- 验证：后端 `ruff check` 通过，解析/合并/降采样/文件筛选冒烟测试通过，控制器路由注册检查通过；前端 `npm run build:prod` 构建通过。

## [2026-09-01] FIX | 工单概览AI结论换行保留与AI分析追问记录补全
- 触发：用户反馈工单详情页概览tab的摘要/根因/解决方案/预防建议/风险说明挤成一行；AI分析tab记录只显示AI结果看不到用户追问（如prod工单INC00001904725，任务2045329100889088的 analysis_context.extraInstruction 中明确有追问文本，但 ticket_message 无对应 question 记录）。
- 架构层：工单域 / 工单详情前端 + AI分析任务创建服务。
- 根因1（格式）：`TicketDetailOverviewTab.vue` 五个结论字段直接 `{{ }}` 插值渲染，HTML 折叠换行；AI分析tab的 `.record-content` 有 `white-space: pre-wrap` 所以正常。
- 根因2（追问丢失）：两条链路行为不一致——AI分析tab追问框先写 question 消息再触发分析（ticket_service.add_message），而“发起AI分析”弹窗走 `create_analysis_task_services` 只把 extraInstruction 放进提示词和 analysis_context，从不写 question 消息。
- 实现：概览tab五个字段改用 `.pre-wrap-text`（pre-wrap + break-word + line-height 1.65）容器；`create_analysis_task_services` 在 `TicketAiDao.add_task` 同一事务内补写 `role=user, message_type=question` 消息（content=extraInstruction，reference_type=ai_analysis，reference_id=task_id）；请求模型新增 `skipQuestionMessage` 字段，协同消息链路（已提前写 question）传 True 防重复；幂等命中/执行中分支在写消息前 return、重试只更新状态、日志拉取自动分析无 extraInstruction，均不产生重复或空消息。
- 验证：ruff 通过；`test_ticket_ai_token_usage.py` + `test_ticket_log_pull_retry_guard.py` 21 用例通过；`vite build --mode production` 构建成功；prod 库确认 INC00001904725 的 extraInstruction 完整保留在任务上下文。
- 文档：更新 `web/public/docs/ticket_detail.md`（主概览格式说明、AI分析记录追问说明），新增 `web/public/docs/updates/2026-09-01-ticket-overview-prewrap-and-ai-question-message.md`。
- 后续：存量任务的追问仍只在任务详情 analysis_context 中，不补写消息；需重启后端并发布前端生效。

## [2026-09-01] FIX | AI执行审计类型中文显示与详情按钮权限
- 触发：AI执行审计页面任务类型下拉只有两个中文选项、列表显示英文编码；来源类型同样显示英文（如 `external_sync_sync_extract`）；操作列看不到任何按钮。
- 架构层：系统管理域 / AI执行审计 / 前端页面 + 权限注册。
- 根因1（英文编码）：前端 `aitaskexecution/index.vue` 枚举写死且过时——任务类型只有 `ticket_translate`/`ticket_knowledge_extract` 两项，来源类型 4 项与实际写入值完全对不上；`formatTaskType`/`formatSourceType` 匹配不到时回显英文原值。数据库实际分布：task_type 有 `ticket_sync_extract`(1688)/`ticket_translate`(603)/`ticket_stat_classify`(366)/`ticket_category_classify`(16)/`ticket_embedding`(2)；source_type 以 `{同步场景}_{动作}` 拼接为主（external_sync_sync_extract、bitable_pull_sync_extract、*_auto_category 等）。
- 根因2（无按钮）：详情按钮绑定 `system:aitaskexecution:query`，但 `perms.py` 只注册了 `...:list`，query 权限字符不存在；`v-hasPermi` 对无权限用户直接移除按钮节点。后端详情接口本就校验 query 权限，故正确修法是补权限定义而非改权限字符。
- 实现：前端补全 9 种任务类型 + 固定/拼接两类来源类型枚举，并新增 `{场景}_{动作}` 规则翻译（SOURCE_SCENE_LABELS/SOURCE_ACTION_LABELS，场景含 external_sync/bitable_pull/remote_pull，动作含 sync_extract/auto_category/status_change_auto_category）；后端 `perms.py` 新增 `admin.system.aitaskexecution.query` F 按钮定义（挂在 aitaskexecution 菜单下，order=1），启动时 sync_registered_menus 自动落库。
- 数据操作：已通过最小 app 执行 sync_registered_menus 落库新按钮（menu_id=295，parent=245）；参照 `system:aiprompt:query` 授权惯例，将 menu_id=295 INSERT 授权给管理员角色（role_id=3）；超管角色（role_id=1）走 `*:*:*` 通配无需授权。
- 验证：`uv run ruff check module_admin/perms.py` 通过；MENU_DEFS 无重复 key；`vite build --mode production` 构建成功；数据库确认按钮菜单与角色授权生效。
- 文档：更新 `web/public/docs/ai_ticket_light_ai.md` 第七章（新增 7.2 任务类型与来源类型说明表、7.4 权限说明），新增 `web/public/docs/updates/2026-09-01-aitask-execution-type-labels-and-detail-permission.md`。
- 后续：普通角色如需看详情按钮，需在角色管理勾选“AI执行审计详情”；后续新增任务类型/来源类型时前端枚举需同步维护，拼接来源可依赖规则翻译兜底。

## [2026-08-31] FIX | 工单AI分析结果未转义引号修复
- 触发：工单 INC00001904725 第二次分析失败（task_2045268316707840，prod，Provider=openai_com/deepseek-v4-flash，与 08-28 失败的 shuidi 不同）：Worker 正常退出且 result.json 内容完整，但报 `AI_WORKER_RESULT_UNPARSEABLE`，文本预览以 ```json 开头。
- 架构层：工单域 / 深度AI分析 / Agent 端结果解析。
- 根因：result.json 带 ```json 围栏（已有剥离兜底），但剥离后仍非法——`root_cause` 字符串值内部输出未转义英文双引号（`停留在"恢复中"（Pending）状态`），json.loads 在 line 7 column 113 报 `Expecting ',' delimiter`。deepseek-v4-flash 即使有 --output-schema 约束也不遵守字符串转义规则。
- 链路确认：执行/解析/Schema 校验都在 Agent 侧（client_new `ticket_ai_analysis_service.py`），服务端只下发任务、记录转发错误和写回结果；错误日志出现在 Agent 日志属正常架构。服务端 `_read_json_file` 只读自产 context.json，无需同步修复。
- 实现：client_new 新增 `_repair_unescaped_quotes`（结构化扫描：字符串内部后跟非 `, } ] :` 结构符的引号补 `\"` 转义，修复结果必须能通过 json.loads 且为 dict 才采纳）；`_extract_json_from_text` 在常规解析全部失败后调用该兜底；两端 prompt 第 5 条新增转义约束（英文双引号必须 `\"`，引用中文术语用中文引号）从源头减少非法输出。Agent 端修复后的结果仍经 accept_candidate Schema 校验，防线未绕过。
- 测试：client_new 新增 `tests/test_ticket_ai_json_quote_repair.py` 5 用例（围栏内修复、纯文本修复、合法 JSON 不改写、真实结束引号不误转义、无法修复返回 None）全部通过；既有 27 个 AI 测试通过；server prompt 套件 5 用例通过；ruff/py_compile 通过。
- 端到端：用真实失败 result.json 走 `_parse_worker_output` 完整链路（含真实 Schema）解析成功，14 字段完整、引号内容正确保留。
- 文档：新增 `web/public/docs/changelog/2026-08-31-ticket-ai-analysis-unescaped-quote-fix.md`，更新 `web/public/docs/ticket_ai_analysis.md` 解析兼容说明。
- 后续：需更新并重启本机 Agent 生效；该工单修复后在页面重新发起 AI 分析即可。

## [2026-08-31] INGEST-CODE | 工单轻量AI手动测试工作台
- 触发：需要按工单/Provider/模型/提示词组合试运行轻量 AI（信息提取、分类、翻译、标题总结、知识提炼），验证不同模型与提示词改法的效果，不影响线上工单。
- 架构层：工单域 / 轻量AI / 测试工作台。
- 新增：`TicketLightAiTestService`（测试编排，复用生产提示词渲染与归一化方法；不读场景开关/不读写提取缓存/不回写工单；审计 task_type 追加 `_test`）、`ticket_ai_test_vo.py`（Pydantic 契约）、`ticket_ai_test_controller.py`（options/tickets/context/prompt-content/run 五接口，均 run_in_threadpool，权限 `ticket:ai:test:run`）、前端 `web/src/api/ticket/aiTest.js` 与 `web/src/views/ticket/aiTest/index.vue`（任务类型/工单远程搜索/Provider-模型联动/提示词模板回填+临时编辑/结果面板含告警与Token）。
- 菜单：`perms.py` 新增 `ticket.ai.test`（工单管理 → 轻量AI测试），启动时 sync_registered_menus 自动同步，角色需勾选后可见。
- 生产同构点：机台编号归一化（含 machineNumberWarnings）、提示词变量渲染、分类结构化归一化与生产完全一致，测试结论可直接参考。
- 验证：新增文件 ruff 全部通过；server 模块与服务导入验证通过；前端 `vite build --mode production` 构建成功。
- 文档：新增 `web/public/docs/ticket_ai_test.md`（用户说明）、`web/public/docs/updates/2026-08-31-ticket-ai-test-workbench.md`，更新 `web/public/docs/updates/history.md`。

## [2026-08-31] FIX | 相似工单向量刷新 quality_status 非空约束报错
- 触发：详情页相似工单报 `Column 'quality_status' cannot be null`（MySQL 1048），SQL 为 `embedding_record` 的 UPDATE；分析确认影响所有"已有向量记录刷新"场景。
- 架构层：工单域 / AI 向量服务 / 向量记录持久化。
- 根因：提交 5b2fc713 为 `embedding_record` 新增非空列 `quality_status`（DDL 带 DEFAULT 'ready'，存量行无损）；但 `vectorize_ticket` 构造新 `EmbeddingRecord` 未显式赋值该字段，`TicketDao.upsert_embedding_record` 更新分支直接用新对象属性覆盖旧行，ORM Python 侧 default 只对 INSERT 生效，UPDATE 写入 NULL 报 1048。因同提交修改了向量字段方案（哈希含字段列表），存量向量哈希全部失配被判 stale，详情页自动刷新高频命中该路径。
- 影响面：详情页相似工单、消息面板 `get_messages_services`、相似案例索引（标 last_index_status=failed）、manualCreate/manualUpdate/closeKnowledge/外部同步场景触发刷新（被 try/except 吞掉、向量静默过期）、`/ticket/similarity/rebuild`。AI 分析主链路（`search_tickets` 关键词检索）只读不写、不报错，但其 similarTickets 是新旧方案错配匹配，相关性劣化。
- 实现：方案 A——`ticket_embedding_service.py` 构造记录处显式 `quality_status="ready"`，不依赖隐式默认值；未加防御性兜底（唯一写入点已保证）。数据无需修复（DDL 默认值已回填存量行）。
- 测试：新增回归用例 `test_vectorize_ticket_builds_record_with_quality_status`（捕获构造对象断言字段非空），验证移除修复时失败、恢复后通过；套件 25 用例全部通过；ruff 通过。
- 文档：新增 `web/public/docs/updates/2026-08-31-ticket-similarity-quality-status-fix.md`，更新 `web/public/docs/updates/history.md` 与本文档（ticket-domain.md 向量服务段落）。
- 后续：修复上线后建议执行一次全量向量重建，把存量向量统一到新文本方案，消除新旧方案错配；外部 Embedding 配置注意 Token 消耗。

## [2026-08-31] INGEST-CODE | 工单AI提取参数回填日志拉取提示快照
- 触发：工单 INC00001904725 AI 提取出 logDate=2026-08-29，但详情页手动拉日志弹窗不回填日期；确认延后处理链路从不重建 `log_pull_hints`。
- 架构层：工单域 / 同步延后处理 / 日志拉取提示快照。
- 原因：bitable_pull 走"快速入库+延后处理"两段式，主入库阶段 AI 未执行，`build_upsert_payload` 构建的 hints 缺 modifyTime/posNo（飞书中文时间键不匹配标准键）；延后处理阶段 AI 提取回填后只更新 `ai_sync_extract`/标题/翻译，不回写 hints，弹窗读不到。
- 实现：`TicketSyncPayloadService` 新增公开方法 `refresh_log_pull_hints`（原内联逻辑抽取 + posNo 兜底补充 log_pull_config 来源，与自动化取值顺序一致）；主路径改为调用该方法（行为不变）；延后处理在 AI 回填并重新 detect 后调用并持久化。
- 回显语义：手动拉取参数保存在 `ticket_log_pull_record`，详情页弹窗经 `latestLogPull` 回显最近一次记录参数（用户实际操作优先于 AI 提取值）；`log_pull_hints` 修复后承载 AI 提取值。
- 测试：新增 `tests/test_ticket_sync_log_pull_hints.py` 4 用例（AI 值进 hints、scoNo 回退、AI 空值保留已有 hints、主路径 payload 写入）全部通过；相关套件 29 用例通过；boundary 套件失败集合 md5 与基线一致（存量问题）。
- 文档：新增 `web/public/docs/updates/2026-08-31-ticket-ai-extract-hints-backfill.md`，更新 `web/public/docs/ticket_log_pull.md` 回填来源说明与 `web/public/docs/updates/history.md`。

## [2026-08-31] INGEST-CODE | 工单AI提取机台编号覆盖逻辑修复
- 触发：工单 INC00001899231 模型正确返回 posNo=24，但后处理用正则从全文取第一个 `POS+数字` 匹配（POS#05，门店排查时检查的机台）无条件覆盖，导致自动化按 5 号机拉日志。
- 架构层：工单域 / 轻量AI统一提取 / 机台编号归一化。
- 实现：`TicketLightAiService._normalize_sync_extract_machine_numbers` 重写为模型结果优先策略；新增 `_extract_all_explicit_machine_nos`（全部候选去重）与 `_reconcile_machine_no_with_source`（单字段对齐：模型有效且命中候选直接采信；原文唯一候选冲突才纠正；多候选冲突保留模型值并告警；模型无效/遗漏时原文候选兜底）。金额拦截仍在 `_normalize_pos_or_sco_no`，防金额误判能力不回退。
- 契约：`machineNumberWarnings` 告警文案更新（新增"已保留模型值，请人工复核"等），仅在审计与日志中使用，接口结构不变。
- 缓存边界：本次不改缓存机制；`extra_data.ai_sync_extract` 以 `sourceHash + promptHash` 命中，代码变更不使旧缓存失效，存量错误结果需清缓存或等源数据/提示词变更后自然重提。
- 测试：`tests/test_ticket_sync_ai_extract_safety.py` 更新金额纠正用例文案，新增多候选保留模型值（INC00001899231 回归）、命中候选无告警、单候选纠正、候选兜底、原文无候选 5 个用例，13 个用例全部通过；`test_ticket_sync_mapping_boundary.py` 的 13 个失败经 stash 对比确认为存量问题。
- 文档：新增 `web/public/docs/updates/2026-08-31-ticket-ai-extract-machine-no-override-fix.md`，更新 `web/public/docs/ticket-sync-automation.md` 归一化策略说明与 `web/public/docs/updates/history.md`。

## [2026-08-30] INGEST-CODE | 相似工单症状/案例索引与混合召回
- 触发：确认生产无 Qdrant 时按 MySQL + 外部 Embedding 落地相似工单准确性改造。
- 架构层：工单域 / 相似检索 / 案例生命周期 / 详情页。
- 新增：`TicketSimilarityProfile`、`TicketSimilaritySignal`、`TicketSimilarityCase`，以及 `EmbeddingRecord.embedding_scope`。
- 变更传播链：工单入库/更新 -> 画像和精确信号 -> symptom 向量；AI/RCA 结论 -> draft 案例 -> 人工确认 verified -> 独立案例向量；详情 -> 精确候选 + MySQL 分批向量扫描 + 可解释重排。
- 生产边界：Embedding 继续为生产 Provider，local_hash 保留测试，Qdrant 不作为生产依赖；不整体拆分 `ticket.extra_data`。
- 文档：新增 `web/public/docs/ticket_similarity.md`、`web/public/docs/updates/2026-08-30-ticket-similarity-case-index.md`、`wiki/flows/ticket-similarity-case-flow.md`。


- 触发：AI分析追问区同时暴露角色、类型、发起AI开关，配置项和操作按钮占用空间较大，普通评论与 AI 分析职责边界不够清晰。
- 实现：详情页 Tab 更名为“AI分析”，固定追问消息为用户提问并自动触发 AI；保留版本、Agent、Provider、模型和附件 JSON 配置，收纳为紧凑配置条与分析上下文入口；消息记录采用 AI/用户区分的气泡布局；生成快照、生成知识库、任务历史统一为结果操作区，顺序固定为快照、知识库、任务历史。
- 评论：保留原评论接口、内部评论、权限、时间线和外部同步语义，仅优化评论 composer、消息块、发送中禁用与空状态；独立详情页复用 `TicketDetailCommentsTab`，与列表详情弹窗行为一致。评论提交不触发 AI。
- 契约：后端接口和数据模型不变，前端仅收敛字段展示和交互布局；AI 结果附件详情继续保留。


- 触发：用户指出协同/AI tab 中“发起AI分析”按钮与“提交消息”（runAi=true）后端等价（均走 `TicketAiAnalysisService.create_analysis_task_services`），按钮冗余；表单字段平铺过长；消息流混入同步导入、快照等系统消息；AI 结果 JSON 直接平铺撑开页面。
- 实现：`TicketDetailCollabTab.vue` 移除顶部“发起AI分析”按钮和 `run-ai` 事件，`任务历史` 按钮移入角色/类型所在行；内容列 span 16→24 铺满整行（原右侧 8 栅格为相似工单卡片）；版本+Agent、Provider+模型 同行两列布局；附件 JSON 放入默认收起的 `el-collapse` 高级选项；消息流按 `messageType in (question/analysis/conclusion)` 过滤（快照 snapshot、同步导入 sync_import、事件动作、系统建单不再展示）；消息附件不再平铺，改为“详情”按钮 + `el-dialog` 弹窗查看格式化 JSON。
- 修正：初版误删了第一行“发起AI”开关（`runAi` 控件，控制提交消息是否触发AI追问，默认开启）；开关不是与“发起AI分析”按钮等价的冗余项而是独立功能，已恢复到第一行，提交提示逻辑同步恢复按开关状态判断。
- 调用方同步：`TicketDetailWithList.vue` 协同 tab 不再监听 `run-ai`；概览 tab 的发起弹窗入口保留（用于日志时间窗等高级参数场景）。
- 契约：后端零改动，`POST /ticket/{ticket_id}/messages` 与页面接口契约不变，过滤纯前端完成。
- 验证：`npx vite build --mode production` 构建通过；更新 `web/public/docs/ticket_detail.md` 协同/AI 章节、新增更新记录 `2026-08-29-collab-tab-simplify.md`。



- 触发：日志拉取管理列表展示了工单编号/标题，但无法直接进入工单明细，排查链路需要手动搜索工单。
- 实现：`web/src/views/ticket/logPullRecord/index.vue` 的「关联工单」列增加点击事件，通过命名路由 `TicketDetail` 解析站内地址并新标签页打开；工单 ID 使用字符串传参，避免大整数精度问题。
- 边界：无 `ticketId` 的记录不渲染跳转行为；未改动后端接口、路由定义和工单详情页。
- 验证：`npm install` 后执行 `npm run build:prod` 构建通过。

## [2026-08-27] FEAT | 工单 AI Token 用量记录与汇总展示

- 触发：工单 AI 分析历史、工单概览和 AI 执行审计之前都无法直接看到每次分析消耗了多少 Token，排查成本和模型费用复盘成本较高。
- 方案：`ticket_ai_analysis_task` 新增 `audit_execution_id`、`input_token_count`、`output_token_count`、`total_token_count` 四个字段；`sys_ai_task_execution` 继续保留原始 `token_usage` JSON，不新增重复列。
- 展示：工单 AI 历史列表和详情弹窗显示输入/输出/总 Token，工单概览通过 `GET /ticket/{ticket_id}/summary` 返回 `aiTokenSummary` 显示整单聚合值，AI 执行审计列表新增“总 Token”列，详情页保留原始 `tokenUsage` JSON。
- 性能取舍：只在单工单概览接口内按 `ticket_id` 做一次 SQL 聚合，不把 Token 汇总扩散到工单列表、分页摘要或批量接口，因此不会对列表性能造成明显影响。
- 验证计划：补充服务层与 Token 归一化测试，并执行定向 `ruff` / `pytest` 校验。

## [2026-08-26] FIX | 工单 AI Agent 队列陈旧请求自动恢复

- 触发：Agent 实际没有执行任务时，工单手动/自动 AI 仍持续打印“等待 Agent 槽位”，`queue_head` 长时间停留在历史请求，`active_count=0`；排队协程同时会持有完整 AI 请求，积压后放大 API 进程内存。
- 根因：旧实现主要在请求缓存缺失或总超时后才清理队列头；若请求在 FastAPI/Celery 断连、重启或 WebSocket 断开前已入队，但请求缓存仍保留 24 小时，就会被历史 `queue_head` 长时间卡住；排队阶段也会持续持有完整 prompt/context。
- 修复：`AgentDispatchService` 新增排队心跳租约与队列头自愈逻辑，抢占槽位前会自动清理已终态、排队租约过期、请求缓存缺失或总超时且无运行租约的队列头；排队阶段仅保留轻量状态，真正发给 Agent 时再从 Redis 恢复完整请求，并对等待日志做固定间隔节流。
- 验证：执行 `uv run pytest tests/test_agent_dispatch_service.py` 与 `uv run ruff check module_qtr/service/agent_dispatch_service.py module_qtr/util/agent_dispatch_config.py tests/test_agent_dispatch_service.py` 通过；补充回归测试覆盖陈旧队列头、排队租约过期和缓存消息恢复场景。
- 排查：只读查询工单 `INC00001882932` 的 AI 任务发现 `queue_head=ticket-ai-analysis:2043457233009664` 对应任务已于 2026-08-26 15:26:13 失败，但 2026-08-26 18:06:22 的后续请求仍被它阻塞。

## [2026-08-26] 工单自动日志去重、自动 AI 复用成功日志、任务日志补齐 TID

- 触发原因：工单修改后会反复自动拉取同一份日志；已有成功日志时自动 AI 有时因为未新建日志记录或缺少版本回填入口而被跳过；任务日志缺少可查询的 TID/trace_id，链路排查困难。
- 影响范围：`server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/modules/ticket/service/sync/ticket_sync_automation_service.py`、`server/modules/ticket/dao/ticket_log_pull_dao.py`、`server/module_task/*`、`web/src/views/*/job/log.vue`、`web/public/docs/*`。
- 关键改动：
  - 新增“相同拉取参数成功记录”匹配逻辑，自动化命中后直接跳过重复拉取；
  - 自动 AI 统一改为可复用成功日志记录触发，并继续走版本回填、条件检查和通知链路；
  - Celery 任务执行日志表新增 `trace_id` 持久化与查询展示，系统/QTR 任务日志页支持按 TID 检索。
- 验证：新增自动日志去重、自动 AI 复用、任务日志 trace_id 的定向测试，并执行 `uv run pytest tests/test_ticket_sync_automation_reuse.py tests/test_ticket_log_pull_retry_guard.py tests/test_celery_job_trace_id.py` 通过。

## [2026-08-26] INGEST-CODE | 自动 AI 历史与内部状态条件过滤

- 触发：同步入库的工单可能已处理或已完成 AI 分析，继续自动分析会浪费 Token。
- 方案：在日志拉取默认配置中增加 `autoAiAnalysisCondition`，支持历史成功条件和内部工单状态多选；自动触发按 AND 关系检查，手动分析不受影响。
- 关键约束：状态使用工单内部 `status` 编码，不使用外部状态文案；状态未映射或不在允许列表时跳过自动 AI 并记录 `auto-ai` 原因。
- 变更范围：同步配置服务、日志拉取请求模型、自动化运行时快照、自动 AI 触发护栏、同步自动化页面、用户说明。

---
title: 操作日志
type: log
source_type: mixed
created: 2026-05-20
updated: 2026-08-25
---

# 操作日志

## [2026-08-27] FIX | 工单导出 tuple 与 Blob 响应异常

- 根因：工单导出服务将分页 Pydantic 结果直接执行 `list(result)`，得到 `('rows', [...])` 字段元组；前端 request 封装对 Blob 直接返回数据，却仍读取 `response.headers`。
- 修复：统一提取 DAO 分页/非分页结果中的 `rows`；导出请求模型支持 camelCase 和当前筛选条件；前端直接保存 Blob 并使用固定文件名。
- 验证：定向 `ruff` 检查通过；Pydantic 导出请求别名解析和分页结果提取回归检查通过；前端生产构建待完成。

## [2026-08-25] FEAT | 工单 AI Agent 跨进程派发与并发队列

- 触发：`start.sh` 以 Supervisor 分进程启动 FastAPI、Celery Worker 和 Celery Beat，自动 AI 需要在 Worker 侧安全投递到 FastAPI 内的 Agent WebSocket 连接。
- 实现：新增系统参数 `ticket.ai.agent.maxConcurrentTasks`，默认值 1；Celery Worker 通过内部网关 `/qtr/agent/ai-analysis/send/{agent_code}` 提交请求，QTR 域用 Redis 共享队列、运行中租约和短锁控制单 Agent 并发，超过上限的请求只排队等待。
- 语义：队列等待和 Agent 执行共用同一个总超时边界，发给 Agent 的等待预算按剩余时间计算，避免并发队列把任务总超时拉长。
- 验证：补充并发队列与剩余超时回归测试；未修改生产数据库。

## [2026-08-25] FIX | 自动 AI 内部网关错误拼接生产代理前缀导致 404

- 触发：生产 `.env.prod` 使用 `APP_ROOT_PATH=/prod-api` 时，Celery Worker 通过 `127.0.0.1:8080` 访问内部 Agent 网关仍携带 `/prod-api`，自动 AI 连续收到 404。
- 根因：本机直连不经过反向代理，内部路由实际为 `/qtr/agent/ai-analysis/send/{agent_code}`；外部代理前缀不应拼接到本机 URL。
- 排查：只读查询 `ticket_ai_analysis_task`、`ticket`、`ticket_event`、`ticket_log_pull_record`；任务 `2043210025327616` 于数据库记录为失败，错误为内部网关 404；同一工单后续自动任务仍复现相同 URL。未修改数据库数据。
- 修复：`TicketAiAnalysisService._build_agent_gateway_url` 仅拼接本机端口和业务路径，并新增 URL 回归测试；同时补充生产发布后统一重启 FastAPI/Celery 进程的运维说明。
- 验证：定向 pytest 通过（3 passed）；当前工作区静态路由包含 `POST /qtr/agent/ai-analysis/send/{agent_code}`。

## [2026-08-25] FIX | 自动 AI 提交失败原因写入通知与工单事件

- 触发：日志拉取成功后自动 AI 提交被拒绝时，原通知只显示 `record_id/version_id`，无法判断是 Agent 未连接、版本映射还是其他前置校验失败。
- 修复：读取 `result.message` 作为统一失败原因，同时写入通知详情（模板 `${reason}`）和 `auto-ai:failed` 工单事件；事件详情保留版本、Agent、Provider 及失败阶段，并单独提交数据库会话。
- 架构诊断：`start.sh` 的 Supervisor 将 FastAPI、Celery Worker、Celery Beat 分进程启动；Agent WebSocket 连接表仅在 FastAPI 进程内，Celery 自动任务无法直接读取。跨进程派发尚未实现，后续需选择 Redis 消息网关或受保护的 FastAPI 内部中转接口。
- 验证：新增自动 AI 提交失败原因写入事件和通知的定向测试；未修改生产数据库。

## [2026-08-23] FEAT | 工单模块通用提示词按编码复用

- 触发：多个项目存在相同 `module_code` 的模块，需要复用共同 AI 分析说明，同时保留项目模块的特殊说明。
- 架构层：工单域 / HRM 模块管理 / AI 提示词编排 / Web 控制台。
- 变更传播链：`hrm_module_common_prompt` 管理资源 -> `TicketPromptService.resolve_prompt_layers` 按模块编码解析 -> AI 任务 `prompt_text/analysis_context` 快照 -> 工单 summary 与详情层级展示。
- 数据规则：跨项目相同编码保留；不合并 `module_id`，不改写历史工单、统计快照或历史 AI 任务；项目内重复编码先只读盘点，确认清理后再加联合唯一索引。
- 更新页面：`web/public/docs/module_common_prompt.md`、`web/public/docs/updates/2026-08-23-module-common-prompt.md`、`server/docs/ticket_read_api.md`、`web/public/docs/ticket_detail.md`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`。
- 更新代码：HRM 模块通用提示词 ORM/VO/DAO/Service/Controller、菜单权限、工单 AI 提示词解析与任务快照、summary 契约、前端管理页和详情展示。

## [2026-08-21] FIX | 问题实例详情 DAO 查询回归

- 触发：进入问题详情、编辑页或绑定工单区域时，`TicketIssueDao` 缺少 `list_tickets_by_issue_id`，请求报属性不存在。
- 根因：新增工单搜索 DAO 时误替换了原有按 Issue 查询绑定工单的方法。
- 修复：恢复 `list_tickets_by_issue_id`，保留 `search_tickets_for_issue`；Issue 详情重新按 `ticket.issue_id` 查询有效工单。
- 更新的页面：`server/modules/ticket/dao/ticket_issue_dao.py`、`web/public/docs/updates/2026-08-21-ticket-issue-dao-regression.md`、`web/public/docs/updates/history.md`。
- 验证：补丁已完成静态结构核对；环境中的 Python/npm 命令执行受到运行器限流和解释器 PATH 差异影响。

## [2026-08-21] FIX | 问题实例新增可选字段校验

- 触发：问题实例新增表单未选择负责人时提交 `ownerId: ""`，Pydantic 整数校验失败并返回“参数或数据异常: ownerId”。
- 修复：`TicketIssueBaseModel` 将可选整数空字符串归一化为 `None`；前端新增提交过滤空可选字段。
- 更新的页面：`server/modules/ticket/entity/vo/ticket_issue_vo.py`、`web/src/views/ticket/issue/index.vue`、`server/tests/test_ticket_issue_service.py`、`web/public/docs/ticket_issue.md`、`web/public/docs/updates/2026-08-21-ticket-issue-create-optional-fields.md`。
- 验证：补充空负责人/项目/模块模型归一化测试；构建命令受当前执行器限流影响，待环境恢复后执行。

## [2026-08-21] INGEST-CODE | 工单问题实例关联增强

- 触发：问题管理页面绑定工单使用内部 ID，工单详情无法直接搜索已有 Issue，工单列表缺少批量归因入口。
- 架构层：工单域 / 问题实例归因 / 工单列表 / 工单详情 / 版本展示。
- 更新的页面：`server/modules/ticket/entity/vo/ticket_issue_vo.py`、`server/modules/ticket/dao/ticket_issue_dao.py`、`server/modules/ticket/service/issue/ticket_issue_service.py`、`server/modules/ticket/controller/ticket_issue_controller.py`、`server/modules/ticket/enums/ticket_enums.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/issue/index.vue`、`web/src/views/ticket/components/TicketDetailWithList.vue`、`web/src/views/ticket/index.vue`、`web/public/docs/2026-08-21-ticket-issue-association-plan.md`、`web/public/docs/ticket_detail.md`、`web/public/docs/updates/2026-08-21-ticket-issue-association.md`、`wiki/flows/ticket-issue-attribution-flow.md`。
- 变更传播链：`ticketNo` 远程搜索 -> Issue 单张业务号绑定 -> `ticket.issue_id` 主归因 -> Issue 影响工单数刷新；工单列表当前页多选 -> 全量预校验 -> 批量事务绑定 -> 目标/旧 Issue 计数刷新 -> `ISSUE_ATTRIBUTED` 事件。
- 关键结论：内部 `ticket_id/first_ticket_id` 保留为稳定关联，用户界面改用工单号；批量归因默认不覆盖其他 Issue；相似度和工单分类仍不自动强绑定；Issue 版本先从绑定工单四类版本实时聚合。
- 验证：已补充问题实例服务定向测试、后端编译和前端构建待环境限流恢复后执行。

## [2026-08-21] FIX | 修复工单日志上下文横向滚动

- 触发：用户反馈工单日志上下文查看窗口在关闭换行时无法左右滑动，影响较长日志内容查看。
- 根因：日志行默认样式使用 `overflow: hidden`，在子元素层截断了单行内容，父级滚动容器无法形成横向溢出范围；该规则来自此前日志大文件显示优化。
- 变更传播链：`LogViewerDialog.vue` 日志上下文行样式 -> `.log-content-block` 横向滚动 -> 工单详情日志拉取和日志拉取记录查看入口；服务端上下文行长度保护及完整行按需读取逻辑保持不变。
- 更新文件：`web/src/components/ticket/LogViewerDialog.vue`、`web/public/docs/ticket_log_viewer.md`、`web/public/docs/updates/2026-08-21-ticket-log-viewer-horizontal-scroll-fix.md`、`web/public/docs/updates/history.md`、`wiki/flows/ticket-log-record-isolated-view.md`。

## [2026-08-21] INGEST-CODE | 修复工单日志拉取门店回填

- 触发：工单详情日志拉取弹窗未回填门店，且工单门店值可能不完整或无法匹配门店配置时仍需要原样显示。
- 根因：详情页切换到轻量 summary 后，`TicketSummaryModel` 未声明 `extraData`，导致 `log_pull_hints`、`external_sync.source` 和自动日志配置在响应模型校验时被过滤；同时历史同步字段可能只保存顶层 `external_field_mapping.ticketStore`。
- 变更传播链：`Ticket.extra_data` -> `TicketSummaryModel.extra_data` -> `useLogViewer` 多来源回填 -> `LogPullConfigFields` 按 `org_no/storeCode/sap_org_no` 匹配；命中后提交 `org_no` 并显示门店名称、`org_no`、`sap_org_no`，未命中保留原始值。
- 更新文件：`server/modules/ticket/entity/vo/ticket_read_vo.py`、`server/tests/test_ticket_summary_log_pull_hints.py`、`web/src/views/ticket/hooks/useLogViewer.js`、`web/src/components/ticket/LogPullConfigFields.vue`、`web/public/docs/ticket_log_pull.md`、`web/public/docs/updates/2026-08-21-ticket-log-pull-store-prefill.md`、`web/public/docs/updates/history.md`、`wiki/entities/services/ticket-domain.md`。


- 结论：生产有效工单的 `submit_time` 已全部回填，工单列表、详情响应和实时统计不再从 `extra_data.external_sync` JSON 或 `create_time` 回退提交时间。
- 列表语义：`/ticket/list` 的提交时间范围筛选、默认排序、`submitTime`/`submit_time` 排序和页面展示统一以 `ticket.submit_time` 为准，默认顺序为 `submit_time DESC, ticket_id DESC`；详情与实时统计沿用相同主表时间口径。
- 性能：移除 JSON `COALESCE` 时间表达式后，默认列表可使用既有 `idx_ticket_del_submit_time (del_flag, submit_time, ticket_id)` 反向扫描，避免全表扫描与 Top-N 排序。
- 索引：ORM 同步声明 `idx_ticket_del_module_code_submit_time`、`idx_ticket_log_pull_ticket_created_status`、`idx_ticket_ai_task_ticket_created_status`；物理 `CREATE INDEX` 由运维按同名、同列顺序手工执行，本次未执行 DDL。
- 边界：`externalCreateTime` 继续保留为外部同步来源和审计元数据；同步、导入和手工创建链路仍负责将业务提交时间写入 `submit_time`。
- 验证：新增列表 SQL 编译、列表响应装饰和 ORM 索引元数据回归测试；生产索引创建后需执行只读 `EXPLAIN` 确认模块筛选和最新日志/AI 状态查询命中新索引。


## [2026-08-21] FEAT | 工单轻量概览与按需读取接口

- 功能：新增工单轻量概览、独立相似工单和消息/快照按需读取接口；旧工单详情与消息接口保持兼容。
- 后端新增：`GET /ticket/{ticket_id}/summary`、`GET /ticket/{ticket_id}/similar-tickets`、`GET /ticket/{ticket_id}/messages/page`、`GET /ticket/{ticket_id}/snapshots/page`。
- 契约：相似工单 `data` 返回 `status/message/items`，消息和快照返回 `items/limit/hasMore`；数量参数默认分别为 5、20、10，最大 100。
- 安全：相似工单使用摘要白名单投影，工单、Issue、消息和快照的 BIGINT 主键按字符串返回。
- 关键日志：概览记录未加载消息、快照、相似度和提示词；相似度与按需读取记录 ticket_id、limit、返回数量和 has_more。
- 用户说明：`server/docs/ticket_read_api.md`。
- 验证：新增文件 compileall 与 Ruff 通过；本环境虚拟环境未安装 pytest，相关测试未能执行。


## [2026-08-26] FIX | 工单AI分析 Agent 响应 JSON 校验误报失败

- 现象：工单 AI 分析实际已由本机 Agent 执行并回传结果，但服务端任务记录被写成 `Cannot check isinstance when validating from json, use a JsonOrPython validator instead.`，页面无法看到真实的 Worker 失败摘要。
- 根因：`HandleResponse.response` 联合类型包含依赖 Python `isinstance` 判定的对象，服务端在工单网关调用和 Redis 缓存回读时误用 `model_validate_json` 直接校验原始 JSON 字符串，Pydantic 在 JSON 校验阶段抛出框架异常。
- 修复：为 `HandleResponse` 增加统一传输负载解析入口，先把 JSON 字符串/字节反序列化为 Python 字典，再执行 `model_validate`；工单 AI 网关与分发缓存统一复用该入口。
- 验证：新增 3 个回归测试，覆盖 `HandleResponse` 传输负载恢复、工单 AI 网关结果解析、Agent 分发缓存读取。
- 影响：修复后页面会优先展示 Agent/Worker 的真实失败原因，例如 PowerShell heredoc 语法不兼容、鉴权失败等，便于继续定位真正的执行问题。

## [2026-08-26] FIX | 工单AI分析提示词约束 Worker 直接输出 JSON

- 现象：Windows Agent 上的 Codex Worker 在部分任务中没有直接返回最终 JSON，而是尝试调用 PowerShell 用 heredoc 写入结果文件，触发 `PowerShell doesn't support heredoc with <<`。
- 根因：当前提示词只要求“输出严格 JSON”，但没有明确禁止 Worker 自行用 shell/python/PowerShell 写结果文件；在 `workspace-write` 沙箱下，模型可能把“产出结构化结果”误解为“需要落盘 JSON 文件”。
- 修复：服务端主提示词与 Agent 本地 fallback 提示词同步增加约束，明确禁止用 shell/heredoc 写结果文件，要求直接把最终 JSON 作为最后一条回复输出，由 CLI/服务自动保存。
- 验证：新增提示词回归测试，校验禁止 shell 文件写入、禁止 heredoc、声明系统自动保存结果文件。
- 影响：优先降低 Windows PowerShell 下 heredoc 误触发概率；若后续仍有个别模型不遵守提示词，再考虑进一步收紧工具权限。

## [2026-08-20] FIX | Provider模型下拉预览字段和工单分析初始化加载

- 现象：Provider弹窗点击“更新模型”后模型选项数量有返回但文案为空；工单AI分析/协同消息弹窗自动回填Provider后模型下拉为空，切换Provider后才出现。
- 根因：模型发现协议服务返回 `model_id/display_name` 普通字典，预览接口未按 Web camelCase 契约转换；工单页面只在 Provider `change` 事件中请求模型，初始化回填未触发请求。
- 修复：预览接口统一输出 `modelId/displayName`；新增工单模型选项加载 hook，初始化和切换均按当前 Provider 加载并忽略过期响应；分析和协同请求透传 `aiModelName`，服务端校验模型属于当前 Provider 启用目录后复用 `selectedWorkerModel` 执行链，空值回退 Provider 默认模型。
- 关键日志：Provider预览成功记录模型数量；任务创建阶段保留 Provider、模型和执行器快照，非法模型直接返回明确错误，不创建任务。
- 验证：后端变更文件 `compileall` 通过；前端 hook 语法检查通过；完整前端构建和真实 Provider/Agent 联调待环境可用后执行。


- 原因：模型目录新增接口为异步 FastAPI 路由，但底层 Service、DAO 和远端模型发现仍是同步实现，直接调用会阻塞事件循环。
- 修复：保留既有同步 Service/DAO 接口，模型目录查询、刷新、手动添加、启用/禁用、删除和模型选项接口统一通过 `await run_in_threadpool(...)` 执行。
- 兼容性：不改造共享 Service/DAO 方法，不切换 `AsyncSessionProxy`，降低对其他调用方的影响。
- 验证：模型目录相关控制器、DAO、Service 的 ruff 检查通过。


- 功能：支持一个 Provider 配置多个可用模型，使用方可按场景选择不同模型，实现"同一 API Key 不同模型"的灵活配置。
- 后端新增：6 个模型管理接口（全局模型列表、刷新并持久化、手动添加、启用/禁用、删除、按编码查询可用模型）。
- 后端修改：`AiProviderProtocolService.generate_text()` 新增 `model_name` 可选参数；`TicketSyncAiConfigService` 各 AI 配置段增加 `modelName` 字段；`TicketLightAiService` 所有调用点透传模型名称。
- 前端新增：Provider 管理页增加"可用模型"管理表格，支持添加/刷新/启用/禁用/删除模型；工单 AI 分析、同步自动化各配置段、协同消息均增加模型选择器。
- 权限：查看模型列表 `system:aiprovider:query`，管理模型 `system:aiprovider:edit`。
- 向后兼容：所有新增字段均为可选，空值时 fallback 到 Provider 的 `default_model`。

## [2026-08-18] FIX | 工单日志搜索内存峰值保护与并发限制

- 触发：生产 Supervisor 记录 FastAPI 在日志搜索开始后多次被 `SIGKILL`，随后由 `autorestart=true` 拉起；搜索实现通过 `communicate()` 和 `splitlines()` 暂存整批 rg 输出，且没有应用层搜索并发上限。
- 根因判断：应用日志只能确认外部 `SIGKILL`，OOM 需由 Pod 状态或 cgroup `memory.events` 最终确认；本次改造针对搜索峰值、超长行和并发叠加增加保护。
- 修复：新增 `maxConcurrentSearches`（默认 2，范围 1-8）和 `maxSearchLineBytes`（默认 524288，范围 1 KiB-4 MiB）配置；rg 最终输出层使用 `--max-columns --max-columns-preview`，Python 降级路径复用同一单行字节限制。
- 修复：rg 管道改为有界队列逐行消费，达到用户动态 `limit`、超时或异常时关闭并 wait 回收子进程；搜索接口不再额外复制固定 500 字符预览。
- 更新的页面：`server/modules/ticket/service/log_pull/ticket_log_service.py`、`server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`server/modules/ticket/util/ticket_log_search_limiter.py`、`server/modules/ticket/controller/ticket_log_pull_controller.py`、`web/src/views/ticket/syncAutomation/hooks/useLogPullStorageConfig.js`、`web/src/views/ticket/syncAutomation/index.vue`、`wiki/flows/ticket-log-record-isolated-view.md`、`wiki/entities/data-models/ticket-core-models.md`。
- 验证：新增并发限制、配置归一化、UTF-8 单行截断、动态 limit、native rg any/all 和进程流式清理测试；ruff 与日志相关 unittest 全部通过。

## [2026-08-17] FIX | 工单 AI 历史任务恢复写入 NULL 导致生产启动失败

- 触发：生产服务启动时清理 `created` / `running` 状态的工单 AI 历史任务，`ticket_ai_analysis_task.command_line` 被批量更新为 `NULL`，触发 MySQL 非空约束错误并导致 FastAPI 被 Supervisor 反复重启。
- 根因：`TicketAiAnalysisService._mark_task_status` 的 `command_line` 参数允许缺省，但更新数据时直接写入 `None`；数据库实体字段 `command_line` 为非空字段。
- 修复：状态更新时将 `command_line is None` 规范化为空字符串；已有命令内容保持不变。
- 验证：新增任务状态更新单元测试，覆盖缺省命令和已提供命令两种场景。
- 影响：仅影响工单 AI 任务状态更新；服务启动恢复流程不再因缺省执行命令触发数据库非空约束异常。

## [2026-08-17] FIX | Codex Worker 旧 bearer token 导致工单 AI 分析 401

- 触发：本地 Agent 使用 Provider `openai_com`（Provider ID 1）执行 Codex Worker 时，`auth.json.OPENAI_API_KEY` 指纹与 Provider 密钥一致且直接访问 `https://ai-router.dmall.com/v1/models` 返回 200，但 Worker `/responses` 返回 `401 Unauthorized: Invalid token`。
- 根因：任务级 Codex Home 从本机配置复制了 `[model_providers.custom]` 下旧的 `experimental_bearer_token`（例如本地代理令牌 `PROXY_MANAGED`）。Codex CLI 对该字段的使用优先级高于 `auth.json`，因此实际请求没有使用 Provider 下发的 API Key。
- 修复：`client_new/services/ticket_ai_analysis_service.py` 在准备任务级 Codex 配置时同步覆盖当前 `model_provider` 对应区段的 `experimental_bearer_token`；鉴权诊断也按该字段、`auth.json`、环境变量的实际回退顺序取值。
- 验证：新增任务级 bearer token 诊断与配置覆盖测试；`client_new` 定向测试 9 项全部通过。
- 影响：仅影响 `codex` Worker 的任务级配置准备和鉴权诊断，不修改本机全局 Codex 配置，不记录 API Key 明文。

## [2026-08-12] FIX | rg 日志搜索文件数过多导致 execve 参数过长应用重启

- 触发：日志搜索 `_search_by_rg_keywords` 将所有 193 个文件路径拼接为 rg 命令行参数，导致 `subprocess.Popen` 底层 `execve` 参数列表超长抛 `OSError`，未被现有异常处理器捕获，uvicorn worker 崩溃重启。
- 修复：
  - 新增 `RG_MAX_FILE_ARGS = 50` 常量，控制 rg 单次命令行文件数上限。
  - `_search_by_rg_keywords` 拆分为入口方法 + `_search_by_rg_keywords_single`（单批搜索）+ `_search_by_rg_keywords_batched`（分批搜索）。
  - 文件数 > 50 时自动按 50 个一批拆分，每批独立执行 rg 管道、合并去重，命中数达上限后跳过剩余批次。
  - 新增 `OSError` 异常捕获，兜底降级为 Python 搜索。
- 更新的页面：`server/modules/ticket/service/log_pull/ticket_log_service.py`。
- 验证：ruff 静态检查通过。

## [2026-08-11] INGEST-CODE | 日志拉取轮询改后台任务查询 + 停止功能落地

- 触发：日志拉取原实现中 `_poll_external_result` 在后台线程池（`max_workers=2`）内同步阻塞轮询外部平台，单条任务最长占用线程 1800s，批量提交时任务排队受并发限制；前端已有「停止」按钮但后端无 `/stop` 路由（404），`CANCELLED` 枚举无消费。
- 架构层：工单日志拉取服务（提交/探测/下载三阶段拆分）、Celery 周期任务、数据模型、控制器、前端日志拉取 Tab。
- 更新的页面：`server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/modules/ticket/dao/ticket_log_pull_dao.py`、`server/modules/ticket/controller/ticket_log_pull_controller.py`、`server/modules/ticket/entity/do/ticket_log_pull_do.py`（新增 `poll_deadline_at`）、`server/config/get_db.py`（兼容列升级）、`server/module_task/scheduler_maintenance.py`（新增 `scan_log_pull_records` 周期任务）、`web/src/views/ticket/components/detail-tabs/TicketDetailLogPullTab.vue`、`web/src/views/ticket/hooks/useLogViewer.js`、`web/src/views/ticket/logPullRecord/index.vue`、`web/public/docs/ticket_log_pull.md`。
- 变更传播链：创建记录投递线程池快速提交申请（写 `poll_deadline_at`）→ Celery 周期任务每 30 秒批量扫描（created 兜底提交 / submitting\polling 超时失败 / 单次探测命中则投递下载）→ 下载解析阶段含协作式取消检查点 → 停止接口置 `CANCELLED`。
- 关键规则：任务提交与轮询探测不再受并发数限制；周期任务 `scan_log_pull_records` 只做 `@register_job` 注册，**不在启动时自动写入 `celery_periodic_task`**，需在「系统监控-定时任务」手动配置（与项目其他定时任务一致）；`CANCELLED` 记录被周期任务跳过；下载/解析中断（线程丢失）重启清理为失败，轮询中记录由周期任务接管。
- 验证：`py_compile` 语法检查通过；ruff 静态检查确认本次改动未引入新错误（剩余 12 个均为原有代码问题）；本地起服务全链路验证待 uv/依赖环境与外部平台可达后执行。

## [2026-08-10] INGEST-CODE | 统一凭证绑定新增模式修复

- 修复统一凭证管理中，从“编辑绑定”切换到“新增绑定”时，表单残留旧 `bindingId` 导致保存误走更新的问题。
- 现在“新增绑定”会强制清空主键，避免同一业务、同一投影类型的后续新增记录覆盖旧记录。
- 同步补充了 `web/public/docs/credential_management.md` 与 `web/public/docs/updates/history.md` 的用户说明和更新记录。

## [2026-08-11] INGEST-CODE | 旧日志拉取记录重拉环境与凭证错误显式提示

- 旧的工单日志拉取记录重新拉取时，如果原记录没有保存环境信息，系统现在会直接报错，不再自动回退到第一个环境。
- 外部请求头解析时保留统一凭证解析失败的具体原因，并包装为“日志拉取外部接口凭证不可用：...”的明确错误。
- 日志拉取配置页仍然可以一次性查看全部环境，不影响现有配置展示。
## [2026-08-09] INGEST-CODE | 统一凭证 HTTP 刷新失败自动登录兜底（补充前端配置入口）

- 触发：统一凭证的 `http_refresh` 场景在刷新失败后，需要自动切换到登录接口重新获取凭证，再用登录得到的新凭证继续刷新。
- 架构层：统一凭证 / HTTP 刷新服务 / 刷新流程文档 / 用户说明文档 / 凭证编辑表单。
- 更新的页面：`server/modules/credential/service/credential_refresh_service.py`、`server/tests/test_credential_refresh_service.py`、`web/src/views/system/credential/components/CredentialDialog.vue`、`wiki/flows/credential-refresh.md`、`web/public/docs/credential_management.md`、`web/public/docs/updates/2026-08-09-credential-refresh-login-fallback.md`、`web/public/docs/updates/history.md`。
- 变更传播链：`http_refresh` 请求失败 -> 读取同配置的 `login_url` -> 执行登录请求并提取新密文 -> 用登录后的新凭证重试刷新 -> 乐观锁写回。
- 关键规则：只影响 `http_refresh` 且已配置登录地址的场景；`http_login` 仍保持单次登录语义不变；登录、刷新和重试请求都继续携带当前凭证中的附加 Header、附加 Cookie 和模板变量；前端在 `http_refresh` 模式下同时提供刷新接口和兜底登录接口配置入口。
- 验证：补充了刷新失败后登录兜底和 `refresh_credential()` 分支调用的定向测试，确保最终写回成功。

## [2026-08-09] INGEST-CODE | 统一凭证 HTTP 刷新失败自动登录兜底

- 触发：统一凭证的 `http_refresh` 场景在刷新失败后，需要自动切换到登录接口重新获取凭证，再用登录得到的新凭证继续刷新。
- 架构层：统一凭证 / HTTP 刷新服务 / 刷新流程文档 / 用户说明文档。
- 更新的页面：`server/modules/credential/service/credential_refresh_service.py`、`server/tests/test_credential_refresh_service.py`、`wiki/flows/credential-refresh.md`、`web/public/docs/credential_management.md`、`web/public/docs/updates/2026-08-09-credential-refresh-login-fallback.md`、`web/public/docs/updates/history.md`。
- 变更传播链：`http_refresh` 请求失败 -> 读取同配置的 `login_url` -> 执行登录请求并提取新密文 -> 用登录后的新凭证重试刷新 -> 乐观锁写回。
- 关键规则：只影响 `http_refresh` 且已配置登录地址的场景；`http_login` 仍保持单次登录语义不变；登录、刷新和重试请求都继续携带当前凭证中的附加 Header、附加 Cookie 和模板变量。
- 验证：补充了刷新失败后登录兜底和 `refresh_credential()` 分支调用的定向测试，确保最终写回成功。

## [2026-08-09] INGEST-CODE | 凭证模板变量校验与 Cookie 写回边界

- 触发：主 Header 为 `Cookie` 的凭证在刷新后被响应映射写入结构化 `cookies`，页面因 Cookie Header 与结构化 Cookie 冲突而无法保存；同时请求模板缺少可发现的变量插入和保存前校验。
- 架构层：统一凭证 / 凭证编辑表单 / HTTP 刷新响应提取。
- 更新的页面：`web/src/views/system/credential/components/CredentialDialog.vue`、`server/modules/credential/service/credential_refresh_service.py`、`server/tests/test_credential_refresh_service.py`、`web/public/docs/credential_management.md`、`web/public/docs/updates/2026-08-09-credential-template-variables-and-cookie-writeback.md`。
- 变更传播链：表单变量下拉 -> 光标位置插入 `${secret.xxx}` -> 保存前字段可用性与映射目标校验 -> 后端刷新写回保护 -> 加密凭证快照。
- 关键规则：保留 `${secret.cookie}` 的语义兼容；新增直接读取主 Header 值的高级 `${secret.headerValue}`（兼容历史 `header_value`）；主 Header 为 Cookie 时拒绝 `cookies` / `cookies.名称` 写回并提示改用 `header.cookie`，非 Cookie Header 保持 Header + Cookie 联合认证。
- 验证：新增后端定向测试覆盖 Cookie Header 写回拒绝、Authorization + 结构化 Cookie 允许、`${secret.headerValue}` 渲染和历史字段兼容；刷新日志对全部请求 Header 脱敏；前端构建验证见本次交付记录。

## [2026-08-09] INGEST-CODE | 凭证刷新 Cookie 模板变量修复

- 触发：开发环境凭证 ID `4` 使用 `http_header` 保存 `Cookie`（`headerName=cookie`、`headerValue` 存放完整 Cookie）时，2026-08-09 09:28:11 的刷新请求日志仍显示 `headers.cookie=${secret.cookie}`。
- 架构层：统一凭证 / HTTP 刷新服务 / 请求模板变量与安全日志。
- 创建的页面：无。
- 更新的页面：`flows/credential-refresh.md`、`contracts/credential-api.md`、`web/public/docs/credential_management.md`、`web/public/docs/updates/2026-08-09-credential-refresh-cookie-template.md`、`web/public/docs/updates/history.md`。
- 创建的双向链接：0 对（既有凭证流程、数据模型与接口契约的链接保持不变）。
- 变更传播链：加密凭证快照（`headerName` / `headerValue`） -> `CredentialRefreshService._build_template_secret` -> `${secret.cookie}` 渲染 -> HTTP 刷新请求；请求参数 -> `_mask_request_for_log` -> 脱敏刷新日志。
- 根因与修复：模板渲染只读取密文原始字段，而该类型没有 `cookie` 字段。现在当 Header 名称为 `Cookie` 时，将 Header 值映射为 `${secret.cookie}`；已有 `cookie` 和 `cookieHeader` 字段保持优先级。
- 验证：针对 ID `4` 的已脱敏配置执行模板渲染，确认结果不再含 `${secret.cookie}` 且值与已保存 Header 值一致；未发起真实刷新请求，避免非必要调用外部系统。请求日志会脱敏 Cookie、Token、Authorization、密码等敏感值。
- 总共涉及页面：5。

## [2026-08-08] INGEST-CODE | 工单日志查看器列宽拖拽手柄修复

- 触发：用户反馈日志查看弹窗搜索结果列表没有列宽分隔线，鼠标也不会显示左右拖动状态，导致列宽拖拽无法使用。
- 架构层：Web 前端 / 工单日志查看器 / Element Plus 虚拟表格。
- 更新的页面：`web/src/components/ticket/LogViewerDialog.vue`、`web/public/docs/updates/2026-08-08-ticket-log-viewer-column-resize-handle-fix.md`、`web/public/docs/updates/history.md`、`wiki/flows/ticket-log-record-isolated-view.md`。
- 变更传播链：`el-table-v2.headerCellRenderer` 回调 VNode -> 全局且受 `.ticket-log-viewer-dialog` 限定的手柄样式 -> 16px 可命中分隔线 -> `pointerdown/pointermove/pointerup` 更新列宽状态 -> 虚拟表格列配置重新计算。
- 关键结论：表格回调生成的 VNode 不能稳定匹配组件 `scoped` 样式；拖拽手柄样式改为弹窗范围内的全局样式，并使用 Pointer Events 和指针捕获避免快速拖动时丢失事件。
- 视觉调整：初版 16px 宽、32px 最小高度的手柄虽然恢复可用性，但会显得过大并可能撑高表头；现改为绝对定位的 12px 热区和 1px/16px 细分隔线，不参与 Flex 布局，保持表头默认 44px 高度。

## [2026-08-07] INGEST-CODE | 工单日志搜索结果列宽拖拽与关键字上限调整

- 触发：用户要求日志搜索结果去掉独立时间列，在日志内容列表头保留时间排序箭头，并评估后直接实现结果列宽拖拽；同时把搜索关键字上限从 10 提升到 20，其他限制保持不变。
- 关键结论：`LogViewerDialog.vue` 继续使用 `el-table-v2` 虚拟表格，但时间排序入口已移动到“日志内容”表头；独立时间列已移除，结果表新增轻量自定义列宽拖拽，拖拽期间只更新列配置，对当前结果量级性能影响可控。
- 变更传播链：`LogViewerDialog.vue` 搜索关键字归一化 -> 后端 `TicketLogSearchRequestModel` 请求校验 -> 旧版 `useLogViewer.js` 兼容 Hook -> 更新记录与知识库说明。
- 限制结论：搜索关键字上限已改为最多 20 个、每个最多 200 字符；高亮关键字也同步改为最多 20 个，并按关键字轮换不同颜色，性能影响仍可接受。

## [2026-08-03] INGEST-CODE | 工单日志查看器搜索结果内容列不换行

- 触发：用户反馈 `web/src/components/ticket/LogViewerDialog.vue` 中虚拟表格的日志内容列会换行，期望保持单行显示。
- 关键结论：`el-table-v2` 的内容单元格需要显式维持单行省略样式，避免长文本在虚拟表格里自动折行并抬高行高。
- 变更传播链：`LogViewerDialog.vue` 搜索结果内容列 `cellRenderer` -> 单行省略样式 -> 更新说明文档和更新历史。
- 文档结论：`web/public/docs/updates/2026-08-03-ticket-log-viewer-search-result-virtual-table.md` 与 `web/public/docs/updates/history.md` 已同步补充这次样式修复。

## [2026-08-03] INGEST-CODE | 帮助文档用户说明与更新记录分层

- 触发：用户希望 `web/public/docs` 主要承载面向最终用户的详细使用说明，同时把变更记录单独放入独立目录并保持自动发现展示。
- 关键结论：帮助中心仍通过 `docs-index.json` 自动发现文档，但索引和菜单规则已按“用户说明 / 更新记录”分层，更新记录统一走 `web/public/docs/updates/`。
- 变更传播链：`web/vite/plugins/docs-index.js` -> `web/src/views/about/about.vue` -> `web/public/docs` 用户说明文档和 `web/public/docs/updates/` 更新记录。
- 文档结论：用户说明需要补齐功能用途、入口、配置项、参数示例、注意事项和常见问题；修改业务逻辑时若无对应说明文档，必须先补齐再交付。

## [2026-07-31] INGEST-CODE | 自动化关注范围模块 Code 与历史统计匹配

- 触发：开发环境配置模块名称关键字 `POS` 后，统计 2026-07-23 至 2026-07-30 无数据；同时需要模块 Code 配置和空条件放行语义。
- 关键结论：开发库历史 POS 工单的 `module_id` 全部为空，原实现只按 HRM 模块 ID 统计导致 0 条；现在实时/快照统计均可直接按工单或快照 `module_name` 关键字匹配，模块 Code 先解析为系统模块 ID。
- 变更传播链：`TicketAutomationScopeService` -> `TicketDao`/统计 DAO -> 处理统计服务 -> 统计页面；同步配置前端新增 `moduleCodes`，范围开启但三类条件均为空时不限制。
- 权限结论：自动化关注范围不单独限制 admin，页面共用 `ticket:sync:config:list/edit`；开发库当前仅 `manager` 角色拥有对应菜单权限。

## [2026-07-31] INGEST-CODE | 工单统计自定义趋势图默认展示

- 触发：已配置且启用的自定义趋势指标在工单统计页面没有显示。
- 关键结论：后端 `/ticket/statistics/trend` 已正常返回 `customMetrics`，但前端加载定义后清空选中项，且趋势容器没有将自定义图纳入可见条件。
- 变更传播链：已启用指标定义 -> 默认选中 `metricCodes` -> 趋势接口 -> 自定义图表容器与 ECharts 渲染。

## [2026-07-31] INGEST-CODE | 自定义趋势空值条件与工单类型候选

- 触发：自定义趋势的工单类型条件需要统计空字符串或 `null`，并希望直接选择系统工单类型。
- 关键结论：新增 `is_empty`/`is_not_empty` 条件，不复用文本 `null`；配置归一化允许这两个运算符没有匹配值，运行时统一处理 `None`、空字符串和空白。
- 变更传播链：趋势指标编辑器 -> 同步配置规范化 -> 条件匹配工具 -> 实时统计和快照指标计算；`issueTypeId` 匹配值候选来自当前 `statClassification.issueTypes`。

## [2026-07-28] INGEST-CODE | AI Provider 能力模型重构

- 触发：用户要求 Provider 明确区分平台、协议和业务用途，模型可远端拉取，密钥查看需密码二次验证，且不保留旧数据兼容代码。
- 架构层：系统管理 / AI Provider；工单轻量 AI；工单 AI 分析 Worker。
- 新增文件：`module_admin/service/ai_provider_capability_service.py`（能力契约）、`module_admin/service/ai_provider_protocol_service.py`（协议调用和模型发现）、`module_admin/service/ai_provider_model_catalog_service.py` 与 `dao/ai_provider_model_dao.py`（模型目录）、`server/sql/20260728_ai_provider_capability_model.sql`（数据库重构脚本）。
- 变更传播链：Provider 平台/协议/用途/执行器 -> `/system/aiprovider/options` 场景过滤 -> 工单配置下拉 -> 轻量直连或 Codex Worker 的服务端强校验。
- 关键结论：`provider_type` 已不再作为兼容入口；执行 SQL 后旧 Provider 必须逐条重新确认用途、执行器与协议，未配置的 Provider 不会出现在工单候选列表。

## [2026-07-28] INGEST-CODE | AI Provider 草稿模型刷新与连通性测试

- 触发：新增或编辑 Provider 时，用户要求“更新模型”和模型测试必须使用弹窗当前填写的地址、协议、模型和扩展配置，不能回退到尚未保存的旧数据库配置。
- 架构层：系统管理 / AI Provider / 表单草稿连接服务。
- 新增文件：`module_admin/service/ai_provider_connection_service.py`。
- 变更传播链：Provider 弹窗草稿 -> `/system/aiprovider/model-catalog/preview` 或 `/system/aiprovider/connection/test` -> 临时 Provider 连接对象 -> 协议服务；新增使用页面密钥，编辑未填写新密钥时仅在服务端读取同一 Provider 的密文密钥。
- 关键结论：模型目录和测试请求均不写数据库、不回显密钥；旧的“按已保存 Provider 配置刷新模型目录”接口已移除，避免临时修改配置时测试错目标。

## [2026-07-28] INGEST-CODE | 工单日志查看器文件范围与 Esc 交互

- 触发：日志查看弹窗的文件范围下拉需要始终展示当前日志拉取记录全部文件；子区域全屏时按 Esc 不应关闭弹窗。
- 架构层：工单模块 / 日志查看器前端交互。
- 更新的页面：`web/src/components/ticket/LogViewerDialog.vue`（准备完成后调用文件列表接口并按后端顺序维护下拉项；全屏子区域优先拦截 Esc 并还原）、`web/public/docs/2026-07-04-ticket-log-viewer-file-scope-highlight.md`、`web/public/docs/2026-07-28-ticket-log-viewer-file-list-and-escape.md`、`web/public/docs/update_history.md`、`wiki/flows/ticket-log-record-isolated-view.md`。
- 变更传播链：`GET /ticket/logs/files` -> `LogViewerDialog.availableFiles` -> 文件范围下拉；文档捕获阶段的 `Escape` 事件 -> 子区域全屏状态还原 -> `el-dialog` 默认关闭行为。
- 关键结论：搜索结果只控制结果表，不再控制可选文件集合；任一子区域全屏时 Esc 被消费并恢复普通视图，非全屏状态下弹窗仍可由 Esc 关闭。

## 2026-07-26
- **群推送人员邮箱解析新增 raw_payload.fields 兜底**：`ticket_sync_notify_service.py` 的 `_resolve_ticket_person_email` 邮箱解析链路新增第四级回退，从 `raw_payload.fields`（多维表格原始字段）中按姓名匹配飞书人员对象直接提取邮箱。解决 bitable_pull 场景下当 email 类字段未映射到 external_field_mapping 且系统无对应用户时，@mention 始终为空的问题。同时将 bitable_pull 场景也纳入 `TicketExternalBitableEmailService.enrich_person_emails` 的反查补齐范围。
- **wiki/flows/ticket-external-sync-flow.md**：更新 5.1.13 步描述，记录新增的邮箱兜底解析逻辑。

## [2026-07-25] INGEST-CODE | 工单群推送条件表达式引擎（v2: 移除旧条件）

- 触发：用户要求完全移除旧的 `autoPushStatuses` 和 `autoSendAfterTime`，以及帮助提示缺少可用字段列表。
- 架构层：工单模块 / 同步服务 / 群推送配置。
- 更新的页面：`server/modules/ticket/service/sync/ticket_sync_group_push_service.py`（删除 `resolve_ticket_submit_time`、`resolve_group_push_auto_send_after_time`、`normalize_group_push_auto_statuses`、`should_skip_auto_group_push_by_status`、`_evaluate_auto_push_condition`、`should_skip_auto_group_push_by_submit_time`；新增 `should_skip_auto_group_push_by_condition`）、`server/modules/ticket/service/sync/ticket_sync_config_service.py`（删除 `DEFAULT_GROUP_PUSH_AUTO_STATUSES`、`normalize_group_push_auto_statuses`、`autoPushStatuses`/`autoSendAfterTime` 配置项）、`web/src/views/ticket/syncAutomation/index.vue`（删除两个旧表单项，更新帮助 popover 加入完整字段列表和更多示例）、`web/src/views/ticket/syncAutomation/hooks/useSyncConfig.js`（删除 `groupPushAutoStatusOptions`、`autoPushStatuses`/`autoSendAfterTime` 所有引用）
- 更新的页面：`wiki/flows/ticket-external-sync-flow.md`（步骤 11.1 描述更新）
- 变更传播链：仅影响自动群推送过滤配置；旧配置 `autoPushStatuses` 和 `autoSendAfterTime` 不再可用，需用 `autoPushCondition` 表达式重写。
- 关键结论：`autoPushCondition` 是唯一过滤条件，留空表示全部推送。语法错误会安全跳过并记录日志。前端帮助 tooltip 已包含完整语法说明、6 个常用示例和按分类列出的所有可用字段。

## [2026-07-25] INGEST-CODE | 工单群推送条件表达式引擎

- 触发：用户要求支持自定义流推送过滤条件，不再仅按工单状态判断。
- 架构层：工单模块 / 同步服务 / 群推送配置。
- 创建的页面：`web/public/docs/2026-07-25-ticket-group-push-custom-condition.md`
- 新增的文件：`server/modules/ticket/service/sync/ticket_sync_condition_evaluator.py`（条件表达式引擎）
- 更新的页面：`server/modules/ticket/service/sync/ticket_sync_group_push_service.py`（`should_skip_auto_group_push_by_status` 优先使用 `autoPushCondition` 表达式）、`server/modules/ticket/service/sync/ticket_sync_config_service.py`（`default_group_push_config` 新增 `autoPushCondition: ""`）、`web/src/views/ticket/syncAutomation/index.vue`（新增自定义推送条件输入框与帮助 tooltip）、`web/src/views/ticket/syncAutomation/hooks/useSyncConfig.js`（默认值与序列化适配）
- 更新的页面：`wiki/flows/ticket-external-sync-flow.md`（步骤 11.1 新增）
- 变更传播链：仅影响自动群推送过滤判断，不影响其他链路；留空时完全向后兼容。
- 关键结论：实现了安全受限的布尔表达式求值器，支持字段比较、列表成员、空值判断和逻辑运算。优先使用自定义表达式，否则回退到原有状态白名单。

## [2026-07-24] INGEST-CODE | 版本号统一管理

- 触发：用户要求统一 server/web/client_new 三端版本号，每端只需修改一处。
- 架构层：基础设施 / 配置管理。
- 创建的页面：`web/public/docs/2026-07-24-version-unified.md`
- 新增的文件：`server/version.py`、`client_new/version.py`
- 更新的页面：`server/config/env.py`（`app_version` 默认值从 `version.py` 导入）、`server/.env.base` / `.env.dev` / `.env.prod` / `.env.test`（删除 `APP_VERSION`）、`server/pyproject.toml`（注释指向 `version.py`）、`client_new/utils/__init__.py`（`VERSION` 从 `version.py` 导入）、`client_new/pyproject.toml`（版本号从 `0.1.0` 同步为 `1.0.4.4`）、`client_new/QTRClientNew.spec` / `QTRClientNewPortable.spec`（从 `version.py` 读取版本设置 exe 文件属性）
- 变更传播链：无传播影响，纯配置变更。
- 关键结论：三端版本独立演进。发版时只需修改 `server/version.py`、`client_new/version.py`、`web/package.json`。`pyproject.toml` 中的 `version` 字段仍需手动同步（Python 包元数据无法动态读取）。

## [2026-07-22] INGEST-CODE | 工单日志查看下载进度迁移至 Redis

- 触发：用户要求将日志准备下载进度从进程内存迁移到 Redis，解决多实例部署时的请求粘性问题。
- 架构层：工单域 / 日志拉取准备进度。
- 创建的页面：`web/public/docs/2026-07-21-ticket-log-view-download-progress.md`
- 新增的文件：`server/modules/ticket/service/log_pull/ticket_log_prepare_progress_service.py`、`web/src/views/ticket/hooks/useLogPrepareProgress.js`
- 更新的页面：`server/modules/ticket/controller/ticket_log_pull_controller.py`、`server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/modules/ticket/service/log_pull/ticket_log_service.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/hooks/useLogViewer.js`、`web/src/views/ticket/components/detail-tabs/TicketDetailLogPullTab.vue`、`web/src/views/ticket/logPullRecord/index.vue`、`wiki/flows/ticket-log-record-isolated-view.md`
- 变更传播链：`TicketLogPrepareProgressService`（新）使用 `app.state.redis` 存储进度快照（key 前缀 `ticket:log-prepare-progress`，TTL 30 分钟）-> Controller 在线程池下载回调中用 `asyncio.run_coroutine_threadsafe` 安全跨线程写入 -> `TicketLogPullService._download_archive` / `_download_file_from_ftp_to_temp` 上报 HTTP/FTP 下载字节 -> 前端 `useLogPrepareProgress` 每 400ms 轮询 `GET /ticket/logs/prepare-progress`，`downloading=true` 时替换列表行"查看日志"按钮为圆形进度条。
- 关键结论：进度状态不持久化，TTL 到期自动清除；若 `CACHE_BACKEND=memory` 则退化为单进程内存存储，行为等价于迁移前。

## [2026-07-21] INGEST-CODE | 工单日志选区高亮回归修复

- 触发：用户反馈工单详情页日志搜索详情中，选中文本无法高亮也无法作为候选词复制，要求修复选中即高亮、取消选区移除临时高亮、保留其他高亮词，并分析是否改用编辑器展示日志详情。
- 架构层：Web 前端 / 工单详情日志拉取 tab / 日志上下文高亮。
- 创建的页面：`web/public/docs/2026-07-21-ticket-log-selection-highlight-regression-fix.md`
- 更新的代码：`web/src/views/ticket/components/detail-tabs/TicketDetailLogPullTab.vue`
- 变更传播链：日志上下文浏览器选区 -> `captureLogViewerHighlight` 写入临时高亮词 -> `TicketDetailLogPullTab.vue` 使用 CSS Highlight API 注册文本节点 `Range` -> 浏览器原生选区保持可复制；不支持 CSS Highlight API 时继续使用 `<mark>` 分片回退。
- 关键结论：当前日志详情只展示上下文窗口，短期继续使用 `<pre>` 更轻；若未来展示整份大日志再考虑 CodeMirror/Monaco，并需要自定义 gutter 才能保留原始日志行号。

## [2026-07-21] INGEST-CODE | 工单优先级双向补齐与群模板处理人兜底

- 触发：用户要求外部推送、内网拉取和飞书多维表格主动拉取入库时，外部优先级和内部优先级缺一侧也要同时入库，并要求群消息模板当前处理人为空时可用内部负责人替换。
- 架构层：工单域 / 外部同步入库 / 飞书主动拉取 / 远端拉取 / 群消息通知模板。
- 创建的页面：`web/public/docs/2026-07-21-ticket-priority-pair-and-assignee-template-fallback.md`
- 更新的页面：`server/modules/ticket/util/ticket_priority_util.py`、`server/modules/ticket/service/sync/ticket_external_sync_request_service.py`、`server/modules/ticket/service/sync/ticket_bitable_pull_service.py`、`server/modules/ticket/service/sync/ticket_remote_sync_service.py`、`server/modules/ticket/service/sync/ticket_sync_payload_service.py`、`server/modules/ticket/service/sync/ticket_sync_notify_service.py`、`web/src/views/ticket/syncAutomation/hooks/useSyncConfig.js`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`ticket_priority_util.complete_ticket_priority_pair` -> 外部推送请求归一化 / 主动拉取记录转换 / 远端拉取模型转换 / 入库 payload 兜底 -> `customer_priority/internal_priority` 同时入库；群消息变量构造 -> 当前处理人展示和 @ 变量为空时回退内部负责人。
- 关键结论：本次不改变“双方都有值时各自入库”的语义，只在缺一侧时按 `Level 0/A/B/C/D <-> P0/P1/P2/P3/P4` 补齐；未安装 `pytest`，本地仅完成 ruff 检查，新增单测待环境补齐后执行。

## [2026-07-17] INGEST-CODE | 工单编辑页 tagText 缺失修复

- 触发：用户点击工单列表的编辑按钮时，编辑弹窗打开阶段报 `Unhandled error during execution of native event handler`，根因是 `reset()` 里访问了未定义的 `tagText`。
- 架构层：Web 控制台 / 工单编辑弹窗 / 表单状态修复。
- 创建的页面：`web/public/docs/2026-07-17-ticket-edit-tagtext-missing-fix.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：编辑弹窗 `reset()` -> `tagText.value = ''` -> 补回 `const tagText = ref('')` -> 编辑按钮恢复正常打开。
- 关键结论：这是一个纯状态缺失问题，补回缺失响应式变量即可，不需要改编辑弹窗的提交或回填流程。

## [2026-07-17] INGEST-CODE | 工单列表更多菜单权限指令告警修复

- 触发：用户进入工单列表页时，控制台持续告警 `Runtime directive used on component with non-element root node`。
- 架构层：Web 控制台 / 工单列表 / 更多菜单权限判断。
- 创建的页面：`web/public/docs/2026-07-17-ticket-list-dropdown-directive-warning-fix.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：`el-dropdown-item` 上的 `v-hasPermi` -> 页面内 `canDeleteTicket` 布尔值 -> 删除项 `v-if` 控制显示 -> Vue 不再对非元素根组件执行运行时指令。
- 关键结论：这次修复只改权限判断挂载位置，不改删除权限语义和删除行为。

## [2026-07-17] INGEST-CODE | 工单列表操作列更多菜单收口

- 触发：用户要求工单列表操作列默认只显示详情、编辑、指派、流转和更多，前四个只显示图标，其他操作收进更多下拉菜单，且更多菜单需要图标和文案同时展示。
- 架构层：Web 控制台 / 工单列表操作列 / 更多动作下拉。
- 创建的页面：`web/public/docs/2026-07-17-ticket-list-more-actions-dropdown.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/hooks/useLogViewer.js`、`web/public/docs/update_history.md`
- 变更传播链：操作列从平铺文本按钮改为图标按钮 + 更多下拉 -> 日志、跳转和删除动作进入更多菜单 -> 更多菜单复用既有日志查看、外链跳转和删除逻辑。
- 关键结论：这次调整只收口展示形态，不新增业务能力；详情、编辑、指派、流转仍保留原权限判断，更多菜单只是承载原本已有的补充动作。

## [2026-07-17] INGEST-CODE | 工单列表与详情默认折叠优化

- 触发：用户要求工单列表默认隐藏大部分筛选项，详情页顶部默认只显示前九项并把更多信息折叠到标题后的按钮里，同时协同 tab 有版本号时自动回填默认版本。
- 架构层：Web 控制台 / 工单列表筛选 / 工单详情展示 / 协同版本默认值。
- 创建的页面：`web/public/docs/2026-07-17-ticket-list-detail-collapse-and-collab-version-default.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/hooks/useTicketList.js`、`web/src/views/ticket/components/TicketDetailWithList.vue`、`web/src/views/ticket/components/detail-tabs/TicketDetailCollabTab.vue`、`web/public/docs/update_history.md`
- 变更传播链：列表页搜索区折叠状态下只保留核心筛选字段 -> 重置后提供展开/收起按钮切换更多筛选 -> 详情页标题行提供更多信息展开/收起按钮，默认只展示前九项和描述/翻译 -> 协同 tab 等待项目版本选项加载完成后回填工单版本或首个可用版本。
- 关键结论：这次调整只改变默认展示和回填时序，不清空任何被隐藏的筛选值；详情页隐藏区只是展示折叠，不影响 tabs、描述或翻译；协同版本默认值优先取工单版本，缺失时才用当前项目首个版本。

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
- 关键结论：tab 组件不是临时模板拆分，而是不接收父级上下文对象；为减少重复 `getTicket`，概览、日志拉取、协同支持 `ticketId/detail` 双入口，父详情已有详情时复用，未传详情时仍可围绕工单 ID 自行闭环。

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

## [2026-07-21] INGEST-CODE | 工单群推送一线人员邮箱错配排查日志
- 触发：用户反馈主动拉取工单群推送中 reporter name 正确但 email 错误，导致飞书 @ 到错误人员；部分工单 email 为空导致无法 @ 一线人员。
- 架构层：工单域 / 主动拉取 / 群消息推送
- 创建的页面：`web/public/docs/2026-07-21-ticket-group-mention-email-diagnostic.md`
- 更新的页面：`flows/ticket-external-sync-flow.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketBitablePullService.build_bitable_pull_sync_object` -> 主动拉取人员字段映射日志；`TicketSyncNotifyService._resolve_ticket_person_email` -> 群推送邮箱来源日志；`TicketSyncNotifyService._resolve_group_mention_open_ids` -> 飞书用户名错配告警。
- 总共涉及页面：2

## [2026-07-21] INGEST-CODE | 新版客户端 POS 启动日志与任务生命周期保护
- 触发：启动 POS 后客户端 Python 进程在 `Qt6Core.dll` 发生访问违规，但独立启动的 POS 继续运行。
- 架构层：新版 PySide6 客户端 / POS 启动 / 本地日志查看
- 创建的页面：`web/public/docs/2026-07-21-client-pos-start-qt-crash-guard.md`
- 更新的页面：无
- 创建的双向链接：0 对
- 变更传播链：`pos_init` 响应 -> 安全日志摘要；`_FileTailThread` -> 超长单行截断 -> `QTextEdit`；`PosController.start_pos` -> Worker 强引用 -> 成功或失败信号后释放。
- 总共涉及页面：1
## [2026-07-21] INGEST-CODE | 查看日志远程下载进度
- 触发：用户要求工单详情和日志拉取管理列表在查看日志需要后端下载时，显示禁用的圆形下载进度。
- 架构层：工单域 / 日志查看 / 日志拉取 / Web 控制台。
- 创建的页面：`web/public/docs/2026-07-21-ticket-log-view-download-progress.md`
- 更新的页面：`wiki/flows/ticket-log-record-isolated-view.md`
- 创建的双向链接：1 对（新增/修改）。
- 变更传播链：详情或管理列表查看日志 -> `/ticket/logs/prepare` -> `TicketLogPrepareProgressService` -> HTTP/FTP 分块下载回调 -> `/ticket/logs/prepare-progress` -> `useLogPrepareProgress` -> 当前行圆形进度条；管理页实时查看复用准备后的 source 源包。
- 总共涉及页面：2。
## [2026-07-22] INGEST-CODE | 日志拉取商家参数配置与门店按需加载

- 触发：商家规模较小，要求不新增商家维护模块或商家表；商家由参数配置维护，选择商家后才按 `vender_no` 查询门店。
- 架构层：工单域 / 日志拉取配置 / 系统参数配置 / 门店选项查询。
- 创建的页面：`web/public/docs/2026-07-22-ticket-log-pull-vendor-config-lazy-store-options.md`。
- 更新的代码：`server/modules/ticket/controller/ticket_log_pull_controller.py`、`server/modules/ticket/dao/ticket_log_pull_dao.py`、`server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`server/sql/20260722_ticket_log_pull_vendor_config.sql`、`web/src/components/ticket/LogPullConfigFields.vue`、`web/src/views/ticket/logPullRecord/index.vue`。
- 变更传播链：`sys_config.ticket.logPull.vendors` -> 日志拉取商家选项接口 -> 商家下拉 -> 携带 `vender_no` 查询 `ticket_log_pull_store_config` -> 门店下拉。
- 关键结论：`vender_no` 是商家参数配置和门店配置的唯一关联键；首次加载不读取门店表，日志拉取记录和外部接口现有的整数 `vendorId` 字段保持兼容。
- 补充交互：商家和门店选择器均保留 `filterable + allow-create + default-first-option`，用户输入并确认的文本可直接作为日志拉取参数，不会被配置选项限制。

## [2026-07-27] INGEST-CODE | 工单 AI 任务级 Codex 模型目录复制
- 触发：Agent 执行工单 AI 分析时，Codex Worker 启动后立即返回“系统找不到指定的文件。 (os error 2)”。
- 架构层：新版 PySide6 客户端 / 工单 AI Worker / Codex 配置隔离。
- 创建的页面：`web/public/docs/2026-07-27-ticket-ai-codex-model-catalog-copy-fix.md`。
- 更新的页面：`flows/ticket-automation-flow.md`、`entities/services/ticket-domain.md`。
- 创建的双向链接：0 对（沿用工单自动化流程与工单域既有双向链接）。
- 变更传播链：用户级 `config.toml.model_catalog_json` -> `TicketAiCodexConfigService.copy_model_catalog` -> 任务级 `.codex_home` -> `codex exec` 启动。
- 总共涉及页面：3。

## [2026-07-27] INGEST-CODE | 工单轻量 AI 配置统一收敛
- 触发：用户要求清理 AI 配置中心与工单同步配置之间的重复配置，不保留旧配置兼容，并让群推送按工作流状态显示名判断。
- 架构层：工单域 / 同步配置 / 轻量 AI / 定时任务 / 群推送 / Web 控制台。
- 创建的页面：`web/public/docs/2026-07-27-ticket-sync-light-ai-config-consolidation.md`。
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-automation-flow.md`、`flows/ticket-external-sync-flow.md`、`web/public/docs/update_history.md`。
- 创建的双向链接：0 对（沿用工单域与同步流程既有双向链接）。
- 变更传播链：`ticket.sync.automation` -> `TicketSyncAiConfigService` -> 翻译/标题总结/分类/参数提取/知识提炼；定时任务显式 `automation` -> 主动拉取任务级覆盖；工作流状态编码 -> `status_name` -> 群推送条件表达式。
- 总共涉及页面：5。
## [2026-07-27] INGEST-CODE | 工单 AI 整包日志缓存与手工选择
- 触发：同一工单重复执行 AI 分析时，Agent 每次重复下载整包日志；用户要求默认使用最新日志，并可手动选择历史日志记录。
- 架构层：工单域 / AI 分析 / 新版 PySide6 Agent / Web 控制台。
- 创建的页面：`web/public/docs/2026-07-27-ticket-ai-log-cache-and-selection.md`。
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-automation-flow.md`、`web/public/docs/update_history.md`。
- 变更传播链：`TicketAiAnalysisRequestModel.log_pull_record_id` -> 成功日志归属校验 -> Agent `log_cache/ticket_<id>/log_pull_<id>/<sourceHash>` -> Worker 提示词实际日志目录；工单详情 AI 弹窗 -> 成功日志选择列表 -> 指定 `logPullRecordId`。
- 关键日志：首次下载记录“下载并解压整包日志”，命中缓存记录“复用本地整包日志缓存”，本地归档可访问时记录“使用本地归档并解压整包日志”。

## [2026-07-28] INGEST-CODE | 工单 AI Codex 鉴权故障诊断

- 触发：历史任务返回 `401 Unauthorized: Invalid token`，需要区分任务级配置复制、当前 key 有效性与 Provider Responses 链路故障。
- 架构层：工单域 / 新版 PySide6 Agent / Codex Worker / OpenAI 兼容 Provider。
- 创建的页面：`web/public/docs/2026-07-28-ticket-ai-codex-auth-diagnostic.md`。
- 更新的页面：`flows/ticket-automation-flow.md`、`entities/services/ticket-domain.md`、`web/public/docs/update_history.md`。
- 变更传播链：任务级 `.codex_home/auth.json` 与 `config.toml` -> Worker 失败诊断 -> 命中 401 时 `GET /models` 探测 -> `ai_analysis_step` / `ai_analysis_error` 事件 -> 服务端系统日志。
- 关键约束：只记录密钥长度与 SHA-256 前 16 位；探测不调用模型、不重试原任务；`/models` 返回 200 时仍需结合 Worker request ID 排查 Provider 的 Responses 链路。

## [2026-07-29] INGEST-CODE | 工单项目版本中心与发布事实

- 触发：用户确认版本必须统一维护，工单自动发现版本时不能阻断业务，并要求开始实施。
- 架构层：工单域 / 版本主数据 / 发布管理 / AI 仓库映射。
- 创建的页面：`concepts/ticket-version-center.md`、`web/public/docs/2026-07-29-ticket-version-center.md`。
- 更新的页面：`index.md`、`entities/data-models/ticket-core-models.md`、`entities/services/ticket-domain.md`、`web/public/docs/update_history.md`。
- 变更传播链：工单手工创建、同步、导入、日志提取和批量版本维护 -> `TicketVersionService.assign_detected_ticket_version` / `validate_ticket_version_ids` -> `ticket_version` 候选/确认版本 -> `ticket.*_version_id`；版本中心 -> `ticket_version_release` 发布事实；版本中心 -> `ticket_ai_repo_mapping.version_id`。
- 关键约束：发布事实不自动关闭工单；验证通过后才由既有工作流处理关闭。未知版本创建 `discovered` 候选版本，不自动创建 AI 仓库映射。
- 总共涉及页面：5。

## [2026-07-29] INGEST-CODE | 工单版本中心仅 ID 关联

- 触发：用户明确不保留旧版本文本和旧数据兼容，要求工单、AI 映射和 AI 任务统一只关联版本中心 ID。
- 架构层：工单域 / 版本中心 / 外部同步 / Excel 导入 / 日志提取 / AI 分析 / Web 控制台。
- 创建的页面：`web/public/docs/2026-07-29-ticket-version-id-only.md`。
- 更新的页面：`concepts/ticket-version-center.md`、`entities/data-models/ticket-core-models.md`、`entities/services/ticket-domain.md`、`web/public/docs/update_history.md`。
- 变更传播链：外部版本文本 -> `TicketVersionService.assign_detected_ticket_version` -> `ticket_version` 候选记录 -> 工单或 AI 链路 `version_id`；版本展示 -> 版本中心反查。
- 关键约束：`ticket`、`ticket_ai_repo_mapping` 和 `ticket_ai_analysis_task` 删除版本文本列；迁移必须先回填 ID 并通过预检，再删列。
- 2026-07-29 补充：历史版本文本回填比较显式统一为 `utf8mb4_unicode_ci`，兼容既有 `utf8mb4_0900_ai_ci` 与 `utf8mb4_unicode_ci` 列的排序规则差异。
- 2026-07-29 修复：版本 DAO 不再通过通用分页工具提前转为字典，服务层以 `TicketVersion` ORM 实体和 `TicketVersionListItem` dataclass 完成发布摘要编排；版本选项接口改为 Pydantic 查询模型，统一接收 `projectId`。
- 2026-07-29 修复：AI 仓库映射列表同样移除通用分页字典转换，服务层以 `TicketAiRepoMapping` ORM 实体和 `TicketAiRepoMappingListItem` dataclass 反查版本中心并输出 Pydantic 响应模型。
- 2026-07-29 修复：`TicketVersionOptionResponseModel` 启用 `populate_by_name`，服务层以 snake_case 构造版本选项时不再触发 camelCase 别名字段缺失校验；工单详情、编辑和仓库映射共用该接口。
- 2026-07-29 修复：迁移生成的版本 ID 超过 JavaScript 安全整数范围时，版本列表、选项、发布记录、AI 映射、AI 任务和工单版本关联响应统一转为字符串；后端请求模型继续按整数校验。
# 2026-07-31 工单可配置分类与趋势指标

- 移除硬编码的 Bug、非Bug、支持类和问题性质趋势；固定趋势改为按工单类型字段聚合。
- `is_problem` 保持既有 AI、工单类型和关闭结果回退入库逻辑；仅从固定趋势统计中移除。
- 增加外部接口字段映射工单类型、人工/外部/AI 分类来源审计和映射规则 ID。
- 既有批量重归类接口新增 `external_mapping` 策略，可依据已保存外部元数据重跑映射。
- 增加受字段白名单保护的自定义趋势指标及日/业务周通用快照表；统计页仅按用户选择的指标查询数据。
- 对应迁移脚本：`server/sql/20260731_ticket_configurable_classification_metrics.sql`；详细操作文档：`web/public/docs/2026-07-31-ticket-configurable-classification-metrics.md`。

## [2026-07-31] INGEST-CODE | 工单批量映射归类前端入口

- 触发：用户确认采用明确的“映射归类”选项，不以正则规则为空作为映射或 AI 的隐式兜底。
- 架构层：工单域 / 同步自动化 Web 控制台 / 批量重归类接口。
- 创建的页面：`web/public/docs/2026-07-31-ticket-external-mapping-reclassification-ui.md`。
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`。
- 创建的双向链接：0 对（沿用工单域与同步自动化既有链接）。
- 变更传播链：同步自动化策略选择 -> `POST /ticket/sync/auto-category/reclassify` 的 `strategy=external_mapping` -> `TicketBatchReclassificationService` -> `TicketExternalClassificationMappingService` -> 工单类型与分类来源审计字段。
- 总共涉及页面：5。
## [2026-07-31] INGEST-CODE | 工单自动化关注范围

- 触发：放开飞书模块过滤后仍需避免范围外模块消耗 AI Token 或发送自动群消息。
- 架构层：工单同步业务层、统计服务层、同步配置与前端统计展示层。
- 创建的页面：无。
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-automation-flow.md`、`log.md`。
- 创建的双向链接：0 对（沿用工单域与自动化流程既有双向关联）。
- 变更传播链：外部字段映射 -> 自动化范围判定 -> AI/日志/向量/自动群推送门禁 -> 默认统计模块过滤。
- 总共涉及页面：3。

## [2026-08-04] INGEST-CODE | 当前系统工单自定义实时统计通知

- 触发：用户要求将专题统计能力扩展为当前系统内可配置的定时统计，结果不落统计快照，并支持配置范围、规则、通知渠道和消息格式。
- 架构层：工单域 / 实时统计服务 / 通知投递 / 调度任务 / Web 配置页。
- 创建的页面：`entities/services/ticket-custom-statistics.md`、`flows/ticket-custom-statistics-notification.md`、`contracts/ticket-custom-statistics.md`、`web/public/docs/updates/2026-08-04-ticket-custom-statistics-notification.md`。
- 更新的页面：`index.md`、`entities/services/ticket-domain.md`、`entities/services/task-scheduler-domain.md`、`web/public/docs/ticket-sync-automation.md`。
- 创建的双向链接：6 对（统计服务、流程、契约、工单域和任务调度域）。
- 变更传播链：`ticket.sync.automation.customStatisticsProfiles` -> `TicketCustomStatisticsDefinitionService` -> `TicketCustomStatisticsDao` -> `TicketCustomStatisticsService` -> `TicketStatisticsNotificationService` -> `TicketSyncNotifyService`；手动入口 `POST /ticket/sync/custom-statistics/run` 与定时任务 `ticket_custom_statistics_report` 复用同一编排服务。
- 总共涉及页面：8。

## [2026-08-05] INGEST-CODE | 工单日志搜索结果时间排序修复

- 触发：用户反馈工单日志查看器搜索结果的“日志时间”表头点击无响应。
- 架构层：Web 前端 / 工单日志查看器 / 虚拟结果表格。
- 更新的页面：`web/src/components/ticket/LogViewerDialog.vue`、`web/public/docs/updates/2026-08-03-ticket-log-viewer-search-result-virtual-table.md`、`web/public/docs/updates/history.md`、`wiki/flows/ticket-log-record-isolated-view.md`。
- 变更传播链：日志时间表头点击 -> `toggleLogTimeSort` 切换升降序 -> 替换 `hits` 数组引用 -> `el-table-v2` 重渲染排序结果。

## [2026-08-05] 实施 | 统一凭证管理模块
- 触发：将 Web Session、日志拉取 Header 和远端同步 API Key 集中管理。
- 架构层：数据模型、服务、接口、定时任务、工单同步。
- 创建的页面：credential-management、credential-refresh、credential-api。
- 更新的页面：log.md。
- 创建的双向链接：3 对（新增）。
- 变更传播链：凭证绑定 → HTTP/浏览器投影 → 工单与 Web 业务。
- 总共涉及页面：4

## [2026-08-05] INGEST-CODE | 统一凭证管理旧状态链路清理

- 触发：凭证管理改造后继续移除 Web 用例和新版客户端遗留的 Browser Session / Runtime Profile 选择、缓存和自动回写。
- 架构层：Web 用例控制台、Web 用例服务、PySide6 Agent 浏览器运行时、统一凭证绑定。
- 更新的页面：`entities/data-models/credential-management.md`、`flows/credential-refresh.md`、`web/public/docs/credential_management.md`、`web/public/docs/updates/2026-08-05-credential-management.md`。
- 变更传播链：Web 用例执行/录制/回放 -> `credentialBindingId` -> `CredentialResolveService` 生成 Playwright storageState -> Agent 浏览器上下文；录制完成 -> 显式创建浏览器凭证与 Web 绑定。
- 关键约束：旧 Session/Profile 不再作为状态来源、缓存键或自动写回目标；普通运行只读凭证快照。

## [2026-08-06] 修复 | 凭证绑定选项查询参数契约

- `/system/credentials/binding-options` 改用 Pydantic 查询模型接收 `businessType`，修复统一凭证管理和 Web 测试页面进入时的 `business_type` 缺失校验错误。

## [2026-08-06] INGEST-CODE | 凭证与绑定 Tab 及浏览器状态回写边界

- 触发：统一凭证页面上下堆叠凭证、绑定和日志环境配置，用户要求改为两个 Tab，并保留日志外部环境的系统参数配置方式。
- 架构层：统一凭证 Web 控制台、凭证绑定服务、浏览器状态回写、日志拉取系统参数。
- 更新的页面：`contracts/credential-api.md`、`entities/data-models/credential-management.md`、`flows/credential-refresh.md`、`index.md`、`web/public/docs/credential_management.md`。
- 变更传播链：凭证绑定 `writebackEnabled` -> storageState 回写接口 -> 版本乐观锁与操作审计；日志环境配置 -> `ticket.logPull.external` 系统参数 -> `credentialBindingId` -> HTTP 投影。
- 关键约束：统一凭证页面仅保留“凭证 / 业务绑定”两个 Tab；普通 Web 执行只读；回写必须显式开启、本地缓存已启用且版本一致。

## [2026-08-06] 修复 | 凭证接口鉴权日志数据库会话

- 现象：凭证新增、更新、删除接口返回 500，日志装饰器在鉴权查询时收到 `query_db=None`。
- 根因：凭证控制器使用 `db` 参数名，而系统日志装饰器按约定读取 `query_db`。
- 修复：统一凭证控制器各接口数据库依赖参数为 `query_db`，保证鉴权和操作日志写入使用同一会话。
## [2026-08-25] INGEST-CODE | 工单自动化结果通知

- 触发：自动拉日志到自动 AI 分析需要按既有推送配置通知成功、失败和跳过结果，并支持业务字段模板变量。
- 架构层：工单同步业务层、日志拉取服务、AI 分析服务、通用通知服务与 Web 同步自动化配置页。
- 创建的页面：无。
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-automation-flow.md`、`log.md`。
- 创建的双向链接：0 对（沿用工单域与自动化流程既有双向关联）。
- 变更传播链：`automationNotification` 配置 -> 自动化启动快照 -> 日志拉取记录/工单 extra_data -> `TicketNotifyService` 模板渲染 -> 既有推送配置投递。
- 总共涉及页面：3。

## [2026-08-25] 修复 | 工单 AI 分析结果回写事务

- 触发：Agent 已在 2026-08-25 17:48:45 返回成功结果，但任务仍显示执行中，日志报 `Data too long for column 'owner'`。
- 根因：AI 的 `owner_suggestion` 为长文本，写入 `ticket_snapshot.owner`（`String(100)`）时 flush 失败；异常分支未先回滚，导致后续失败状态更新继续命中已失效事务。
- 修复：快照 owner 展示字段按 100 字符截断，完整结果保留在 `ticket.ai_analysis` 与快照结构化数据；异常处理先回滚数据库会话，再写入失败终态。
- 更新页面：`flows/ticket-automation-flow.md`、`web/public/docs/ticket_detail.md`、`web/public/docs/updates/2026-08-25-ticket-ai-result-writeback.md`。

## [2026-08-25] INGEST-CODE | 指定工单手动自动化补跑

- 触发：需要在飞书多维表格主动拉取定时任务关闭时，按指定工单号模拟拉取并重放既有自动化。
- 架构层：工单同步控制器、`TicketManualAutomationService`、Pydantic 请求模型与 Web 同步配置页。
- 创建的页面：无。
- 更新的页面：`flows/ticket-automation-flow.md`、`flows/ticket-external-sync-flow.md`、`log.md`、`web/public/docs/ticket-sync-automation.md`。
- 创建的双向链接：0 对（沿用工单域、外部同步流程和自动化流程既有双向关联）。
- 变更传播链：同步配置页 -> `POST /ticket/sync/automation/manual-run` -> 手动自动化服务 -> 飞书单工单同步入库或本地 `Ticket` ORM 快照 -> `bitable_pull` 后处理。
- 关键约束：飞书模式忽略定时开关、常规筛选和时间窗口，但仍要求连接与字段映射完整且精确匹配唯一记录；数据库模式不重新入库、不覆盖工单字段；两种模式均服从自动化范围与现有场景开关。
- 总共涉及页面：4。


## [2026-08-25] 修复 | 工单 AI 分析 Provider 下发优先级

- 触发：工单分析选择 Claude Code/Codex Provider 后，Agent 仍可能读取旧 `workerEnv` 或任务工作区配置。
- 根因：服务端扩展环境变量覆盖了 Provider 核心变量；Codex `config.toml` 的缩进 `base_url` 未被替换；Claude 工作区 `.env` 只追加、不覆盖旧值。
- 修复：Provider 核心连接配置优先于 `workerEnv`，Codex 支持缩进配置覆盖，Claude `.env` 对同名变量执行覆盖。
- 并发配置：`ticket.ai.agent.maxConcurrentTasks`，默认值 `1`，入口为“系统管理 → AI 配置中心 → Agent 并发数”。


## [2026-08-27] 修复 | 工单与问题实例导出范围

- 触发：工单列表勾选一条记录导出却返回默认 10 条；问题实例管理勾选后点击“导出工单”没有可见响应。
- 根因：`TicketQueryModel` 只按 camelCase 别名接收输入，服务内部使用 snake_case 构造导致 `ticketIds`、`pageSize` 和 `isPage` 被静默忽略；问题实例页面维护了导出状态和请求逻辑，但遗漏了绑定状态的列选择对话框模板。
- 修复：选中工单导出使用 `TicketQueryModel.model_validate` 按 `ticketIds/pageNum/pageSize/isPage` 构造查询；问题实例页面补齐导出列选择对话框；两处导出 ID 均保持字符串传输，交由 Pydantic 在接口边界校验并解析，避免 BIGINT 精度丢失。
- 验证范围：新增服务回归测试，确认选中 ID、分页大小和分页标记会完整传入 DAO 查询；前端构建验证导出对话框模板与脚本可编译。

## [2026-08-28] FIX | 工单日志查看准备进度复用

- 触发：日志查看弹窗关闭后再次打开会重复发起准备/下载请求；离开工单详情页后重新进入也无法恢复下载进度，日志拉取记录管理页存在相同体验。
- 修复：前端按“工单 ID + 日志拉取记录 ID”在模块级复用准备请求和进度状态；已处于 `preparing/downloading` 时只等待原任务，列表显示环形进度；重新加载列表时通过 `/ticket/logs/prepare-progress` 恢复后端 Redis 中的进度。
- 影响范围：`web/src/views/ticket/hooks/useLogPrepareProgress.js`、`web/src/views/ticket/hooks/useLogViewer.js`、工单详情日志拉取 Tab、日志拉取记录管理页、日志查看器用户说明。
- 验证：待执行前端生产构建和静态检查。
## [2026-08-28] INGEST-CODE | 工单 AI Worker 失败错误码透传

- 客户端对 Worker 输出进行结构化错误分类，避免工单正文中的 `Error:` 污染 Provider 异常。
- Agent 网关保留内层 `success/errorCode/errorMessage`，服务端失败分支不再从响应文本或分析结果反向匹配异常。
- 工单 AI 任务表和 AI 审计表增加 `error_code`，失败响应不再返回工单信息或工作区结果元数据。
- `PermissionDenied` 作为本地诊断告警保留；与 Provider 致命错误同时出现时不覆盖主错误。
- 本次未调整 hybrid 日志读取策略和模型上下文限制。

## [2026-09-06] FEATURE | 资源采集服务可视化配置

- 背景：资源指标推送配置原本写死在 `.env.*`（VM_URL/VM_USER/VM_PASSWORD/VM_JOB/VM_INSTANCE/VM_MERCHANT/QTR_METRICS_EXTENDED_ENABLED），修改或启停需要改配置文件并重启 API/Worker/Beat 三个进程。
- 方案：新增数据表 `metrics_collector_profile`，每行一个采集服务实例（推送地址、认证密文、标签、间隔、批次、超时、扩展开关、启用状态、revision）；新增后端模块 `server/modules/metrics/`（controller/service×2/dao/entity/util 分层），菜单与权限注册在 `modules/metrics/perms.py`，挂在「系统监控」目录下，权限码 `monitor:metrics_collector:*`。
- 热生效机制：`MetricsCollectorRuntimeService` 由 API lifespan、Celery `worker_ready` 信号、Beat `setup_schedule` 三处接入；采集线程（`utils/metrics/collect.py` 重构为多通道模型）不访问数据库，运行时服务每 5 秒加载启用配置转换为 `CollectorProfileSnapshot` 注入线程，按 `revision` 比对热生效；推送结果经 `result_listener` 回调回写配置行供页面展示。
- 兼容处理：env 兜底逻辑按要求移除，`MetricsSettings`/`MetricsConfig` 已删除；`QTR_METRICS_ROLE` 保留用于角色标签。升级后无启用采集服务则指标停止推送，需在页面新建。
- 前端：新增 `web/src/views/monitor/metrics/`（列表 + 启停开关 + 弹窗表单）与 `web/src/api/system/metricsCollector.js`，接口前缀 `/monitor/metrics-collectors`。
- 异常隔离：采集器构建失败跳过采集、扩展指标失败不影响基础指标、数据库不可用保留现有通道、推送结果回写失败仅记 debug 日志，任何采集/推送异常不冒泡到主业务。
- 验证：新模块导入与 `server.py` 全量导入链通过；`uv run ruff check` 无新增问题类别（B008/B019/E501 为项目既有基线）；`npm run build:prod` 构建通过；现有 `tests/test_memory_metrics.py` 语义已对齐（多通道模型）。

## [2026-09-06] FIX | 资源指标 role 标签分层（分组混乱修复）

- 现象：VM 中 blue 组的 `cpu_usage_percent`、`memory_used_mb`、`qtr_cgroup_*` 等 6+ 项机器/容器级指标被拆成 api/celery_beat/celery_worker 三条序列（三进程读到的是同一份数据，值几乎相同），面板按机器聚合时 sum 会三倍虚高；2026-08-27 扩展指标上线前的进程序列则缺失 `role`，三个进程互相覆盖同一条 `qtr_process_*` 序列，RSS/CPU 曲线呈锯齿跳变无法归因。
- 根因：`collect.py` 对所有指标统一附加标签，未区分指标归属层级——机器级数据不该带 `role`，进程级数据必须带 `role`。
- 修复：`_format_samples`/`_labels`/`_append_metric` 增加 `with_role` 维度：machine 与 cgroup 指标强制剥离 `role`；`qtr_process_*` 与 `qtr_task_*` 强制携带 `role`。`role` 引入时间经 VM 数据回溯确认约为 2026-08-27（扩展指标上线），该日期前的历史序列存在覆盖问题。
- 附带发现：VM 中存在 `machine=home`（instance=TEST，无 role）的旧环境数据，已于 2026-09-03 左右停止推送；`machine=dev` 仅存在于 30 天前，均为历史遗留非当前链路。
- 验证：新增 `test_machine_level_metrics_do_not_carry_role_label` 与 `test_legacy_mode_samples_exclude_extended_metrics` 两个回归用例，tests/test_memory_metrics.py 7 个用例全部通过；ruff 无新增问题。
