# 工单 stepReason 排查过程评论同步

## 背景

飞书 webhook 推送的 `stepReason` 是排查过程大文本，格式中以 `20260616 熊杰：` 或 `20260616：` 开头的段落表示一次新的回复。原同步链路只保存工单主体，无法把新增排查过程稳定追加为评论，也无法区分本地评论和外部同步评论。

## 变更

1. `ticket_comment` 扩展同步来源字段：`source_type/source_system/source_record_id/source_field/source_segment_key/source_segment_index/source_content_hash/external_created_at`，并增加 `attachments` 预留字段。
2. 手工评论默认 `source_type=local`，不会被外部同步覆盖。
3. 外部推送归一化保留 `stepReason` 到同步模型和 `extraData.step_reason`。
4. 同步入库后按 `stepReason` 拆分评论片段，使用 `source_system + source_record_id + stepReason + segmentIndex` 生成 `source_segment_key`，按该键幂等新增或更新外部评论。
5. pending 拉取 payload 携带 `comments`，内网 remote pull 优先按远端 `sourceSegmentKey` 同步评论；没有评论列表时再用 `stepReason` 兜底解析。
6. 评论附件字段已预留，后续 Web 评论带附件时可直接写入 `attachments`，不影响本次外部同步幂等规则。

## 去重规则

- 本地评论：`source_type=local`，不参与外部同步幂等，不会被覆盖。
- 外部评论：按 `source_segment_key` 定位同一条外部评论。
- 同一 `segmentIndex` 内容变化时，更新该外部评论内容和 `source_content_hash`。
- 新增段落会生成新的 `segmentIndex` 和幂等键，追加为新评论。

## 数据库

执行迁移：

```sql
server/sql/20260616_ticket_comment_sync_source.sql
```

## 验证

- `uv run python -m py_compile modules/ticket/service/ticket_sync_service.py modules/ticket/service/ticket_service.py modules/ticket/dao/ticket_dao.py modules/ticket/entity/do/ticket_do.py modules/ticket/entity/vo/ticket_vo.py controller/ticket_controller.py`
- `uv run ruff check modules/ticket/service/ticket_sync_service.py modules/ticket/service/ticket_service.py modules/ticket/dao/ticket_dao.py modules/ticket/entity/do/ticket_do.py modules/ticket/entity/vo/ticket_vo.py controller/ticket_controller.py`
