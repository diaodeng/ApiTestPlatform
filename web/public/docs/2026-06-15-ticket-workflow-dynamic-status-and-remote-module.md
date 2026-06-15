# 工单动态工作流状态与远端模块同步修复

## 背景

工单工作流支持在页面中新增状态节点和配置流转规则，但工单列表页、详情页和状态流转弹窗仍使用前端静态状态枚举，导致新增或修改后的状态不能作为流转目标选择。

同时，内网从远端拉取 pending 工单再入库时，转换逻辑只读取 `moduleName/module_name`，未兼容外部推送字段 `ticketModle`，公网侧模块字段变化可能在二次同步到内网时丢失。

## 本次调整

- 工单列表页加载时读取 `/ticket/workflow/config`，优先使用工作流状态节点生成状态筛选、列表展示、详情展示和时间线状态名称。
- 状态流转弹窗不再展示全部静态状态，而是根据当前工单状态和已配置的工作流流转规则，只展示当前状态可流转到的目标状态。
- 若当前状态没有配置可用流转规则，前端给出提示，避免用户选择后被后端状态机拒绝。
- `/ticket/workflow/config` 读取权限放宽为 `ticket:workflow:list` 或 `ticket:ticket:status` 任一满足，保证有流转权限的用户能拿到候选状态。
- 公网外部推单更新已有工单时，如果新 `ticketModle` 有文本但未命中有效 HRM 模块 ID，会清空旧 `module_id` 并用新模块文本覆盖 `module_name`，避免继续展示旧模块。
- 远端拉取转换补充兼容 `ticketModle`、`ticketModel`、`ticket_model` 以及 `extraData.external_field_mapping.ticketModle`，用于回填本地 `moduleName`。

## 影响范围

- 前端：`web/src/views/ticket/index.vue`
- 后端：`server/modules/ticket/controller/ticket_controller.py`
- 后端：`server/modules/ticket/service/ticket_sync_service.py`

## 使用说明

新增工作流状态节点后，还需要新增或更新对应的流转规则。只有配置了从当前状态到目标状态的规则后，目标状态才会出现在工单流转弹窗中。

公网外部推单的 `ticketModle` 会优先匹配 HRM 模块；匹配成功时写入模块 ID 和模块名称，匹配失败但字段有值时只保留模块文本并清空旧模块 ID。如果需要稳定匹配到具体 HRM 模块 ID，仍需在同步自动化配置中维护模块映射或保证模块名称可匹配。
