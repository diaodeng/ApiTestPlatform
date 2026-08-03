# 工单编辑页 tagText 缺失修复

## 变更内容

1. 为工单编辑页补回 `tagText` 响应式变量。
2. 修复点击工单“编辑”按钮时 `reset()` 访问 `tagText.value` 报错的问题。
3. 避免编辑弹窗打开阶段触发 `Unhandled error during execution of native event handler`。

## 影响范围

- `web/src/views/ticket/index.vue`

## 说明

- 这次修复只补回缺失状态，不改变标签输入的保存与回填逻辑。
