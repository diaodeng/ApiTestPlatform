# 工单列表更多菜单权限告警修复

## 变更内容

1. 工单列表“更多”下拉中的删除项从 `v-hasPermi` 改为页面内权限布尔值控制。
2. 保持删除动作的权限判断不变，只是避免把指令挂在 `el-dropdown-item` 这类非元素根节点组件上。
3. 修复进入工单列表页时控制台持续出现的 Vue 警告：`Runtime directive used on component with non-element root node`。

## 影响范围

- `web/src/views/ticket/index.vue`

## 说明

- 这次修复只调整渲染方式，不改变删除权限和删除行为。
- 其他仍挂在普通元素上的 `v-hasPermi` 保持不动。
