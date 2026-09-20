---
title: 更新历史
---

> 本文档为历史变更记录月度总结，按时间倒序排列。

## 2026-09-23
- Mock 响应头透传修复：客户端 mitmproxy 在 Mock 命中后重建响应时只保留 Content-Type，导致 Mock 服务端的命中标记头 `mockId`（`规则id_响应id`）与用户在响应头模板中配置的全部自定义头（业务 token 头、多条 `Set-Cookie` 等）无法到达被测应用，出现"直连 Mock 正常、走客户端代理异常"且无法从应用侧定位命中规则；修复为按 `multi_items()` 全量透传（保留重复头），仅剔除 `Content-Length`（自动重算）、`Content-Encoding`（探测已解压 body，保留压缩声明会解压失败）与 `Transfer-Encoding/Connection/Keep-Alive` 逐跳头，头键值按 utf-8 显式编码（`Response.make` 元组入参不自动转 bytes）。Mock 未命中/超时放行/断点链路不受影响，Mock 服务端无改动。详见：[Mock响应头透传修复](2026-09-23-client-mock-response-header-passthrough.md)，用户说明：[抓包与Mock使用说明](../client/mitm-proxy.md)。

## 2026-09-22
- 日志拉取门店编号空间治理（生产 INC00002013662 排查产物）：来源门店编码（store_code/SAP 编号）与日志接口机构号（org_no）在弹窗回显与 hints 落库两处混用——回显值 333 被前端三字段 OR 跨列匹配改写到 sap_org_no=333 的仓库门店（org 550944）且无告警，未匹配的来源编码会被当 org_no 落入 hints 并可被直接提交；修复为提交字段只承载 org_no（匹配收窄 org_no-only、hints 匹配失败不写并清除旧映射、来源编码仅展示映射关系），提交前对匹配不到 org_no 的值二次确认以保留手输新店 org_no 的合法场景。详见：[门店编号空间治理](2026-09-22-log-pull-store-id-space-fix.md)，用户说明：[日志拉取使用说明](../ticket_log_pull.md)。

## 2026-09-20
- AI 分析结果解析失败修复（生产 INC00002000624N 排查产物）：模型在结果字符串值内嵌请求体 JSON 示例且不转义双引号，旧版单遍引号修复启发式无法处理"内层键值对"形态导致整个有效分析被丢弃（`AI_WORKER_RESULT_INVALID`，重试亦复现）；按新结果处理流程修复——`json.loads` 失败后先经**回溯式 json-repair**（键/值字符串上下文判定 + 嵌入花括号剪枝，纯标准库，实测挽救两次生产失败样本），仍失败触发 **Agent 端补救重试**（转存首次现场后 resume 会话发送纠错指令再执行一轮，成功合并 token 走成功链路），两道防线都失败才落库失败；服务端把解析失败的诊断摘要并入任务错误信息，列表页直接可见具体断点。无数据库结构变更。详见：[AI结果JSON修复与补救重试](2026-09-20-ticket-ai-result-json-repair-retry.md)，用户说明：[工单深度AI分析说明](../ticket_ai_analysis.md)。
- 桌面客户端 Agent 页补齐迁移遗漏配置：新增「AI 设置」弹窗（AI 工作区根目录 / AI 本地仓库路径 / Codex CLI 路径，迁移自旧版 PySide 页面的 AI 配置区，Codex CLI 为旧版缺失的新增入口），三项均支持「浏览」选择；浏览器设置弹窗手动下载恢复 chrome/msedge 两种内核（共 5 种）、chromium/firefox/webkit 手动路径补「浏览」按钮；无后端改动。详见：[Agent页AI设置与浏览器设置补齐](2026-09-20-client-agent-ai-setting-and-browser-fix.md)，用户说明：[Agent连接使用说明](../client/agent.md)。

## 2026-09-20
- Web 测试插件包补齐 playwright 传递依赖（pyee/greenlet）并修复录制弹窗体验：①插件构建脚本 `build_plugins.py` 此前只打包 playwright 本体，漏掉其声明的传递依赖 pyee 与 greenlet，导致插件安装后运行时 `import playwright` 报 `ModuleNotFoundError: No module named 'pyee'`，而守卫导入统一提示"插件未安装"误导用户反复重装；已补齐两个依赖条目，并在导入失败时区分"插件未安装"与"插件不完整/损坏"（后者附真实异常并提示重装插件）。②「新建录制」弹窗三处体验修复：状态信息由两列 descriptions 改为独立提示条（错误全文展示不再截断溢出）、录制失败后自动复位到表单态并显示"重新开始录制"按钮（不再停留在"停止录制"运行态）、失败原因以错误提示条常驻展示。

- 手动登录链路允许浏览器凭证内容为空：此前录制/执行只要选择了浏览器状态凭证就要求凭证已配置 `storageState`，导致首次录制/首次执行（浏览器状态还不存在）被"浏览器凭证未配置 storageState"拦死；修复为开启手动登录时凭证仅作为目标站点与回写目标的引用、允许空状态启动，登录后的最终状态由 Agent 上报（可显式保存新凭证或按绑定回写）；未开启手动登录时仍要求凭证有内容（无人工补录机会）。覆盖开始录制与 Web 用例运行两条链路，回放链路无手动登录参数维持原行为。详见：[统一凭证管理](../credential_management.md)。

- 配置任务「新建录制」弹窗浏览器选项补齐：弹窗内浏览器下拉此前手写为 Chromium/Firefox/WebKit 三项，漏掉了 Chrome 和 Microsoft Edge；改为复用 Web 用例录制页共享的 `browserOptions` 常量（Chromium/Chrome/Microsoft Edge/Firefox/WebKit 五项），与既有录制页保持一致。客户端 Agent 浏览器规格表本就支持全部五种（chrome/msedge 经 channel 启动本机安装浏览器），后端原样透传，无需后端改动。

- 配置任务页新增「新建录制」入口：任务管理 Tab 顶部新增录制按钮，弹窗内填写起始地址/执行 Agent/浏览器/手动登录/登录凭证投影后直接开始录制，支持实时状态轮询与停止；录制不关联 Web 用例（`webCaseId` 留空，后端本就支持），录制记录与 Web 测试管理共用同一会话表，完成后用「录制转模板」生成版本草稿。前端新建独立录制组合函数与弹窗组件，复用既有录制接口，后端无改动。详见：[配置任务管理](../configuration-task.md)。

- 修复录制记录列表接口 `isPage=false` 报错：`GET /hrm/web-case/recording/list` 在 `isPage=false` 时 DAO 返回模型列表，但控制器固定按分页对象处理导致 `AttributeError: 'list' object has no attribute 'model_dump'`；修复为按 `is_page` 分支返回（与 Agent 列表接口同模式），分页调用方行为不变。

- 录制转模板支持下拉搜索录制记录：「录制记录ID」手工输入改为可搜索下拉，弹窗打开自动加载最近录制记录（显示会话名称/ID/状态），支持按名称远程搜索；草稿和录制中的记录不在可选范围。任务列表操作说明已补充到用户文档（运行=立即同步执行、定时=仅保存配置需配合调度任务、版本=可执行快照）。详见：[配置任务管理](../configuration-task.md)。

- 配置任务执行 Agent 改为下拉选择：新增/编辑任务、运行确认、定时配置三处弹窗的「执行Agent」由手工输入改为下拉选择，选项来自系统已登记 Agent（显示名称/编码/在线状态），三处共享同一份列表避免重复请求；定时配置弹窗提示文案明确「保存定时配置不会自动创建调度任务，需到系统监控→定时任务手工创建」的两段式约定。详见：[配置任务管理](../configuration-task.md)。

- 配置任务菜单注册上线：新增顶级目录「门店配置」（独立于测试管理、工单管理，集中存放生产配置类功能），其下挂载「配置任务」页面菜单（组件 `hrm/configuration-task/index`）与全部任务/资源/产物/报告权限按钮；菜单和按钮由后端启动时的菜单同步自动写入，首次部署重启后端即可在左侧菜单看到「门店配置 → 配置任务」入口。详见：[配置任务管理](../configuration-task.md)。

## 2026-09-19
- 配置任务前端管理页面、录制转模板与定时触发上线：新增「配置任务」页面（任务管理 + 运行记录两个 Tab，版本抽屉含草稿编辑/发布/阶段切分，运行详情含阶段审批/重试/产物/报告入口，定时配置弹窗与录制转换弹窗）；后端新增 `POST /templates/from-recording`（录制步骤重建→变量/fileKey 标记→版本草稿）与任务级定时配置接口（5 字段 cron，存任务 remark 受控段），定时执行入口 `module_task.scheduler_configuration.trigger_configuration_task_run`（同步执行复用运行编排，triggerType=scheduled）。详见：[配置任务管理](../configuration-task.md)。

- 配置任务 SFTP 资源、下载回传与删除保护上线：新增 SFTP Provider（复用统一凭证绑定，远端先写 `.part` 再原子 rename，凭证加密保存不回显明文）；`POST /resources/sftp` 上传文件并登记 READY 资源；`GET /resources/{id}/download` 按 Provider 下载回传（SFTP 服务端直连 / Agent 本地经 `file_read` 命令），回传前重新校验 SHA-256；`POST /resources/{id}/delete` 带引用保护——被产物引用默认拒绝、管理员可 force，删除走 `DELETING → DELETED` 状态机，远端文件清理失败保留 `DELETING` 可重试。Agent 端新增 `file_read/file_delete` 受控命令。详见：[配置任务资源](../configuration-task-resource.md)。

- 配置任务阶段审批闸门、截图产物与报告归档上线：版本支持按步骤切分阶段（READ/PREPARE_WRITE/WRITE/VERIFY 模式），WRITE 阶段执行前强制审批（拒绝即取消运行，重试需重新审批）；Agent 失败步骤自动截图上报，服务端登记为受控资源并建立产物引用（task_artifact）；运行报告归档为 Word 兼容文件（零依赖，Word/WPS 直接打开）并登记产物，可选飞书机器人通知。需执行 `server/sql/20260919_configuration_task_stage_artifact.sql`。详见：[配置任务管理](../configuration-task.md)。

