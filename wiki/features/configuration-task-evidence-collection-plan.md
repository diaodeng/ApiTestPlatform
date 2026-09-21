---
title: 门店配置运行取证与证据包实施方案
type: feature
topic: configuration-task-evidence
source_type: design
canonical: true
knowledge_state: current
confidence: high
freshness: 2026-09-21
created: 2026-09-20
updated: 2026-09-21
related_files:
  - server/modules/configuration_task/service/task_run_service.py
  - server/modules/configuration_task/service/stage_service.py
  - server/modules/configuration_task/service/artifact_service.py
  - server/modules/configuration_task/service/report_service.py
  - server/modules/configuration_task/entity/vo/task_vo.py
  - server/module_qtr/controller/agent_controller.py
  - client_new/services/web_test_service.py
  - web/src/components/hrm/case/webcase/utils/shared.js
  - web/src/components/hrm/case/webcase/domain/stepDomain.js
  - web/src/components/hrm/case/webcase/components/StepDetail.vue
  - web/src/views/hrm/configuration-task/components/VersionStepTable.vue
  - web/src/views/hrm/configuration-task/components/VersionDrawer.vue
  - web/src/views/hrm/configuration-task/components/RunDetailDrawer.vue
---

# 门店配置运行取证与证据包实施方案

> 制定日期：2026-09-20，第一期实施更新：2026-09-21。本文同时记录已实现的显式取证步骤、阶段证据策略、Agent-local 元数据登记、文件完整性校验和产物受控访问边界；证据包生成、查询和下载仍未上线。

## 1. 结论与设计原则

### 1.1 统一结论

门店配置取证采用两层模型：

1. **显式取证步骤**：在步骤编排中插入一个独立的 `capture_screenshot` 步骤，明确“在哪个页面状态取证、证据叫什么、证据属于什么语义”。
2. **阶段级取证策略**：在阶段编排中明确“本阶段是否需要证据、需要哪些证据类型、证据不完整时如何处理”。

两层的职责不能混淆：

- 阶段策略负责约束和校验完整性，不代替具体截图位置；
- 显式步骤负责实际采集，不隐式改变其他网页动作的截图行为；
- 失败截图继续由 Agent 自动生成，属于诊断产物，不属于业务成功证据；
- 认证凭证（账号、Cookie、Token、`storageState`）继续归统一凭证域管理，不进入截图证据域；
- 运行成功和证据完整是两个状态，不能因为截图上传失败就伪造业务失败，也不能因为页面点击成功就宣称业务配置成功。

### 1.2 推荐默认行为

| 场景 | 默认行为 |
|---|---|
| 未配置业务取证 | 不采集成功步骤截图 |
| 显式 `capture_screenshot` 步骤 | 到该步骤时采集一张业务证据截图 |
| 阶段策略为 `OPTIONAL` | 显式取证步骤按配置执行，缺失不阻断验收 |
| 阶段策略为 `REQUIRED` | 必须满足阶段声明的证据类型，否则证据状态为 `INCOMPLETE` |
| 修改前后取证 | `WRITE/PREPARE_WRITE/VERIFY` 阶段建议使用 `before_screenshot` + `after_screenshot` |
| 失败步骤 | 自动产生 `failure_screenshot`，用于诊断，不计入成功取证完整性 |
| 截图上传失败 | 业务执行状态和证据状态分别记录，不能互相覆盖 |

### 1.3 不采用的方案

不采用以下方式作为主模型：

- 给每一个点击、填写、上传动作增加“执行后截图”开关；
- 默认每一步成功后都截图；
- 只增加一个全局“成功截图”开关；
- 把截图写入统一认证凭证；
- 把截图 Base64 写入步骤模板、普通运行 JSON 或普通日志；
- 只生成一份没有原始图片、没有校验清单的 Word 元数据报告。

## 2. 当前实现基线

### 2.1 已有能力

当前已经存在以下基础链路：

```text
配置任务版本
  -> task_run 创建并冻结版本/输入资源/阶段快照
  -> Agent 接收 run_case
  -> Agent 执行 Web 步骤
  -> 截图、日志等文件写入 Agent 受控目录
  -> web_run_* 事件回传资源元数据和 Agent-local 定位信息
  -> resource_object + task_artifact 登记资源索引
  -> 受控访问服务按 artifact_id 校验权限、状态和元数据一致性
  -> 按 Agent-local / SFTP / server report Provider 读取并二次校验摘要
  -> preview/download 返回正文；证据包仍未上线
```

关键现状：

- `client_new/services/web_test_service.py` 已支持显式 `capture_screenshot`，失败步骤仍保留自动 `failure_screenshot`；
- 前端已提供 `capture_screenshot` 动作和专属字段编辑；
- `task_artifact` 支持 `step_screenshot`、`failure_screenshot`、`execution_log`、`report` 等类型，并通过证据字段关联运行阶段和稳定步骤；
- `artifact_service.py` 仍保留旧 Base64 事件兼容解析；新 metadata-only 事件由 Agent 先落受控目录，服务端只登记资源和产物元数据；
- 运行详情当前显示产物元数据，并提供按 `artifact_id` 的安全预览和单张下载；证据包导出仍未上线；
- `report_service.py` 当前生成 Word 兼容 `.doc` 并写入服务端本地目录，这是现状兼容行为，不等同于 Agent 证据正文，也不是新的证据包实现；
- 阶段事件优先按稳定 `stepId` 关联；旧 Agent 的展示索引和历史 0-based 索引仅作为兼容回退，无法映射时记录明确告警；阶段只有在阶段内全部步骤成功或跳过后才成功，重复/乱序事件不能提前结束阶段；
- 阶段终态、阶段重试和孤儿运行恢复均具备状态收敛保护：迟到终态不覆盖既有结果，重试清理上一轮执行字段，孤儿运行同步收敛当前/后续阶段并刷新证据状态；

验收证据、失败诊断截图、执行日志和报告的正文来源按 Provider 分离：截图/日志的 metadata-only 事件只说明 Agent-local 资源已登记，登记前会通过 `file_stat` 校验实际文件存在、未过期、大小和 SHA-256；访问时通过 `file_read` 携带 expected 元数据并再次校验摘要。当前报告由服务端报告服务生成 Word 兼容文件。服务端保存资源索引、校验元数据、业务关联和可用性状态，不保存 Agent 绝对路径，也不把其作为接口契约；artifact preview/download 已上线，证据包正文和打包能力尚未上线。

### 2.2 当前实现边界必须保留

后续开发不能把以下设计文档中的“规划字段”误认为当前已经实现：

