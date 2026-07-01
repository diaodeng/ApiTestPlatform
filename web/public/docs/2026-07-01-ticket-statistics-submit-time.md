# 2026-07-01 工单统计时间口径改为提交时间

## 背景

外部同步工单可能晚于用户实际提交时间入库，若统计页按本地 `create_time` 过滤和分桶，会把历史提交的工单统计到同步入库当天，导致时间范围、趋势粒度和存量趋势失真。

## 调整内容

1. 工单统计概览接口 `GET /ticket/statistics/overview` 的时间范围改为按工单提交时间过滤。
2. 工单趋势接口 `GET /ticket/statistics/trend` 的新增数、问题性质趋势、模块趋势、细分问题趋势和存量计算改为按工单提交时间归属趋势桶。
3. 工单提交时间优先读取外部同步元数据 `extra_data.external_sync.externalCreateTime`，缺失时读取 `extra_data.external_sync.source.externalCreateTime`，仍缺失时回退本地 `ticket.create_time`。
4. 关闭数和解决数仍按 `closed_at`、`resolved_at` 所在时间桶计算，不受提交时间替代影响。
5. 统计页筛选项文案从“时间范围”调整为“提交时间范围”，明确筛选口径。

## 影响范围

- 仅影响工单统计页及对应统计接口。
- 不改变工单列表的创建时间筛选和提交时间筛选字段语义。
- 外部同步数据没有提交时间时仍使用本地创建时间兜底，避免历史数据被过滤丢失。
