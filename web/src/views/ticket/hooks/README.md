# 工单模块 Composables 提取计划

本目录用于从 `index.vue`（5,436 行）中按功能域提取 composable hooks。

## 目标

将 `index.vue` 的 `<script setup>`（~3,118 行）拆分为职责单一的 composable，每个不超过 400 行。

## 计划提取的 Composables

| 文件 | 职责 | 涉及函数数 | 优先级 |
|------|------|-----------|--------|
| `useOptions.js` | 下拉选项加载（项目/模块/Agent/Provider/分类等） | ~25 | 🔴 高 |
| `useTicketList.js` | 列表查询、分页、排序、筛选、列配置、自然语言搜索 | ~20 | 🔴 高 |
| `useTicketForm.js` | 新增/编辑表单、验证规则、提交、重置 | ~15 | 🔴 高 |
| `useTicketDetail.js` | 详情面板开关、数据加载、翻译、路由 | ~15 | 🔴 高 |
| `useLogPull.js` | 日志拉取记录、提交、重试、删除、自动刷新 | ~20 | 🟡 中 |
| `useLogViewer.js` | 日志查看器、搜索、上下文、异常提取 | ~15 | 🟡 中 |
| `useAiAnalysis.js` | AI分析发起、任务历史、重试、状态轮询 | ~15 | 🟡 中 |
| `useComments.js` | 评论加载、提交 | ~5 | 🟢 低 |
| `useTimeline.js` | 时间线、事件、RCA、快照 | ~10 | 🟢 低 |
| `useWorkflow.js` | 工作流配置、状态选项 | ~5 | 🟢 低 |

## 提取原则

1. 每个 composable 返回一个对象，包含该功能域所有的 ref/computed/function
2. 共享状态（如 `currentTicketId`）通过 composable 参数传递
3. 提取后 `index.vue` 的 `<script setup>` 变为组装层（~200 行）
4. 每次提取一个 composable，提取后立即验证 `npm run dev`

## 示例

```js
// hooks/useOptions.js
import { ref } from 'vue'
import { listTicketProjectOptions, ... } from '@/api/ticket/ticket'

export function useOptions() {
  const projectOptions = ref([])
  // ... more refs

  async function loadProjectOptions() {
    // ... implementation
  }

  return {
    projectOptions,
    loadProjectOptions,
    // ... more exports
  }
}
```

## 执行状态

- [ ] useOptions.js
- [ ] useTicketList.js
- [ ] useTicketForm.js
- [ ] useTicketDetail.js
- [ ] useLogPull.js
- [ ] useLogViewer.js
- [ ] useAiAnalysis.js
- [ ] useComments.js
- [ ] useTimeline.js
- [ ] useWorkflow.js
