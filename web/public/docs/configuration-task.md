# 配置任务管理

> 配置任务用于把“按商家、门店执行一组网页操作 SOP 并绑定输入文件”的实施工作结构化。当前提供任务定义、版本快照、输入资源绑定、运行执行、阶段审批闸门、显式截图步骤、阶段证据策略字段、Agent-local 产物元数据登记、产物受控预览/下载和报告归档（Word 兼容文件 + 飞书通知）。截图正文仍由 Agent 受控目录持有；证据包生成、查询和下载尚未上线。

## 功能与入口

页面菜单位置：**门店配置 → 配置任务**（顶级目录「门店配置」独立于测试管理、工单管理，集中存放生产配置类功能；菜单由后端启动时自动同步，首次部署重启后端即可看到）。

页面内有两个 Tab：

- **任务管理**：任务列表、新建任务、版本管理（抽屉）、运行、定时配置、录制转模板；
- **运行记录**：全部运行实例列表、运行详情抽屉（阶段进度、审批、产物、报告入口）。

新增/编辑任务的「执行Agent」为下拉选择，选项来自系统已登记的 Agent（`测试管理 → Agent` 维护），显示名称、编码和当前在线状态；运行确认与定时配置弹窗中的执行 Agent 同样为下拉选择，留空则使用任务上配置的 Agent。

任务接口位于 `/configuration-tasks`，需要登录并具备对应权限：

- `GET /configuration-tasks`：查询任务列表，支持 `keyword` 和 `limit`。
- `POST /configuration-tasks`：创建任务，需提供 `taskName`、`agentCode` 和可选 `variables`。
- `GET /configuration-tasks/{taskId}`：任务详情。
- `PUT /configuration-tasks/{taskId}`：更新任务名称、描述、Agent、变量或状态。
- `POST /configuration-tasks/{taskId}/versions`：创建版本草稿（`DRAFT`）。
- `GET /configuration-tasks/{taskId}/versions`：版本列表。
- `GET /configuration-tasks/versions/{versionId}`：版本详情。
- `PUT /configuration-tasks/versions/{versionId}`：更新版本草稿。
- `POST /configuration-tasks/versions/{versionId}/publish`：发布版本。
- `POST /configuration-tasks/{taskId}/runs`：创建运行并同步执行。
- `POST /configuration-tasks/runs/{taskRunId}/stop`：停止或取消运行。
- `GET /configuration-tasks/{taskId}/runs`：运行列表。
- `GET /configuration-tasks/runs/{taskRunId}`：运行详情。
- `POST /configuration-tasks/versions/{versionId}/stages`：保存版本阶段切分（仅草稿）。
- `GET /configuration-tasks/versions/{versionId}/stages`：查询版本阶段定义。
- `GET /configuration-tasks/runs/{taskRunId}/stages`：查询运行阶段列表。
- `POST /configuration-tasks/runs/stages/{runStageId}/approve`：审批 WRITE 阶段（通过/拒绝）。
- `POST /configuration-tasks/runs/stages/{runStageId}/retry`：重试失败阶段。
- `GET /configuration-tasks/runs/{taskRunId}/artifacts`：按任务/运行归属查询运行产物元数据。
- `GET /configuration-tasks/artifacts/{artifactId}/preview`：按 `artifactId` 预览安全 MIME 类型的产物正文。
- `GET /configuration-tasks/artifacts/{artifactId}/download`：按 `artifactId` 下载产物正文。
- `POST /configuration-tasks/runs/artifacts/agent-report`：Agent 上报步骤截图/日志（供客户端集成）。
- `POST /configuration-tasks/runs/{taskRunId}/report`：生成并归档运行报告，`notifyFeishu=true` 时推送飞书通知。
- `POST /configuration-tasks/templates/from-recording`：录制会话转任务版本草稿（录制→模板转换器）。
- `GET /configuration-tasks/{taskId}/schedule`：查询定时触发配置。
- `PUT /configuration-tasks/{taskId}/schedule`：保存定时触发配置（cron 5 字段表达式）。

权限码包括 `configuration_task:task:list/query/add/edit/publish/run/approve`、`configuration_task:artifact:upload/query/preview/download`、`configuration_task:report:generate`、`configuration_task:resource:list/query/add/edit/transfer/sftp/download/delete`。权限按钮已随菜单自动注册，给角色勾选对应权限即可。

