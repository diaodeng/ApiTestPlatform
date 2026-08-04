# 远端拉取状态与内部负责人映射修复

## 背景

内网服务从公网服务拉取工单后，若公网侧入库时没有完成状态映射，内网即使配置了 `ticket.sync.automation.statusMappings`，拉取入库后仍显示公网原始状态文案。同时，公网工单中由外部推送带入的内部负责人没有在内网工单上展示。

## 变更

1. `remote_pull` 入库时继续禁止复用公网环境的项目、模块和用户 ID，避免跨环境 ID 污染。
2. `remote_pull` 入库时允许使用内网本地 `statusMappings` 对远端状态文本重新映射，远端传 `ticketStatus/ticket_status/status` 或 `extraData.external_field_mapping.ticketStatus` 均可参与匹配。
3. `remote_pull` 入库时允许使用内网本地 `assigneeMappings` 与邮箱/姓名解析当前处理人、报告人和内部负责人；未命中本地用户时保留远端人员文本。
4. 远端 pending 工单转换为本地模型时补齐 `internalOwnerName/internalOwnerEmail`，兼容顶层字段和 `extraData.external_field_mapping` 快照，确保外部推送进入公网服务的内部负责人能继续传递到内网。

## 影响范围

- 只影响内网主动执行远端拉取并以 `sync_scene=remote_pull` 入库的路径。
- 公网外部直推 `/ticket/sync/external` 的原有外部字段映射逻辑不变。
- 跨环境 ID 边界不变：远端用户 ID 不会直接写入内网，只会通过内网映射配置、邮箱或姓名解析本地用户。

## 验证

- 已执行 `python -m py_compile server/modules/ticket/service/ticket_sync_service.py`，语法检查通过。
- 已执行 `uv run ruff check modules/ticket/service/ticket_sync_service.py`，静态检查通过。
