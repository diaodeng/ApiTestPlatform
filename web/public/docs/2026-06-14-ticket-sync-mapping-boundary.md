# 工单同步映射边界整理

## 背景

外部推送、远端拉取、通知和自动化链路共用 `sync_external_ticket`，历史上多个环节会读取 `raw_payload`、`external_field_mapping`、`external_sync.source` 和内部字段，导致排查时很难判断数据到底在哪个阶段被映射或丢失。

## 调整内容

1. `/ticket/sync/external` 只接受约定字段的驼峰/下划线写法，不再通过非契约别名猜测字段。
2. 外部推送入口会保留完整原始请求到 `extraData.raw_payload`。
3. 外部推送入口会生成 `extraData.external_field_mapping`，用于通知模板、人员邮箱解析和问题排查复用。
4. 外部字段映射仅在第三方直推边界执行，包括项目、模块、商家、状态、人员和门店。
5. 远端拉取入库不再执行外部字段映射，改为使用远端返回的内部字段、业务码、版本号和日志拉取提示字段。
6. 映射失败时允许只保留文本，不强制写入内部 ID，避免因为第三方数据暂未维护映射而阻断入库。
7. 翻译、分类、自动日志拉取、自动 AI 分析、群推送和发布就绪状态保持原有功能。

## 远端拉取 ID 关联边界

1. `remote_pull` 下项目只允许通过 `projectCode` 关联本地 `HrmProject.project_code`，未命中时只保留远端项目名称。
2. `remote_pull` 下模块只允许通过 `moduleCode` 关联本地 `HrmModule.module_code`，未命中时只保留远端模块名称。
3. `remote_pull` 下不会使用远端 `projectId/moduleId/currentAssigneeId`，避免公网和内网 ID 不一致导致错绑。
4. `remote_pull` 下当前处理人按邮箱优先、名称兜底匹配本地 `SysUser`；匹配失败时只写 `current_assignee_name`，不写 `current_assignee_id`。
5. `external_sync` 第三方直推仍保留原有映射配置能力，项目、模块、状态、人员等继续按本环境配置映射。

## 外部推送字段契约

默认必填字段：

- `ticketNo`
- `description`
- `internalPriority`
- `ticketVender`
- `ticketModle`
- `createTime`
- `reporterName`

常用可选字段：

- `title`
- `customerPriority`
- `reason`
- `ticketStatus`
- `ticketAssignee`
- `ticketAssigneeEmail`
- `reporterEmail`
- `ticketStore`
- `ticketPos`
- `ticketSco`
- `ticketUrl`

字段只兼容驼峰和下划线两种写法，例如 `ticketNo/ticket_no`。字段名不符合契约时不会猜测，缺少必填字段会返回 422。

## 影响面

1. 工单催办：继续优先使用 `raw_payload` 和 `external_field_mapping` 中的邮箱，再按姓名匹配系统用户。
2. 群消息：继续使用内部工单字段和同步元数据渲染模板，门店信息优先来自同步快照。
3. 汇总统计：仍基于本地工单表或飞书多维表格统计，不依赖外部字段映射。
4. 远端拉取：不再按本地外部映射规则二次解释远端数据，避免公网/内网映射配置不一致导致字段被重写。
