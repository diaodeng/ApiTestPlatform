# 2026-09-02 工单详情展示组件统一复用，独立详情页改为纯只读

## 变更内容

第二阶段复用改造：把列表详情弹窗与独立工单详情页重复实现的展示块抽取为共享组件，并通过显式能力参数隔离写操作。

### 新增共享组件（`web/src/views/ticket/components/detail-shared/`）

- **`TicketSimilarPanel.vue`**：相似工单统一面板，包含"工单内容相似"与"处理案例相似"两个卡片区域，统一相似度展示、命中原因/冲突、向量状态提示（stale/missing 等提示不隐藏已召回结果）、"系统详情/飞书详情"跳转。"归入同一问题"写按钮由 `allowBindIssue` 参数控制（默认关闭），触发时通过 `bind-issue` 事件回传给宿主处理；跳转为只读行为始终保留。
- **`TicketDescriptionBlock.vue`**：描述与 AI 翻译统一展示块，原文/译文独立折叠。"翻译"写按钮由 `allowTranslate` 参数控制（默认关闭），权限仍由 `v-hasPermi="['ticket:ticket:edit']"` 控制，点击通过 `translate` 事件回传宿主。

### 共享 Tab 增加只读模式

- **`TicketDetailCollabTab`**：新增 `readOnly` 参数（默认 false），为 true 时隐藏"AI 追问编辑区"和"分析结果操作"（生成快照/生成知识库），仅保留分析记录查看。
- **`TicketDetailCommentsTab`**：新增 `readOnly` 参数（默认 false），为 true 时隐藏评论提交区，仅保留评论列表。

### 独立详情页（`TicketDetailView.vue`）改为纯只读

- 移除顶部"关联/更换问题实例"按钮及整个绑定弹窗（含问题搜索、归因类型、确认开关等表单逻辑）；
- 移除相似案例确认（`updateTicketSimilarityCaseStatus`）相关逻辑；
- 相似区域、描述/翻译区接入共享组件，均以只读模式传入；
- AI 分析、评论标签以 `read-only` 模式传入；
- 顶部仅保留"刷新"按钮。

### 列表详情弹窗（`TicketDetailWithList.vue`、`TicketDetailOverviewTab.vue`）能力不变

- 弹窗描述/翻译区替换为 `TicketDescriptionBlock`（`allow-translate: true`，翻译按钮与权限保持原样）；
- 概览 Tab 相似区域替换为 `TicketSimilarPanel`（`allow-bind-issue: true`，"归入同一问题"保留，事件回传后仍走原 `bindTicketIssueFromSimilar` 链路）；
- 顺带清理了弹窗壳中被替换掉的描述区样式和独立页重复实现的链接解析/跳转函数。

## 行为变化

- **独立详情页不再提供任何写操作入口**：此前有 `ticket:issue:bind` 权限的用户可以在独立页关联问题实例、确认相似案例，现在这些操作只保留在列表详情弹窗。后端接口与权限均未变化。
- **弹窗概览相似区域交互细节统一**：相似度展示统一为带一位小数的百分比（原为整数百分比）、向量状态提示样式与独立页一致；跳转按钮样式由链接改为按钮（行为一致）。
- **弹窗描述区视觉样式变化**：由"左标签右内容"网格布局改为上下标题+内容块布局，与独立详情页一致；展开/收起、翻译按钮行为不变。

## 涉及文件

- 新增：`web/src/views/ticket/components/detail-shared/TicketSimilarPanel.vue`、`TicketDescriptionBlock.vue`
- 修改：`TicketDetailView.vue`、`TicketDetailWithList.vue`、`detail-tabs/TicketDetailOverviewTab.vue`、`detail-tabs/TicketDetailCollabTab.vue`、`detail-tabs/TicketDetailCommentsTab.vue`

## 兼容性

- 后端接口、权限码均无改动；写操作全部仍在列表详情弹窗内保留。
- 共享 Tab 的 `readOnly` 默认 false，弹窗侧不传该参数时行为与之前完全一致。

## 注意事项

- 从独立详情页需要完成归因/追问/评论时，请到 **工单管理 → 工单列表** 打开对应工单的详情弹窗操作。