- 阶段与步骤关联已优先使用稳定 `stepId`，旧 `stepIndexes` 只用于兼容转换和展示顺序；
- Agent-local 资源不等于服务端备份，Agent 离线或本地文件清理后不能保证立即取回；
- artifact 访问统一使用 `artifact_id`；`resourceId` 只是资源身份，`objectKey` 只是受控相对定位键，二者都不是下载授权；访问服务会校验任务/运行/产物/资源归属、状态、大小、SHA-256、MIME、Agent 和 objectKey 一致性，并记录脱敏访问审计；
- 当前报告不是包含原始截图的验收凭证包。

## 3. 领域术语和边界

### 3.1 认证凭证与运行证据的区别

| 类型 | 解决的问题 | 示例 | 归属 |
|---|---|---|---|
| 认证凭证 | 如何登录和访问系统 | 用户名、密码、Cookie、Token、`storageState` | `auth_credential` / `auth_credential_binding` |
| 运行证据 | 本次运行后页面实际呈现了什么 | 修改前截图、修改后截图、查询结果截图 | `resource_object` + `task_artifact` |
| 诊断产物 | 为什么运行失败 | 失败截图、执行日志、定位器尝试信息 | `resource_object` + `task_artifact` |
| 交付证据包 | 如何把一次运行的证据交给其他团队 | Agent 侧生成的 ZIP、HTML 摘要、DOCX/PDF、manifest | `resource_object` + `task_artifact` 元数据；文件正文只在 Agent 受控目录 |

截图不能写入认证凭证。统一凭证继续只允许业务传递 `credentialBindingId`，不在任务步骤或证据包中保存密文、Cookie 或完整 `storageState`。

### 3.2 证据类型

第一期统一使用以下证据类型：

| `evidenceType` | 含义 | 是否证明成功 |
|---|---|---|
| `checkpoint_screenshot` | 某个业务检查点的页面状态 | 需结合断言和上下文，单独不等于成功 |
| `before_screenshot` | 写入、导入或修改前的原始状态 | 证明修改前状态 |
| `after_screenshot` | 写入后重新查询并验证后的状态 | 证明页面呈现的结果，仍需结合断言 |
| `failure_screenshot` | 步骤失败时的现场截图 | 只证明失败现场，不证明业务成功 |
| `execution_log` | 执行日志或结构化运行信息 | 不能替代页面证据 |
| `report` | 摘要报告或证据包索引 | 不能替代原始证据 |

`step_screenshot` 可以作为历史兼容输入，但新流程建议统一使用有业务语义的 `evidenceType`。服务端可在兼容期把旧 `step_screenshot` 映射为 `checkpoint_screenshot`。

## 4. 产品模型

### 4.1 显式取证步骤

在 Web 步骤数组中增加独立动作：

```text
动作类型：capture_screenshot
中文名称：截图 / 采集证据
```

该步骤不需要定位器，不执行点击或表单操作，只在当前页面状态采集证据。它应像 `goto`、`sleep`、`assert_page_contains` 一样成为标准步骤，可新增、删除、启停、移动和复制。

### 4.1.1 步骤示例

```json
{
  "stepId": "capture-before-save",
  "stepIndex": 4,
  "stepName": "保存前截图",
  "actionType": "capture_screenshot",
  "enabled": true,
  "continueOnFailure": false,
  "timeoutMs": 10000,
  "params": {
    "evidenceType": "before_screenshot",
    "evidenceKey": "store-config-before-save",
    "label": "门店配置修改前",
    "required": true,
    "fullPage": false,
    "maskSelectors": [],
    "note": "记录提交前的现有配置"
  },
  "assertions": []
}
```

### 4.1.2 步骤参数

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `evidenceType` | string | `checkpoint_screenshot` | `checkpoint_screenshot`、`before_screenshot`、`after_screenshot` |
| `evidenceKey` | string | 自动生成 | 版本内稳定唯一，用于阶段规则匹配和证据包引用 |
| `label` | string | 步骤名称 | 面向用户和交付团队展示的证据名称 |
| `required` | boolean | `false` | 该显式证据是否必须成功产生 |
| `fullPage` | boolean | `false` | 是否采集整页；第一期只支持视口和整页 |
| `maskSelectors` | string[] | `[]` | 采集前需要遮罩的页面元素选择器 |
| `note` | string | `""` | 证据说明，不写敏感数据 |
| `waitMs` | integer | `0` | 截图前额外等待页面稳定的时间，受步骤超时限制 |

第一期不建议支持任意 JavaScript、任意本地路径或复杂图片后处理。元素截图、区域截图、自动识别敏感字段可作为后续能力。

### 4.1.3 显式步骤执行语义

执行顺序为：

```text
进入 capture_screenshot 步骤
  -> 检查步骤是否启用
  -> 按 waitMs 等待页面稳定
  -> 按 maskSelectors 执行遮罩
  -> 调用 Playwright page.screenshot
  -> 计算截图大小和 SHA-256
  -> 上报 web_run_artifact
  -> 记录步骤结果和产物关联
  -> 恢复页面遮罩状态（如实现为临时 DOM 修改）
```

截图失败时：

- 步骤结果必须返回 `failed` 和明确错误信息；
- 业务步骤是否继续由 `continueOnFailure` 决定；
- 阶段和运行证据完整性由阶段策略另行计算；
- 不得把截图 Base64 放入 `result_json`；
- 日志必须记录运行 ID、阶段、步骤、证据键和失败原因，但不得记录截图正文。

## 4.2 阶段级取证策略

阶段编辑器增加“取证策略”配置。它负责回答：

> 本阶段是否需要业务证据？需要哪些类型？缺失后是否影响验收？

### 4.2.1 策略结构

```json
{
  "evidencePolicy": {
    "mode": "REQUIRED",
    "requiredTypes": ["before_screenshot", "after_screenshot"],
    "requiredEvidenceKeys": [
      "store-config-before-save",
      "store-config-after-save"
    ],
    "completenessPolicy": "BLOCK_ACCEPTANCE",
    "retentionDays": 90,
    "maskProfileId": "store-default"
  }
}
```

### 4.2.2 策略模式

| `mode` | 语义 | 适用阶段 |
|---|---|---|
| `NONE` | 不要求业务截图；失败诊断截图仍可产生 | 纯准备、内部跳转、无业务结果的阶段 |
| `OPTIONAL` | 执行显式取证步骤，但缺失不判定证据不完整 | 普通查询、辅助检查 |
| `REQUIRED` | 至少满足 `requiredTypes` 或 `requiredEvidenceKeys` | 需要交付凭证的查询或核对阶段 |
| `BEFORE_AFTER` | 必须存在一份 Before 和一份 After，并且两者都成功 | 修改、导入、状态变更后的验证阶段 |

推荐默认值：

- `READ`：`OPTIONAL`；
- `PREPARE_WRITE`：涉及敏感配置时使用 `REQUIRED` + `before_screenshot`；
- `WRITE`：原则上由前后阶段共同取证，不把点击保存本身当作成功证据；
- `VERIFY`：`REQUIRED` + `after_screenshot`，或使用 `BEFORE_AFTER` 覆盖完整修改阶段。