- 配置任务运行控制与维护能力补齐：运行接口新增停止/取消（复用 Agent `stop_run_case`，终态收敛 `CANCELLED`）、手动登录两阶段执行（先开浏览器等人工登录再继续步骤）、可配置超时（默认 1800 秒）；同一 Agent 同时只允许一个运行（并发租约拒绝新运行）；Agent `web_run_*` 实时事件按 ID+Agent 归属接入配置任务运行，步骤进度实时落库且不影响 Web 用例链路；新增两个定时任务——资源/传输过期清理（收敛 `EXPIRED`）与孤儿运行恢复（超时无进展的 `RUNNING` 收敛 `FAILED`）。详见：[配置任务管理](../configuration-task.md)。

- 配置任务运行域最小闭环上线：新增任务定义、版本快照（含 fileKey→资源 ID 输入绑定）和运行实例三张表与接口；版本发布校验绑定资源就绪且归属执行 Agent，运行时冻结输入快照并复用既有 Web `run_case` 协议下发 Agent（输入绑定注入 `resourceBindings`），同步返回终态。阶段审批、截图产物和报告归档仍未提供。详见：[配置任务运行域](2026-09-19-configuration-task-run-domain.md)，用户说明：[配置任务管理](../configuration-task.md)。

- 配置任务资源与 Agent 传输切片上线：在资源元数据表基础上新增资源传输表和服务端 `begin/chunk/commit` 编排，绑定 Agent WebSocket `session_id`，只有 Agent commit 返回的实际大小和 SHA-256 与资源元数据匹配时才进入 `READY`；旧 `ready` 入口不能绕过 Agent commit。资源创建者范围、已登记 Agent 和在线 session 校验已接入，资源 ID 继续按字符串返回。详见：[配置任务资源与 Agent 传输切片](2026-09-19-configuration-task-resource.md)。

- Agent 本地资源 manifest 与分片发布协议上线：新增受控 `storage/resources` 文件存储与原子 manifest，支持 `requestType=7` 的 `file_publish_begin/file_chunk/file_publish_commit/file_stat/file_cleanup` 小 JSON 控制命令，校验分片/文件大小与 SHA-256，支持乱序与同 hash 重复分片幂等；拒绝路径穿越、符号链接逃逸、目录和超限输入，不实现任意文件读取、目录浏览、SFTP 或 AI workspace 改造。详见：[Agent 本地资源分片发布](../client/agent-resource-protocol.md)。

- 门店配置任务文件存储设计规划：明确复用 Web 录制与 Agent 执行能力，首期允许输入文件保存在执行 Agent 的受控目录，服务端通过资源 ID、版本、大小和 SHA-256 追踪；后续以独立 Provider 接入 SFTP。该记录仅说明设计边界，文件上传、截图归档和 SFTP 功能尚未上线。详见：[门店配置任务文件存储设计](2026-09-19-configuration-task-file-storage-design.md)。

- 自动拉日志 AI 门店编码映射修复（生产 INC00001988278 排查产物）：AI 统一提取的门店是外部门店编码（如 8555），而运行参数合并优先级 AI 高于字段识别，会把已映射好的内部 org_no（如 558464）覆盖回外部编码，提交前按 org_no 校验门店配置失败，自动拉日志被记为"参数不完整"跳过、只能人工补拉；修复为合并前先将 AI 门店按门店配置（`sap_org_no → org_no`，仅唯一候选）映射为内部 org_no 再参与合并，映射失败保留原值由提交前校验拦截，自动化审计新增 `aiStoreMappedFrom` 保留 AI 原始编码。详见：[自动拉日志门店映射修复](2026-09-18-ticket-auto-log-pull-ai-store-mapping.md)，用户说明：[工单同步自动化](../ticket-sync-automation.md)、[日志拉取使用说明](../ticket_log_pull.md)。

## 2026-09-18
- 自动拉日志 AI 门店编码映射修复（生产 INC00001988278 排查产物）：AI 统一提取的门店是外部门店编码（如 8555），而运行参数合并优先级 AI 高于字段识别，会把已映射好的内部 org_no（如 558464）覆盖回外部编码，提交前按 org_no 校验门店配置失败，自动拉日志被记为"参数不完整"跳过、只能人工补拉；修复为合并前先将 AI 门店按门店配置（`sap_org_no → org_no`，仅唯一候选）映射为内部 org_no 再参与合并，映射失败保留原值由提交前校验拦截，自动化审计新增 `aiStoreMappedFrom` 保留 AI 原始编码。详见：[自动拉日志门店映射修复](2026-09-18-ticket-auto-log-pull-ai-store-mapping.md)，用户说明：[工单同步自动化](../ticket-sync-automation.md)、[日志拉取使用说明](../ticket_log_pull.md)。

## 2026-09-17
- 统一凭证新增多步认证链（第二、三期）：支持"账密登录 → 提取一次性 ticket → TOTP → Set-Cookie"两步及以上全自动认证（登录链 `loginSteps` / 刷新链 `refreshSteps`），步骤间共享会话 Cookie、multipart 请求体、`url_query`/`regex` 提取加工、语义化步骤 id、条件步骤（兼容部分账号需要 OTP 的混合场景）、临时变量与凭证写回分离，任一步失败保留旧快照；编辑页新增多步认证链开关、步骤编辑器、流程预览与"测试登录/刷新流程"按钮（真实执行、不写回凭证）；新增 `POST /system/credentials/{id}/test-login-flow` 接口；需执行 `server/sql/20260917_credential_login_steps.sql`。旧单步登录/刷新配置行为不变。详见：[多步认证链](2026-09-17-credential-multi-step-login.md)，用户说明：[统一凭证管理](../credential_management.md)。

## 2026-09-15
- 日志拉取管理页自动拉取记录整行错位修复：`ac45a758` 新增"拉取人"列时模板调用了未定义的 `getPullSourceSceneLabel`（实际导入名为 `getLogPullSourceSceneLabel`），自动拉取记录（`pullSource=automation`）渲染"拉取人"单元格 tooltip 分支时行渲染函数抛 TypeError，生产构建下该行"拉取人" `<td>` 被渲染为注释占位节点、后续单元格整体左移一格且文字重叠（人工记录走 `v-else` 分支不受影响）；修正函数名一行修复，已用真实构建产物+模拟后端复现并验证新版后端/旧版后端/旧版后端系统账号三种数据场景均正常。详见：[日志拉取管理列错位修复](2026-09-15-log-pull-record-column-shift-fix.md)，用户说明：[日志拉取使用说明](../ticket_log_pull.md)。

## 2026-09-14
- 工单 AI 分析 Agent 断连治理（生产 INC00001967826 排查产物）：①AI 下发快速失败——提交时或排队期间 Agent 离线立即失败并明确提示，不再空转到 1 小时总超时；②服务端心跳判离线——改为按"最后收到消息时间"判定（2 分钟阈值），删除"有未完成请求跳过判定"，修复心跳时间被无条件刷新导致判定失效的缺陷；③客户端心跳看门狗——90 秒未收到服务端消息即主动断开自动重连，解决机器睡眠唤醒后连接已死但界面显示运行中且永不重连的问题；④执行中连接中断自动恢复——新增"恢复中（等待Agent补交）"任务状态，Agent 重连补交后由恢复扫描定时任务（60 秒，需执行种子 SQL 或在任务调度页创建）自动写回成功、不重复消耗 token，超恢复期限（任务超时+15 分钟）才置败通知；恢复期间可取消、不可重试。详见：[Agent断连治理](2026-09-14-ticket-ai-agent-connection-recovery.md)，用户说明：[工单深度AI分析说明](../ticket_ai_analysis.md)。
- 桌面客户端 Agent 页「显示请求/响应日志」勾选状态回显修复：勾选状态早已通过 save_config 持久化到后端 show_logs（日志输出正常），但页面每次挂载时勾选框硬编码为不勾选、applyConfig 未回显，导致切换页面再切回显示未勾选而日志仍在输出；修复为 applyConfig 中用 config.show_logs 回显勾选状态（初始化/配置同步/服务器保存三条路径均覆盖）。详见：[Agent日志勾选状态修复](2026-09-14-client-new-agent-log-checkbox-state.md)，用户说明：[桌面客户端pywebview界面](../client/pywebview-ui.md)。
- 桌面客户端 POS 列表优化：①操作列按内容决定宽度（`.pos-table` 操作列 `width:1%+nowrap` 贴内容收缩，右侧不再留大片空白）；②操作列六个按钮改为内联 SVG 图标按钮（core.js 新增零依赖 `icon()` 工具，Feather Icons 路径 + currentColor 跟随主题，语义由 title 悬停提示保留）；③路径列恢复旧版环境信息行动态更新——左侧列两行（完整路径+信息行），初始「环境: 未获取」，查看环境时显示获取中（主题色高亮）并按旧版 `_format_env_message` 格式回填摘要（本地/远端 商家 | 门店ID(sap/org) | 环境 | 版本 | POS，含商家与门店信息），信息行已完整故查看环境不再弹窗；本地环境切换成功后自动重新获取并刷新左侧列、自动关闭弹窗，状态按路径记忆、重渲染不丢失；④更多菜单补回「复制路径」（分隔线隔开，纯前端复制）；⑤路径支持鼠标选中复制，双击路径单元格即复制完整路径（对齐旧版交互）；⑥底部状态区——状态文本可选复制，停止POS后状态区以停止结果为准不再保留之前 POS 信息，新增「收起/展开」按钮整体显示或隐藏状态与日志面板。详见：[POS列表优化](2026-09-14-client-new-pos-list-optimization.md)，用户说明：[桌面客户端pywebview界面](../client/pywebview-ui.md)。
- 桌面客户端 mitmproxy 设置弹窗修复：①证书路径为空时占位提示直接显示实际生效的默认证书路径（取后端解析结果），脚本路径注明"留空使用客户端内置脚本"；②代理字段语义修正——新增「代理模式」下拉（local/regular/wireguard/socks5/dns）与仅 local 模式显示的「拦截应用」输入框（支持手动输入 + datalist 下拉选择，mitm_api 新增 list_processes 进程枚举接口，首次点击自动加载、旁有「加载」按钮刷新），移除后端不消费的遗留「代理客户端」字段；修复迁移遗留缺陷：`save_config` 调用的 `_is_proxy_active` 在迁移时丢失导致运行中保存配置必现 AttributeError，已按旧版语义补回；⑥详情区对齐旧版样式——总览/请求/响应三个标签页（总览摘要+17 项键值表、请求/响应信息卡+Form/Cookies/Headers/Body 分区卡片，卡片带复制、Body 支持 JSON 格式化且状态记忆，新增复制请求/响应/cURL），隐藏详情时详情整列收起、列表自动占满整行；③断点/包含/排除/流量过滤/Mock 等开关与对应内容输入框改为同一行展示，dump 模式下 web 相关复选框禁用；④全部输入框补充格式 placeholder，标签旁新增可点击「?」气泡说明（core.js 新增 helpTip 组件）；补回迁移时丢失的「附加 Body」字段。弹窗按基础配置/Mock 与请求改写/过滤与拦截/延迟设置重新分组。详见：[mitm设置弹窗修复](2026-09-14-client-new-mitm-setting-dialog-fix.md)，用户说明：[抓包与Mock使用说明](../client/mitm-proxy.md)。

