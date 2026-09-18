# 自动拉日志 AI 门店编码映射修复（生产 INC00001988278 排查产物）

- 背景：生产工单 INC00001988278（MY-马来西亚 / POS-客户端，商家 58949，门店 org_no 558464，外部编码 8555）在 2026-09-17 16:45 多维表格定时同步时，`autoLogPullOnBitablePull` 已开启、字段识别（identify 步骤）已正确映射出门店 org_no 558464 与 POS 2，但自动拉日志仍被跳过，审计原因：`自动拉日志参数不完整，缺少: storeId(门店未匹配到正确的org_no)`，最终由人工手工拉取成功（记录 `pull_source=manual`）。
- 根因：自动拉日志运行参数按"默认值 → 字段识别 → hints → 任务级 logPullConfig → AI 统一提取 → 任务级覆盖"优先级合并（`TicketSyncAutomationInputService.resolve_runtime_config`）。AI 统一提取结果中的 `store` 是外部门店编码（本单为 8555），优先级高于字段识别与 hints，合并时把已映射好的内部 org_no 558464 覆盖回外部编码 8555；提交前按 `org_no` 校验 `ticket_log_pull_store_config` 必然失败。既有的"识别已映射值不被来源编码覆盖"保护（`detected_mapped_store_id` 分支）只在 `sourceStoreCode` 非空时生效，本单外部字段映射无门店字段，`sourceStoreCode` 为空，保护未触发。
- 修复（方案 1，AI 值与字段识别同构）：
  - `resolve_runtime_config` 新增可选 `db` 会话参数；提供会话且 AI 提取出门店时，合并前先按门店配置把 AI 门店编码映射为内部 org_no：商家取字段识别/hints/任务级配置，环境取"拉日志默认值"环境分组部分（冒号前，与 `detect_fields` 门店映射口径一致），调用 `TicketSyncFieldMappingService.resolve_store_by_external_value`（`sap_org_no → org_no`，仅唯一候选时映射成功）。
  - 映射成功时写入 `aiStoreMappedFrom` 保留 AI 原始编码供自动化审计追溯，并输出关键日志；映射失败（商家未知或候选不唯一）时保留原值，交由提交前 `verify_store_by_org_no` 门店校验拦截，行为与历史一致。
  - 生产调用方 `run_sync_automation` 已传入数据库会话；`db=None` 的纯单元场景保持历史行为，既有测试不受影响。
- 附带说明：AI 提取值映射为 org_no 后，`TicketStoreResolutionUtil.select_store_id`（`sourceStoreCode` 非空分支）中"AI 值等于/包含来源编码才采用 AI"的判断不受影响——当 AI 与来源编码是同一门店时两者本就同值；其余场景返回来源编码，与修复前结果一致。
- 验证：ruff 通过；新增回归用例"AI 外部编码映射为 org_no 后参与合并（INC00001988278 场景）"与"无 db/映射未命中保留原值"，`tests/test_ticket_sync_extract_state.py` 与 `tests/test_ticket_sync_automation_reuse.py` 共 15 个用例全部通过。
- 用户说明同步：[工单同步自动化](../ticket-sync-automation.md)、[日志拉取使用说明](../ticket_log_pull.md)。