## 版本与输入绑定

版本草稿的步骤编辑与 Web 测试管理的用例编辑**共用同一公共组件（WebStepEditor）**，交互与样式完全一致，提供可视化表格和高级 JSON 两种模式（编辑弹窗内 Tab 切换）：

- **可视化步骤**：表格支持列表内直接编辑（点击单元格即可修改动作类型、步骤名称、首选定位器和输入参数），以及新增、前插、上移/下移、删除、启停；点击行选中后可用「编辑当前步骤」，或点行内「编辑」打开步骤详情编辑弹窗（支持动作类型、定位器、参数、断言、目标快照等完整编辑能力）；存在截图步骤时表格自动显示"证据"列；「上传文件」动作配置 `fileKey` 与文件来源（见下）；
- **高级 JSON**：直接编辑步骤数组 JSON，可「应用 JSON 到可视化」或「使用当前可视化刷新 JSON」双向同步；保存草稿时若停留在 JSON Tab，系统会先自动应用 JSON 编辑，应用失败会提示并中止保存；
- **差异说明**：与用例编辑唯一的界面差异是版本步骤详情弹窗不显示"指纹"字段——用例的指纹在保存时由服务端计算入库，用于元素库匹配；版本步骤 JSON 不落指纹，显示空值没有意义。

版本草稿包含 `startUrl`、`browserName`（Chromium/Chrome/Microsoft Edge/Firefox/WebKit）、`headless`、`credentialBindingId`（统一凭证的浏览器状态绑定，编辑弹窗中下拉选择、可留空）、`variables`、`steps` 和 `inputBindings`：

### 上传文件步骤的文件来源

「上传文件（upload_file）」步骤在版本编辑器（任务步骤编辑）中配置文件来源，有两种模式可切换：

| 模式 | 步骤参数 | 说明 |
|---|---|---|
| 资源绑定 | `resourceIds` | 下拉选择「资源管理」页面上传到任务执行 Agent 的资源（仅显示 `READY` 状态）；也可不选（保持"暂不指定"），运行前在「输入绑定」里把 `fileKey` 关联到资源 ID |
| Agent 目录文件 | `agentPath` | 下拉浏览执行 Agent 受控上传目录（`storage/upload_inputs/`）内的文件，选择受控相对路径；文件由使用方自行放置到该 Agent 目录并保证存在 |

- 字段按文件来源**模式驱动显隐**：选"暂不指定"时显示资源键（可选，配合输入绑定运行时换文件）；选"资源绑定"/"Agent 目录文件"时只显示对应下拉，资源键隐藏——资源键与其他文件来源不会同时出现；
- **解析优先级（显式来源优先）**：步骤参数 `resourceIds` > 步骤参数 `agentPath` > 输入绑定（`fileKey` → 资源 ID）。即步骤里显式选择了文件来源时，输入绑定中的同键配置**不会被使用**；输入绑定仅在"暂不指定"来源时兜底生效；
- `agentPath` 只接受受控上传根目录内的相对路径（正斜杠），拒绝绝对路径、盘符与 `..` 逃逸；文件被挪动或删除后运行会失败，错误提示中不会出现服务器绝对路径；
- 录制产生的上传步骤会保留样本文件名（`fileNames`）做占位展示，它只用于识别该步骤上传的是什么文件，运行时实际使用的是绑定的资源或 Agent 目录文件；
- 多文件上传打开 `multiple` 开关，输入绑定对应键可绑定多个资源（最多 20 个）。

> 文件来源选择器（资源绑定 / Agent 目录文件）在步骤表格单元格和步骤详情弹窗中均可使用，下拉按任务执行 Agent 过滤 READY 资源，选项格式为"文件名 · 大小 · 资源ID 尾段"。


```json
{
  "startUrl": "https://test.example.com/store",
  "browserName": "chromium",
  "headless": true,
  "inputBindings": {
    "price_tag": ["900000000000001"]
  }
}
```

