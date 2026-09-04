# 2026-09-03 工单模块映射大小写回归修复

## 问题现象

- 2026-08-28 起新入库工单（外部同步 / 多维表格主动拉取）全部出现 `module_id` 为空、`module_code` 为空字符串。
- 工单扩展字段 `extra_data.module_mapping.matchedBy` 均为 `unmatched`，而 8 月 27 日及以前存在 `mapping_moduleCode` 等成功匹配。
- 2026-09-03 手动执行多维表格拉取后，当天 135 条工单全部缺失模块归属；此前通过 `sync_ticket_module_mapping.py` 数据修复脚本回填过的模块字段，也被后续拉取覆盖清空（受影响约 979 条历史工单 + 310 条新工单）。

## 根因

2026-08-27 提交 `132ba29`（修复状态映射问题）将 `SyncUtil.normalize_keywords` 的关键字归一化统一为小写（`strip().lower()`），映射关键字 `keywords / aliases / matchText` 从此全部输出为小写。

但模块映射匹配器 `TicketSyncFieldMappingService._match_module_mapping_with_project` 中比较用的 `target`（工单模块文本）**没有同步小写**，`target in keywords` 因大小写不一致永远为 False：

- 配置关键字：`"POS - 客户端"` → 归一化后 `["pos - 客户端", ...]`
- 工单文本：`"POS - 客户端"`（未小写）→ `"POS - 客户端" in ["pos - 客户端"]` → False

因此所有工单的模块映射全部落空（`matched_by=unmatched`），payload 组装时走"携带了模块文本但未解析到模块"分支，按设计清空 `module_id=None`、`module_code=""`，只保留 `module_name` 文本。

注：手动执行多维表格拉取只是**触发面**——它批量入库/更新了一批工单，而映射匹配失败导致这些工单全部写入空模块字段。同一缺陷在定时拉取、外部推送等所有入库链路上同样存在。

## 修复内容

1. `server/modules/ticket/service/sync/ticket_sync_field_mapping_service.py`
   - `_match_module_mapping_with_project`：`target` 补充小写归一化（`target_lower = target.lower()`）后再与关键字精确比较，并同步修正注释说明该约束。
2. `server/scripts/sync_ticket_module_mapping.py`
   - `mapping_keywords` / `match_module_mapping` 与运行时语义对齐（关键字与 target 统一小写），避免脚本与运行时匹配结果再次不一致。
3. `server/tests/test_ticket_sync_module_mapping_case.py`（新增）
   - 回归测试：配置关键字与工单文本大小写不一致必须命中；projectId 项目隔离不受影响；`mapping_keywords` 输出小写；端到端解析断言。
4. `web/public/docs/ticket-sync-automation.md`
   - 补充"关键字匹配语义"说明（忽略大小写、完全相等匹配、不模糊猜测）。

## 影响与风险

- 项目映射 / 商家映射走的 `match_mapping_contains`、状态映射走的 `match_mapping_exact` 中 `target` 均已小写，不受本次缺陷影响，无行为变化。
- 修复后 `match_mapping_contains` 与 `_match_module_mapping_with_project` 均为"归一化后完全相等"匹配，符合 8/14 提交 `2929892` 的精确匹配设计意图，只是补上了大小写兼容。
- 已有 13 个 `test_ticket_sync_mapping_boundary.py` 用例在修复前（HEAD 基线）即失败，与本次改动无关；本次新增 6 个用例及相邻同步用例全部通过。

## 遗留事项

- 存量数据修复：2026-09-03 已执行 `server/scripts/sync_ticket_module_mapping.py` 全量回填，共更新 1045 条工单的 `module_id` / `module_code`（与 `hrm_module` 实际行一致，`module_name` 未改动，一致性抽查无异常）。修复后仍有约 725 条因映射配置未覆盖（如 `POS - 促销/优惠券/会员（包括集成）`、`POS - NewStore`、`店务 - 收货/退货/DDR`、`BI` 等）或项目下缺模块记录而无法回填，需在「工单同步自动化 → 模块映射」补齐配置 / 补齐模块数据后重跑脚本继续修复。脚本为预览确认后执行的幂等设计，可安全重复执行。