### 4.2.3 完整性处理策略

| `completenessPolicy` | 业务执行成功时 | 证据包状态 |
|---|---|---|
| `WARN` | 不影响业务状态 | `INCOMPLETE`，允许导出并显著提示 |
| `BLOCK_ACCEPTANCE` | 不回滚业务，也不伪造业务失败 | 禁止标记为“验收完成”，可导出诊断包 |
| `BLOCK_RUN` | 仅在后续需要强审计的版本启用 | 缺证时阻断后续阶段或运行，第一期不默认开启 |

第一期默认只实现 `WARN` 和 `BLOCK_ACCEPTANCE`，不在没有完整审批和恢复设计前启用 `BLOCK_RUN`。

### 4.2.4 阶段策略与显式步骤的关系

阶段规则不自动产生业务截图。推荐关系如下：

```text
阶段策略 REQUIRED + requiredTypes=[before_screenshot]
  -> 阶段内必须存在 enabled 的 capture_screenshot 步骤
  -> 该步骤 evidenceType=before_screenshot
  -> 步骤执行成功并登记产物
  -> 阶段证据状态 COMPLETE
```

如果策略声明了 `requiredEvidenceKeys`，则必须按证据键匹配；如果只声明 `requiredTypes`，则每个类型至少需要一项，阶段内多个同类型截图中的任意一张即可满足要求。若要精确要求某个序号，也应通过证据键规划具体步骤，而不是依赖同类型候选的数量。

这样既保留了阶段级统一约束，又避免系统在用户没有明确页面状态时自动截图。

## 5. 流程编排规则

### 5.1 推荐的只读核对流程

```text
阶段：查询现状（READ，OPTIONAL 或 REQUIRED）
  1. 打开门店配置页面
  2. 填写门店编号
  3. 点击查询
  4. 断言页面包含目标门店
  5. 截图：当前配置（checkpoint_screenshot）
```

### 5.2 推荐的修改流程

```text
阶段：查询现状（READ，REQUIRED）
  1. 打开页面
  2. 查询门店
  3. 断言门店身份正确
  4. 截图：修改前（before_screenshot）

阶段：准备修改（PREPARE_WRITE，REQUIRED）
  5. 填写新配置
  6. 截图：待提交值（checkpoint_screenshot，可选）

阶段：提交配置（WRITE，审批）
  7. 点击保存
  8. 等待保存响应

阶段：验证结果（VERIFY，REQUIRED）
  9. 重新查询
  10. 断言新值已经生效
  11. 截图：修改后（after_screenshot）
```

### 5.3 失败流程

```text
1. 执行网页动作
2. 动作或断言失败
3. Agent 自动采集 failure_screenshot 并写入 Agent 受控目录
4. 服务端登记诊断产物元数据和 Agent-local 定位信息
5. 阶段记录业务失败和证据状态
```

失败截图不能自动满足 `after_screenshot` 要求，也不能被证据包标记为验收通过证据。

### 5.4 步骤移动和阶段关联

现有阶段主要以 0-based `stepIndexes` 关联步骤。引入显式取证步骤后，必须优先解决索引错位问题：

1. 新增 `stepId` 或 `stepKey` 作为稳定身份；
2. 阶段定义同时保存 `stepIds`；
3. `stepIndexes` 仅作为兼容字段和展示顺序；阶段编辑器通过“第几步 · 动作 · 步骤名称”多选项选择步骤，提交时以稳定 `stepId` 为准自动派生当前索引；
4. 运行产物优先使用 `stepId` 关联，索引只作为回退；
5. 步骤新增、删除、上移、下移后，阶段编辑器根据稳定 `stepId` 保持关联，并在保存时重新计算兼容索引；
6. 保存和发布时校验每个步骤只属于一个阶段，或明确允许跨阶段引用；
7. 老版本没有 `stepId` 时，在发布/运行快照阶段生成稳定映射，不能直接依赖当前数组位置。

前端阶段编辑器现在通过步骤选择项维护阶段关联：选项显示步骤序号、动作和步骤名称，内部值仍为稳定 `stepId`；步骤移动不会改变 ID，保存时自动派生兼容的 `stepIndexes`。历史阶段只有索引时按当前版本步骤回填 ID，引用已不存在步骤时保留异常提示，不能静默丢失关联。

阶段编辑器通过步骤选择项维护阶段关联；步骤发生结构变化后，用户可在选择器中检查当前步骤名称和序号，系统按稳定 ID 保持关联，并在保存时重新计算兼容索引。

## 6. 数据模型设计

### 6.1 版本阶段定义

在 `configuration_task_stage` 中增加或扩展 `evidence_policy_json`，随版本发布冻结：

```json
{
  "mode": "BEFORE_AFTER",
  "requiredTypes": ["before_screenshot", "after_screenshot"],
  "requiredEvidenceKeys": [],
  "completenessPolicy": "BLOCK_ACCEPTANCE",
  "retentionDays": 90,
  "maskProfileId": "store-default"
}
```

规则：

- 草稿可编辑，发布后不可原地修改；
- 发布校验阶段模式、证据类型、证据键和步骤映射；
- `BEFORE_AFTER` 至少要求版本内存在可匹配的 Before/After 显式步骤；
- `NONE` 不要求成功截图步骤，但失败诊断策略仍独立生效；
- `retentionDays` 应受系统最大值限制，不能由普通用户无限延长。

### 6.2 运行阶段快照

在 `task_run_stage` 中保存：

- `evidence_policy_snapshot_json`；
- `evidence_status`：`NOT_REQUIRED`、`PENDING`、`COMPLETE`、`INCOMPLETE`；
- `evidence_missing_json`：缺失证据类型或证据键；
- `evidence_error_message`：脱敏错误摘要。

阶段快照不能再读取正在变化的版本草稿，确保历史运行可追溯。

### 6.3 运行产物字段

继续复用 `task_artifact` 作为通用产物引用，但增加证据关联字段：

| 字段 | 说明 |
|---|---|
| `artifact_type` | `step_screenshot`、`failure_screenshot`、`execution_log`、`report`、`evidence_package` |
| `evidence_type` | `checkpoint_screenshot`、`before_screenshot`、`after_screenshot`、`failure_screenshot` |
| `evidence_key` | 显式步骤中的稳定证据键 |
| `run_stage_id` | 运行阶段 ID |
| `stage_key` | 阶段稳定标识 |
| `step_id` | 步骤稳定 ID |
| `step_index` | 运行时展示序号，兼容旧数据 |
| `sequence_no` | 同一步骤多次产物的顺序号 |
| `is_required` | 是否由步骤或阶段策略要求 |
| `captured_at` | Agent 采集时间 |
| `mask_applied` | 是否执行遮罩 |
| `mask_profile_id` | 使用的遮罩策略 |
| `page_url` | 脱敏后的页面 URL 摘要，可选 |
| `note` | 用户可见说明，不写敏感数据 |
| `provider_type` | 首期固定为 `agent_local` |
| `agent_code` | 文件实际持有 Agent 编码 |
| `object_key` | Agent 受控相对定位键或 manifest locator，不保存绝对路径 |
| `file_size` / `mime_type` | Agent 上报并由服务端校验的文件元数据 |
| `sha256` | Agent 计算并由取回时再次校验的内容摘要 |
| `availability_status` | `ONLINE`、`AGENT_OFFLINE`、`NOT_FOUND`、`CHECKSUM_MISMATCH` |

