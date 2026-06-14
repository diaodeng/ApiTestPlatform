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
