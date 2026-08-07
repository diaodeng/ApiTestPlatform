# 2026-06-26 多维表格主动拉取富文本换行保留

## 背景

飞书多维表格长文本字段在接口中可能以富文本片段数组返回，例如 `{"text": "\n", "type": "text"}` 或空文本片段。主动拉取历史归一化会把列表元素逐个 `strip()` 后再按分隔符拼接，导致真实换行被丢弃，描述内容挤在一起，`stepReason` 排查过程也无法按日期行正确拆分评论。

## 变更

1. `TicketSyncService._normalize_bitable_record_scalar()` 增加富文本片段识别。
2. 当字段值是飞书富文本片段数组时，按原片段顺序直接拼接 `text`，不再按逗号等分隔符拼接。
3. 富文本片段中的 `"\n"` 会保留为真实换行，`{"text": "", "type": "text"}` 会作为空片段自然忽略，不再 JSON 化为文本内容。
4. 普通多选、人员数组等非富文本数组仍沿用原有去重和分隔符拼接逻辑。

## 影响范围

1. 影响飞书多维表格主动拉取字段映射中的长文本、排查过程等富文本字段。
2. `description` 会保留原始换行格式。
3. `stepReason` 会保留日期行换行，后续 `parse_step_reason_segments()` 能继续按 `20260624 张三：` 这类行首格式拆分同步评论。

## 验证

新增单测覆盖富文本片段数组：

1. 描述字段 `第一行 + 换行 + 空片段 + 第二行` 转换后为 `第一行\n第二行`。
2. 排查过程字段保留两条日期行换行，并能拆成两条评论片段。

验证命令：

```bash
uv run python -m unittest tests.test_ticket_sync_mapping_boundary
uv run ruff check modules/ticket/service/ticket_sync_service.py tests/test_ticket_sync_mapping_boundary.py
```
