---
title: 日志拉取配置合并与并发数生效
date: 2026-08-13
---

# 日志拉取配置合并与并发数生效

## 变更概述

- 将日志拉取的三类配置（拉日志默认值、存储与资源限制、外部接口环境分组）统一收纳到「工单同步自动化 → 日志拉取配置」Tab。
- 将最大并发数从同步配置 `logPullDefaults.logPullConcurrency` 迁移到存储配置 `maxWorkers`，并使其真正生效。

## 变更明细

### 后端

- `TicketLogPullStorageConfigModel` 新增 `maxWorkers` 字段（默认 2，范围 1~20）。
- `TicketLogPullService._default_storage_config` 新增 `maxWorkers` 默认值，`_normalize_storage_config` 增加收敛校验（1~20）。
- `TicketLogPullService` 新增 `apply_executor_max_workers`，按配置动态重建线程池；`queue_record` 改为在锁内捕获 executor 引用，避免重建竞态。
- 保存存储配置后即时应用新的并发数；`ensure_param_config_rows` 初始化时按当前配置校准线程池。
- 同步配置 `logPullDefaults` 移除 `logPullConcurrency`，`normalize_sync_config` 清理历史遗留字段，避免两处配置不一致。

### 前端

- 新增 `hooks/useLogPullStorageConfig.js`，承载存储与资源限制配置的加载/保存。
- `hooks/useSyncConfig.js` 移除 `logPullPostProcess` 与 `logPullConcurrency` 相关逻辑，后处理开关改为由存储配置卡片维护。
- `syncAutomation/index.vue`：「外部接口」Tab 更名为「日志拉取配置」，新增「存储与资源限制」卡片，迁移「拉日志默认值」与「日志拉取后处理」内容。

## 影响面

- 历史同步配置中的 `logPullConcurrency` 会在加载时被清理；并发数以存储配置 `maxWorkers` 为准。
- 后处理开关的读写接口不变（仍为 `post-process-config`），但前端入口从「公共配置」迁移到「日志拉取配置 → 存储与资源限制」。
