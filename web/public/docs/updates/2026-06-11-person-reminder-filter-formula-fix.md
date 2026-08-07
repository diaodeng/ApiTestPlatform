# 2026-06-11 按人催办过滤公式参数修复

## 背景

按人催办（`personReminder`）与汇总统计（`summaryReport`）在多维表格数据源下支持 `filterFormula`。
页面文案要求填写“飞书 filter 公式文本”，但后端历史实现会把该字段先按 JSON 解析再序列化，导致开启过滤公式后容易触发飞书接口参数异常。

## 变更内容

1. 新增过滤公式归一化逻辑：`_normalize_bitable_filter_formula`。
1. `filterFormula` 改为按“公式文本”直接透传到飞书 `records` 接口 `filter` 参数，不再做 JSON 对象序列化。
1. 兼容历史“JSON 字符串包裹公式”的写法（会自动解包为纯公式文本）。
1. 当输入 JSON 对象/数组（例如 `{"conjunction":"and"...}`）时，后端会直接返回明确错误提示，避免继续请求飞书并报模糊参数异常。

## 过滤公式使用说明

1. 请直接填写飞书公式文本，例如：`CurrentValue.[状态] != "已关闭"`。
1. 不要填写 JSON 对象或 JSON 数组格式。
1. 若历史配置是带外层引号的字符串（JSON 字符串），系统会自动兼容。

## 影响范围

1. 人员催办预览接口：`POST /ticket/sync/notify/person/preview`
1. 人员催办执行接口：`POST /ticket/sync/notify/person/run`
1. 使用 `query_bitable_records` 的汇总统计链路（`summaryReport.dataSource=bitable`）