不建议把全部证据字段继续塞进 `note` 或任意 JSON，核心字段应可查询、可排序、可审计。`resource_id` 只用于索引和权限校验，不能单独授权下载。

### 6.4 证据包对象

建议新增 `task_evidence_package`，用于登记一次由 Agent 生成的证据包。服务端只保存证据包的索引、状态和校验元数据，不保存 ZIP、HTML、DOC 或截图正文。证据包生成时由服务端校验权限并向运行所属 Agent 下发组包请求；Agent 在本地受控临时目录生成文件后，回传资源元数据和受控定位信息。

建议字段：

| 字段 | 说明 |
|---|---|
| `package_id` | 对外字符串化 ID |
| `task_run_id` | 所属运行 |
| `package_version` | 同一次运行的证据包版本 |
| `status` | `REQUESTED`、`BUILDING`、`READY`、`FAILED`、`EXPIRED`、`UNAVAILABLE` |
| `resource_id` | 指向 Agent-local ZIP 资源的索引 ID，不代表服务端保存了 ZIP |
| `agent_code` | 生成和持有文件的 Agent 编码 |
| `object_key` | Agent 受控相对定位键或 manifest locator，不保存绝对路径 |
| `manifest_sha256` | 包内 manifest 校验和 |
| `file_sha256` | 证据包文件校验和 |
| `file_size` / `mime_type` | Agent 上报并由服务端校验的文件元数据 |
| `artifact_count` | 纳入的产物数量 |
| `evidence_status` | `COMPLETE`、`INCOMPLETE`、`DIAGNOSTIC_ONLY` |
| `created_by` / `created_at` | 生成审计 |
| `expires_at` | Agent-local 文件和索引的保留期限 |
| `last_access_status` | 最近一次取回状态，如 `ONLINE`、`AGENT_OFFLINE`、`NOT_FOUND`、`CHECKSUM_MISMATCH` |

同一个运行可以重新生成新版本，但已生成版本不可覆盖。服务端只登记版本和元数据；包的可下载性取决于 Agent 在线、受控文件仍存在且校验通过。Agent 离线时可以继续查看包索引，但不能返回“可下载”状态。

## 7. Agent 与服务端执行链路

### 7.1 下发运行计划

`task_run_service.py` 构造 `run_case` 时，应将证据计划作为运行快照的一部分下发或由服务端保存并在事件接收时解析：

```json
{
  "runtimeOptions": {
    "resourceBindings": {},
    "evidencePlan": {
      "version": 1,
      "steps": {
        "capture-before-save": {
          "stageKey": "query",
          "evidenceType": "before_screenshot",
          "evidenceKey": "store-config-before-save",
          "required": true,
          "maskProfileId": "store-default"
        }
      }
    }
  }
}
```

推荐服务端保留运行快照，并在事件接收时再次校验 Agent 上报的 `stageKey`、`stepId` 和 `evidenceType`，不能完全信任 Agent 自报的阶段归属。

### 7.2 Agent 事件契约

`web_run_artifact` 的截图事件建议扩展为“先由 Agent 写入本地、再上报索引元数据”的形式：

```json
{
  "type": "web_run_artifact",
  "web_case_run_id": "123",
  "payload": {
    "artifactType": "step_screenshot",
    "evidenceType": "before_screenshot",
    "evidenceKey": "store-config-before-save",
    "stageKey": "query",
    "stepId": "capture-before-save",
    "stepIndex": 4,
    "stepName": "保存前截图",
    "fileName": "02-query-004-before.png",
    "mimeType": "image/png",
    "objectKey": "resources/evidence_01J...",
    "providerType": "agent_local",
    "agentCode": "agent-gray04",
    "fileSize": 248912,
    "sha256": "...",
    "capturedAt": "2026-09-20T10:20:30.123Z",
    "maskApplied": true,
    "maskProfileId": "store-default",
    "pageUrl": "https://example.com/store/******"
  }
}
```

`objectKey` 只能是 Agent 受控目录内的相对定位键或 manifest locator，不能是绝对路径。Agent 必须在上报前确认文件已经写入受控目录并计算大小、SHA-256；服务端只登记并校验这些元数据，不接收截图正文作为持久化内容。现有 Base64 事件只作为兼容迁移输入，兼容处理完成后应立即释放正文，不得写入服务端文件目录、数据库 JSON 或日志。

服务端必须校验：

- 运行 ID 存在且属于当前 Agent；
- `stepId` 属于运行版本；
- `stageKey` 与运行阶段快照匹配；
- `evidenceType` 与显式步骤参数匹配；
- `providerType=agent_local` 时 `agentCode` 必须等于运行 Agent，`objectKey` 必须通过相对路径和目录边界校验；
- 文件类型、文件大小、SHA-256、文件名和版本信息符合限制；
- 不接受路径穿越、绝对路径、任意本地路径或客户端自定义 Provider；
- 重复上报按 `(agentCode, objectKey, version)` 幂等，不重复生成资源。

资源登记成功不等于文件当前可下载。服务端应通过 Agent 心跳或取回探测维护 `ONLINE`、`OFFLINE`、`NOT_FOUND`、`CHECKSUM_MISMATCH` 等可用性状态。

### 7.3 Agent 执行改造点

`client_new/services/web_test_service.py` 需要按职责改造：

1. 在动作枚举和无定位器动作集合中加入 `capture_screenshot`；
2. `_run_single_step` 识别截图步骤，不解析定位器；
3. 在截图步骤中执行等待、遮罩、截图和结果构造；
4. 由运行循环通过专用 artifact sender 上报，不把 Base64 放进步骤结果；
5. 失败步骤自动截图逻辑保持不变，但补充 `stepId`、`stageKey` 和 `capturedAt`；
6. 截图上传异常只影响证据状态，不应覆盖已经确定的网页动作结果；
7. 每次截图使用中文或稳定英文日志字段，日志格式统一使用 f-string；
8. 截图失败、遮罩失败、上报失败分别记录原因，便于判断缺失发生在哪一段。

不建议直接在 `_execute_action` 中静默截图并丢弃上报结果，因为该方法没有足够的运行阶段和产物上下文，容易造成截图产生但无法关联。

## 8. 服务端 API 设计

### 8.1 阶段取证策略

沿用阶段保存接口，在阶段模型中增加 `evidencePolicy`，请求体继续使用 Pydantic 模型，不使用裸 `dict` 作为公开契约：

