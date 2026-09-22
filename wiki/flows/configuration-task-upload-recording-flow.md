---
title: 配置任务文件上传录制与回放流程
type: flow
source_type: design
canonical: true
knowledge_state: current
confidence: high
freshness: 2026-09-22
created: 2026-09-22
updated: 2026-09-22
related_files:
  - client_new/services/web_test_service.py
  - server/modules/configuration_task/service/task_run_service.py
  - server/modules/configuration_task/controller/resource_controller.py
  - server/modules/configuration_task/service/resource_transfer_service.py
  - web/src/components/hrm/case/webcase/components/WebStepEditor.vue
  - web/src/components/hrm/case/webcase/domain/stepDomain.js
---

# 配置任务文件上传录制与回放流程

本页定义门店配置任务里文件上传场景的录制与回放方案。结论：录制**不拦截**浏览器原生文件选择弹窗（人工选文件、页面流程自然继续），录制脚本通过 `change` 事件识别 `<input type=file>`，记录一条 `upload_file` 占位步骤（文件名占位、定位器直接指向 input）；回放**必须拦截**弹窗（执行器注册空 `filechooser` 监听抑制原生弹窗），再由 `upload_file` 步骤通过 `set_input_files` 自动赋值，零人工介入。文件来源支持"资源绑定"与"Agent 受控目录文件"两种模式，资源由资源管理页面手动维护并区分 Agent。

## 背景与关键事实

1. 录制链路是 Playwright 有头浏览器 + 注入 `RECORDER_SCRIPT`（`client_new/services/web_test_service.py`）监听 DOM 事件回传。原生 Windows 文件选择框是操作系统窗口，DOM 脚本与 CDP 都无法感知或控制其内容。
2. Playwright 只在页面存在 `filechooser` 事件监听者时才开启 CDP `Page.setInterceptFileChooserDialog` 拦截（驱动 coreBundle.js 已确认）。没有监听者时弹窗真实弹出——录制正利用这一点让人工选文件。
3. 浏览器安全机制（fakepath）决定 JS 层只能拿到 `C:\fakepath\文件名`，拿不到真实路径。因此"录制时人工选的那个文件"不会自动归档为资源；正式文件在编辑阶段通过资源绑定或 Agent 目录文件指定。
4. 回放 `set_input_files` 直接对 input 赋值，不弹任何对话框，且不要求元素可见（隐藏 file input 也可用）。
5. 旧实现缺陷：`change` 监听未区分 file 类型，会把文件选择记录成"填写输入框"步骤（值为 fakepath 假路径），回放必然失败（Playwright 禁止 fill file input）。本方案顺带根除。

## 录制与回放行为对照

| 环节 | 弹窗行为 | 文件来源 | 说明 |
| --- | --- | --- | --- |
| 录制 | 浏览器原生弹窗，人工选 | 人工在弹窗中选（仅作样本让页面流程继续） | 不注册 filechooser 监听 |
| 回放 | 无弹窗（空 filechooser 监听抑制） | 资源绑定或 Agent 受控目录，`set_input_files` 赋值 | 步骤序列"点击上传按钮 + upload_file"中的 click 会触发 chooser，被监听吞掉 |

## 方案切片

