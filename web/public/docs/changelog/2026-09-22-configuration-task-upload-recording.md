# 2026-09-22 配置任务文件上传录制与回放

## 变更主题

文件上传场景的录制与回放闭环：录制占位、回放自动注入、编辑双模式文件来源、资源管理页面。

## 追加：上传文件名保真（同日修复）

端到端测试发现并修复：资源模式回放时页面收到的 `File.name` 曾是 resourceId（manifest 落盘无原始文件名），被测系统按文件名/扩展名解析会失败。现执行器注入前以 manifest 的 `original_file_name` 在系统临时目录生成命名副本，注入后清理；`agentPath` 模式天然保留真实文件名、不产生副本。dev 端到端复验：资源模式运行 SUCCESS，页面断言"收到文件 price-tag.xlsx 大小 409613"通过。

同日顺带修复三个接口层 bug：`agent_upload_file_vo` 缺 `@as_query` 装饰器（后端启动失败）；`ResourceQueryModel.keyword` 与 `AgentUploadFileQueryModel.prefix` 参数未传时 None 未归一（列表接口 500）。

## 具体变化

1. **录制（Agent 端）**：录制不拦截浏览器原生文件选择弹窗，人工选文件后页面流程照常继续；`change` 事件识别 `<input type=file>`，生成「上传文件」占位步骤（文件名占位、`fileKey` 自动生成、定位器直接指向文件输入框），并根除了旧实现把文件选择误记成"填写输入框"（fakepath 假路径）导致回放必失败的问题。
2. **回放（Agent 端）**：执行会话统一注册空 `filechooser` 监听抑制原生文件选择弹窗；`upload_file` 步骤通过 `set_input_files` 自动注入文件，零人工介入。新增 `params.agentPath` 解析分支：支持 Agent 受控上传根目录（`storage/upload_inputs/`）内的受控相对路径，拒绝绝对路径、盘符与 `..` 逃逸。
3. **编辑器（Web）**：上传步骤单元格支持「资源绑定 / Agent 目录文件」双模式切换；资源下拉按任务执行 Agent 过滤 `READY` 资源，Agent 目录下拉支持一层目录导航；录制样本文件名做占位展示；步骤摘要同步展示文件来源。
4. **资源管理页面（Web）**：门店配置下新增「资源管理」菜单页（列表筛选/分片上传/详情/删除），上传走服务端既有 begin/chunk/commit 编推送到 Agent 落盘，文件实体只存 Agent、服务端只记账。
5. **服务端**：新增 `GET /configuration-tasks/agent-upload-files`（转发 Agent `file_list` 受控列目录命令）；`perms.py` 注册资源管理页面菜单。

## 相关文档

- 设计：wiki `flows/configuration-task-upload-recording-flow.md`
- 用户说明：`configuration-task.md`（上传文件步骤的文件来源 / 录制中的文件上传）、`configuration-task-resource.md`（资源管理页面 / Agent 受控上传目录）

## 已知边界

- `showOpenFilePicker`（File System Access API）与拖拽上传不在本方案覆盖内；
- 极端动态 DOM 下文件输入框无稳定属性时定位器可能需要人工微调；
- `agentPath` 模式的文件存在性由使用方保证，文件被挪动后运行失败（错误提示不含绝对路径）。
