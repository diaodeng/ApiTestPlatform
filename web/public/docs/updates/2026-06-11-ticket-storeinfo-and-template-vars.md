# 2026-06-11 外部推单门店字段与群消息变量补强

## 背景

外部推单里新增了 `storeInfo` 字段；同时消息模板需要支持直接引用 `reporterName` 与门店信息变量。

## 改动点

1. 外部同步入参门店字段兼容增强：
   - 门店字段解析顺序调整为 `ticketStore -> storeInfo -> storeId`。
   - 兼容驼峰/下划线写法（`storeInfo/store_info`）。
1. 外部字段识别链路补强：
   - 字段提取逻辑同步支持 `storeInfo/store_info`，保证后续门店匹配流程可用。
1. 群消息模板变量补充：
   - 新增提单人变量：`reporter_name`、`reporterName`。
   - 新增门店变量：`store_info`、`storeInfo`（优先展示配置门店信息，未命中则展示原始值）。
   - 同时补充 `store_id`、`store_name` 便于模板细分展示。

## 门店保存规则

1. 当 `storeInfo`（或 `ticketStore/storeId`）存在，且能命中“商家ID + 门店配置(sap_org_no)”时：
   - 保存配置门店（`storeId` 使用配置门店编码，`storeName` 使用配置门店名称）。
1. 当无法命中门店配置时：
   - 保留原始门店值用于后续展示和消息变量渲染。

## 影响范围

1. `POST /ticket/sync/external` 外部推单字段归一化。
1. 同步后门店识别与自动化参数提取链路。
1. 群消息模板渲染能力（新增变量）。
