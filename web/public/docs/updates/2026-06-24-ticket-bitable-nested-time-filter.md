# 2026-06-24 多维表格主动拉取嵌套时间过滤修复

## 背景

主动拉取的 `filterFormula` 已支持飞书 `records/search` 的嵌套 filter JSON。嵌套模式下，服务需要在最外层 `children` 追加默认时间窗口，同时仍要递归补齐内部已配置时间字段的动态 `value`。

## 变更内容

1. `TicketSyncService._build_bitable_pull_time_filters` 会先递归补齐已有时间字段条件，再判断顶层结构。
2. 顶层存在 `children` 时视为嵌套模式：默认时间窗口作为一个新的 `children` 条件组追加到最外层。
3. 顶层不是嵌套模式时只补齐内部时间字段的空 `value`，不再额外追加默认时间范围。
4. 删除主动拉取查询循环中的临时 `print`，避免定时任务输出非结构化调试信息。

## 示例

嵌套模式会保留原有条件组，并在最外层追加时间窗口：

```json
{
  "conjunction": "and",
  "children": [
    {
      "conjunction": "and",
      "conditions": [
        { "field_name": "更新时间", "operator": "isGreaterEqual", "value": ["ExactDate", "1782233940000"] }
      ]
    },
    {
      "conjunction": "or",
      "conditions": [
        { "field_name": "更新时间", "operator": "isGreater", "value": ["ExactDate", "1782233940000"] },
        { "field_name": "创建时间", "operator": "isGreater", "value": ["ExactDate", "1782233940000"] }
      ]
    }
  ]
}
```

扁平模式只补齐已有时间字段：

```json
{
  "conjunction": "and",
  "conditions": [
    { "field_name": "更新时间", "operator": "isGreaterEqual", "value": ["ExactDate", "1782233940000"] },
    { "field_name": "状态", "operator": "contains", "value": ["待处理"] }
  ]
}
```