```text
POST /configuration-tasks/versions/{versionId}/stages
GET  /configuration-tasks/versions/{versionId}/stages
GET  /configuration-tasks/runs/{taskRunId}/stages
```

发布时返回明确校验错误，例如：

```text
阶段「验证结果」要求 after_screenshot，但版本中没有可匹配的显式取证步骤：store-config-after-save
```

### 8.2 产物查询和消费

现有产物列表接口保留：

```text
GET /configuration-tasks/runs/{taskRunId}/artifacts
```

新增专用消费接口：

```text
GET /configuration-tasks/runs/{taskRunId}/artifacts/{artifactId}/preview
GET /configuration-tasks/runs/{taskRunId}/artifacts/{artifactId}/download
```

接口语义是“服务端鉴权 + 在线 Agent 取回”，不是服务端文件下载：

1. 服务端每次访问重新校验用户、任务权限、运行归属、产物状态和 Agent 归属；
2. 服务端根据 `resource_id` 找到 Agent 编码和受控 `object_key`，生成一次性取回请求；
3. Agent 在线时校验请求签名、资源归属、相对路径边界和文件 SHA-256，再通过 WebSocket/专用安全通道分片流式返回；
4. 服务端可以把数据流中继到请求方，但不落盘、不写缓存、不把正文写入数据库；
5. 预览只允许白名单 MIME 类型，并使用流式响应；下载使用短期授权和内容处置头；
6. 下载和预览写入审计日志，日志只记录资源 ID、Agent、结果、大小、校验和，不记录正文；
7. Agent 离线、文件不存在或校验不一致时返回明确错误状态，不返回空文件，也不能把元数据状态伪装成 `READY_FOR_DOWNLOAD`。

建议把资源可用状态与资源生命周期分开：

- 生命周期：`PENDING`、`READY`、`EXPIRED`、`DELETED`；
- 当前取回状态：`ONLINE`、`AGENT_OFFLINE`、`NOT_FOUND`、`CHECKSUM_MISMATCH`、`ACCESS_DENIED`。

`resourceId` 不能直接当下载凭证，Agent 绝对路径不出现在响应中。

### 8.3 证据包接口

建议新增：

```text
POST /configuration-tasks/runs/{taskRunId}/evidence-packages
GET  /configuration-tasks/runs/{taskRunId}/evidence-packages
GET  /configuration-tasks/evidence-packages/{packageId}
GET  /configuration-tasks/evidence-packages/{packageId}/download
```

生成请求建议：

```json
{
  "includeFailureArtifacts": true,
  "includeExecutionLog": true,
  "includeReport": true,
  "evidenceStatusPolicy": "ALLOW_INCOMPLETE"
}
```

请求体和响应必须使用 Pydantic 模型；`packageId`、`resourceId` 等 BIGINT 对外统一序列化为字符串。生成流程为：

```text
用户请求生成
  -> 服务端鉴权并冻结纳入产物的元数据清单
  -> 服务端向运行所属 Agent 下发 build_evidence_package
  -> Agent 在受控临时目录读取本地证据并生成 manifest/summary/report/ZIP
  -> Agent 计算 ZIP 大小、SHA-256 和受控 objectKey
  -> Agent 回传 package 状态和 resource 元数据
  -> 服务端登记 task_evidence_package，不保存 ZIP 正文
```

生成请求必须明确目标 Agent。Agent 离线时可以创建 `REQUESTED` 或返回 `AGENT_OFFLINE`，不能由服务端自行假定能够读取文件；如果产品需要离线组包，只能由用户在拥有权限的本地工具中使用已取回文件生成，不属于服务端组包能力。

证据包生成必须有明确策略：

- `ALLOW_COMPLETE_ONLY`：仅完整证据允许 Agent 生成并交付；
- `ALLOW_INCOMPLETE`：允许导出，但包内和页面显著标记缺失；
- `DIAGNOSTIC_ONLY`：只导出失败诊断，不作为验收包。

`GET .../download` 只触发服务端鉴权和 Agent 在线流式取回。下载完成后由请求方保存到本地；服务端不保存下载副本。

## 9. 证据包格式

### 9.1 推荐第一期使用 ZIP

第一期使用 ZIP 作为原始证据交付格式，但 ZIP 由 Agent 在受控本地临时目录生成，服务端只登记其资源元数据和 Agent-local 定位信息。用户下载时由在线 Agent 流式返回到请求方本地；服务端不保存 ZIP、HTML、DOC 或截图正文。

内部结构建议如下：

```text
configuration-task-evidence-{taskRunId}-v{packageVersion}/
├── manifest.json
├── summary.html
├── report.doc
├── stages/
│   ├── 01-query/
│   │   └── 001-store-config-checkpoint.png
│   ├── 02-write/
│   │   └── 002-store-config-before.png
│   └── 03-verify/
│       └── 003-store-config-after.png
├── failures/
│   └── step-005-failure.png
└── logs/
    └── execution.json
```

大图作为 Agent 本地受控目录中的独立文件保留，`summary.html` 和 `report.doc` 使用相对路径或包内文件名引用，不把图片 Base64 复制到运行 JSON。服务端保存的 `manifest_sha256`、`file_sha256` 和 `object_key` 只用于索引、校验和取回，不代表服务端存在对应文件。

### 9.2 manifest 内容

`manifest.json` 至少包含：

```json
{
  "schemaVersion": 1,
  "packageId": "900000000000010",
  "taskRunId": "900000000000001",
  "taskName": "门店配置任务",
  "versionNo": 3,
  "agentCode": "agent-gray04",
  "operator": "operator",
  "store": "门店标识",
  "environment": "生产环境",
  "businessStatus": "SUCCESS",
  "evidenceStatus": "COMPLETE",
  "generatedAt": "2026-09-20T10:20:30Z",
  "items": [
    {
      "artifactId": "900000000000002",
      "stageKey": "verify",
      "stepId": "capture-after-save",
      "stepIndex": 11,
      "evidenceType": "after_screenshot",
      "evidenceKey": "store-config-after-save",
      "relativePath": "stages/03-verify/003-store-config-after.png",
      "resourceId": "900000000000003",
      "fileSize": 248912,
      "sha256": "...",
      "capturedAt": "2026-09-20T10:20:20Z",
      "required": true,
      "status": "READY"
    }
  ]
}
```

manifest 示例中的每个 `items[]` 元素还应包含：

```json
{
  "agentCode": "agent-gray04",
  "objectKey": "artifacts/run-123/evidence/02-query-004-before.png",
  "availabilityStatus": "ONLINE"
}
```

`relativePath` 只表示 ZIP 内部路径；`objectKey` 只表示 Agent-local 受控定位键，二者都不是服务端文件路径。

manifest 中不能保存：