- `inputBindings` 的键是步骤里 `upload_file` 使用的 `fileKey`（也可用于其他运行时输入），值是资源 ID 字符串数组，每个键最多绑定 20 个资源；资源 ID 不是 Agent 本地路径，资源必须处于 `READY` 且属于任务执行 Agent；
- 版本编辑弹窗中输入绑定默认为**结构化编辑**：按行动态增删"键 + 资源"（键下拉自动收集版本内所有上传步骤的 fileKey，资源下拉按执行 Agent 过滤 READY 资源，也允许手输 ID）；需要精确手写时可点"高级 JSON"切换为文本模式，保存后两种模式等价；
- `variables` 是版本级运行变量，任务变量先合并、版本变量后合并，同名顶层变量以版本变量为准；步骤占位符支持 `${name}` 和 `{{name}}`，建议使用与占位符完全一致的扁平键名；
- 已发布版本不可修改；需要调整时使用"复制为新草稿"（步骤/输入绑定/变量/阶段切分一并复制）或"撤销发布"（仅限从未运行过的版本）；
- 发布时服务端校验：至少一个启用步骤；每个绑定资源存在、状态 `READY`、且资源所属 Agent 与任务执行 Agent 一致。

### 版本生命周期

版本按 `草稿（DRAFT）→ 已发布（PUBLISHED）→ 已废弃（DEPRECATED）` 演进，各状态下可用操作如下：

| 操作 | 草稿 | 已发布 | 已废弃 | 说明 |
|---|---|---|---|---|
| 编辑/保存 | ✓ | 仅查看 | 仅查看 | 快照不可变原则：发布后内容不可改，编辑弹窗中保存按钮禁用 |
| 发布 | ✓ | ✓（重新发布） | ✗ | 成为任务当前版本 |
| 复制为新草稿 | ✓ | ✓ | ✓ | 步骤、输入绑定、变量、阶段切分一并复制，新版本号自动递增；复制件与源版本解耦 |
| 撤销发布 | — | ✓（仅限无运行记录） | — | 回退为草稿继续编辑；已有运行记录的版本会被拒绝（改用废弃+复制） |
| 废弃 | — | ✓ | — | 下架：不可再发起运行，历史运行记录保留可追溯；若它是任务当前版本，指针自动回退到最近一个未废弃的已发布版本 |
| 删除 | ✓ | ✗ | ✗ | 仅草稿可物理删除（阶段定义一并清理）；已发布/已废弃版本永久保留以维持运行可追溯 |

版本状态与任务"当前版本"的联动：发布将当前版本指针切到该版本；撤销发布或废弃会自动把指针回退到最近一个未废弃的已发布版本，若没有则置空（此时任务需先发布一个版本才能运行）。

## 任务列表操作说明

任务列表每行的操作按钮作用如下：

| 按钮 | 作用 | 是否立即执行 |
|---|---|---|
| 编辑 | 修改任务名称、描述、执行 Agent、业务变量和状态；只影响任务定义本身，不触碰已发布版本 | 否 |
| 版本 | 打开版本管理抽屉：查看版本列表、编辑草稿、切分阶段、发布版本。版本是"某次可执行的完整快照"（起始地址、步骤、输入文件绑定、变量），发布后不可变；运行时只能运行已发布版本 | 否 |
| 运行 | 打开运行确认弹窗，点「开始运行」后**立即创建一次运行并同步等待执行完成**（可能持续数分钟），期间可到运行记录 Tab 看进度 | **是** |
| 定时 | 打开定时配置弹窗，保存 cron 表达式和默认执行版本/Agent。**保存动作只把配置记录在任务上，不会立即执行，也不会自动创建调度任务**；要真正定时执行还需到「系统监控 → 定时任务」手工创建触发任务（见下文"定时触发运行"） | 否 |
| 录制转模板 | 把一条 Web 录制记录转成该任务的版本草稿（不发布），供后续编辑后发布 | 否 |

顶部工具栏的「新建录制」按钮打开独立录制弹窗，直接在本页面开始一次录制（不关联 Web 用例），详见下文"录制与录制转模板"。
## 运行执行

`POST /configuration-tasks/{taskId}/runs` 默认使用任务当前发布版本，也可用 `versionNo` 指定历史版本：

```json
{
  "agentCode": "agent-gray04",
  "versionNo": 3,
  "triggerType": "manual",
  "manualLoginEnabled": false,
  "manualLoginWaitSec": 120,
  "timeoutSeconds": 1800
}
```

