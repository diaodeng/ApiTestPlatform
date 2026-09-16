# 2026-09-11 AI 结果回帖新增消息形态开关与卡片字段白名单

## 背景

接续同日 [AI 分析结果回帖卡片化](2026-09-11-ai-reply-card-message.md)：卡片化后卡片/纯文本的判定是"模板留空即卡片"，没有显式开关；且卡片区块固定全量展示，无法按需裁剪。本次按需求补充两项配置。

## 变更内容

### 1. `aiResultFollowUp.messageStyle` 消息形态开关（card / text，默认 card）

- 仅**回帖模板留空**时生效：`card` 发飞书卡片（默认），`text` 使用系统默认纯文本模板；
- 配置了自定义回帖模板（`template`）时始终按模板发纯文本，开关不生效；
- 归一化时非法取值回退 `card`。

### 2. `aiResultFollowUp.cardFields` 卡片展示字段白名单（留空 = 全量展示）

卡片模式下配置什么字段就展示什么区块，未配置的区块不渲染。可选字段（与后端 `TicketAiResultReplyCardService.CARD_FIELD_KEYS` 一致）：

| 字段 key | 区块 |
|---|---|
| `ticket_info` | 工单基础信息（工单号/标题/模块/商家） |
| `analysis_summary` | 结论 |
| `root_cause` | 根因分析 |
| `fix_suggestion` | 修复建议 |
| `evidence` | 依据 |
| `risk_items` | 风险项 |
| `next_steps` | 后续动作 |
| `confidence` | 置信度备注 |
| `ticket_link` | 查看工单按钮 |

规则：无效字段剔除；全部无效回退全量展示；字段已配置但结果载荷为空时不渲染该区块（避免 `-` 占位）；失败卡片的「失败原因」区块始终保留。切到纯文本或配置模板后白名单不生效但保留原值。

### 3. 前端配置页（同步自动化 → 群推送 → AI 分析结果话题回帖）

新增「消息形态」单选（卡片/纯文本）与「卡片展示字段」多选；卡片字段多选仅在形态为卡片时显示（隐藏不清空，切回可恢复），推送模式为 push_config 时随组禁用。

### 4. 涉及文件

- 后端：`ticket_ai_result_reply_card_service.py`（新增 `CARD_FIELD_KEYS` / `normalize_card_fields` / `card_fields` 参数）、`ticket_sync_config_service.py`（默认配置与归一化）、`ticket_sync_group_push_service.py`（形态判定与白名单透传）；
- 前端：`web/src/views/ticket/syncAutomation/index.vue`、`hooks/useSyncConfig.js`；
- 测试：`server/scripts/test_ai_result_card_push.py` 新增 `trimmed` 场景。

## 兼容性

存量配置无 `messageStyle`/`cardFields` 时归一化为 `card` + 空列表，行为与上一版卡片化一致；无 DDL。

## 验证

- 新增 10 个测试（形态判定 4、卡片字段白名单 6），`tests/test_ticket_ai_result_follow_up.py` 42 用例 + 12 子测试全部通过；
- `scripts/test_ai_result_card_push.py trimmed` 经 `.env.dev` 群机器人 webhook 真实发送字段裁剪卡片（仅结论/根因/建议），飞书 `code=0`，其余区块未出现；
- 改动文件 ruff 通过（config_service 的 11 处 E501 为存量基线，非本次引入）。
