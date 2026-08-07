# 工单日志拉取商家参数配置与门店按需加载

## 背景

日志拉取创建弹窗原先从门店配置表读取全部门店，再在服务层按商户编号聚合商家和门店。这会让商家名称依赖门店表字段，并且首次打开页面就返回全部门店。

当前商家规模只有十几个，预计也仅几十个，不需要新增独立商家表或商家维护模块。

## 方案

- 商家清单改为系统参数配置 `sys_config`，配置键为 `ticket.logPull.vendors`。
- 配置值使用 JSON 数组，每项必须包含 `venderNo` 和 `vendorName`。
- 日志拉取弹窗首次只请求商家清单；商家下拉展示为 `vender_no - 商家名称`。
- 用户选择商家后，前端携带 `vender_no` 调用门店选项接口；后端通过 `ticket_log_pull_store_config.vender_no` 精确查询对应门店。
- 商家和门店下拉均保留自由输入、筛选和确认取值能力；输入未配置值后确认时，输入文本直接作为当前表单值。
- 不新增商家表，也不新增门店表关联字段；`vender_no` 是商家配置和门店配置之间唯一的关联键。

## 参数配置示例

在系统参数配置中新增或编辑：

```text
参数名称：工单日志拉取商家配置
参数键名：ticket.logPull.vendors
参数值：[{"venderNo":"10001","vendorName":"华东商家"},{"venderNo":"10002","vendorName":"华南商家"}]
```

`venderNo` 必须与门店导入数据中的“商户编号”完全一致，并且当前外部日志拉取接口仍要求其可转换为整数 `vendorId`。

部署时执行 `server/sql/20260722_ticket_log_pull_vendor_config.sql`，会幂等创建空配置项；之后在系统参数配置中填写真实商家数据。

## 接口行为

```text
GET /ticket/log-pull/vendor-store-options
```

只返回商家配置和日志拉取参数示例，不查询门店表。

```text
GET /ticket/log-pull/vendor-store-options?vender_no=10001
```

返回商家配置以及该 `vender_no` 对应的门店列表。门店数据直接由 `ticket_log_pull_store_config` 的等值查询获得。

## 导入门店

继续使用现有门店配置模板和导入接口：

```text
GET  /ticket/log-pull/store-config/template
POST /ticket/log-pull/store-configs/import
```

导入前先确保 Excel 中的“商户编号”已在 `ticket.logPull.vendors` 参数中配置，否则该商户及其门店不会出现在日志拉取下拉列表中。
