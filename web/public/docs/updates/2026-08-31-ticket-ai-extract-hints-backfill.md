---
title: 工单AI提取参数回填日志拉取提示快照修复
date: 2026-08-31
type: fix
scope: server/modules/ticket
---

# 工单AI提取参数回填日志拉取提示快照修复

## 背景

工单 INC00001904725（飞书多维表格主动拉取场景）AI 提取出了正确的日志日期 2026-08-29，但工单详情页"手动拉日志"弹窗中日期没有被回填，需要用户手工输入。

## 原因

bitable_pull 场景走"快速入库 + 延后处理"两段式链路：

1. **主入库阶段**（`defer_post_process=True`）跳过 AI 提取，`build_upsert_payload` 先行构建 `extra_data.log_pull_hints`（详情页弹窗的回填数据源）。此时日期只能从 `log_pull_config` 和 raw_payload 标准键获取，而飞书原始入参的时间是中文键名（如 `(IT)上报时间`），匹配不上，hints 里没有 modifyTime。
2. **延后处理阶段**（Celery）执行 AI 提取并成功得到 logDate/posNo，但回写时只更新 `ai_sync_extract`、标题、翻译等字段，从不重建 `log_pull_hints`，提取结果永远到不了弹窗。

所有走延后处理的 bitable_pull 工单都受影响。

## 修复方案

- `TicketSyncPayloadService` 新增公开方法 `refresh_log_pull_hints`，将原 `build_upsert_payload` 内联的 hints 构建逻辑抽取为独立方法，并补充 `log_pull_config` 中的 posNo/scoNo 作为兜底来源（与自动化链路的取值顺序一致）。
- 主入库路径 `build_upsert_payload` 改为调用该方法，行为不变。
- 延后处理路径（`TicketSyncPostProcessService.run_deferred_sync_post_process`）在 AI 统一提取回填并重新 detect 之后调用该方法，把 AI 提取出的门店、POS/SCO（含 scoNo 回退）和日期写入 `extra_data.log_pull_hints` 并随工单更新持久化。

## 回显说明（手动拉取后的数据保留）

用户手动拉取日志后，提交参数完整保存在日志拉取记录 `ticket_log_pull_record`（vendorId、storeId、posNo、command_content.modifyTime/path 等）。重新进入详情页时，弹窗回填优先级为：`log_pull_hints` → `latestLogPull`（最新一条拉取记录摘要，含 posNo/storeId/vendorId/modifyTime）→ `ticket_automation.logPullConfig` → `log_pull_config`。因此**手动选择过的门店、机台、日期在下一次打开弹窗时能自动回显**（来自最新拉取记录），无需额外处理。注意两点：

- `latestLogPull` 回显的是"最近一条记录"的参数（含失败记录），如最近一次是失败的手动尝试，弹窗会回显失败那次的参数。
- `log_pull_hints` 修复后由 AI 提取值填充，若用户手动改过参数再拉取，记录回显会覆盖 hints 的值（用户实际操作优先）。

## 影响范围

- `server/modules/ticket/service/sync/ticket_sync_payload_service.py`：抽取 `refresh_log_pull_hints`，posNo 兜底补充 log_pull_config 来源。
- `server/modules/ticket/service/sync/ticket_sync_post_process_service.py`：延后处理 AI 提取回填后刷新 hints。
- `server/tests/test_ticket_sync_log_pull_hints.py`（新增）：4 个用例覆盖 AI 回填值进 hints、scoNo 回退、AI 未提取时保留已有值、主路径 payload 写入。

## 验证

- `uv run ruff check` 通过。
- `tests/test_ticket_sync_log_pull_hints.py` 4 个用例全部通过。
- 相关套件 `test_ticket_sync_ai_extract_safety.py`、`test_ticket_sync_extract_state.py`、`test_ticket_sync_automation_reuse.py` 共 29 个用例通过。
- `test_ticket_sync_mapping_boundary.py` 的 13 个失败经 stash 前后失败集合 md5 对比确认与基线完全一致，属存量问题。

## 存量数据

修复部署后仅对新同步/重同步的工单生效。已入库工单的 `log_pull_hints` 不会自动补齐，但其手动拉取记录回显（latestLogPull）不受影响；如需补齐存量工单 hints，可重新触发对应工单的同步（源数据未变时 AI 提取会命中缓存，hints 重建不依赖缓存失效）。