- 密码；
- Cookie；
- Token；
- 完整 storageState；
- Agent 绝对路径；
- 未脱敏的敏感页面 URL 查询参数。

### 9.3 排序规则

证据包内统一按以下顺序排序：

1. 阶段顺序；
2. 步骤顺序；
3. 证据类型优先级：`before`、`checkpoint`、`after`、`failure`；
4. 同一步骤的 `sequenceNo`；
5. 产物创建时间。

文件名不能作为唯一排序依据，manifest 必须记录机器可读的排序字段。

## 10. 运行状态和证据状态

业务执行和证据完整性分开保存：

```text
业务状态：PENDING / RUNNING / SUCCESS / FAILED / CANCELLED
证据状态：NOT_REQUIRED / PENDING / COMPLETE / INCOMPLETE / FAILED
```

### 10.1 组合展示

| 业务状态 | 证据状态 | 用户看到的含义 |
|---|---|---|
| `SUCCESS` | `COMPLETE` | 业务执行成功，证据完整 |
| `SUCCESS` | `INCOMPLETE` | 业务执行成功，但验收证据不完整 |
| `SUCCESS` | `NOT_REQUIRED` | 业务执行成功，本次不要求业务证据 |
| `FAILED` | `COMPLETE` | 业务失败，但要求的证据已完整采集 |
| `FAILED` | `INCOMPLETE` | 业务失败且诊断或要求证据不完整 |
| `CANCELLED` | `INCOMPLETE` | 运行取消，不能作为完整验收结果 |

运行详情必须同时显示两个状态，不允许只显示一个“成功”标签造成误解。

## 11. 前端实施方案

### 11.1 动作类型和步骤编辑

修改位置：

- `web/src/components/hrm/case/webcase/utils/shared.js`
- `web/src/components/hrm/case/webcase/domain/stepDomain.js`
- `web/src/components/hrm/case/webcase/components/StepDetail.vue`
- `web/src/views/hrm/configuration-task/components/VersionStepTable.vue`

实施内容：

1. `actionOptions` 增加“截图 / 采集证据”；
2. `stepNeedsTarget('capture_screenshot')` 返回 `false`；
3. `normalizeStepParams` 增加截图参数归一化和默认值；
4. `summarizeStepParams` 显示证据类型、证据键和必选状态；
5. `StepDetail` 针对截图动作显示专属表单；
6. 隐藏截图动作不需要的定位器和断言区域；
7. 保留 JSON 模式兼容，切换视觉模式时不能丢失未知字段；
8. 步骤表格增加“取证”标签和证据类型摘要；
9. 新增、删除、移动步骤时同步阶段映射或提示用户复核。

### 11.2 阶段编辑器

修改位置：

- `web/src/views/hrm/configuration-task/components/StageEditor.vue`
- 以及阶段相关 API 和模型文件

新增“取证策略”区块：

- 是否要求业务证据；
- 取证模式：不要求、可选、必需、Before + After；
- 必需证据类型；
- 必需证据键；
- 缺失处理：提示、阻断验收；
- 遮罩策略；
- 保留天数。

界面应显示阶段内可匹配的截图步骤，并在保存前给出校验提示：

```text
当前阶段要求 after_screenshot，但阶段内没有启用的 after_screenshot 步骤。
```

### 11.3 运行详情

修改位置：

- `web/src/views/hrm/configuration-task/components/RunDetailDrawer.vue`
- `web/src/api/hrm/configuration_task.js`

产物列表从以下形式：

```text
类型 | 文件名 | 资源ID | 大小
```

升级为：

```text
阶段 | 步骤 | 证据类型 | 预览 | 文件名 | SHA-256 | 状态 | 操作
```

新增能力：

- 图片缩略图和原图预览（Agent 在线时通过流式取回）；
- 单个产物下载（Agent 在线时通过流式取回）；
- 按阶段、类型筛选；
- 显示必需证据缺失原因和当前取回状态；
- 生成证据包（向 Agent 下发组包指令）；
- 下载证据包（Agent 在线时流式返回到请求方本地）；
- 展示业务状态和证据状态；
- 区分验收证据与失败诊断产物。

## 12. 存储、权限和安全

### 12.1 存储策略

当前产品边界下，所有运行文件均只保存在 Agent 受控目录：

1. **诊断截图、验收截图、执行日志、报告和证据包**都由 Agent 在受控 `storage_root` 下创建和管理；
2. 服务端只保存 `resource_id`、`agent_code`、`provider_type=agent_local`、受控 `object_key`/manifest locator、文件名、MIME、大小、SHA-256、版本、业务关联、生命周期和最近取回状态；
3. 服务端不保存文件正文，不把 Agent 绝对路径作为业务契约，不把 Base64 写入数据库、报告或普通日志；
4. 用户预览、下载或生成证据包时，服务端负责权限校验、一次性取回授权和审计，在线 Agent 负责读取本地文件并通过安全通道流式返回；
5. Agent 离线时，服务端只能展示元数据、保留期限和“暂不可取回”状态，不能提供空文件、伪造下载成功或把资源标记为可用；
6. 报告和证据包必须由 Agent 侧或请求方本地生成。`report_service.py` 如果保留，只能负责报告元数据、模板或组包指令编排，不得继续把 `.doc`、ZIP 或截图写入服务端本地目录；
7. Agent 本地文件不存在、过期、校验不一致或清理后，服务端更新取回状态并保留脱敏错误摘要，业务执行状态不因此被改写。

首期不新增服务端文件或对象存储 Provider。未来如果确实增加服务端或对象存储，必须作为独立 Provider、独立迁移和明确的产品决策上线，不能在本方案中默认为已具备。

### 12.2 权限

需要区分：

- 查看运行记录；
- 预览截图；
- 下载单张截图；
- 生成证据包；
- 下载证据包；
- 删除或提前过期证据。

`resourceId` 不是授权凭证。每次访问都必须重新校验用户、任务范围、运行归属和产物权限，并记录审计日志。

### 12.3 脱敏

第一期至少支持：

- 密码输入框默认遮罩；
- 用户配置 `maskSelectors`；
- 截图元数据标记 `maskApplied`；
- 遮罩失败时按策略拒绝交付或标记证据不完整；
- 不在日志、manifest 或报告中输出截图 Base64；
- 页面 URL 脱敏后再入库。

遮罩失败不能静默当作成功截图。

### 12.4 保留和删除

证据资源必须遵循引用保护：

- 有运行、报告或证据包引用时，服务端不能直接删除资源索引；应先标记 `EXPIRED`，再向 Agent 下发清理通知；
- Agent 收到清理通知后，在本地受控目录执行删除并回传结果；服务端仅更新索引状态和审计信息；
- 证据包在保留期内不可覆盖；
- 删除和提前过期必须记录操作人、原因和时间；
- 失败诊断截图与正式验收证据可以使用不同保留周期。

## 13. 服务边界和代码拆分

遵循当前项目的职责边界：