运行创建时会冻结版本快照和输入资源摘要（版本、大小、SHA-256）。执行复用既有 Web 用例的 `run_case` 协议：输入绑定注入 `runtimeOptions.resourceBindings`，Agent 在受控目录内按资源 ID 解析文件。运行状态为 `PENDING/RUNNING/SUCCESS/FAILED/CANCELLED`；当前为同步执行，HTTP 响应返回最终状态和步骤结果，执行过程中的步骤进度会通过 Agent 事件实时写入运行记录，可随时通过运行详情查看。

运行控制与限制：

- **并发租约**：同一 Agent 同时只允许一个运行中的配置任务；存在未完成运行时新运行会被拒绝，需要等待完成或先停止。
- **手动登录**：`manualLoginEnabled` 为 `true` 时先打开浏览器等待人工登录（等待 `manualLoginWaitSec` 秒），登录完成后自动继续执行步骤；适合需要扫码或验证码的页面。
- **超时**：`timeoutSeconds` 默认 1800 秒，可按任务时长调整（30–21600 秒）。
- **停止**：`POST /configuration-tasks/runs/{taskRunId}/stop` 向 Agent 发送停止命令并把运行收敛为 `CANCELLED`；Agent 离线时本地状态仍会收敛，保证取消幂等。
- **孤儿恢复**：服务重启或 Agent 断线导致运行长期无进展时，恢复任务（建议 10 分钟周期，阈值 60 分钟）会把运行收敛为 `FAILED`（错误码 `RUN_ORPHAN_RECOVERED`），同时把当前 `RUNNING` 阶段收敛为 `FAILED`、尚未执行的 `PENDING/WAITING_APPROVAL` 阶段标记为 `SKIPPED`，并刷新证据完整状态；可重新发起运行。
- **资源过期清理**：清理任务（建议每小时周期）把超过保留期的资源收敛为 `EXPIRED`、超时未完成的传输收敛为 `EXPIRED`；资源过期后不能被新版本引用，历史运行按快照不受影响。

两个维护任务需要在「系统监控 → 定时任务」中创建：`module_task.scheduler_maintenance.cleanup_configuration_task_resources` 和 `module_task.scheduler_maintenance.recover_configuration_task_runs`。

运行中步骤的 `upload_file` 参数写 `fileKey` 加文件来源（`resourceIds` 或 `agentPath`），不会写入任何服务器绝对路径；回放执行上传时由 Agent 直接向文件输入框注入文件，不会再弹出文件选择框，也不需要人工介入。

## 阶段与审批闸门

版本草稿支持把步骤切分为阶段（最多 20 个），每个阶段声明模式：

| 模式 | 用途 | 执行策略 |
|---|---|---|
| `READ` | 查询、核对 | 自动执行 |
| `PREPARE_WRITE` | 打开并填写待提交值 | 自动执行 |
| `WRITE` | 保存、导入、状态变更 | 执行前必须审批 |
| `VERIFY` | 修改后重新查询 | 自动执行 |

阶段切分请求示例（前端阶段编辑器会根据步骤选择自动生成 `stepIds` 和兼容的 `stepIndexes`）：

```json
[
  {
    "stageKey": "query",
    "stageName": "查询现状",
    "mode": "READ",
    "stepIds": ["step-open-store", "step-check-config"],
    "stepIndexes": [0, 1]
  },
  {
    "stageKey": "save",
    "stageName": "提交配置",
    "mode": "WRITE",
    "stepIds": ["step-save"],
    "stepIndexes": [2]
  }
]
```

- 在版本管理的“阶段”编辑器中，步骤通过“第几步 · 动作 · 步骤名称”多选项选择，不需要手工复制稳定 ID；保存时系统以选中的稳定 `stepId` 为准，自动计算当前版本对应的 `stepIndexes`。
- 步骤移动不会改变其稳定 `stepId`；`stepIndexes` 只用于兼容旧版本和展示顺序。历史阶段若引用了当前版本不存在的步骤，会保留异常提示，确认处理后才能保存。

- 运行创建时阶段快照到运行记录；`WRITE` 阶段创建即进入 `WAITING_APPROVAL`，审批通过后才允许执行；
- 审批拒绝会取消整个运行（错误码 `STAGE_REJECTED`）；
- 任一阶段失败会自动跳过后续阶段；失败阶段可重试，`WRITE` 阶段重试必须重新审批；
- 未声明阶段时按单一全量阶段执行，保持向后兼容。

