# 步骤编辑公共组件 WebStepEditor 统一（2026-09-21）

## 变更背景

门店配置的版本步骤编辑此前是独立实现（VersionStepTable），与 Web 测试管理的用例编辑存在明显体验差距：列表不能内联编辑、没有前插按钮、JSON 编辑是纯文本框、样式细节不一致，步骤详情弹窗"指纹"字段永远为空。本次把两者统一到同一公共组件。

## 主要变更

- **新增公共组件**（`web/src/components/hrm/case/webcase/`）：
  - `components/WebStepEditor.vue`：步骤编辑器（可视化表格 + 内联单元格编辑 + 前插/上移/下移/编辑/删除 + 证据列自动显隐 + 高级 JSON 双向同步 + 步骤详情弹窗挂载），支持 `serializeSteps`（JSON 预览格式注入）、`showFingerprint`（指纹字段显隐）与 `flush`（保存前应用 JSON）、`resetUi`（重置内部状态）；
  - `components/WebStepDetailDialog.vue`：步骤详情弹窗，采用用例编辑器原版样式，并合并了截图证据（`capture_screenshot`）与上传文件（`upload_file`）参数编辑区块；
  - `composables/useStepEditorTable.js`：表格与 JSON 同步的组合逻辑，基于既有 domain 层（stepDomain/locatorDomain/assertDomain/snapshotDomain）实现；
  - `styles/web-step-editor.scss`：步骤编辑样式（从用例侧 dialogs.scss 抽取，两侧类名保持一致）。
- **用例管理接入**：CaseEditorDialogs 改为薄壳（用例表单 + WebStepEditor），JSON Tab 仍展示提交格式（serializeSteps 注入 prepareStepForSubmit）；useCaseEditorManager 删除已平移的表格/详情函数（约 41 个）与相关状态，只保留用例表单、校验与提交序列化链路。
- **门店配置接入**：VersionDrawer 用 WebStepEditor 替换 VersionStepTable 与纯文本 JSON 框；详情弹窗不显示"指纹"字段（版本步骤不落指纹）；保存草稿前自动应用 JSON Tab 编辑。
- **删除死代码**：共享目录下从未被引用的 `CaseEditor.vue`（495 行）、`composables/useCaseEditor.js`（594 行）、空的 `index.js`，以及被 WebStepEditor 取代的 `StepDetail.vue` 与配置任务自己的 `VersionStepTable.vue`。

## 行为变化（用例管理侧）

- 步骤表格与详情弹窗改由公共组件渲染，交互与原来一致；新增：保存时停留在 JSON Tab 会先自动应用 JSON（原来只在手动点击"应用"或保存时校验）。
- JSON Tab 文本仍为提交格式（prepareStepForSubmit 后），该行为未变。

## 步骤区域交互优化（同日补充）

针对版本编辑弹窗可视化步骤区域的四项优化（两侧编辑器同步生效）：

1. **单一竖向滚动条**：版本编辑弹窗的滚动统一收敛到弹窗 body（`max-height: calc(100vh - 180px)`，footer 固定在外），表格不再内部限高滚动，消除双滚动条叠加；滚动可达全部内容（输入绑定、版本变量等底部区域完整可见）。
2. **移除"编辑当前步骤"按钮**：行内"编辑"按钮已覆盖该能力，工具栏只保留"新增步骤"（用例管理与门店配置两侧统一移除）。
3. **表格内容单行省略**：步骤名称/定位信息/输入参数列禁用换行，超出列宽显示省略号，悬浮显示完整内容 tooltip；完整编辑仍在详情弹窗中进行。样式类 `step-cell-text` 由多行换行改为单行省略。
4. **表格限高参数化**：新增 `tableMaxHeight` 属性（默认 560，保持用例管理原行为）；门店配置传空值改为跟随弹窗 body 滚动。

## 回归修复（同日补充）

统一上线后浏览器实测发现并修复两个问题：

1. **步骤表格从含定位快照的步骤起渲染中断**（表现为列缺失、弹窗叠加、控制台 `null (reading 'emitsOptions')`）：公共组件引用的 domain 函数 `describeStepTarget` 内部调用了不存在的 `describeLocator`（历史拆分遗留）。已在 `locatorDomain.js` 补齐该函数并由 `stepDomain.js` 导入；同时删除 `stepDomain.js` 中引用未定义符号的死导出。
2. **Web 测试管理页面空白**：`index.vue` 给录制管理器的依赖注入引用了三个已从用例编辑器解构中移除的函数。已改为统一从 domain 层导入（`getActionLabel` 补导出）。

若遇到页面渲染空白或 404，先确认只运行了一个前端 dev server 实例并整页刷新；多个实例并存或热更新残留会导致类似假象。

## 弹窗层级修复（同日补充）

版本管理抽屉内的"编辑版本"与"阶段切分"弹窗此前嵌在抽屉 DOM 内，受抽屉 transform 祖先影响，弹窗与遮罩被限制在抽屉区域而非覆盖整个窗口。已为两个弹窗添加 `append-to-body`，挂载到 body 后全窗口居中覆盖；抽屉内的步骤详情弹窗此前已是 append-to-body，行为一致。任务页直开的定时/录制转模板/运行配置弹窗不受影响。

## 验证

- `npm run build:prod` 构建通过。
- 被删文件在全仓库已无引用（grep 校验）。
- 建议回归：用例管理新增/编辑/JSON 应用/保存；门店配置版本草稿编辑、阶段切分、发布；录制转模板后的版本步骤展示。

## 遗留说明

- `views/hrm/webcase/styles/dialogs.scss` 中的同名样式类保留（录制/运行等对话框仍在引用），与 `web-step-editor.scss` 需同步维护。
- 版本步骤"指纹"按设计不在界面显示；如未来需要指纹用于元素库匹配，需在版本保存链路补服务端计算。
