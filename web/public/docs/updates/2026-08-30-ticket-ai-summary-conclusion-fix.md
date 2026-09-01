---
title: 工单概览AI结论显示为空修复
---

# 工单概览AI结论显示为空修复

## 问题现象

- 工单详情概览的"最新AI结论"卡片中，摘要、根因、解决方案等字段显示为 "-"，仅有"最新执行状态"标签正常（如"成功"）。
- 影响所有已成功完成 AI 分析的工单，与工单本身数据无关。

## 根因

任务摘要序列化方法 `_serialize_task_summary` 从任务的 `analysisResult` JSON 中提取结论字段时，使用了驼峰键（`analysisSummary` / `rootCause` / `fixSuggestion`），而入库时统一写入的是 snake_case 键（`analysis_summary` / `root_cause` / `fix_suggestion`）。键名不匹配导致提取结果恒为空，概览接口返回的 `latestAiAnalysis` 中三个结论字段始终为 `null`。

## 变更内容

- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py` 的 `_serialize_task_summary`：结论字段提取改为 snake_case 键优先、驼峰键兼容（防止历史上存在异常写入），修复后概览与任务历史两侧的结论字段均能正常返回。

## 影响范围

- 工单详情概览"最新AI结论"卡片（读取 `/ticket/{id}/summary` 的 `latestAiAnalysis`）。
- AI 任务历史弹窗及工单列表的 `latestAiAnalysis` 摘要（同源序列化方法）。

## 注意事项

- 本修复不改动数据库存储格式，`analysis_result` 列仍为 snake_case 键。
- 概览卡片中"快照版本/快照时间/预防建议/风险说明"来自 ACR 快照；轻量概览接口不返回快照数据，且早期成功任务未生成快照，这部分仍可能显示 "-"，与本次修复无关。
