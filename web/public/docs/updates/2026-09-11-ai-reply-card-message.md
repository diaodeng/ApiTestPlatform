# 2026-09-11 AI 分析结果回帖改为飞书卡片消息

## 背景

AI 分析结果话题回帖（`groupPush.aiResultFollowUp`）此前以一条纯文本回帖到工单群话题：工单号、标题、结论、根因、修复建议、置信度、详情链接全部挤在一段文案里，结论/根因/建议无法快速区分，群内阅读体验差。

## 变更内容

### 1. 新增卡片构造服务 `ticket_ai_result_reply_card_service.py`

新增 `TicketAiResultReplyCardService`（`server/modules/ticket/service/sync/`），纯格式化构造飞书经典 interactive 卡片，不访问数据库、不发网络请求：

- **成功卡片**（绿色头）：工单基础信息（工单号带链接/标题/模块/商家，两列字段布局）→ 分区块展示「📌 结论」「🔍 根因分析」「🛠 修复建议」，可选展示「📎 依据」「⚠️ 风险项」「➡️ 后续动作」（结果载荷中给出才展示，空字段不渲染，避免大片 `-` 占位）→ 底部备注展示置信度（小数自动转百分比）→「查看工单」按钮。
- **失败卡片**（红色头）：工单基础信息 + 「❌ 失败原因」区块 + 查看工单按钮。
- 单区块文本超 3000 字符自动截断，防超长 AI 结果撑爆卡片（卡片整体上限 30k 字符）。

### 2. 回帖发送支持卡片形态 `ticket_sync_notify_service.py`

`send_feishu_thread_reply` 新增可选参数 `card`：传入卡片字典时按 `msg_type=interactive` 发送卡片回帖，不传保持原纯文本行为。评论同步等既有调用方不传该参数，行为不变。

### 3. 回帖链路接入 `ticket_sync_group_push_service.py`

`send_ai_result_thread_reply` 消息形态判定：

- `aiResultFollowUp.template`（回帖模板）**留空**：默认发送**卡片**；
- 用户配置了**自定义模板**：保持纯文本，尊重既有自定义行为（自定义模板里可能依赖 `${xxx}` 变量拼装文本，卡片形态无法表达）。

其余逻辑（sendOn 时机、幂等占坑、锚点收集、无锚点策略、replyInThread）全部不变，仅消息体形态变化。

### 4. 测试脚本 `scripts/test_ai_result_card_push.py`

通过 `.env` 配置的飞书群机器人 webhook 真实发送成功/失败样例卡片做渲染验证。注意：群机器人若开启关键词安全校验需在卡片文本中命中关键词（本环境关键词为 `TRunner`，脚本已内置；正式链路走飞书应用身份回帖，无关键词限制）。

## 行为影响

- 默认配置（模板留空）的租户回帖消息从文本变为卡片，内容信息量不减（置信度、详情链接保留）；
- 已配置自定义模板的租户无任何变化；
- 无数据库 DDL、无配置项增删、无前端改动。

## 验证

- `scripts/test_ai_result_card_push.py` 经 `.env.dev` 群机器人 webhook 真实发送成功 + 失败两张卡片，飞书返回 `code=0`，群里渲染正常（结论/根因/建议分区块、绿色/红色头、查看工单按钮）。
- `tests/test_ticket_ai_result_follow_up.py` 32 用例 + 12 子测试全通过（回帖链路回归）。
- 改动文件 `uv run ruff check` 通过。
- 说明：webhook 渠道验证的是卡片结构与渲染；正式回帖走 im/v1 messages reply `msg_type=interactive`，两者卡片 JSON 完全一致，reply 接口对 interactive 消息的支持为飞书开放平台标准能力。
