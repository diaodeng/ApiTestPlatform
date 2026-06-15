# 工单协同追问触发 AI 分析修复

## 背景

工单详情页 `协同/AI` 中提交追问时，消息能正常保存，但页面看不到 AI 分析任务被发起；当后端因为缺版本号、仓库映射或 Agent 配置等原因未创建任务时，前端仍只提示消息提交成功。

## 修复内容

1. 后端 `TicketService.add_message` 在 `runAi=true` 时，将本次追问正文作为 `extraInstruction` 传给 `TicketAiAnalysisRequestModel`，确保 Agent/Codex 能拿到用户这次追问的分析重点。
2. 后端返回结果新增 `aiTriggered`，并在 `message` 中区分“AI 任务已提交”和“消息已保存但 AI 未发起”的原因。
3. 前端提交协同消息后读取 `result.aiSuccess/result.aiMessage`，AI 未触发时显示 warning，AI 触发成功时刷新 AI 任务历史。

## 影响范围

- 只影响工单详情页协同消息提交后的 AI 追问链路。
- 消息保存仍先提交事务；AI 任务创建失败不会回滚协同消息，页面会展示失败原因。
- AI 任务仍沿用工单版本号、Agent 和 Provider 选择规则。

## 验证建议

1. 工单存在版本号和有效仓库映射时，在 `协同/AI` 提交追问，确认提示 AI 追问任务已提交，任务历史出现新任务。
2. 工单缺版本号或映射缺失时，确认消息保存成功，但页面 warning 展示未发起原因。
