---
title: 工单AI参数提取机台编号覆盖逻辑修复
date: 2026-08-31
type: fix
scope: server/modules/ticket
---

# 工单AI参数提取机台编号覆盖逻辑修复

## 背景

工单 INC00001899231（门店 213819，2026-08-27，故障机台 24 号）同步提取时，AI 模型（deepseek-v4-flash）已正确返回 `posNo=24`，但最终提取结果为 `posNo=5`，导致自动化按 5 号机拉取了日志。

## 原因

2026-08-24 引入的防金额误判后处理逻辑（`_normalize_sync_extract_machine_numbers` + `_extract_explicit_machine_no`）会用正则从"标题+描述+原始入参"全文中查找第一个 `POS+数字` 匹配，并无条件覆盖模型结果。该工单描述前部有"the store confirmed that POS#05 was checked"（门店排查时检查过 5 号机），第一个正则匹配为 5，覆盖了模型正确的 24。

该覆盖设计的初衷是防止模型把金额 `$44,510.00` 的片段（44）当成机台编号，但工单正文提到多个机台是常见场景（"检查过 A 机、故障在 B 机"），"第一个匹配当真相"的固定覆盖在语义判断上不可靠。

## 修复方案

机台编号归一化改为**模型结果优先**，原文正则候选只承担两个职责：

| 场景 | 处理方式 |
|------|----------|
| 模型返回有效编号且命中原文任一候选 | 直接采信模型结果，无告警 |
| 模型返回有效编号，原文只有一个机台候选且与模型冲突 | 判定模型误判（如把金额片段当编号），用原文唯一候选纠正并告警 |
| 模型返回有效编号，原文有多个候选且模型值不在其中 | 不猜测，保留模型结果并告警"请人工复核" |
| 模型返回无效值（金额类文本等），原文存在候选 | 用原文第一个候选兜底并告警 |
| 模型未填写该字段，原文存在明确候选 | 采用原文候选并提示"模型未提取" |
| 原文没有任何机台候选 | 保持模型结果（通常为 null），无告警 |

金额拦截仍在 `_normalize_pos_or_sco_no` 中保留（货币符号、千分位、两位小数格式直接拒绝），防金额误判能力不回退。

新增 `_extract_all_explicit_machine_nos` 提取原文全部机台语义候选（按出现顺序去重），替代原来只取第一个匹配的 `_extract_explicit_machine_no`（后者保留，供兜底场景使用）。

## 影响范围

- `server/modules/ticket/service/ai/ticket_light_ai_service.py`：`_normalize_sync_extract_machine_numbers` 重写为模型优先策略；新增 `_reconcile_machine_no_with_source` 单字段对齐方法；新增 `_extract_all_explicit_machine_nos`。
- `server/tests/test_ticket_sync_ai_extract_safety.py`：更新原金额纠正用例的告警文案，新增多候选保留模型值、命中候选无告警、单候选纠正、候选兜底、原文无候选 5 个用例。

## 验证

- `uv run ruff check` 通过。
- `uv run pytest tests/test_ticket_sync_ai_extract_safety.py` 13 个用例全部通过（含 INC00001899231 场景回归：模型 24 不再被覆盖）。
- `tests/test_ticket_sync_mapping_boundary.py` 存在 13 个失败，经 stash 前后对比确认为分支存量问题，与本次改动无关。

## 注意事项

提取结果缓存在工单 `extra_data.ai_sync_extract`，缓存命中以 `sourceHash + promptHash` 为键。**只改代码不会使旧缓存失效**，修复前已按错误 posNo 提取且源数据未变化的工单，会继续命中旧缓存结果。如需纠正存量工单，需清理对应工单的 `extra_data.ai_sync_extract` 缓存或等待源数据/提示词变更后自然失效。