1. **录制占位步骤（client_new，RECORDER_SCRIPT）**：`change` 监听识别 `type=file`，emit `upload_file` 步骤——`stepName` 为"上传文件 xxx"（多文件拼接文件名），`params.fileKey` 自动生成 `file_<序号>` 占位、`multiple`、`fileNames`（仅展示），`resourceIds` 留空；`targetSnapshot` 用 `buildSnapshot(input, { preferStableLocators: true })`，定位器即 input 本身，编辑时只换文件不动定位。同一事件不再落"填写输入框"分支。
2. **回放抑制弹窗（client_new，执行器）**：执行会话创建/复用页面时调用 `_suppress_replay_file_chooser(page)` 注册空监听；录制会话（`_start_recording`）不得调用。
3. **编辑器上传配置 UI（web）**：上传步骤行支持 fileKey 编辑 + 文件来源双模式——「资源绑定」下拉（`GET /configuration_task/resource?agentCode=<任务默认Agent>&status=READY`，写入 `params.resourceIds`）与「Agent 目录文件」下拉（受控相对路径，写入 `params.agentPath`）；未绑定时展示录制样本 `fileNames` 占位。
4. **回放解析扩展（client_new）**：`_resolve_upload_file_paths` 优先级为 fileKey 运行绑定 → `params.resourceIds` → `params.agentPath`；agentPath 基于受控上传根目录校验（根内、拒绝 `..`/绝对路径/盘符/符号链接、必须存在且为文件），错误消息不含绝对路径。**文件名保真**：manifest 落盘文件名是 resourceId，执行器注入前经 `_stage_upload_files` 以 manifest 的 `original_file_name` 生成系统临时目录副本，注入后清理（清理失败交由系统回收），保证页面收到的 `File.name` 与登记资源一致；agentPath 模式天然保留真实文件名、不产生副本。
5. **Agent 受控目录 + 列表能力（client_new + server）**：Agent 约定受控上传根目录（独立于资源 manifest），提供受控列目录命令（仅相对路径/大小/修改时间，拒绝越级）；服务端在配置任务模块提供转发查询接口（校验 Agent 在线）。
6. **资源管理页面（web，服务端复用）**：列表（agentCode/状态/关键字筛选）、上传、删除、详情。上传走现有 `POST /configuration_task/resource/{id}/transfers`（begin）→ chunk（单块 512 KiB，Base64）→ commit 编排，服务端 `resource_transfer_service` 推送 Agent 落盘为 READY；文件实体只存 Agent `storage/resources/`，服务端仅登记元数据。资源记录带 `agent_code`，页面按 Agent 区分展示。

## 参数契约（upload_file 步骤 params）

```json
{
  "fileKey": "file_1",
  "resourceIds": ["res_01J..."],
  "agentPath": "inputs/price-tag.xlsx",
  "multiple": false,
  "fileNames": ["样本.xlsx"]
}
```

- `fileKey`：运行时输入绑定键（`runtimeOptions.resourceBindings[fileKey] -> resourceIds`，服务端 `task_run_service` 注入并校验资源 READY 且属于执行 Agent）。
- `resourceIds`：资源绑定的默认值（运行绑定缺省时兜底）。
- `agentPath`：Agent 受控上传根目录下的相对路径，只接受正斜杠相对路径；绕过资源 TTL/哈希/审计，文件存在性由使用方保证，属已知取舍。
- `multiple`：多文件开关；`fileNames`：录制样本文件名，仅展示占位，不参与回放。

## 边界与风险

- `window.showOpenFilePicker`（File System Access API）不走 CDP file chooser 拦截，弹窗仍会出现；拖拽上传不属于 file chooser，两者均不在本方案覆盖内。
- 极端动态 DOM 下 file input 无稳定属性时定位器候选可能不稳，回放按定位器权重链逐个尝试；这是"编辑不用改定位元素"承诺的例外情形。
- 回放抑制弹窗后，若用例缺少 upload_file 步骤，页面会停在等待选择状态，由步骤超时暴露。
- agentPath 模式文件被人为挪动/改名后回放失败，错误提示需友好且不含绝对路径。
- 客户端壳已由 PySide6 迁移为 pywebview（`client_new/pyproject.toml` 依赖确认）；本方案不依赖客户端 UI 能力。pywebview 内建 `create_file_dialog` 可弹系统文件选择框，若未来需要"Agent 端弹窗选文件"可直接使用，但当前方案不需要。

## 参见

- [配置任务文件协议](../contracts/configuration-task-file-protocol.md)
- [门店配置文件存储流程](configuration-task-file-storage.md)
- [Web 录制流程](ticket-recording-flow.md)
- [配置任务复用 Web 录制与执行](configuration-task-web-reuse.md)