### 13.1 Controller

只负责：

- 路由；
- Pydantic 请求/响应模型；
- 权限；
- 异步接口中的线程池包装；
- 响应转换。

不在 controller 中生成 ZIP、不解析截图、不计算业务证据完整性。

### 13.2 Service

建议拆分或新增：

- `evidence_policy_service.py`：阶段策略校验、证据完整性计算；
- `artifact_service.py`：产物元数据登记、幂等和查询，不保存验收文件正文；
- `evidence_package_service.py`：生成 Agent 组包指令、冻结 manifest 元数据、登记包版本和状态；不在服务端写 ZIP、HTML、DOC 或截图；
- `artifact_access_service.py`：预览、下载授权、Agent 在线取回协调、流式中继和审计；不落盘、不缓存文件正文；
- `task_run_service.py`：只负责编排运行计划和调用下层服务。

不要继续把证据包生成、资源取回、阶段完整性规则全部追加到一个主 service 文件。Agent 侧应有独立的资源访问、临时组包和 SHA-256 校验实现，不能让服务端通过任意本地路径代读 Agent 文件。

### 13.3 DAO 和 Util

- DAO 只负责表查询和元数据持久化；
- `evidence_manifest_util.py` 只做纯字段整理、排序和 JSON 生成；
- Agent 侧 ZIP/报告写入、服务端到 Agent 的流式传输等有副作用逻辑放在各自专用 service；
- 服务端不得通过通用文件系统 API 读取 Agent 绝对路径；
- 不新增只做 re-export 的兼容 shim。

### 13.4 定时任务

定时任务只负责：

- 查询到期的 Agent-local 资源索引和证据包元数据；
- 创建数据库会话；
- 调用清理 service，向对应 Agent 下发删除/过期通知或标记资源不可取回；
- 输出关键日志。

不能在调度函数中直接实现文件扫描、证据包拼装、Agent 目录访问和删除策略。Agent 负责在本地受控目录执行实际清理，服务端只更新索引和审计状态。

## 14. 实施阶段和交付物

### 阶段 0：契约和文档基线

交付：

- 更新 wiki 中配置任务实际实现状态；
- 新增用户可见的取证和证据包说明；
- 修正定时能力、运行列表和统一凭证旧口径冲突；
- 确认商家、门店、环境的结构化来源；
- 确认保留期限、角色权限和脱敏默认值。

验收：产品、后端、Agent、前端对 `capture_screenshot`、阶段策略和证据包状态定义达成一致。

### 阶段 1：显式取证步骤最小闭环

交付：

- 前端可新增和编辑 `capture_screenshot`；
- Agent 可在准确步骤采集截图；
- 服务端可登记带 `stepId/evidenceKey` 的产物；
- 失败截图继续工作；
- 运行详情至少能看到证据类型和步骤关联。

验收：一个版本可以完成“查询 → 断言 → 截图”，截图不影响普通运行结果，重复事件幂等。

### 阶段 2：阶段级策略和完整性

交付：

- 阶段配置支持 `NONE/OPTIONAL/REQUIRED/BEFORE_AFTER`；
- 发布校验阶段策略与显式步骤；
- 运行阶段计算 `evidenceStatus` 和缺失项；
- 运行详情显示业务状态和证据状态。

验收：缺失必需 After 时显示“业务可能成功，但验收证据不完整”，不能误标为验收通过。

### 阶段 3：预览、下载和 Agent 在线取回

交付：

- Agent-local 资源访问协议和安全相对定位键；
- 单张截图预览和下载的服务端鉴权、Agent 流式取回和审计；
- 资源取回状态、校验失败和 Agent 离线提示；
- Agent-local 资源过期、删除通知和引用保护；
- 报告在 Agent 侧或请求方本地生成，服务端只登记报告元数据。

验收：用户可以在 Agent 在线时从运行详情打开并下载截图；Agent 离线时可以查看元数据，但页面明确显示“暂不可取回”，不返回空文件或虚假成功。

### 阶段 4：Agent 侧证据包

交付：

- `task_evidence_package` 元数据模型；
- Agent 侧 ZIP、manifest、summary、报告和原始截图组包；
- 包版本、Agent-local `object_key`、文件大小和 SHA-256；
- 生成、查询、在线取回 API；
- 完整/不完整/诊断包策略；
- 请求方本地保存下载文件的流程。

验收：其他团队拿到请求方本地下载的 ZIP 后，只根据 manifest 就能判断运行、阶段、步骤、截图类型和完整性；服务端数据库中不出现 ZIP 或截图正文。

### 阶段 5：安全和运营增强

交付：

- 默认遮罩和遮罩策略管理；
- 下载/预览审计报表；
- 保留期和清理任务；
- 大文件分片/断点传输；
- PDF/DOCX 展示版报告；
- 飞书通知附证据包授权链接。

## 15. 测试方案

### 15.1 后端单元测试

至少覆盖：

1. 截图步骤参数默认值和非法值校验；
2. 阶段策略 `NONE/OPTIONAL/REQUIRED/BEFORE_AFTER`；
3. required 类型和 evidenceKey 匹配；
4. 阶段证据完整性计算；
5. 重复截图事件幂等；
6. 不属于运行版本的 `stepId` 被拒绝；
7. 不属于阶段的 `stageKey` 被拒绝；
8. 资源大小、MIME、SHA-256、文件名、Provider 和受控 `objectKey` 校验；
9. 业务成功但证据不完整时两种状态不互相覆盖；
10. manifest 排序、字段脱敏和哈希；
11. 有引用资源时，服务端不能直接删除资源索引；过期后由 Agent 执行实际清理并回传结果；
12. 下载权限和审计。

### 15.2 Agent 测试

至少覆盖：

1. `capture_screenshot` 不需要定位器；
2. `fullPage` 参数生效；
3. `waitMs` 不超过步骤总超时；
4. 遮罩成功后截图；
5. 截图文件先写入 Agent 受控目录，再上报 `objectKey`、大小和 SHA-256；
6. 截图失败返回步骤错误；
7. 上报失败不把 Base64 写入步骤结果或服务端持久化字段；
8. 原有失败截图行为不回归；
9. `continueOnFailure` 与 required 证据策略分离；
10. 同一截图重复上报幂等；
11. Agent 离线、文件丢失、校验失败时取回状态正确；
12. 页面关闭、取消和超时时正确清理。

### 15.3 前端测试和构建

至少覆盖：

- 动作选项显示和步骤归一化；
- JSON/可视化模式切换不丢字段；
- 阶段策略表单与步骤匹配提示；
- 步骤移动后的阶段映射提示；
- 运行详情证据状态、预览、下载和证据包按钮；
- `npm run build:prod`。

### 15.4 联调验收场景

至少准备四个场景：

1. 只读查询 + checkpoint；
2. 修改前 Before + 修改后 After；
3. 必需 After 缺失但业务执行成功；
4. 网页动作失败并产生 failure_screenshot。

