# AI 执行审计列表页说明

## 页面位置

- 菜单：系统管理 -> AI执行审计
- 路由：`/system/aitaskexecution/index`

## 页面能力

- 按任务类型、来源类型、Provider、状态和关键字分页查询。
- 支持查看单条审计详情。
- 详情中展示：
  - 请求载荷
  - 响应载荷
  - 原始响应文本
  - Token 用量
  - 错误信息

## 权限

- `system:aitaskexecution:list`
- `system:aitaskexecution:query`

## 说明

- 当前页面只做只读审计查看，不提供编辑和删除。
- 审计数据来自轻量 AI 调用链路，主要覆盖工单翻译和工单关闭后的知识提炼。
