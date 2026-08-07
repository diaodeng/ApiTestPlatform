---
title: 工单翻译开关与外部同步映射说明
type: note
source_type: code
created: 2026-06-06
updated: 2026-06-06
---

# 工单翻译开关与外部同步映射说明

本次补齐了工单新增、编辑、外部同步三条链路的配置一致性，核心点如下：

## 1. 工单翻译总开关

- 系统参数：`ticket.ai.translate.enabled`
- 位置：AI 配置中心
- 作用：统一控制工单创建、编辑、外部同步入库时是否执行轻量翻译
- 关闭后：
  - 新增工单保留原文
  - 编辑工单保留原文
  - 外部同步工单保留原文

## 2. 外部同步自动化配置

系统参数：`ticket.sync.automation`

新增配置项：

- `autoTranslateOnSync`
- `statusMappings`
- `assigneeMappings`

行为说明：

- `autoTranslateOnSync=true` 时，外部同步会在入库前执行翻译
- `statusMappings` 用于把外部文字状态映射到本地工单状态枚举
- `assigneeMappings` 用于把外部处理人文字映射到本地 `sys_user`

## 3. 关联规则

当前项目的关联方式是：

- 项目、模块：优先走 `ticket.sync.automation` 中的映射规则，再回退到文本匹配 HRM 项目/模块名称
- 状态：建议维护状态映射，映射不到时保留原始文本
- 处理人：建议维护人员映射，能命中用户时写入 `current_assignee_id`，否则保留名称

## 4. 自动化链路

外部工单同步后，可继续复用已有自动化链路：

- 版本号提取
- 自动拉日志
- 自动 AI 分析

如果同步请求携带 `automation`，或者系统参数允许自动化执行，就会沿用同一套处理流程。

