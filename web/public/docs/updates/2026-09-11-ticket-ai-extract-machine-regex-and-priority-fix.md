---
title: 工单AI机台编号提取正则修复与唯一候选覆盖策略取消
date: 2026-09-11
type: fix
scope: server/modules/ticket
---

# 工单AI机台编号提取正则修复与唯一候选覆盖策略取消

## 背景

工单 INC00001952225（`[08/09 23:56 POS#2 ] Store 0546因同事收完大數後做日結點算死機...`）：用户修正提取提示词后，模型已正确返回 `posNo=2`、`logDate=2026-09-08`，但重新执行提取后落库的 `posNo` 仍是 56，提示"模型POS=2与原文唯一机台候选POS=56不一致，已采用原文值"——**修正提示词永远无法生效**，且 `identify` / `log_pull_hints` / 自动拉日志全部使用错误的 56 号机。

## 原因（两个问题叠加）

1. **正则误提取（56 的来源）**：`_extract_all_explicit_machine_nos` 的"数字在前 POS 在后"分支（`(\d+)\s*POS`）匹配到了标题中时间 `23:56` 的分钟数字（`:56 POS`），并且该匹配把 `POS` token 一并消耗，导致 `finditer` 后续无法再用"POS 在前数字在后"分支匹配紧随其后的 `POS#2`——真实机台号 2 从候选中消失，唯一候选变成 56。
2. **覆盖策略方向性错误**：2026-08-31 引入的归一化策略中，"原文唯一机台候选与模型冲突时，判定模型误判，用原文候选硬覆盖模型值"这一分支把正则候选当成了比模型更可信的真值。但正则没有语义判断能力，当正则自身误提取时，"纠错器"反而把模型改对的结果改错；且正则在每次提取时重新执行，提示词修正的结果到不了落库层。

## 修复方案（两项配套）

**正则修复**（`_extract_all_explicit_machine_nos`）：

- 三个分支的编号数字均排除时间语境：数字后跟随 `数字+冒号+数字`（`HH:mm`）不作为候选（含回溯绕过防护），前置分支数字前紧邻冒号（`23:56 POS`）同样排除；
- "数字在前 POS 在后"两个分支在 POS 后追加负向前瞻：POS 自身还紧跟分隔符+数字时不匹配（那是"POS 在前数字在后"分支的领地），避免吞掉 POS token 使 `POS#2` 不可见；
- 顺带修复中文前置编号分支（`N号POS`）数字组此前未捕获导致该形态永远取不到候选的存量缺陷。

**策略修复**（`_reconcile_machine_no_with_source`）：

| 场景 | 旧策略 | 新策略 |
|------|--------|--------|
| 模型值有效且命中原文任一候选 | 直接采信 | 不变 |
| 模型值有效，原文**唯一**候选且冲突 | **用原文候选硬覆盖** | 保留模型值并告警"请人工复核" |
| 模型值有效，原文多个候选且不在其中 | 保留模型值并告警 | 不变（与上一行合并为同一分支） |
| 模型值无效 / 未填写，原文有候选 | 原文候选兜底 | 不变 |

正则从"纠错者"降级为"兜底者"：模型可随提示词进化，正则不可进化，不可进化的规则不得覆盖可进化的模型结果。

## 影响范围

- `server/modules/ticket/service/ai/ticket_light_ai_service.py`：`_extract_all_explicit_machine_nos` 正则三处调整；`_normalize_sync_extract_machine_numbers` / `_reconcile_machine_no_with_source` 策略与注释更新。提取链路（同步统一提取、AI 测试工作台）共用该方法，行为同步生效。
- `server/tests/test_ticket_sync_ai_extract_safety.py`：原"唯一候选纠正"用例改写为"唯一候选冲突保留模型值"；新增 INC00001952225 时间劫持回归、纯时间语境无候选、`N号POS` 捕获 3 个用例。

## 验证

- `uv run pytest tests/test_ticket_sync_ai_extract_safety.py` 16 用例全部通过；`-k "light_ai or sync_extract or log_pull_hints"` 相关 29 用例全部通过。
- 正则行为脚本验证 11 个场景全部符合预期（含本案例标题、`#2 POS`、多候选、`2号POS`、词内嵌入不匹配、`POS 23:56` 时间后缀等）。
- `uv run ruff check` 通过。
- 全量测试 25 failed + 11 errors 经 stash 前后对比确认为分支存量问题（`test_python_assert_ast` / `test_ticket_issue_service` / `test_ticket_sync_mapping_boundary` 等，本次未触碰），与本次改动无关。

## 注意事项

- 提取结果缓存在工单 `extra_data.ai_sync_extract`，缓存键为 `sourceHash + promptHash`：**修改提示词会改变 promptHash 使缓存自然失效**，本案例中提示词已修正的工单在下次同步事件到达时会自动重新提取；但仅改本次代码不触发重提取。
- 存量已被写错 `posNo` 的工单（如 INC00001952225 当前 `identify/log_pull_hints` 中 posNo=56），需等待下一次外部同步事件重新提取，或人工修正。
