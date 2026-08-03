# 2026-06-10 AI配置中心默认提示词补齐（分类统计 / 日志参数提取）

## 背景

AI 配置中心中“分类统计提示词”和“日志参数提取提示词”依赖 `common` 分类提示词模板。
当系统没有内置对应模板时，下拉为空，用户无法直接选择并填写。

## 本次改动

后端默认提示词初始化新增 2 条占位模板（内容允许为空）：

- `ticket_stat_classify_default`
  - 名称：工单分类统计默认提示词
  - 分类：`common`
- `ticket_log_extract_default`
  - 名称：工单日志参数提取默认提示词
  - 分类：`common`

同时补齐配置默认值与回退逻辑：

- `ticket.ai.category.classify.prompt.code` 默认值改为 `ticket_stat_classify_default`；
- `ticket.ai.log_extract.prompt.code` 默认值改为 `ticket_log_extract_default`；
- AI 配置汇总接口读取配置时，若以下字段为空字符串会自动回退默认编码：
  - `ticket.ai.category.classify.prompt.code` -> `ticket_stat_classify_default`
  - `ticket.ai.log_extract.prompt.code` -> `ticket_log_extract_default`

## 效果

- 新环境启动后会自动插入上述默认模板；
- 老环境即使已有空配置值，也能在 AI 配置中心回显默认编码并正常下拉选择；
- 用户可直接进入提示词管理编辑模板内容，不再被“无可选项”阻塞。