## 16. 验收标准

功能达到以下条件才可称为“支持自定义取证”：

- 用户可以在步骤编排中看到并插入显式截图步骤；
- 用户可以在阶段编排中设置是否需要取证及需要哪些证据类型；
- 阶段策略不会隐式在不明确的页面状态自动截图；
- 显式截图有稳定的步骤、证据键、阶段和运行关联；
- 失败截图和成功业务证据分类清晰；
- 业务执行状态与证据完整状态独立；
- 运行详情可在 Agent 在线时预览和下载截图，Agent 离线时显示暂不可取回；
- 证据包包含 manifest、原始截图、校验和和运行摘要，并由 Agent 侧生成、在请求方本地保存；
- 证据包不泄露认证凭证、密码、Cookie、Token 或 Agent 绝对路径；
- 服务端只保存证据索引和元数据，不保存截图、报告或 ZIP 正文；
- 资源取回、过期、删除和下载都有权限和审计；
- 修改类流程可以证明 Before、执行和 After 验证链路，而不是只证明点击了保存按钮。

## 17. 风险与处理建议

| 风险 | 影响 | 处理 |
|---|---|---|
| 继续使用 stepIndex 作为唯一关联 | 插入截图后阶段错位 | 引入 stepId/evidenceKey，索引只作兼容 |
| Agent 离线或本地文件过期 | 证据暂时无法取回，不能满足即时交付 | 页面明确显示不可取回；保留 Agent 在线策略、过期提醒和本地备份流程，不伪造下载成功 |
| 服务端只保存索引 | 服务端无法独立恢复文件 | 接受当前产品边界；Agent 受控目录负责权威文件，请求方在在线时下载到本地 |
| 截图包含敏感数据 | 数据泄露 | 默认遮罩、选择器遮罩、权限、审计、保留期 |
| 截图上报失败覆盖业务状态 | 运行结果被误判 | 分离 businessStatus/evidenceStatus |
| 阶段策略过强阻断生产 | 流程无法恢复 | 第一期开启 WARN/BLOCK_ACCEPTANCE，暂不默认 BLOCK_RUN |
| 每一步都截图导致资源膨胀 | Agent 磁盘、网络和查询压力 | 只允许显式步骤，限制阶段和运行截图数量 |
| 报告只列资源 ID | 其他团队无法直接验收 | Agent 侧 ZIP + manifest + 原始截图 + 摘要，下载到请求方本地 |
| 方案字段与现有 wiki 冲突 | 后续会话误判实现状态 | 代码落地后同步更新 wiki 和用户说明 |

## 18. 待确认事项与推荐默认值

以下事项不阻塞方案落地，若没有新的业务约束，按推荐值执行：

| 事项 | 推荐默认值 |
|---|---|
| 成功步骤是否默认截图 | 否 |
| 显式截图动作 | `capture_screenshot` |
| 默认证据类型 | `checkpoint_screenshot` |
| 修改类流程 | Before + After |
| 阶段缺证处理 | `BLOCK_ACCEPTANCE`，不回滚业务 |
| 失败截图 | 默认保留，单独归类为诊断产物 |
| 证据包格式 | Agent 侧 ZIP + manifest + HTML/Word 摘要，下载到请求方本地 |
| 存储位置 | Agent 受控目录；服务端仅保存索引和元数据 |
| 文件取回 | Agent 在线时由服务端鉴权后流式返回；离线时显示暂不可取回 |
| 首期截图范围 | viewport/fullPage，暂不做任意元素裁剪 |
| 首期遮罩 | 密码字段默认遮罩 + 配置选择器 |
| 证据包生成 | 服务端下发组包指令，Agent 侧生成；也可由请求方使用已取回文件本地生成 |
| 资源 ID 对外展示 | 允许展示元数据，但不能作为下载授权 |
| 阶段策略默认 | READ=OPTIONAL，VERIFY=REQUIRED，WRITE 前后按业务配置 |

## 19. 实施时需要同步维护的文件

### 方案和知识库

- 本文档：`wiki/features/configuration-task-evidence-collection-plan.md`；
- `wiki/index.md`；
- `wiki/entities/services/configuration-task-domain.md`；
- `wiki/entities/data-models/configuration-task-resource-models.md`；
- `wiki/flows/configuration-task-web-reuse.md`；
- `wiki/flows/configuration-task-file-storage.md`；
- `wiki/contracts/configuration-task-file-protocol.md`。

### 用户说明

- `web/public/docs/configuration-task.md`；
- `web/public/docs/configuration-task-resource.md`；
- `web/public/docs/updates/history.md`，以及对应日期的独立更新记录。

### 代码范围

- 后端：配置任务 Pydantic 模型、阶段服务、运行服务、产物服务、证据策略服务、证据包服务、资源访问服务、controller 和 DAO；
- Agent：Web 步骤动作分发、截图采集、遮罩、artifact 事件；
- 前端：动作选项、步骤域、步骤详情、阶段编辑器、运行详情、API 封装；
- 数据库：阶段策略、产物证据字段、证据包、资源引用和审计迁移。

## 20. 方案落地检查清单

### 契约

- [ ] 已确定“验收证据”与“认证凭证”名称边界；
- [ ] 已确定 `capture_screenshot` 和证据类型枚举；
- [ ] 已确定阶段策略和缺证处理策略；
- [ ] 已确定证据包保留期限和权限；
- [ ] 已确定商家、门店、环境的结构化来源。

### 编排

- [ ] 步骤支持显式取证；
- [ ] 阶段支持取证策略；
- [ ] Before/After 步骤和阶段匹配校验存在；
- [ ] 步骤移动不会静默破坏阶段映射；
- [ ] 发布时校验证据策略和步骤。

### 执行

- [ ] Agent 可以准确执行截图步骤；
- [ ] 截图事件带运行、阶段、步骤和证据键；
- [ ] 失败截图仍正常产生；
- [ ] 截图失败不会覆盖业务状态；
- [ ] 日志记录了关键决策和不执行原因。

### 存储和交付

- [ ] 证据资源的 Agent-local 受控定位、文件元数据和生命周期已登记；
- [ ] Agent 在线时预览、下载和流式取回权限已实现；
- [ ] Agent 离线、文件不存在和校验失败时能显示明确不可取回状态；
- [ ] 证据包包含 manifest 和 SHA-256，并由 Agent 侧生成；
- [ ] 证据包版本不可覆盖；
- [ ] 引用保护、Agent 清理通知和过期审计已实现。

### 文档和验证

- [ ] wiki 实现状态已同步；
- [ ] 用户说明包含入口、参数、示例、注意事项和常见问题；
- [ ] 更新记录已补充；
- [ ] 后端测试通过；
- [ ] Agent 联调通过；
- [ ] 前端构建通过；
- [ ] 四类验收场景均通过。
