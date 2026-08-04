# 工单用户配置、列表列与统计块显示

## 背景

工单列表和统计页的可视信息越来越多，不同用户关注维度不同；同时后续还会出现用户级 AI 提示词、Provider 等个性化配置。若为每类配置单独建表，会导致表结构碎片化。

## 实现

1. 新增通用用户配置表 `sys_user_config`，按 `user_id + config_type + config_key` 唯一保存少量 JSON 配置。
2. 新增当前用户配置接口：
   - `GET /system/user-config/current`
   - `GET /system/user-config/current/{config_type}/{config_key}`
   - `PUT /system/user-config/current`
3. 工单列表新增筛选项：根因分类、解决方式、关闭结果。
4. 工单列表新增列：根因分类、解决方式、关闭结果，并通过“列设置”按用户保存显示列配置。
5. 工单统计页新增“显示配置”，按用户保存哪些统计块显示。

## 设计取舍

用户配置采用统一表存储，`config_type` 负责功能域隔离，`config_key` 负责具体配置项区分，`config_value` 保存 JSON。该方式适合当前“配置杂但数量少”的场景；后续如果某类配置具备强查询、审计或权限模型，再拆独立业务表。

## 风险

1. 首次启动会通过 `create_all` 创建新表，MySQL/SQLite 会补齐唯一索引；生产库若禁止自动 DDL，需要手动创建 `sys_user_config`。
2. 当前列设置只控制前端显示，不改变后端列表返回字段。
