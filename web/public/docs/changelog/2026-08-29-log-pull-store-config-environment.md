# 2026-08-29 日志拉取门店配置支持环境隔离

## 变更主题

门店配置（`ticket_log_pull_store_config`）新增 `environment` 字段，实现按环境分组隔离管理，覆盖配置列表、导入、门店下拉、自动拉日志识别与校验全链路。

## 变更内容

### 数据库

- `ticket_log_pull_store_config` 新增 `environment VARCHAR(50)` 列（默认空串）及索引，迁移脚本：`server/sql/20260829_ticket_log_pull_store_config_environment.sql`，需手动执行。

### 后端

- 门店配置唯一匹配键由 `vender_no + org_no + sap_org_no` 升级为 `environment + vender_no + org_no + sap_org_no` 四元组，同一门店可在不同环境各存一条。
- `GET /ticket/log-pull/vendor-store-options` 新增可选 `environment` 参数，门店懒加载按环境过滤。
- `GET /ticket/log-pull/store-configs` 查询模型新增 `environment` 过滤项（精确匹配）。
- `POST /ticket/log-pull/store-configs/import` 新增 `environment` Form 字段（必填）；增量导入按四元组匹配，**覆盖导入只清空所选环境的旧数据**，其他环境不受影响。Excel 模板与解析逻辑不变，环境由弹窗选择。
- 自动拉日志链路：`list_store_candidates_by_external_value`、`resolve_store_by_external_value`、`verify_store_by_org_no` 均新增环境参数；自动识别与校验门店时使用同步配置 `logPullDefaults.environment`（`group:item` 格式）的分组部分过滤门店，即自动分析环境与日志拉取默认环境一致。

### 前端

- 日志拉取管理页：
  - 门店配置弹窗查询区新增「环境」下拉（选项与拉取日志弹窗同源），列表新增「环境」列；
  - 导入弹窗新增「环境」必选项，提交时随 FormData 传给后端；导入弹窗样式与原有结构保持一致；
  - 查询区切换环境后门店选项随之刷新。
- 拉取日志弹窗（`LogPullConfigFields`）：门店下拉随当前环境分组过滤加载，环境切换后自动重新加载门店列表。

## 行为约定

- 门店查询为**严格精确匹配**：按环境查询时只返回该环境的门店，环境为空的存量记录不会兜底返回，只能在「全部环境」查询中看到。
- 覆盖导入只清空所选环境：`delete_store_configs_by_environment`，不再清空全表。
- 导入必须选择环境，后端对空环境直接拒绝。

## 影响范围与升级步骤

1. 执行 `server/sql/20260829_ticket_log_pull_store_config_environment.sql`；
2. 存量门店数据环境为空串，如需在指定环境生效，请用导入弹窗按环境重新导入；
3. 自动拉日志若此前依赖"环境无关"的门店匹配，升级后必须保证门店配置已导入到默认日志环境对应的环境分组下，否则会因门店校验不通过而跳过自动拉日志。

## 相关文件

- `server/sql/20260829_ticket_log_pull_store_config_environment.sql`
- `server/modules/ticket/entity/do/ticket_log_pull_do.py`
- `server/modules/ticket/entity/vo/ticket_log_pull_vo.py`
- `server/modules/ticket/dao/ticket_log_pull_dao.py`
- `server/modules/ticket/service/log_pull/ticket_log_pull_service.py`
- `server/modules/ticket/service/sync/ticket_sync_field_mapping_service.py`
- `server/modules/ticket/service/sync/ticket_sync_automation_service.py`
- `server/modules/ticket/controller/ticket_log_pull_controller.py`
- `server/tests/test_ticket_log_pull_store_config_environment.py`
- `server/tests/test_ticket_log_pull_vendor_options.py`
- `web/src/api/ticket/ticket.js`、`web/src/api/ticket/logPull.js`
- `web/src/views/ticket/logPullRecord/index.vue`
- `web/src/components/ticket/LogPullConfigFields.vue`
- `web/public/docs/ticket_log_pull.md`