## 2026-09-13
- 桌面客户端一键发版构建与版本库跟踪清理：新增 `scripts/build_release.py` 统一编排 PyInstaller 两个 spec、插件包构建与产物整理，区分 dev/release 两种模式——release 三道硬闸门（工作区干净、tag==v{version.py} 且在 HEAD、Gitee 无同名 release）任一不满足拒绝构建；构建信息采用「进 git 的 version_build.py 固定加载器 + gitignore 的 version_build_local.py 动态值」两层设计，关于页版本号旁展示、插件 manifest 写入 build_mode/build_commit；正式产物按自更新资产匹配规则命名（QTRClientNew.exe / QTRClientNew_portable.zip）并附 .sha256 与 release-manifest.json 清单；插件 zip、build_webview、dist_webview、构建日志、.codeweaver 等约 150MB 构建产物退出 git 跟踪（分发走 Gitee release 附件），发版提交回归纯源码；确认版本比对按数字归一化与 tag 命名禁忌（禁字母+数字后缀）。详见：[一键发版构建](2026-09-13-client-new-one-command-release-build.md)。
- 桌面客户端 Agent 页服务选择改为名称下拉：顶部「服务地址」输入框移除，替换为「服务」下拉框（选项显示服务名称，value 存地址），连接中（连接中/运行中/断开中）下拉框锁定不可切换，停止后才可更换；恢复 server_list 旧版存储语义 `{服务地址: 服务名称}`、current_server 存地址（修正迁移时写反导致管理弹窗两列颠倒），修改/删除当前服务时 current_server 跟随/回退；开始连接的状态提示不再携带连接地址，地址仅记日志。详见：[Agent服务名称下拉](2026-09-13-client-new-agent-server-name-select.md)，用户说明：[桌面客户端pywebview界面](../client/pywebview-ui.md)。
- 桌面客户端日志页双路独立监听与文件对话框修复：本地日志/程序日志改为后端按 source 隔离的两路 tail（`start_tail/stop_tail` 按来源操作，启停互不影响，log_tail 事件携带 source），本地日志「选择文件」仅选中不监听（首次进入默认选中当天程序日志文件），勾选「监听日志」开始、取消停止，监听中换选文件自动切换；程序日志由独立开关完全监听当前程序自身日志；日志输出区支持鼠标选中复制（复制按钮优先复制选中文本，无选区复制全部）；修复文件选择框 TypeError（file_types 需传字符串列表而非元组列表）与 FOLDER_DIALOG 弃用告警（改用 FileDialog.FOLDER）。详见：[日志页双路独立监听](2026-09-13-client-new-log-page-independent-monitors.md)，用户说明：[桌面客户端pywebview界面](../client/pywebview-ui.md)。
- 桌面客户端移除插件 Pip 安装模式：内置嵌入式 Python 运行时（runtime/python，几十 MB）仅为该一种安装方式服务，体积代价过高；插件安装回归「在线下载 + 本地 zip 安装」两种方式，功能不变；同步移除 Pip 源配置、锁版本清单生成（plugins/pip_pins.py）、运行时准备脚本（scripts/setup_pip_runtime.py）与 spec 打包块，manifest 的 Python 版本兼容校验保留。详见：[移除Pip安装模式](2026-09-13-client-new-remove-plugin-pip-install.md)，用户说明：[插件管理](../client/plugins.md)。
- 桌面客户端界面由 PySide6 迁移到 pywebview：原生窗口 + WebView2 渲染的无构建原生 HTML/CSS/JS 前端（新增 `client_new/ui_web/` 包：app.py 窗口装配、event_bus 事件推送、dialog_bridge 弹窗桥、api/ 七个子 API 门面、static/ 前端 SPA），服务层零改动复用，agent_client_service 剥离 Qt Signal 改回调注册；删除 ui/controller/workers/emitter 等全部 Qt 层与 pyside6 依赖，新增 pywebview>=5.4；配置文件无缝沿用；行为变化与注意事项见用户说明。详见：[pywebview迁移](2026-09-13-client-new-pywebview-migration.md)，用户说明：[桌面客户端pywebview界面](../client/pywebview-ui.md)。
- 桌面客户端插件安装新增 Pip 模式：新增内置嵌入式 Python 运行时（`scripts/setup_pip_runtime.py` 准备，华为云镜像下载 embeddable Python + get-pip 清华源引导 pip），两个打包 spec 在 runtime/python 存在时自动打入（目录版实测 87MB→128MB，单文件版压缩后约 +15~20MB）；插件管理新增「Pip 源」配置（默认清华 PyPI 镜像，可改内网私有源）与每行「Pip安装」按钮，执行 `pip install --target` 安装锁版本依赖（新增 `plugins/pip_pins.py` 由 build_plugins.py 自动从构建 venv 生成），装后补写 manifest 并复用原子替换逻辑；目录替换逻辑从 install_from_zip 抽取为 `_replace_plugin_dir` 两路共用。已实跑运行时准备、真实 pip 安装冒烟（playwright cp314 wheel）与便携版全量打包。详见：[插件Pip安装模式](2026-09-13-client-new-plugin-pip-install.md)，用户说明：[插件管理](../client/plugins.md)。
- 桌面客户端插件包 manifest 版本兼容信息与跨版本回退下载：`build_plugins.py` 产物 manifest 新增 `python_version`（构建时 CPython 大.小版本，硬约束）与 `app_version`（配套客户端版本，参考）；`install_from_zip` 安装前对 Python 版本强校验，不兼容拒绝安装（在线/配置源/本地三路径统一生效，旧格式包跳过校验向后兼容）；Gitee 在线下载放宽为"同版本 release 优先、缺附件时按最新在前回退其他 release"，回退安装成功消息注明来源，应用版本不同仅软提示不拦截。详见：[manifest版本兼容与跨版本回退](2026-09-13-client-new-plugin-manifest-compat.md)，用户说明：[插件管理](../client/plugins.md)。
- 桌面客户端插件在线下载支持 Gitee 按版本自动下载：未配置下载源时自动从 Gitee releases 中查找 tag 与当前客户端版本一致的 release，下载其中的 `{插件名}.zip` 附件（存在 `.sha256` 则强校验），配置了下载源仍优先走配置源；Gitee release 地址、版本归一化与附件定位逻辑从 utils/common 下沉为新增的 utils/gitee_release 共享 util，主程序更新检查与插件下载两链路共用；移除「在线下载」的"先配下载源"前置拦截。发版约定：tag 与 version.py 版本一致，同一 release 上传三个插件 zip 及可选 .sha256。详见：[插件Gitee按版本下载](2026-09-13-client-new-plugin-gitee-release-download.md)，用户说明：[插件管理](../client/plugins.md)。

