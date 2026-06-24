# 2026-06-24 专题工单统计按主题归类修正

## 背景

`module_task.scheduler_maintenance.ticket_topic_stats_report` 在采集飞书工单群消息时，原逻辑虽然有 `extract_topic` 方法，但实际分类时直接把整条消息正文传入 `get_category_bucket`。飞书富文本、@ 人员或详情字段中只要出现 `gv/coupon/voucher/券` 等片段，就可能把非券类工单误归类为“券”。

本次排查样例：

- Ticket：`INC00001660915`
- 主题：`OPEN TICKET - Z read differs from EOD Consolidated Report`
- 该主题本身不包含券类关键词，应归为“其他”并被专题统计跳过。

## 改动

1. `TOPIC_BLOCK_PATTERN` 和 `TOPIC_LINE_PATTERN` 支持中文全角冒号 `：`，兼容飞书消息中的 `主题：`。
2. `collect_topic_records` 改为先提取 `topic`，再仅用主题文本执行 `get_category_bucket(topic)`。
3. 英文专题关键词改为词边界匹配，避免 `coupon/gv/promo/point` 等片段命中其他单词内部；中文关键词继续按包含匹配。
4. 命中记录中的 `topic` 保存主题文本，不再保存整条消息正文。
5. 新增单元测试覆盖：
   - 全角 `主题：` 可正确提取主题；
   - BI 报表类标题不会误判为“券”；
   - 主题含 `coupon:` 时仍归类为“券”；
   - 英文关键词出现在其他单词内部时不触发专题分类。

## 影响范围

- 仅影响专题工单会话状态统计定时任务的分类口径。
- 不影响工单主表、AI 分类、同步入库和其他统计接口。
- 统计结果会更贴近“按主题归类”的原设计，详情/回复中的关键词不再参与专题分类。

## 验证

计划执行：

```bash
cd server
uv run python -m py_compile modules\ticket\service\ticket_topic_stats_service.py tests\test_ticket_topic_stats_service.py
uv run python -m unittest tests.test_ticket_topic_stats_service
uv run ruff check modules\ticket\service\ticket_topic_stats_service.py tests\test_ticket_topic_stats_service.py
```
