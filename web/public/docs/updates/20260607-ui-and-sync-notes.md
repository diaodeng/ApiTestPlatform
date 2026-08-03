# 2026-06-07 前端展示与同步说明

## 这次修复了什么

1. 修复 `hrm/module`、`hrm/project`、`ticket/aiRepoMapping`、`ticket/syncAutomation`、`system/aiconfig` 页面中的模板截断和字符串语法问题，保证生产构建可通过。
2. 将 `ticket/syncAutomation` 调整为单列卡片式布局，底部保存/刷新按钮固定在页面末尾，映射配置与拉日志默认值区域改为更大的输入区。
3. 将 `system/aiconfig` 调整为更宽的主内容区，避免顶部提示词与提示词选择框被压缩到一小条看不清。

## 开关边界

1. `autoRunOnSync` 和 `autoTranslateOnSync` 只控制外部同步入库后的自动化流程。
2. `remoteSync.enabled` 只表示远端拉取任务是否允许执行，不代表前端自动启动定时任务。
3. 手动新增工单的自动翻译开关不放在同步配置页，仍由工单新增/编辑页自己控制，避免不同数据入口混用同一套开关。

## 业务码策略

1. 项目和模块增加 `project_code` / `module_code`，外部同步优先按业务码匹配。
2. 兼容既有 `project_id` / `module_id`、名称映射和历史数据回填，避免影响原有项目和模块使用。