## 产物登记

### 证据模式与截图步骤的关系（重要）

阶段配置里的"证据模式"（不要求 / 可选 / 必需 / 前后对照）**只是约束声明，不会自动截图**。实际采集业务截图必须在版本步骤中显式添加一个"截图 / 采集证据"（`capture_screenshot`）动作的步骤，由它决定在哪个页面状态取证、证据叫什么、属于什么语义。两者的分工：

- **截图步骤（实际采集）**：插入在步骤编排中，执行到该步骤时采集一张业务证据截图；
- **阶段证据模式（约束校验）**：声明"本阶段需要哪些证据"，发布和保存阶段时会校验该阶段包含的步骤里是否存在能产出这些证据的截图步骤，不满足则拒绝。

各证据模式的校验要求：

| 证据模式 | 校验规则 |
|---|---|
| 不要求（NONE） | 不检查截图步骤；但不能同时声明"必需类型" |
| 可选（OPTIONAL） | 不强制截图步骤存在，截图缺失不阻断 |
| 必需（REQUIRED） | 阶段包含的步骤中必须至少有一个截图步骤，且覆盖声明的"必需类型" |
| 前后对照（BEFORE_AFTER） | 必须同时包含"修改前"（before_screenshot）和"修改后"（after_screenshot）两类截图步骤 |

常见问题：发布时提示"阶段 xxx 要求证据，但未配置 capture_screenshot 步骤"，说明该阶段证据模式选了"必需"或"前后对照"，但阶段勾选的步骤里没有任何截图动作步骤。请编辑版本，在该阶段的步骤区间内新增"截图 / 采集证据"步骤（详情中可设置证据类型、证据键），再保存阶段切分。失败诊断截图（`failure_screenshot`）由 Agent 自动生成，仅用于排障，不能充当业务成功证据。

Agent 执行失败步骤时自动截图，并通过事件上报到服务端；服务端把截图登记为 Agent 本地受控资源并建立产物引用（`task_artifact`）。metadata-only 事件登记前会调用 Agent `file_stat`，只有实际文件存在且大小、SHA-256 均与上报元数据一致时，资源才进入 `READY`、产物才标记为 `ONLINE`；Agent 离线、文件不存在、过期、被替换或摘要/大小不一致时保留引用但标记不可用，不伪造可取回状态。首期支持以下证据相关约定：

- 步骤可显式声明 `actionType=capture_screenshot`，用于在明确的页面状态采集业务截图；该步骤不执行点击、填写或定位器操作；
- 截图参数可携带 `evidenceType`（`checkpoint_screenshot`、`before_screenshot`、`after_screenshot`）、`evidenceKey`、`label`、`required`、`fullPage`、`maskSelectors`、`note` 和 `waitMs`；
- 阶段定义可携带证据策略字段 `evidencePolicy`，用于表达 `NONE`、`OPTIONAL`、`REQUIRED` 或 `BEFORE_AFTER`，以及所需证据类型/证据键和缺失处理策略；`requiredTypes` 表示每种类型至少一项，阶段内同类型存在多张截图时任意一张即可满足，若要精确指定某张截图应使用 `requiredEvidenceKeys`；字段随阶段快照保存，当前只作为契约和元数据登记，不提供证据包生成；
- Agent 上报的 `web_run_artifact` 事件以 `stepId` 作为稳定步骤身份，服务端保存 `stepKey`/步骤元数据；旧版仅有 `stepIndex` 或 Base64 `data` 的事件继续兼容；metadata-only 事件可登记 Agent-local 资源元数据，不要求把截图正文写入运行 JSON；
- 产物类型包括 `step_screenshot`、`failure_screenshot`、`execution_log`、`report`。产物只保存资源引用和元数据，不把图片 Base64 写入运行记录或报告正文；重复事件按资源身份/引用语义幂等处理。

### 产物预览、下载与访问审计

运行详情中的产物访问必须使用产物自己的 `artifactId`，不能把 `resourceId` 或 `objectKey` 当作授权凭证。运行产物列表先校验任务/运行归属；预览和下载再校验产物、运行、任务、资源和当前用户权限，管理员可跨范围访问。