## 2026-09-12
- 桌面客户端 Qt 运行时二次瘦身：定位出插件化后剩余体积大头为 PySide6 被 PyInstaller hook 连带收集的冗余 Qt 运行时（虚拟键盘插件拖入 QML/Quick 引擎约 17MB、qpdf 图片插件拖入 Qt6Pdf 约 5MB、软件 OpenGL 回退 opengl32sw 约 20MB、96 个翻译文件只保留 zh_CN），新增 `scripts/qt_slim.py` 在两个打包 spec 的 Analysis 后统一过滤 103 个条目；目录版 `_internal` 122MB→76MB，单文件版 55MB→37.6MB。详见：[Qt运行时二次瘦身](2026-09-12-client-new-qt-runtime-slim.md)。
- 桌面客户端 Agent 页面信息精简：①移除地址下方重复的 MAC/连接地址展示行（完整连接地址=地址+/MAC，页面不再展示，状态信息行保留）；②服务器选择后的最大发送、自动重试、重试次数、重试间隔、断线重连、低频间隔 6 项配置收敛到新增的「连接设置」弹窗（主开关联动禁用子项），顶栏只留状态/地址/别名/显示日志，小屏不再溢出；配置保存链路不变。详见：[Agent页面信息精简](2026-09-12-client-new-agent-page-declutter.md)，用户说明：[Agent连接使用说明](../client/agent.md)。
- 插件安装目录支持自定义：默认恢复为程序目录下 storage/plugins（拷贝程序目录整体带走插件，绿色便携）；插件管理页新增"安装目录"行（浏览/保存），修改时弹影响提示并三选一（迁移已装插件/仅保存/取消）；旧版本历史位置（exe 目录/LOCALAPPDATA）的插件启动时自动迁移到当前根目录；插件配置文件路径打包态固定到 exe 目录，保证 helper 子进程能读到自定义目录。详见：[安装目录自定义](2026-09-12-client-new-plugin-install-dir-config.md)，用户说明：[插件管理](../client/plugins.md)。
- 修复插件化后重新打包报 `PermissionError: WinDivert64.sys 拒绝访问`：根因是打包态插件根目录原为 exe 所在目录（即构建输出目录），运行数据写入其中后，local 模式加载的 WinDivert 内核驱动锁定 .sys 文件，PyInstaller 清理输出目录时删除失败；现插件运行数据可配置安装位置，构建产物目录不再被运行时污染。已在构建输出目录装过插件的用户升级后插件自动搬走；打包前若驱动残留锁定请 `sc stop WinDivert`（管理员）。详见：[插件目录解耦](2026-09-12-client-new-plugin-dir-decouple.md)，用户说明：[插件管理](../client/plugins.md)。
- 桌面客户端 mitmproxy 页面体验优化：①首次使用提示"未找到 mitmproxy CA 证书"时自动追加引导——先点击「启动」运行一次代理，证书在首次启动时自动生成后再安装；②信息栏移除与设置重复的代理端口/Web 端口展示；③「当前模式说明」与「当前运行方式」收纳进信息栏右侧「?」按钮，点击弹窗查看完整说明；④主窗口启动时自动最大化，适配笔记本小屏。详见：[mitm页面体验优化](2026-09-12-client-new-mitm-page-ux.md)，用户说明：[抓包与Mock使用说明](../client/mitm-proxy.md)。
- 桌面客户端拆分「抓包代理」插件 + 菜单按插件显隐：mitmproxy 内核及其独占依赖（tornado/aioquic/cryptography 等 36 包）拆为第三个插件 proxy，主程序 exe 从 71MB 降至 55MB（插件化累计从 100+MB 降 45%）；「mitmproxy」菜单在插件未安装时隐藏，安装重启后出现；helper 子进程启动前激活插件（插件根目录改 frozen 感知路径）；tornado 改 mitmweb 模式懒导入；补齐 6 个主程序不可达的标准库 hiddenimports（xml.dom.minidom 等在冒烟中实际暴露缺失）。详见：[拆分抓包代理插件](2026-09-12-client-new-proxy-plugin.md)，用户说明：[插件管理](../client/plugins.md)。
- 桌面客户端插件化瘦身：主程序不再内置桌面测试依赖（cv2/numpy/pytesseract/pyautogui/pynput/pillow）与 Web 测试依赖（playwright），新增「插件管理」入口（主界面右上角「插件」按钮）——支持在线下载（可配下载源+sha256 校验）与本地 zip 安装，插件安装到 storage/plugins/ 后重启生效；插件缺失时对应功能返回明确提示、其他功能不受影响，安装失败自动回滚，所有插件异常仅记日志不波及主进程。打包 spec 排除上述重依赖并新增 scripts/build_plugins.py 插件包构建脚本，主程序体积大幅下降。详见：[插件化瘦身](2026-09-12-client-new-plugin-architecture.md)，用户说明：[插件管理](../client/plugins.md)。
- 桌面客户端 mitmproxy 抓包性能优化三项：①流量入口过滤——新增"过滤静态资源流量"开关与过滤路径规则（后缀/子串匹配，默认过滤 png/js/css/字体等静态资源），命中流量完全放行不记录不 mock，系统代理模式下无关流量不再拖慢代理与界面；②mock 探测连接复用——按代理会话持有单个 httpx 连接池，消除每请求重建连接与 TLS 握手，探测前清 cookie、会话结束显式释放；③UI 节流——流量列表改 250ms 定时批量渲染（整批只触发一次刷新），断点流量旁路立即显示保证放行按钮即时可用。设置弹窗「路径匹配」组可配置，保存热生效。详见：[mitm性能优化三项](2026-09-12-client-new-mitm-performance-optimization.md)，用户说明：[抓包与Mock使用说明](../client/mitm-proxy.md)。

## 2026-09-11
- AI 结果回帖新增消息形态开关与卡片字段白名单：`aiResultFollowUp.messageStyle`（card 默认 / text，仅回帖模板留空时生效，配置了自定义模板始终纯文本）决定模板留空时发卡片还是默认文本模板；`aiResultFollowUp.cardFields` 卡片展示字段白名单（工单信息/结论/根因分析/修复建议/依据/风险项/后续动作/置信度/查看工单按钮），勾什么显什么、留空全量、失败原因区块保留；前端配置页同步新增单选与多选（纯文本/模板时隐藏不清空）。已真实发送字段裁剪卡片验证渲染。详见：[消息形态开关与字段白名单](2026-09-11-ai-reply-style-switch.md)。
- AI 分析结果回帖改为飞书卡片消息：默认配置（回帖模板留空）下，AI 结果回帖从一整段纯文本改为交互卡片——结论、根因分析、修复建议分区块展示，附依据/风险/后续动作（有才展示）、置信度与「查看工单」按钮，成功绿色头/失败红色头；配置了自定义回帖模板的仍走纯文本不受影响。回帖时机、幂等、锚点等逻辑不变。已用群机器人真实发送成功/失败样例卡片验证渲染。详见：[AI结果回帖卡片化](2026-09-11-ai-reply-card-message.md)。
- 工单AI机台编号提取正则修复与唯一候选覆盖策略取消（背景：INC00001952225 修正提示词后模型已正确返回 posNo=2，但原文正则把标题时间 `23:56 POS#2` 的分钟 56 当成唯一机台候选并硬覆盖模型值，导致提示词修正永远无法生效、自动拉日志用错机台）：正则三处修复——编号数字排除时间语境（`HH:mm` 及前置冒号）、"数字在前 POS 在后"分支不再吞掉后跟编号的 POS token（`POS#2` 重新可见）、顺带修复 `N号POS` 中文前置编号数字组未捕获的存量缺陷；覆盖策略改为**模型优先、正则仅兜底**——模型值有效但不在原文候选中时（不论候选数量）统一保留模型值并告警人工复核，只有模型值无效/未填写才用原文候选兜底。存量已写错 posNo 的工单需等下次同步事件重提取或人工修正（提示词变更本身会使提取缓存失效）。详见：[机台编号提取正则与优先级修复](2026-09-11-ticket-ai-extract-machine-regex-and-priority-fix.md)。
- 扩展字段状态数据统一迁移 SQL：`sql/20260911_migrate_extra_data_state_to_tables.sql` 三段合一（锚点表回填 / 任务表幂等列回填 / 宽表状态回填），基于 JSON_TABLE 纯 SQL 实现且幂等可重跑，可替代 Python 版回填脚本；已对生产库（OceanBase 4.3.5，实测支持 JSON_TABLE、不支持 DEFAULT ON EMPTY、LONGTEXT 全表 LIKE 需 query_timeout hint 放宽超时）完成只读 preview：11 条锚点、3 条幂等记录、2507 个状态工单待回填，两个事故工单（INC00001934853/R）字段解析抽样验证正确。
- 同步过程状态宽表阶段 2b 存储地基：`ticket_sync_process_state` 建表（一工单一行，发布域+群推送执行域）+ DO + 带行锁 DAO（按域更新白名单、处理锁抢占/超时/幂等释放、批量拉取查询）+ 13 个 DAO 单测，纯增量零行为影响，DDL 可随阶段一窗口执行；服务层切换蓝图（group_push_service 状态方法改表、delivery/notify/payload 读方适配、回填脚本、R 单并发场景回归）已写入文档供下会话实施。automation 步骤状态明确保留 JSON 不列化。详见：[同步过程状态宽表 2b](2026-09-11-sync-process-state-foundation.md)。
- AI 结果回帖阶段二第一批（oncePerTicket / 抢占式幂等 / 手动补发）：`aiResultFollowUp` 新增 `oncePerTicket` 幂等粒度开关（默认关保持任务级，开启后工单回帖成功一次即不再回）；回帖幂等升级抢占式标记（发送前条件 UPDATE 占坑防并发重复发送，全部失败自动释放允许重试）；新增手动补发接口 `POST /ticket/{ticket_id}/ai-analysis/tasks/{task_id}/reply-resend`——不重跑分析直接读取任务持久化结果补发到群话题，存量锚点丢失工单先手动发群消息建锚点再补发即可。编排状态宽表（`ticket_sync_process_state`）为阶段 2b 待实施。详见：[AI结果回帖阶段二](2026-09-11-ai-reply-phase2.md)。
- 群推送锚点与回帖幂等拆表（INC00001934853/R 回帖丢失的根治方案阶段一）：话题锚点从 `extra_data` JSON 拆到独立表 `ticket_group_push_anchor`（message_id 唯一约束、单工单保留 20 条），回帖幂等改用 `ticket_ai_analysis_task.result_replied_at` 列（条件 UPDATE 防并发重复标记），两处 `build_meta` 白名单移除已拆字段，表为唯一事实源；飞书评论入站匹配从"全表扫描工单解析 JSON"改为锚点表索引查询。需按顺序执行：`sql/20260911_ticket_group_push_anchor.sql` → `scripts/migrate_group_push_anchor.py apply` → 部署（生产 preview 实测 23 单存量、4 单有锚点）。详见：[群推送锚点拆表迁移](2026-09-11-group-push-anchor-table-migration.md)。

