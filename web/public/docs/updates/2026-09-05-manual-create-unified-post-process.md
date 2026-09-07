# 2026-09-05 手动创建工单接入统一同步后处理链路

## 变更主题

工单四种入库场景（外部推送、远端拉取、多维表格拉取、手动创建）的后处理链路统一。此前手动创建只内联执行 AI 分类和向量刷新，场景开关形同虚设；本次将手动创建桥接到与另外三个场景相同的统一后处理编排，各步骤是否执行完全由既有场景开关和表单任务级参数决定。

## 对用户的影响

- **手动新增工单**（工单管理 → 新增）保存成功后，后台会按同步自动化配置执行完整后处理：
  - AI 同步提取（`aiSyncExtract.manualCreateEnabled`）：从标题/描述提取门店、POS/SCO、日志日期、版本号，回填日志拉取提示；
  - 翻译（`translateConfig.translateOnManualCreate` 或表单勾选"自动翻译"，任一开启即执行；已有成功翻译时跳过）；
  - AI 自动分类（`aiClassification.runOnManualCreate`，行为与之前一致）；
  - 同步后自动化（`automationConfig` 的 `autoIdentifyOnManualCreate` / `autoLogPullOnManualCreate` / `autoAiAnalysisOnManualCreate`）：自动识别回写、相似工单检索、自动拉日志、自动 AI 分析，含自动化步骤审计与通知；
  - 向量刷新（相似工单配置 `sceneTriggers.manualCreate`，行为与之前一致）；
  - 发布状态收敛与自动群推送（`groupPush.sendAfterManualCreate`）。
- 表单勾选的"自动拉日志/自动翻译"作为任务级参数，与场景开关取"或"；表单填写的日志拉取参数优先于 AI 提取结果。
- 自动化关注范围（`automationScope`）现在同样约束手动创建的工单。
- 未配置 Agent/Provider 时开启 `autoAiAnalysisOnManualCreate` 会降级关闭自动 AI 并记录日志，不会导致保存失败。
- 手动创建接口的响应时间不变（后处理在 Celery/后台线程执行）；工单新增页原有交互不受影响。

## 对开发/维护者的影响

- 新增 `server/modules/ticket/service/sync/ticket_manual_create_post_process_service.py`：手动创建后处理桥接服务（开关合并、载荷构造、Celery/后台分发）。
- `TicketService.create_ticket` 移除内联 AI 分类、向量刷新与即时日志任务创建，统一交给桥接服务分发后处理。
- `TicketSyncService` 删除与 `TicketSyncPostProcessService` 重复的 8 个私有方法，内联路径改调公开方法（`resolve_sync_title`、`translate_sync_description` 等）。
- 非延后入库路径（当前仅远端拉取）补齐向量刷新，`sceneTriggers.remotePull` 开关自此实际生效。
- 分类场景匹配放宽：`manual_create_auto_category`（统一编排来源）与 `ticket_manual_create_auto_category`（旧内联来源）均命中 `runOnManualCreate`。
- 当前处理人别名对补齐规则（`ticketAssignee` ↔ `currentAssigneeName`）下沉到 `modules/ticket/util/ticket_person_alias_util.py`，外部推送与多维表格拉取共用。

## 同日追加：远端拉取场景开关放开（方案A）

- 删除 `TicketRemoteSyncService` 中强制注入 `automation(auto_identify/log_pull/ai_analysis=False)` 的逻辑，远端拉取入库后 automation 保持 None，与其他三个场景一致走"场景开关"分支。
- 生效变化：`translateOnRemotePull`、`autoIdentifyOnRemotePull`、`autoLogPullOnRemotePull`、`autoAiAnalysisOnRemotePull` 四个开关自此真实生效（此前被写死的任务级参数短路，打开也不执行）。
- 默认行为不变：四个开关默认值均为 False，未显式打开时内网仍不执行自动拉日志/AI；双环境部署下建议内网保持关闭，自动化结果随 pending 从公网同步。
- 内网打开自动拉日志/AI 的前置条件与外部推送一致：Agent 在线、日志接口可达、日志参数可解析；参数不完整时走既有"跳过+通知"路径，并受自动化关注范围总闸门约束。
