# 2026-09-15 - 新增工单详情页数据导出脚本（只读导出为 Markdown）

## 变更内容

新增 `server/scripts/export_ticket_detail_md.py`，用于按工单号从数据库导出与前端「工单详情页」口径一致的完整数据，并渲染为 Markdown 文档供其他系统使用。本次已用该脚本导出生产库工单 `INC00001939452` 和 `INC00001846424` 的详情页全量数据。

### 导出产物形式（每次导出同时产出两个版本）

- `ticket_<工单号>.md`：完整版，包含全部原始数据（extra_data/ai_analysis 等大 JSON、消息流/快照逐条 JSON、RCA 全量结构）。
- `ticket_<工单号>_brief.md`：简化版，只保留详情页各 Tab 实际展示的数据（约 150 行）：
  - 基本信息：编号、标题、状态、处理人、项目/模块、外部链接、工单类型、根因分类、优先级、严重等级、来源、提单人、各时间点、问题性质、解决方式、关闭结果、细分问题、问题实例归属与归因确认、发生/修复/发版版本、总耗时、日志拉取状态；
  - 工单描述（原文 + AI 翻译）；
  - 最终处理（根因/解决方案）；
  - 最新 AI 结论（概览 Tab 口径：快照版本/时间/摘要/根因/方案/预防/风险/负责人）；
  - 历史（状态流转、指派记录、排查事件时间线、RCA 页面展示字段）；
  - 评论、相似/关联工单、日志拉取记录列表（页面列表字段）。

### 覆盖的数据范围（与详情页各接口/Tab 对应）

| 数据块 | 口径来源 |
| --- | --- |
| 工单主信息全量字段 | 详情接口 `GET /ticket/{id}`（含 AI 翻译、同步摘要、版本标签、问题实例归属等装饰字段） |
| 扩展字段 / AI 分析预留 / 标签 | `extra_data`、`ai_analysis`、`tags` JSON 大字段单独成节 |
| AI 提示词分层 | `TicketPromptService.resolve_prompt_layers`（只读） |
| 最新日志拉取摘要 / 最新 AI 分析摘要 | `TicketLogPullService.get_latest_summary`、`TicketAiAnalysisService.get_latest_summary` |
| 协同消息流 / ACR 快照 | `TicketDao.list_messages`、`TicketDao.list_snapshots` |
| 相似/关联工单 | 只读查询 `ticket_relation`（双向） |
| 状态历史 / 指派历史 / 事件 / RCA | 时间线接口 `GET /ticket/{id}/timeline` 同源（`TicketDao.get_timeline`，不含评论） |
| 评论 | `TicketDao.list_comments` |
| 日志拉取记录列表 | `TicketLogPullService.list_log_pull_records_services`（非分页全量，同详情页「日志拉取」Tab） |

### 副作用控制

- 全程只执行 SELECT，不 commit、不写库。
- 跳过详情接口中的相似工单向量子链路（`TicketSimilarityQueryService` 在向量缺失时会生成向量、调用外部 Embedding/Qdrant 服务并写库），改为只读查询 `ticket_relation`，并在导出文档头部标注该差异。

### 已踩过的坑（后续维护注意）

- `TicketLogPullQueryModel` 继承的 `QueryModel` 配置了 `alias_generator=to_camel` 且未开启 `populate_by_name`：按字段名 `ticket_id=...` 构造会被 Pydantic 静默忽略，导致查询条件退化为 `ticket_id IS NULL`、导出无关工单的日志拉取记录。必须用别名构造：`TicketLogPullQueryModel.model_validate({"ticketId": ..., "isPage": False})`。脚本内已写注释说明。

## 变更文件

- 新增 `server/scripts/export_ticket_detail_md.py`：只读导出脚本（详情 + 时间线 + 评论 + 日志拉取记录 → Markdown，每次导出同时产出完整版与简化版）。
- 生成产物 `server/scripts/output/ticket_detail_export_20260915_141336/ticket_INC00001939452.md`、`ticket_INC00001846424.md` 及对应 `_brief.md` 简化版（导出快照，供其他系统取用）。

## 使用方式

```bash
cd server
uv run python scripts/export_ticket_detail_md.py INC00001939452 INC00001846424
# 可选 --out-dir 指定输出目录；不带工单号时默认导出上述两个工单
```

## 影响范围

仅新增独立只读脚本与导出产物，不改动任何业务代码、接口与页面行为。