- `preview` 只允许 `image/png`、`image/jpeg`、`image/webp`、`text/plain`、`application/json`，响应以内联方式返回；其他 MIME 类型请使用下载。
- `download` 以附件方式流式返回，文件名会去除路径和不安全字符，并返回 `Content-Length`、`X-Artifact-Id`、`X-Artifact-SHA256` 和 `X-Content-Type-Options: nosniff`。
- Agent-local 产物通过 Agent `file_read` 读取，服务端携带登记的 expected 大小和 SHA-256，并在返回前再次计算摘要；服务端报告只从固定的 `storage/configuration-task-reports/` 目录读取，SFTP 资源走 SFTP Provider，不会误走报告路径。
- preview/download 成功和失败都会写入脱敏访问审计；审计不保存图片 Base64、Cookie、Token、Agent 绝对路径或文件正文。
- 资源为 `FAILED`/`EXPIRED`、产物不是 `ONLINE`、文件被替换或读取后摘要不一致时，访问失败并返回稳定错误码，不返回空文件。

业务执行状态和证据完整性不是同一个状态：运行可能是 `SUCCESS`，但因必需截图缺失而需要提示证据不完整；失败诊断截图也不能自动充当业务成功证据。

## 录制与录制转模板

### 两种录制入口

录制记录与 Web 测试管理共用同一套数据和链路（记录保存在录制会话表，可在 Web 测试管理 → 录制记录中查看），但提供两个入口：

1. **本页面直接录制**：任务管理 Tab 点「新建录制」，填写起始地址、选择执行 Agent（可选手动登录、登录凭证投影）后开始录制。录制不关联任何 Web 用例，专用于生成配置任务版本草稿。录制过程中弹窗显示实时状态，完成后点「停止录制」。

   **「停止后保存凭证」开关（行为随是否选择登录凭证变化）**：

   - **未选择登录凭证**：开关为「停止后保存为新凭证」——录制停止后把本次会话结束时的浏览器状态（含手动登录后的登录态）保存为一个新的统一凭证（名称可自定义，默认 `录制凭证-{录制ID}`）。首次录制、或登录态需要留存的场景建议开启；保存后可在版本编辑和运行配置中选用这个新凭证，下次执行免登录。
   - **已选择登录凭证**：开关变为「停止后回写所选凭证」——录制停止后把最终浏览器状态**覆盖写回**所选的那个凭证，下次用该凭证执行即免登录。此模式要求该凭证绑定在统一凭证管理中开启了「允许回写」，未开启时开关禁用并提示；回写带乐观锁版本校验，凭证若在此期间被刷新或编辑过会保留服务端较新状态并提示重试。
   - 不开启开关：浏览器状态只随录制记录留存，不写入统一凭证库。
2. **Web 测试管理录制**：在「测试管理 → Web测试管理」中录制（可关联用例、回放、存为用例），之后回到本页面用「录制转模板」引用。

### 录制中的文件上传

录制页面点击"上传"按钮时，浏览器会正常弹出系统文件选择框，由录制人**手动选择一个文件**，页面流程照常继续，上传之后的步骤可以正常录制：

- 选择文件完成后，录制会生成一条「上传文件 文件名」步骤，定位器直接指向页面的文件输入框本体（即使输入框在页面上不可见）；
- 该步骤的文件名是**样本占位**（浏览器安全机制拿不到真实路径），仅用于识别这一步上传的是什么文件；编辑阶段在版本编辑器里为它选择「资源绑定」或「Agent 目录文件」即可，**不需要修改定位元素**；
- 录制阶段不做任何文件上传归档，正式文件通过「资源管理」页面上传，或放在执行 Agent 的受控上传目录中；
- 回放时执行"点击上传按钮"不会再弹出文件选择框（由 Agent 自动抑制），随后由上传步骤直接注入文件。

### 录制转模板

在任务列表点「录制转模板」，**下拉选择**一条录制记录（支持按名称搜索，弹窗打开时自动加载最近的录制记录，选项显示会话名称、记录 ID 和当前状态；草稿和录制中的记录不在可选范围）并标记变量/上传 fileKey，即可把既有 Web 录制转成任务版本草稿：

