# 工单可配置分类与趋势指标

## 分类规则

同步自动化的“系统字段”页新增外部字段工单类型映射。`sourceField` 是外部同步接口字段名，例如 `externalCategory`，不是多维表格列名。规则按优先级从高到低匹配，支持 `equals`、`contains`、`in` 和 `regex`。规则命中后工单保存目标类型、`classification_source=external_mapping`、规则 ID 及命中审计元数据；没有命中才允许 AI 回填类型。人工编辑类型会标记为 `manual`，后续外部同步不会覆盖。

## 趋势统计

固定“问题性质趋势”已替换为“工单类型趋势”，只统计工单的 `issue_type_id/issue_type_name`。`is_problem` 保持原有入库语义：AI 未明确返回时，仍可按工单类型和关闭结果配置回退；只是默认趋势不再统计它。

自定义趋势指标由管理员维护指标、分组和条件。允许的字段由后端白名单控制，避免配置参与任意 SQL；每个条件可使用 `equals`、`contains`、`in`、`regex`，分组支持全部满足或任一满足，指标支持分组重叠或互斥。统计页先加载定义，用户选择指标并点击查询后才请求对应 `metricCodes`。

## 快照与补跑

日快照和业务周快照把自定义指标结果写入 `ticket_statistics_metric_snapshot`，按快照键覆盖重算。执行 `server/sql/20260731_ticket_configurable_classification_metrics.sql` 后，先配置规则/指标，再用已有日快照和业务周快照维护任务补跑需要的历史范围。旧固定问题性质快照字段不再读取，不需要处理。

已有的 `POST /ticket/sync/auto-category/reclassify` 批量重归类接口新增 `strategy=external_mapping`。它会利用每张工单已保存的 `extra_data.external_field_mapping/raw_payload` 重跑外部映射；传 `forceReclassify=true` 才会覆盖人工锁定的工单类型。
