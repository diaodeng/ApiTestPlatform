# 工单自动拉日志与自动分类补充说明（2026-06-10）

## 1. 自动拉日志参数门槛（外部同步自动化）

外部同步链路中，`auto_log_pull=true` 时新增硬性校验：

- 必须同时具备 `vendorId`
- 必须同时具备 `storeId`
- 必须同时具备 `posNo`（或从 `SCO` 识别）
- 必须同时具备日志日期 `modifyTime`

参数提取补充：

- 商家ID先按 `ticketVender` 关键字映射；若未命中，会按已识别项目回退查询 `ticket_log_pull_project_vendor_map`；
- 门店ID按“商家ID + 门店字段（`sap_org_no`）”查询 `ticket_log_pull_store_config`，命中取配置值，未命中原样保存；
- POS/SCO 显式支持 `ticketPos/posNo/posId` 与 `ticketSco/scoNo/scoId`（兼容驼峰/下划线），并保留正文正则识别兜底。

任一参数缺失时：

- 自动拉日志直接跳过（不提交拉取任务）；
- 在同步自动化步骤里记录跳过原因；
- 若同时开启自动 AI 分析，也会同步标记为跳过（因为没有日志任务可承接）。

## 2. 自动分类能力（轻量 AI 配置中心）

新增轻量 AI 配置项：

- `ticket.ai.category.classify.enabled`
- `ticket.ai.category.classify.provider.code`
- `ticket.ai.category.classify.prompt.code`

分类目标值固定为：

- 促销、券、会员、取单挂单、eservice、POS卡死、POS客户端、现金管理、销售回传、日结、支持类

触发时机：

- 外部直推入库后（后台后处理）
- 内网拉取公网工单入库后

默认策略：

- 工单已有分类时不重复分类；
- AI 异常或无可识别分类时仅记录，不影响工单入库与后续流程。

## 3. 历史数据批量重归类接口

新增接口：

- `POST /ticket/sync/auto-category/reclassify`

用途：

- 对历史工单批量重跑自动分类；
- 支持传 `ticketIds` 精确重跑；
- 未传 `ticketIds` 时按 `pageNum/pageSize` 分页扫描；
- `forceReclassify=true` 时可覆盖已归类工单。

## 4. 日志拉取弹窗回填

日志拉取弹窗关联工单后，会优先从工单同步元数据/日志提示字段自动回填：

- 商家ID（`vendorId`）
- 门店ID（`storeId`）
- POS（`posNo` / `scoNo`）

门店值支持保留“非下拉配置内值”，避免外部同步原样门店被前端清空。

## 5. 日志成功后的版本号自动回填

日志拉取成功后，会统一执行“版本号补全”：

- 若工单已存在版本号（主字段或 `extra_data.version_key`），直接复用；
- 若工单缺少版本号，则自动读取日志文本并按规则提取版本号；
- 提取成功后同时回写 `ticket.version_key` 与 `extra_data.version_key`；
- 即使未启用“日志后自动AI分析”，也会执行版本号回填，不影响日志入库结果。

## 6. 手动新增工单的自动分类

工单“手动新增”链路新增自动分类能力（受 AI 配置中心总开关控制）：

- 仅在工单当前 `category_name` 为空时触发；
- 归类成功后回写 `category_name`，并记录 `extra_data.auto_category_classify` 元信息；
- 已归类工单不会重复分类，异常不影响新增成功返回。