- 标记中的步骤索引按转换后步骤数组从 **0 开始**，第 1 步写 `0`；它不是页面显示的 `stepIndex`，也不是录制事件序号；
- 变量标记 `{"0": "store.id"}`：仅对已有 `fill` 或 `select_option` 步骤生效，把输入值替换为 `${store.id}` 占位符；`select_option` 会替换为 `values` 数组中的占位值；
- 变量值在任务编辑的业务变量或版本编辑的版本变量中提供。运行时支持 `${变量名}` 和 `{{变量名}}`，建议直接使用扁平键名，例如 `{"store.id": "2625868"}`；版本变量与任务变量同名时优先使用版本变量；
- 上传标记 `{"3": "price_tag"}`：仅对第 4 步已经是 `upload_file` 的动作生效，为其设置逻辑 `fileKey=price_tag`；不会把普通输入或点击步骤转换成上传步骤；
- `fileKey` 不是 Agent 本地文件路径。转换后还需在版本编辑器的「输入绑定」中填写同名键，例如 `{"price_tag": ["900000000000001"]}`；资源必须已上传、状态为 `READY`，且属于任务执行 Agent；
- 转换生成 DRAFT 版本，不会自动发布，也不会自动填写输入绑定，需在版本编辑器中检查步骤、补充资源绑定后发布。录制过程中如需增加断言，请按住 **Alt 键点击**目标元素：有文本时生成“文本包含”断言，无文本时生成“元素可见”断言；Alt+点击不会触发实际点击，配置任务录制默认把断言追加到上一条步骤，普通点击不会自动生成断言。

## 定时触发运行

任务的「定时」配置支持 5 字段 cron（本地时区）：`0 9 * * *` 每天 9 点、`0 9 * * 1-5` 工作日 9 点、`*/30 * * * *` 每 30 分钟。

- 可指定执行版本号和 Agent（缺省使用任务当前发布版本和任务上配置的 Agent）；
- 定时触发的运行 `triggerType=scheduled`，同样受并发租约、审批闸门和超时约束；
- 未启用定时或任务配置缺失时调度自动跳过，不做任何写操作。

### 定时配置与调度任务是两回事（重要）

定时执行需要**两处配置同时生效**，缺一不可：

1. **任务上的「定时」按钮**：保存 cron 表达式和默认执行版本/Agent。这一步只是把配置记录在任务上（触发时读取使用），**不会自动创建任何调度任务，保存后到点不会自己执行**。
2. **「系统监控 → 定时任务」的调度任务**：这是真正到点执行的调度器，必须手工创建一条：调用目标填 `module_task.scheduler_configuration.trigger_configuration_task_run`，参数填 `{"task_id": 任务ID}`，cron 与任务上的定时配置保持一致。

两者关系：调度任务到点后调用触发入口，触发入口读取任务上的定时配置（是否启用、执行哪个版本、用哪个 Agent），再创建一次运行并同步执行。任务上未启用定时（`enabled=false`）时，即使调度任务存在也会跳过不执行；反过来只有任务上的定时配置而没有调度任务，则永远不会有触发时机。

定时弹窗内有醒目提示说明这一约定。

## 报告归档

`POST /configuration-tasks/runs/{taskRunId}/report?notifyFeishu=true` 生成运行报告并归档：

- 报告文件为 Word 兼容 HTML（`.doc`），Word/WPS 可直接打开另存为 `.docx`，无需额外依赖；
- 报告内容：运行信息、阶段执行结果、产物清单（文件名 + 资源 ID）；
- 报告文件保存在服务端 `storage/configuration-task-reports/`，登记为资源并关联产物引用；
- `notifyFeishu=true` 时推送飞书机器人通知（使用系统统一飞书配置），推送失败不影响归档。


## ID 与注意事项

- 响应中的 `taskId`、`versionId`、`currentVersionId`、`taskRunId` 均为字符串（数据库 BIGINT）；前端不能对其调用 `Number()`。
- 版本发布后不可变；修改任务变量不影响已发布版本，新变量在下一个版本中生效。
- 资源必须通过资源传输接口完成 `begin/chunk/commit` 进入 `READY` 后才能被版本引用。
- 当前不提供：批量门店编排、运行中 Web 界面实时进度推送（可通过运行详情轮询查看）、证据包生成与下载。产物 preview/download 已上线，必须使用 `artifactId` 访问；定时配置接口已上线，但保存任务上的定时配置不会自动创建调度任务，必须另行配置调度器；生产环境 `WRITE` 阶段已默认强制审批闸门，请勿为审批账号开通无人值守的自动审批。
