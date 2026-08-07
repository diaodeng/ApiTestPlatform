# 2026-07-21 工单优先级双向补齐与群模板当前处理人兜底

## 结论

1. 外部推送、飞书多维表格主动拉取、远端拉取入库都会补齐外部优先级和内部优先级。
2. 映射关系固定为 `Level 0 -> P0`、`Level A -> P1`、`Level B -> P2`、`Level C -> P3`、`Level D -> P4`。
3. 入库数据双方都有值时各自保留，只在某一侧为空时按映射补齐缺失侧。
4. 群消息模板中当前处理人变量为空时，会使用内部负责人作为展示和 `@` 兜底。

## 变更原因

外部工单入库存在多种入口：外部系统推送、公网到内网远端拉取、飞书多维表格主动拉取。实际数据里可能只提供外部优先级或只提供内部优先级，原逻辑存在直接复制优先级值或默认写入 `P3` 的情况，无法稳定保存两套优先级语义。

群消息模板常配置当前处理人字段，但部分入库数据只有内部负责人，没有当前处理人。为了减少模板分支和人工配置成本，当前处理人变量需要在为空时自动回退内部负责人。

## 实现说明

1. 新增纯工具 `ticket_priority_util.py`，只负责优先级文本归一、外部转内部、内部转外部和成对补齐，不访问数据库或外部接口。
2. `/ticket/sync/external` 请求归一化阶段先执行优先级补齐，再做必填校验，因此只传 `customerPriority=Level A` 时可补出 `internalPriority=P1`。
3. 主动拉取转换模型阶段复用同一工具，`extraData.external_field_mapping` 会记录补齐后的 `customerPriority/internalPriority`。
4. 远端拉取转换模型阶段不再给缺失优先级强制默认 `P3`，而是基于远端已有字段或 `external_field_mapping` 成对补齐。
5. 入库 payload 构造阶段再次使用同一工具作为兜底，避免绕过模型转换的测试或兼容对象漏补。
6. 群消息变量 `${assignee_name}`、`${current_assignee_name}`、`${currentAssigneeName}` 在当前处理人为空时回退 `internal_owner_name`；`${assignee_at}` 和 `${current_assignee_at}` 在当前处理人无法解析时回退内部负责人 `@`。

## 验证

1. 已执行 `uv run ruff check ...`，相关后端文件和测试文件通过。
2. 已尝试执行 `uv run pytest server/tests/test_ticket_sync_mapping_boundary.py -q` 和 `uv run python -m pytest tests/test_ticket_sync_mapping_boundary.py -q`，当前后端虚拟环境缺少 `pytest` 模块，未能运行单测。
3. 已新增测试用例覆盖外部推送、主动拉取、远端拉取和群模板变量兜底，待安装 `pytest` 后可直接执行。

## 剩余风险

1. 若历史同步配置显式把优先级字段都从必填列表移除，完全缺少优先级的数据仍可能按主表默认值落库。
2. 若外部传入无法识别的自定义优先级，缺失侧会保留原值兜底，不会强行映射到 `P1-P4`。