## 2026-09-10
- 群推送话题锚点擦除修复（AI 分析结果不回帖工单群，生产工单 INC00001934853 / INC00001934853R 实测定位）：两处 `build_meta` 白名单重建 `sync_state` 时未包含 `group_push_message_refs`（话题锚点）与 `ai_result_reply_task_ids`（回帖幂等记录），外部同步更新/多维表格拉取等任何读改写工单扩展字段的链路都会把锚点静默擦除，AI 终态回帖因"无群消息锚点"被 skip；现两处白名单补齐字段并补默认空列表，新增 6 个回归测试；`.env.prod` 与该问题无关，回帖开关全部在 `sys_config('ticket.sync.automation')` 且生产配置正确。存量被擦除锚点的工单需按用户文档手动补发。详见：[群推送锚点擦除修复](2026-09-10-group-push-anchor-erasure-fix.md)。
- 启动脚本 apt 源切换归档修复 ripgrep 缺失（背景：工单 INC00001941655 日志搜索报"保护阈值"错误，实测生产容器没有 rg）：bullseye EOL 后 USTC 镜像站 security 池清理范围扩大到 libfreetype6（libcairo2 的依赖），apt 事务任一包 404 即整体失败导致 ripgrep 一直装不上，日志搜索被迫走 Python 降级并触发 256MB 保护阈值；另 start.sh 的 set -e 因 && 链写法豁免了 apt 失败，应用带着缺失依赖静默启动。现 apt 源切换阿里云 debian-archive 永久冻结归档（国内可达、承诺不清理、无 Valid-Until）、删除 security 源、兼容传统与 deb822 两种源格式、拆散 && 链让失败可被捕获、安装后自检 rg/libcairo 显式报错。详见：[启动脚本apt归档修复ripgrep缺失](2026-09-10-start-sh-apt-archive-ripgrep-fix.md)。

## 2026-09-09
- 自动拉日志同参数决策矩阵与拉取人列：外部工单重复同步时，同参数拉取记录失败后每次执行任务都会重复创建相同拉取并重复发送失败通知（根因：自动链路只查"成功"记录去重，失败记录永远匹配不到）；现改为按同参数最新记录状态决策——不存在/已取消则创建、进行中则等待并在需要时补充AI配置、成功则复用并按记录级AI任务去重、失败则静默跳过（不创建不AI不通知，仅内部留痕），人工修正参数重新拉取后自动恢复；日志拉取列表新增「拉取人」列区分自动拉取与人工拉取及具体拉取人；同时修复人工停止后后台线程把状态覆盖回成功/失败的竞态。需执行 `server/sql/20260909_ticket_log_pull_source.sql`。详见：[自动拉日志同参数决策矩阵与拉取人列](2026-09-09-log-pull-decision-matrix-and-puller.md)。
- 自动AI分析复用记录开关语义修复：他人手工提前拉取日志成功（未勾选自动AI）后，同步自动化链路复用该记录触发自动AI时按"被复用记录自身的快照"判断开关导致跳过分析（场景配置开了也白开，生产工单 INC00001939452 实测复现）；现复用成功记录触发自动AI时以本次自动化的场景级开关、分析条件与 Agent/Provider 为准覆盖记录快照，日志拉取自身链路与手工链路行为不变。详见：[自动AI分析复用记录开关语义修复](2026-09-09-auto-ai-reuse-record-switch-override.md)。

## 2026-09-08
- Agent 孤儿租约清理与 AI 回传协议瘦身（背景：当日 10:35 生产 fastapi 第三次被 cgroup OOM Kill，且两个工单重试后"一直 AI 分析中"约 24 分钟）：服务启动时自动清空上次进程遗留的 Agent 运行租约（原先要等租约自然过期，实测阻塞 24 分钟，现在秒级恢复排队）；量化确认 Agent 回传体 8MB 中 `raw_output`（完整 worker stdout）占 99.7%，Agent 客户端回传改为 8000 字符头部摘要（完整内容留在本地工作区文件），服务端增加旧版 Agent 大响应的就地截断兜底，消除 OOM 的直接诱因。详见：[Agent孤儿租约清理与AI回传协议瘦身](2026-09-08-agent-lease-cleanup-and-response-slim.md)。
- 相似工单检索内存优化与监控修复（背景：当日 12:31 生产 fastapi 进程被 cgroup 内存上限 OOM Kill 重启）：相似工单检索改为「精确信号预筛 + 分页扫描」，检索文本带错误码/Trace ID/Request ID 时先按信号索引筛候选再做向量比对（生产实测约 11 秒缩短到 0.2 秒内），无信号时按 500 条/页分页扫描并逐页释放，单次检索内存增量从约 30MB 降到 10MB 级；修复 cgroup v1 环境 OOM 计数恒为 0、Worker 进程任务指标被误标 `role=api`、服务重启后 AI 迟到结果缓存查询报错三个观测缺陷；新增 RSS 阈值触发的 tracemalloc 诊断快照并支持页面可视化配置（系统监控 → 资源采集服务 → 内存诊断快照，保存后约 5 秒全进程热生效，环境变量保留为回退来源），用于归因进程内存阶跃。详见：[相似工单检索内存优化与监控修复](2026-09-07-ticket-similarity-scan-memory-optimization.md)。
- 日志版本号提取正则收紧并支持可视化配置：日志拉取链路原先用宽松硬编码正则提取版本号，导致 `launcher_version:1.0.6.8`（启动器版本）被误提取为工单版本、`OpenGL parsed version: 4` 也有误提取风险；现默认正则锚定 `ms_h/ms_l/ls_h/ls_l` 特征行只取 `x.y.z` 起步版本号，且正则列表改为可在「同步自动化 → 来源与拉取 → 存储与资源限制」卡片可视化维护（JSON 数组），配置为空或非法时自动回退内置默认；工单标题/描述文本提取同样收紧（排除带前缀字段与单数字片段）。详见：[日志版本提取正则收紧与可配置](2026-09-07-log-version-extract-pattern-config.md)。

## 2026-09-06
- 资源采集通道配置轮询缺失修复：页面已启用采集服务但 Grafana/VictoriaMetrics 仍查不到 memory_pressure 等任何指标，根因是采集线程的通道配置注入方法（replace_profiles）没有任何周期调用方，配置从未进入采集线程，采集节拍全部空转；现采集线程启动时注入配置加载回调并每 5 秒自轮询数据库配置热生效（首轮立即加载），数据库异常时保留现有通道继续推送；修复后无需重启，页面"采集线程运行状态"的 activeProfileIds 可确认配置已加载。详见：[资源采集通道配置轮询缺失修复](2026-09-06-metrics-collector-profile-polling-fix.md)。
- 资源指标 role 标签分层修复：机器/容器级指标（cpu、memory、cgroup）被三个进程各推一条带 role 的序列导致聚合三倍虚高，扩展指标上线前进程序列缺失 role 导致三进程互相覆盖曲线锯齿跳变；现按指标归属分层——机器/容器级强制剥离 role，进程/任务级强制携带 role；历史数据约 2026-08-27 前标签形态不同，长期对比需剔除。详见：[资源指标role标签分层修复](2026-09-06-metrics-role-label-layering-fix.md)。
- 资源采集服务可视化配置：指标推送配置从 .env 环境配置迁移到数据库并提供「系统监控 → 资源采集服务」管理页面，支持添加多个采集服务（多推送通道）、随时启停（5 秒内热生效无需重启）、设置推送间隔/批次/超时/标签/认证（密码加密存储），可查看最近推送状态与失败次数及各进程采集线程运行状态；原 VM_URL/VM_USER/VM_PASSWORD/VM_JOB/VM_INSTANCE/VM_MERCHANT/QTR_METRICS_EXTENDED_ENABLED 环境配置失效，升级后需在页面新建并启用采集服务否则指标停止推送；采集线程重构为多通道模型，采集/推送异常全部隔离不影响主业务。详见：[资源采集服务可视化配置](2026-09-06-metrics-collector-ui.md)。
- 统一凭证编辑语义修正与自动刷新可见性：默认登录模板仅在新增凭证时自动填入（编辑不再被反复填回），登录接口新增"恢复默认模板"按钮；已保存敏感字段清空保存即从凭证中删除（原为留空保留旧值）；凭证列表新增"自动刷新"与"最近刷新"列；定时刷新跳过原因细分并对未开启自动刷新的 HTTP 凭证每天记录一条提醒审计；编辑页新增"到期时间"字段；刷新服务删除重复定义方法与死代码。UAT 凭证过期根因：自动刷新开关未开启被定时任务静默跳过（任务本身正常），三个 UAT 凭证已开启自动刷新（间隔 7200 秒）。详见：[凭证编辑语义与自动刷新可见性](2026-09-06-credential-edit-semantics-and-auto-refresh-visibility.md)。

## 2026-09-04
- 客户端 Agent 连接卡死修复：点击"连接服务器"后页面卡住直到连接成败，根因是 UI 线程同步执行重型模块首次导入（约 1.5 秒，含 playwright/pyautogui/cv2）与 MAC 解析；现改为点击后按钮立即置灰进入"连接中"，导入与 MAC 解析全部移入后台线程，页面全程可响应；连接准备阶段可随时点"停止"取消，失败后按钮恢复可点。详见：[Agent 连接非阻塞修复](2026-09-04-client-agent-connect-nonblocking.md)。
- 工单AI分析重试复用缓存修复：重试新建的审计记录来源引用从系统工单ID统一为业务工单号（与首次创建同口径）；Agent 命中本地缓存结果直接回传时，服务端识别后不再把恢复出的历史 token 重复计入本次任务与审计（每次真实调用只对应一份 token 记录），任务状态明确提示"复用 Agent 缓存结果"。服务端重启即生效，旧版 Agent 由兜底识别兼容。详见：[重试复用缓存来源引用与Token修复](2026-09-04-ticket-ai-retry-cache-reuse-source-ref-and-token.md)。

