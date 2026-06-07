# 工单同步自动化说明

## 入口

- 菜单：工单管理 -> 工单同步配置
- 路由：`/ticket/sync-automation`

## 页面目标

这页只管理“外部同步入库”后的自动化行为，包含三类数据源：

- 第三方系统直接调用 `/ticket/sync/external` 推送工单
- 内网系统调用 `/ticket/sync/pending` 拉取外网工单
- 拉取后回写 `/ticket/sync/ack` 的交付状态

手动新增/编辑工单的“创建后拉日志”不在这里配置，走工单新增页；手动新增工单的轻量翻译则走 `ticket.ai.translate.*` 和 AI 配置中心。
工单新增/编辑页现在额外提供“手动自动翻译”开关，最终值会写到 `extraData.manualAutomation.autoTranslate`。

## 配置项

### 1. 外部同步基础开关

- `autoRunOnSync`
  - 外部同步入库后是否进入自动化链路。
- `autoTranslateOnSync`
  - 第三方接口直推场景下，是否自动翻译工单描述。
- `defaultPullLimit`
  - 内网拉取未同步工单时的默认拉取数量。
- `remoteSync.sourceSystem`
  - 内网拉取后写入的外部系统标识。

### 2. 远端同步连接

- `remoteSync.enabled`
  - 是否允许远端拉取任务执行。
  - 这不是“启动定时任务”的按钮，只是控制任务是否放行；任务仍然由调度器或手动触发。
- `remoteSync.pullUrl`
  - 拉取未同步工单的地址。
- `remoteSync.ackUrl`
  - 回写交付结果的地址。
- `remoteSync.consumer`
  - 消费者标识，用于追踪每个拉取方的回执进度。
- `remoteSync.includeClosed`
  - 拉取时是否包含已关闭工单。
- `remoteSync.autoTranslateOnPull`
  - 仅控制“内网定时拉取外网工单”这条链路是否自动翻译。
  - 这样可以和第三方直推场景独立控制，避免同一工单在不同同步链路里重复翻译。

### 2.5 工单手动新增/编辑

- `auto_translate`
  - 工单页“手动自动翻译”开关。
  - 关闭后，手动新增/编辑不会再调用轻量翻译。
  - 该值会保存在 `extraData.manualAutomation.autoTranslate`，方便后续编辑回显。

### 3. 识别规则

- `projectMappings`
- `moduleMappings`
- `vendorMappings`
- `storeMappings`
- `statusMappings`
- `assigneeMappings`
- `posPatterns`
- `scoPatterns`
- `versionPatterns`

### 4. 日志拉取默认值

- `logPullDefaults`

这部分用于外部同步后自动拉日志的默认参数，页面已加宽显示，避免字段过多时看不全。

### 5. 提示词模板

- `promptTemplates.classificationHint`
  - 后续扩展 AI 识别时复用的分类提示词。

## 逻辑梳理

### 第三方直推

1. 外部系统调用 `/ticket/sync/external`
2. 服务端按同步来源和映射规则写入工单
3. 如开启 `autoTranslateOnSync`，会自动翻译描述
4. 如开启 `autoRunOnSync` 或请求里携带自动化配置，会继续走识别、拉日志、AI 分析

### 内网拉取外网工单

1. 定时任务调用 `/ticket/sync/pending`
2. 只有 `remoteSync.enabled=true` 才会真正执行拉取
3. 每次拉取完成后，服务端会再走一次外部同步入库
4. 是否自动翻译由 `remoteSync.autoTranslateOnPull` 单独控制

### 回写交付状态

1. 入库成功或失败后，服务端调用 `/ticket/sync/ack`
2. 远端系统据此更新拉取状态

## 说明

- `remoteSync.enabled` 不是“手动启动定时任务”的开关，而是任务执行前的放行条件。
- 手动新增工单和外部同步是两条独立链路，配置不要混用。
- 如果你只想关闭“内网拉取链路”的自动翻译，优先改 `remoteSync.autoTranslateOnPull`，不要去动第三方直推的 `autoTranslateOnSync`。

## 业务码匹配

- `project_code`
  - 项目业务码，建议人工维护并在内网/公网之间同步保持一致，外部同步时会优先用它匹配项目。
- `module_code`
  - 模块业务码，建议跟随项目一起同步维护；外部同步时如果同时带了 `project_code` 和 `module_code`，会优先按业务码直接落库。
- 兼容顺序
  - 业务码优先
  - 再看 `projectMappings` / `moduleMappings`
  - 再回退到项目/模块名称兜底
  - 如果公网和内网要使用同一套业务码，优先人工将内网的项目和模块同步到公网，而不是依赖名称自动生成或自动推导
