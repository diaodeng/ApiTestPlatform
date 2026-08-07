# 2026-06-24 多维表格过滤条件 JSON 文案修正

## 背景

多维表格查询已改为将 `filterFormula` 作为飞书 `records/search` 的 `filter` 条件对象传入，配置内容应为 JSON 条件结构。页面和部分说明文档仍提示填写 `CurrentValue.[字段] ...` 这类公式文本，容易导致配置人员按旧口径填写后查询失败。

## 当前配置格式

`filterFormula` 支持 JSON 对象，或内容为 JSON 对象的字符串。示例：

```json
{
  "conjunction": "and",
  "conditions": [
    {
      "field_name": "(RD)工單狀態",
      "operator": "contains",
      "value": ["3. 待产研处理", "2. 1.5线处理", "4. 产研处理中"]
    }
  ]
}
```

时间大于等于示例，日期/时间字段值建议使用 13 位毫秒时间戳。下面示例表示大于等于 `2026-06-24 00:00:00`（Asia/Shanghai）：

```json
{
  "conjunction": "and",
  "conditions": [
    {
      "field_name": "更新时间",
      "operator": "isGreaterEqual",
      "value": 1782230400000
    }
  ]
}
```

## 变更内容

1. 同步配置页将公共配置、主动拉取、按人催办、汇总统计中的“过滤公式”文案调整为“过滤条件JSON”。
2. 主动拉取示例从公式文本改为飞书 `records/search` filter JSON。
3. 后端过滤参数解析失败提示改为“请填写飞书 records/search filter JSON”，避免继续提示公式文本。
4. 运行时配置兼容任务参数直接传 JSON 对象，避免对象被转成 Python 字符串后解析失败。

## 说明

主动拉取配置里的 `updatedAtField` 会作为默认时间窗口过滤字段之一，同时仍用于构造同步来源中的 `source.pushedAt`。主动拉取未显式传 `createdAfter` 时默认使用当前时间前 1 小时作为窗口下限，并在飞书 `records/search` 请求参数中追加“更新时间字段或创建时间字段大于等于窗口下限”的过滤条件。

`createdAfter` 仍保留为兼容入参，用于覆盖默认窗口下限；它不再代表本地过滤逻辑。

主动拉取会按“外部工单字段模型”里的默认必填字段校验映射后的记录；缺少必填值的记录不会入库，会记录 `missing_required_fields` 日志并计入失败数。