## 2026-09-03
- 工单模块映射大小写回归修复：8/28 起新入库工单 module_id/module_code 全部为空，根因是 8/27 关键字归一化统一小写后，模块映射匹配的工单文本未同步小写导致映射永远无法命中（手动多维表格拉取只是触发面）；现已修复并补回归测试，存量数据可用模块映射修复脚本回填。详见：[工单模块映射大小写回归修复](2026-09-03-ticket-module-mapping-case-fix.md)。
- 工单AI分析结果schema清洗与失败崩溃修复：部分模型未被 Codex 输出 schema 真实约束，会在结果中附加额外字段或把证据写成对象导致校验失败；现于校验前做保守清洗（剔除额外字段、证据对象转字符串），清洗动作留日志可审计；同时修复结果无效分支的变量先使用后赋值崩溃（此前会掩盖真实失败原因）。需更新重启 Agent 生效。详见：[AI分析结果schema清洗与崩溃修复](2026-09-03-ticket-ai-schema-sanitize-and-unbound-fix.md)。
- 工单相似精确信号召回修复与相似结果缓存：修复混合召回中 Trace ID/Request ID 命中候选被丢弃的缩进缺陷；相似工单查询结果按工单+数量+配置指纹缓存到 Redis（TTL 5 分钟），向量刷新与案例状态变更后主动失效，Redis 不可用自动降级直查。详见：[相似召回修复与结果缓存](2026-09-03-ticket-similarity-signal-fix-and-result-cache.md)。

## 2026-09-02
- 工单详情展示组件统一复用，独立详情页改为纯只读：相似工单面板与描述/翻译块抽取为共享组件（写操作通过 allowBindIssue/allowTranslate/readOnly 显式控制）；独立详情页移除问题实例关联、案例确认、追问、评论提交等写入口，定位为只读查看页；列表详情弹窗能力不变。详见：[详情组件复用与只读化](2026-09-02-ticket-detail-shared-components-readonly.md)。
- 独立工单详情页轻量加载提速：打开页面改用轻量概览接口，不再串行加载消息、全部快照和相似工单；相似工单拆为独立查询并在首次进入"相似工单"标签时懒加载，相似检索不再阻塞首屏；快速切换工单时旧响应自动丢弃。详见：[独立详情页轻量加载](2026-09-02-ticket-standalone-detail-light-load.md)。
- 问题实例绑定工单操作列新增外部地址按钮：点击在新标签页打开工单的外部系统详情链接（有链接才显示），链接解析与工单列表/详情页一致；绑定工单列表后端补同步摘要装饰支持链接兜底。详见：[问题实例绑定工单外部地址按钮](2026-09-02-issue-bound-ticket-external-link.md)。
- 工单导出新增 URL 列：工单列表导出和问题实例关联工单导出的导出列勾选新增"URL"选项，导出工单详情链接（取工单链接字段并按同步摘要兜底，无链接为空）；URL 仅用于导出，不在表格列设置中展示。详见：[工单导出新增 URL 列](2026-09-02-ticket-export-url-column.md)。
- 可观测上报迁移至 Agent 侧：实测测试服务端与生产可观测平台网络隔离导致服务端上报超时，任务级 span 改由执行 Agent 直连平台上报（六个终态出口全覆盖，INPUT 为最终渲染提示词）；服务端只下发配置不再出站；OTEL 环境注入分层（主开关=基础配置，CLI 开关=CLI 专属+TRACEPARENT）。详见：[可观测上报迁移至 Agent 侧](2026-09-02-ai-provider-observability-agent-reporting.md)。
- AI Provider 可观测上报（OTLP）：Provider 新增可观测配置（端点/鉴权/密钥加密存储），工单 AI 分析任务级调用（完整输入/输出/Token/耗时/错误）上报可观测平台；可选开启本机 Codex / Claude Code CLI 原生遥测，Claude 经 TRACEPARENT 挂接任务链路，Codex 经 session.id 关联；上报为旁路能力不影响任务执行。详见：[AI Provider 可观测上报](2026-09-02-ai-provider-observability.md)。
- AI分析任务取消、提交结果类型标识与并发锁标识：新增协作式取消接口与任务历史"取消"按钮（Agent Worker 前后检查点感知，迟到结果不覆盖取消态，已消耗 token 照实入审计）；提交/重试响应新增 outcome 字段区分"新建/重试/关联执行中任务/复用历史结果"并按类型提示；Agent 锁冲突返回携带原任务 ID 供定位。详见：[AI分析任务取消与提交结果类型](2026-09-02-ticket-ai-cancel-and-outcome.md)。
- AI分析并发防重、重试独立审计与Agent锁心跳续租：并发提交相同参数由数据库级活跃锁拦截（不再白耗 token）；重试每次新建独立审计记录，原记录不可变，历次尝试的 token 与失败原因可追溯；复用历史结果写入轻量复用事件（不计 token）；Agent 工作区锁改心跳续租，消除长任务双 Worker 并发写风险；执行入口状态白名单防取消任务误执行。详见：[AI分析并发防重与审计尝试](2026-09-02-ticket-ai-concurrency-guard-and-audit-attempts.md)。
- AI分析断链恢复与Token真实消耗记录：服务重启期间 Agent 已完成的任务自动恢复写回（Agent 本地待补交清单 + 服务端迟到响应入缓存 + 启动恢复检测），不再一律标记"服务重启中断"；失败/超时/缓存命中路径尽力提取真实 token 消耗计入审计，不再显示空值；成功写回创建者归属提交人；Agent 新增"断线重连"开关（高频窗口用尽后低频永久重连）。详见：[AI分析断链恢复与Token真实消耗记录](2026-09-02-ticket-ai-reconnect-recovery-and-token-usage.md)。

## 2026-09-01
- 日志拉取列表操作按钮改为常显：工单详情页的重新拉取按钮、管理页的资源曲线和重新拉取按钮不再依赖行悬浮；管理页操作列扩宽至 270px，避免右侧操作按钮被截断或溢出。详见：[日志拉取记录管理页操作列](2026-09-01-ticket-log-pull-action-column.md)、[工单详情日志拉取 Tab 操作列](2026-09-01-ticket-detail-log-pull-action-column.md)。
- 日志内存分析全面升级：扫描引擎复用 rg 搜索管道（保留降级与保护），数据点携带行号/epoch 并增加解析统计；弹窗内容区可滚动、内存面板可最小化、点日志行自动最小化；图表与日志双向联动（点曲线跳日志行、点日志行画标记线）；日志拉取记录管理页新增"曲线"独立入口（曲线+数据点列表，点击跳日志）。详见：[内存分析升级与双向联动](2026-09-01-ticket-log-resource-curve-linkage.md)。同日追加图表-日志分栏布局（宽屏左右/窄屏上下，拖拽调比例，联动不再折叠图表）。


- 日志查看器内存分析体验修复：解析完成后进度条定格 100% 并显示成功图标与总耗时提示（约 1.5 秒后切换图表）；扫描性能优化新增 `Process cpu` 字节锚点预过滤，跳过无关行的解码与正则匹配。详见：[完成态图标与扫描性能优化](2026-09-01-ticket-log-viewer-memory-progress-and-scan-perf.md)。

## 2026-08-31

- 新增轻量AI测试工作台：支持选择工单、Provider/模型和提示词（可临时编辑），对信息提取、分类统计、翻译、标题总结、知识提炼五类任务试运行；展示模型原始输出、归一化结果、机台校验告警、Token 用量和耗时，不回写工单数据。详见：[轻量AI测试工作台](../ticket_ai_test.md)、[更新说明](2026-08-31-ticket-ai-test-workbench.md)。
- 修复相似工单向量刷新报"Column 'quality_status' cannot be null"的问题：向量刷新构造记录时未显式赋值非空列质量状态，导致已有向量的刷新（详情页相似工单、消息面板、案例索引、向量重建等）全部失败；现已在构造处显式赋值并新增回归用例，存量数据无需修复，建议执行一次全量向量重建统一到新文本方案。详见：[相似工单向量刷新quality_status非空约束报错修复](2026-08-31-ticket-similarity-quality-status-fix.md)。
- 修复工单AI提取参数回填日志拉取提示快照：延后处理阶段AI提取出的门店、POS/SCO和日志日期现在会同步写入 `log_pull_hints`，详情页手动拉日志弹窗能正确回填日期和机台（INC00001904725场景）。手动拉取过的参数继续通过最新拉取记录回显，用户实际操作优先。详见：[工单AI提取参数回填日志拉取提示快照修复](2026-08-31-ticket-ai-extract-hints-backfill.md)。
- 修复工单AI参数提取机台编号覆盖逻辑：模型正确提取的POS/SCO编号不再被原文正则第一个匹配无条件覆盖（INC00001899231中模型返回24被POS#05覆盖为5导致错误拉取日志）；归一化改为模型结果优先，原文候选仅在模型值无效、模型遗漏或原文唯一候选冲突时兜底纠正，多候选冲突时保留模型值并告警。详见：[工单AI参数提取机台编号覆盖逻辑修复](2026-08-31-ticket-ai-extract-machine-no-override-fix.md)。

## 2026-08-30

- 修复工单概览"最新AI结论"卡片摘要、根因、解决方案恒为空的问题（任务摘要序列化键名不匹配）。详见：[工单概览AI结论显示为空修复](2026-08-30-ticket-ai-summary-conclusion-fix.md)。
- 工单详情 Tab 职责收敛：将「协同/AI」更名为「AI分析」，隐藏角色、类型和发起AI开关，保留版本、Agent、Provider、模型及附件 JSON 配置并改为紧凑配置区；追问仍自动触发 AI，快照、知识库、任务历史统一为结果操作区。评论 Tab 保持普通评论且不触发 AI，仅优化编辑器、消息块和提交反馈。详见：[工单详情 AI分析与评论区布局优化](2026-08-30-ticket-detail-ai-followup-layout.md)。

## 2026-08-29

