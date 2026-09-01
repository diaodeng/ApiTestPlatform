---
title: 工单概览AI结论格式保留与AI分析追问记录补全
---

# 工单概览AI结论格式保留与AI分析追问记录补全

## 变更日期

2026-09-01

## 变更概述

修复工单详情页两个体验问题：

1. **概览 tab AI 结论挤成一行**：摘要、根因、解决方案、预防建议、风险说明五个字段原来直接插值渲染，AI 输出的多段文案（换行分隔）全部挤成一行。现在这五个字段保留换行与空格，按 AI 原始格式分段显示，与 AI 分析 tab 的展示效果一致。
2. **AI 分析记录看不到用户追问**：从“发起AI分析”弹窗提交的分析任务，用户填写的“本次分析重点/追问内容”（extraInstruction）只会进入 AI 提示词，不会写入工单消息流，导致 AI 分析记录里只能看到 AI 分析结果，看不到用户问了什么。现在创建 AI 分析任务时会自动把追问内容写入一条“我的追问”消息（关联对应任务ID），与 AI 分析结果成对展示。

## 用户可见变化

- 概览 tab 的五个 AI 结论字段支持多行显示，长内容阅读体验与 AI 分析 tab 一致。
- AI 分析 tab 的“AI分析记录”中，从发起分析弹窗提交的追问也会显示为“我的追问”记录；通过追问框提交的链路行为不变（消息本身已记录，不会重复）。
- 追问消息通过 `referenceId` 关联到对应 AI 分析任务，可在消息上追溯是哪次分析任务使用该追问。
- 未填写追问内容的分析任务（如日志拉取自动触发的分析）不会产生空追问消息。

## 涉及文件

- `web/src/views/ticket/components/detail-tabs/TicketDetailOverviewTab.vue`：五个 AI 结论字段改用 `pre-wrap` 样式容器渲染，保留换行。
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`：`create_analysis_task_services` 创建新任务时写入 `question` 消息（跳过条件：`skipQuestionMessage` 或追问内容为空）。
- `server/modules/ticket/entity/vo/ticket_vo.py`：`TicketAiAnalysisRequestModel` 新增 `skipQuestionMessage` 字段。
- `server/modules/ticket/service/core/ticket_service.py`：协同消息触发 AI 分析链路传 `skipQuestionMessage=True`，避免同一追问重复写两条消息。

## 行为边界

- 幂等命中（相同请求直接返回历史结果）和“相同任务执行中”分支发生在写消息之前，不会产生重复追问消息。
- 重试已有任务只更新状态，不写追问消息。
- 日志拉取自动触发的 AI 分析没有追问内容，不写追问消息。
- 历史存量任务的追问内容仍保存在任务的 `analysis_context.extraInstruction` 中，不会补写消息。

## 注意事项

- 后端服务需重启后生效；前端需重新构建发布。
