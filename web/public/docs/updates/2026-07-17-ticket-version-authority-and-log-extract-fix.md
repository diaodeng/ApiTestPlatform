# 2026-07-17 工单发生版本权威字段与日志提取修复

## 结论

工单“bug 首发版本 / 提单版本”统一以 `affected_version` 作为权威字段；`versionKey` 和 `extra_data.version_key` 仅保留为历史接口、AI 仓库映射和旧数据兜底兼容。

## 修复内容

1. 新增版本号归一化工具，过滤 `version`、`版本号`、`appVersion` 等字段名被误识别为版本号的情况。
2. 工单详情返回时统一由 `affected_version` 派生 `affectedVersion/versionKey`，无效旧值不再展示。
3. 编辑页保存发生版本时，以用户当前填写的 `versionKey` 覆盖 `affectedVersion`，避免旧 `affectedVersion` 抢占。
4. 日志下载完成后自动提取版本号前，先检查工单已有 `affected_version` 或兼容版本字段；已有有效版本时不再扫描日志。
5. 日志提取成功后写入 `affected_version`，并暂时同步 `extra_data.version_key` 作为历史链路兼容字段。
6. 同步入库、同步自动化识别、轻量 AI 正文提取和 AI 分析仓库映射都接入同一套版本号归一化与主表优先规则。

## 影响范围

- 不删除 `extra_data.version_key`，避免影响已有 AI 仓库映射、历史任务和旧数据。
- 不改变计划修复版本、实际修复版本、实际发版版本字段语义。
- 已经误写成 `version` 的历史数据不会继续在详情接口中展示，但数据库脏值仍建议后续按实际工单范围清理。