- 协同/AI 标签页简化：移除独立“发起AI分析”按钮（提交消息即自动发起分析），任务历史按钮移入表单首行，版本/Agent、Provider/模型同行排列，附件 JSON 默认收起；消息流只展示 AI 分析相关消息，AI 结果 JSON 改为“详情”弹窗查看。详见：[协同/AI 标签页简化调整](2026-08-29-collab-tab-simplify.md)。
- 问题实例详情页绑定工单列表的状态列、独立工单详情页顶部状态由显示状态编码改为显示状态名称（含自定义工作流状态名），标签颜色与工单列表页一致。详见：[工单状态展示为状态名称](2026-08-29-ticket-status-name-display.md)。
- 独立工单详情页顶部新增「关联问题实例」按钮，支持在详情页内搜索并归因到指定问题实例，已归属时支持换绑（需二次确认）。详见：[独立工单详情页支持关联问题实例](2026-08-29-ticket-detail-issue-bind.md)。
- 工单详情弹窗概览 tab 相似工单由展示 3 条调整为 5 条；协同/AI tab 移除相似工单卡片，候选查看与归因操作统一收敛到概览 tab。详见：[工单详情页相似工单展示调整](2026-08-29-ticket-detail-similar-ticket-display.md)。

## 2026-08-28

- 日志拉取管理列表的「关联工单」列支持点击跳转工单详情，新标签页打开；无关联工单的记录保持原展示。详见：[日志拉取记录支持跳转工单详情](2026-08-28-ticket-log-pull-ticket-link.md)。
- 修复日志查看弹窗关闭后再次打开重复发起下载的问题；详情页和日志拉取记录管理页复用同一记录的准备任务，并在列表恢复环形下载进度。详见：[工单日志查看准备进度复用](2026-08-28-ticket-log-viewer-prepare-progress.md)。

## 2026-08-27

- 工单链路内存泄漏治理：修复 Agent 分片注册表泄漏，日志拉取与 AI 分析大字段改为延迟加载和超长裁剪，部署层注入 `MALLOC_ARENA_MAX=2` 缓解堆碎片；接口契约不变。详见：[工单链路内存泄漏治理](2026-08-27-ticket-memory-leak-fixes.md)。
- 工单 AI 历史、工单概览和 AI 执行审计新增 Token 用量展示，支持查看输入 Token、输出 Token、总 Token，以及单工单维度的累计汇总。详见：[工单 AI Token 用量记录与展示](2026-08-27-ticket-ai-token-usage.md)。

## 2026-08-26

- 补充工单 AI 分析 Worker 提示词约束，明确禁止用 shell/PowerShell heredoc 自行写结果文件，要求直接输出最终 JSON，降低 Windows 下 `<<`/heredoc 语法误触发概率。
- 修复工单 AI 分析通过本机 Agent 网关回收结果时，服务端对 `HandleResponse` 误用 `model_validate_json` 导致任务被错误标记为失败，页面只看到 `Cannot check isinstance when validating from json`；现在改为先解析传输 JSON，再按 Python 对象校验，并保留 Agent 返回的真实失败信息。详见：[工单 AI Agent 响应 JSON 校验修复](2026-08-26-ticket-ai-agent-response-json-fix.md)。
- 修复工单 AI 分析在 Agent 无活动任务时仍被历史陈旧队列头阻塞的问题；服务端现在会按排队租约、终态和总超时自动清理失效队列头，并减少排队阶段的大请求内存占用。详见：[工单 AI Agent 队列陈旧请求自动恢复](2026-08-26-ticket-ai-agent-queue-stale-recovery.md)。
- 修复工单自动拉日志在相同拉取参数已成功时仍重复提交的问题；自动化现在会直接复用已有成功日志记录。
- 修复只开启自动 AI 或命中历史成功日志时，未重新拉日志也无法继续自动分析的问题；系统会复用最近成功日志继续版本回填和自动 AI。
- 任务日志新增 `TID / trace_id` 持久化与查询展示，支持按同一次链路排查完整日志。详见：[工单自动日志去重与任务 TID](2026-08-26-ticket-log-pull-dedupe-and-job-tid.md)。

## 2026-08-25

- 修复生产环境自动 AI 通过本机 Agent 网关时错误拼接 `/prod-api` 代理前缀导致 404；内部直连改用 `/qtr/agent/ai-analysis/send/{agent_code}`，详见：[自动 AI 内部网关 404 修复](2026-08-25-ticket-ai-agent-gateway-root-path.md)。
- 修复工单 AI 分析结果回写失败后任务长期停留在“执行中”的问题；超长建议负责人字段按快照列长度安全截断，并在异常时先回滚事务再写入失败终态。
- 新增工单 AI Agent 并发配置 `Agent 并发数`，自动 AI 通过 FastAPI 内部网关跨进程派发，超过上限的请求进入 Redis 队列等待。
- 修复工单 AI 分析选择 Claude Code/Codex Provider 后仍使用旧 `workerEnv` 或任务工作区配置的问题，Provider 核心连接配置现在会覆盖旧值。详见：[工单 AI 分析 Provider 下发修复](2026-08-25-ticket-ai-provider-override.md)。

## 2026-08 月（8 天，23 项变更）

### 自动日志门店编码映射修复
- 修复外部同步自动拉日志时将 SAP 门店编码直接作为日志接口 `storeId`，导致门店校验失败、未创建日志拉取记录的问题。
- 自动日志优先使用按商家门店配置映射后的 `org_no`，并保留 `sourceStoreCode` 原始值；参数校验跳过时增加明确告警日志。
- 详见：[自动日志门店编码映射修复](2026-08-25-ticket-log-pull-store-mapping.md)。

### 内存增长监控接入
- 新增 API、Celery Worker、Celery Beat 的进程和 cgroup 内存趋势指标。
- 新增 Celery、用例执行、工单日志拉取、工单 AI 分析的任务前后内存快照和结构化日志。
- Prometheus/VictoriaMetrics 使用低基数标签，具体任务 ID 通过日志关联；补充运维说明和诊断测试。
- 详见：[内存增长监控接入](2026-08-25-memory-growth-monitoring.md)。


### 工单详情页翻译内容显示修复
- 修复工单详情页翻译区域有时显示"原文 + 【AI翻译】标记 + 译文"拼接内容的问题。
- 后端 `ai_translation` 字段去掉了危险的 `translated_description` fallback，确保只存储纯译文。
- 前端两个详情组件的 `detailAiTranslation` 增加防御性 `【AI翻译】` 标记剥离逻辑；`TicketDetailView.vue` 的 `detailOriginalDescription` 补齐分割处理。
- 详见：[工单详情页翻译内容显示修复](2026-08-24-ticket-translation-display-fix.md)。


### 问题实例详情查询回归修复
- 恢复问题实例按 `issue_id` 查询绑定工单的 DAO 方法，修复详情、编辑和绑定区域报 `TicketIssueDao has no attribute list_tickets_by_issue_id` 的问题。
- 详见：[问题实例详情查询回归修复](2026-08-21-ticket-issue-dao-regression.md)。


### 问题实例新增可选字段校验修复
- 修复问题实例新增时未选择负责人，空字符串 `ownerId` 触发整数参数校验错误的问题。
- 后端归一化可选整数空值，前端提交前过滤空的可选字段。
- 详见：[问题实例新增可选字段校验修复](2026-08-21-ticket-issue-create-optional-fields.md)。


### 工单问题实例关联增强
- 问题实例绑定工单改为按业务工单号/标题搜索，首张工单不再展示内部 ID。
- 工单详情新增直接关联或更换已有问题实例，工单列表新增当前页多选批量关联问题。
- 批量归因默认不覆盖已有问题归属，服务端全量校验并在事务中更新；问题详情绑定工单展示四类版本信息。
- 详见：[工单问题实例关联增强](2026-08-21-ticket-issue-association.md)。


### 工单模块通用提示词
- 新增 HRM「模块通用提示词」管理入口，按 `module_code` 跨项目复用 AI 分析说明，同时保留各项目模块的专属说明。
- 工单详情和分析任务按项目默认、模块通用、项目模块的顺序展示和组装提示词层；历史任务继续使用原始快照。
- 详见：[工单模块通用提示词](2026-08-23-module-common-prompt.md)。

### 工单日志查看器横向滚动修复
- 修复日志上下文关闭换行时无法左右查看较长日志内容的问题。
- 关闭换行时保留单行布局并支持横向滚动，开启换行时按可视区域折行；超长行仍可通过独立阅读区查看完整内容。
- 详见：[工单日志查看器横向滚动修复](2026-08-21-ticket-log-viewer-horizontal-scroll-fix.md)。

### 工单日志拉取门店回填修复
- 修复工单详情轻量概览响应过滤 `extraData` 导致日志拉取弹窗无法回填商家、门店和 POS 的问题。
- 兼容历史 `external_field_mapping.ticketStore` 原始门店值；命中门店配置时按 `org_no` 提交并展示名称、`org_no`、`sap_org_no`，未命中则保留原值。
- 详见：[工单日志拉取门店回填修复](2026-08-21-ticket-log-pull-store-prefill.md)。

### 工单列表提交时间与性能索引调整
- 工单列表和详情的提交时间展示、筛选和排序统一使用主表 `submit_time`，不再以同步 JSON 时间或本地创建时间回退。
- ORM 同步声明模块业务码列表索引，以及按工单查询最新日志拉取/AI 分析状态的复合索引；生产物理索引需由运维手工创建。
- 详见：[工单列表提交时间与性能索引调整](2026-08-21-ticket-list-submit-time-performance.md)。

### 工单模块 Controller 异步阻塞修复
- 修复工单模块 6 个 Controller 文件中共 64 个 `async def` 接口在事件循环中直接执行同步 DB 操作导致阻塞的问题。
- 统一使用 `run_in_threadpool` 将同步 Service 调用包装到线程池执行，避免阻塞 FastAPI 主事件循环。
- 修复 `extract_ticket_knowledge` 接口在 async 函数中直接调用 `query_db.commit()`/`rollback()` 的错误。
- 仅改动 Controller 层，不涉及 Service/DAO 层，不影响接口契约和行为语义。

### 工单日志搜索内存优化
- 每次 rg 搜索完成后对搜索文件调用 `posix_fadvise(POSIX_FADV_DONTNEED)` 释放 OS 页缓存，避免多次搜索不同工单日志后内存持续增长。
- 移除 rg 搜索路径中 Python 侧的 `_match_keywords` 二次校验和 `_truncate_search_content` 冗余截断，rg 管道链已确保输出正确性。
- 优化 `_run_rg_pipeline` 子进程/线程清理：显式关闭 stdout 管道、join 超时从 200ms 延长至 3s、增加双重关闭异常保护。
- 文件编码检测优先从 `.lineidx` 索引读取缓存值，减少 `charset_normalizer` 实时探测。

### 修复 Codex Worker 使用旧 bearer token 导致的误报鉴权失败
- 修复工单 AI 分析 Agent 复制本机 Codex 配置后，仍沿用 `config.toml` 中旧的 `experimental_bearer_token`，导致 Provider API Key 实际可用但 Worker 请求 `/responses` 返回 `401 Unauthorized`。
- Provider 下发时现在同步覆盖任务级 `config.toml` 的 bearer token，并让鉴权诊断按 Codex CLI 实际优先级读取该配置，避免把 `auth.json` 的有效密钥误判为实际请求密钥。
- 补充 AI Provider 管理说明与故障排查指引。

### 工单模块映射修复脚本
- 新增一次性数据修复脚本 `server/scripts/sync_ticket_module_mapping.py`：按「工单同步配置」的 `moduleMappings` 将 `ticket.module_name`（现有模块名）与模块映射配置匹配，解析出正确模块后更新 `ticket.module_id`/`module_code`，不改 `module_name`。
- 工单有 `project_id` 时按 `(project_id + module_code)` 等组合在 `hrm_module` 内解析避免跨项目同 code 串模块；无项目时按全局唯一条件解析。脚本先预览确认后再执行，支持 `limit` 参数小范围验证。

### 日志拉取配置合并与并发数生效
- 「工单同步配置 → 外部接口」Tab 更名为「日志拉取配置」，统一收纳日志拉取三类配置：拉日志默认值、存储与资源限制、外部接口环境分组。
- 原「公共配置」页的「拉日志默认值」卡片与「日志拉取后处理」卡片迁移到新 Tab；「存储与资源限制」新增页面承载此前无入口的轮询/下载/入库/搜索护栏配置。
- 最大并发数从同步配置的 `logPullDefaults.logPullConcurrency` 迁移到存储配置的 `maxWorkers`，并真正生效：保存后按新值重建日志拉取线程池（1~20），修复此前线程池硬编码为 2、前端配置无效的问题。

### 工单 AI 分析执行器可配置（Codex / Claude Code）
- AI Provider 新增 `preferredExecutor` 默认执行器字段；工单 AI 分析支持 `codex` 与 `claude_code` 两种执行器。
- 发起 AI 分析弹窗新增“执行器”下拉，选项按当前 Provider 的兼容执行器收敛，并按默认执行器回填，用户可覆盖。
- Claude Code 以 `claude -p --output-format json --json-schema` 非交互模式执行，采用 `plan` 只读权限与 `Read,Grep,Glob,Bash(rg *)` 工具白名单，结果从 stdout 的 `structured_output` 解析。
- Provider 选项接口在分析场景不再硬编码 `executor=codex`，后端按分析执行器集合过滤，仅支持 Claude Code 的 Provider 也能出现在候选中。

### 凭证绑定新增模式修复
- 修复统一凭证管理里从“编辑绑定”切换到“新增绑定”时，表单残留旧绑定主键导致后续保存误走更新的问题。
- 现在新增绑定会始终创建新记录，同一业务、同一投影类型可以继续保留多条绑定。

### 旧日志拉取记录重拉环境与凭证错误显式提示
- 历史工单日志拉取记录重新拉取时，如果原记录没有保存 environment，不再默认回退到第一个环境，而是直接返回“当前记录缺少环境信息，无法重新拉取”。
- 外部请求头解析时保留统一凭证解析失败的具体原因，并包装为“日志拉取外部接口凭证不可用：...”的明确错误，便于区分凭证过期、解绑和域名不匹配等问题。
- 日志拉取配置页仍可一次性查看全部环境，不影响现有配置展示。
### 日志查看器体验优化
- 搜索结果列表迁移至虚拟表格，缓解大数据量滚动卡顿；新增列宽拖拽、时间排序箭头、多关键字轮换高亮。
- 关键字上限提升至 20 个（每词 200 字符），日志内容列单行省略避免行高变化。
- 修复列宽拖拽手柄表头撑高、按住拖拽事件丢失及搜索区全屏 Esc 还原逻辑。

### 凭证刷新与脱敏
- HTTP 刷新凭证支持 Cookie/Header 敏感脱敏日志、高级变量 `${secret.headerValue}`、变量插入按钮和保存前校验。
- 修复 Cookie Header 中 `${secret.cookie}` 未替换及结构化 cookies 写回矛盾；新增"刷新失败→自动登录→再刷新"兜底链路和对应配置入口。

### 工单日志查看器超长行展开优化
- 日志上下文区对单行内容继续保留截断展示，但”展开完整内容”后改为当前行下方的独立阅读块，不再挤在原始行内，避免展开后仍然字号太小、内容难以看清。
- 展开块增加更大的内边距、加粗标题、独立滚动和更大的正文行高，提升超长日志行的可读性。
- 展开块新增**全宽**按钮（撑满上下文面板宽度）、**全屏**按钮（固定全屏阅读）和**复制**按钮，支持一键复制完整内容到剪贴板。
- 用户说明同步补充超长行展开的使用方式，避免误以为展开后只是原地放大一小段文本。

## 2026-07 月（28 天，122 项变更）

### 同步自动化与多维表格
- 配置统一迁移至 `ticket.sync.automation`，整合轻量 AI、自动化关注范围、必填字段模型、必填校验和外部映射归类策略。
- 多维表格主动拉取补齐分页循环修复、`page_token` 熔断、富文本换行保留、人员 @ 解析、嵌套时间过滤、JSON 字段文档化预览、优先/责任兜底、强制同步翻译和 Celery 用户上下文。

### 轻量 AI 重构与 Provider 升级
- AI Provider 重构为平台/协议/用途/执行器/默认模型五维模型；密钥二次验证、远端模型目录、用途过滤和强校验。
- 工单翻译、标题总结、分类、参数提取、知识提炼统一到同步配置页，AI 配置中心只保留 AI 分析 Worker。
- Provider 下拉按用途/执行器过滤，执行前强校验；Codex Worker 失败脱敏诊断包含 API Key 长度/SHA-256 和轻量鉴权探测。

### 工单统计与分类
- 新增细分问题固定枚举、趋势统计图/表、提交时间口径、是否真实问题统计、根因/解决方式/关闭结果枚举配置。
- 分类 AI 提示词与 Provider 抽离到系统管理，同步页只选编码；状态变更触发分类支持防重复和强制覆盖。

### 日志查看与分析
- 搜索结果恢复 CSS Highlight API 高亮，避免 DOM 重建卡顿；文件范围下拉保持后端完整列表。
- 先全局搜索再按文件收敛、换行开关、选中文本同内容高亮及上一段/下一段切换。
- AI 分析日志缓存复用、手动选择分析来源、Agent 诊断失败鉴权。

### 版本中心与项目治理
- 新增项目版本中心：版本注册、待确认候选、版本管理页、发布历史、AI 仓库映射关联版本。
- 发生版本统一、影响版本列、协同版本默认值、版本权限修复、版本治理配置迁移。

### 前端交互与配置
- 工单列表补齐多选筛选、表头排序、处理状态列、用户列配置/统计块显示配置及下拉菜单联动隐藏。
- 详情弹窗组件化拆分、折叠/展开描述翻译、编辑保存非阻塞化、标签文本回填和模块名称回填修复。

### 通知与消息
- 群消息模板 @ 变量 `${report_at}`/`${assignee_at}` 等和当前处理人兜底逻辑。
- 催办任务覆盖飞书参数，修复全员分支未返回和单邮箱字符串兼容。

### 内存与资源
- 查询结果内存水位优化、内存更新调用降至单次、资源守卫及时释放 EventSource。

## 2026-06 月（13 天，118 项变更）

### 多维表格拉取与推送
- 飞书多维表格主动拉取从外部推单链路独立为定时任务配置页，支持字段映射、记录 URL、同步链接复制。
- 字段映射预览元数据、嵌套人员对象提取、富文本片段 @ 映射、排查过程评论同步幂等。
- 推送侧补齐邮箱幂等、拉取侧优先/责任兜底、必填字段模型化、分页循环修复、强制同步翻译。

### AI 分类与相似度
- AI 分类统计并入同步配置：外部/远端/手动三种入库触发、状态变更触发、comment 纳入防重、结构化回填。
- 相似度检索配置化 Provider：Qdrant + OpenAI Embedding、场景触发、历史向量重建。

### 日志拉取
- 下载来源语义修复（source=auto/service/original）、非阻塞代理下载、商家/门店/POSID 列。
- 日志切割显式开关、保存方式交互优化、日志拉取通知配置与推送。

### Git Worktree 与 AI Agent
- Agent 代码分析按仓库分支创建固定 worktree，复用已有目录、分支校验和本地 Git 凭据。

### 用户配置与展示
- 列设置/统计块用户级保存、模块多选筛选、模块代码过滤、处理状态列、评论延期加载。

### 通知与群消息
- 消息 @ 变量模板、必填字段配置、中文乱码修复。

