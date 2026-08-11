# syncAutomation 拆分计划

当前 `index.vue`（3,968 行）包含 5 个 Tab 页 + ~1,800 行 script。

## Tab 分布

| Tab | 行号 | 行数 | 计划组件 |
|-----|------|------|----------|
| 公共配置 | 14-679 | 665 | `SyncBasicConfig.vue` |
| 同步 | 680-1624 | 944 | `SyncPushConfig.vue` |
| 映射/规则 | 1625-1683 | 58 | `SyncMappingRules.vue` |
| 系统字段 | 1684-1923 | 239 | `SyncSystemFields.vue` |
| 操作 | 1924-2147 | 223 | `SyncOperations.vue` |
| Script | 2164-3968 | ~1,800 | 拆分为多个 composable |

## 拆分策略

1. 每个 Tab 模板抽取为独立组件，通过 props 接收 form 数据，通过 emit 通知变更
2. Script 部分按 Tab 对应的数据域拆分为 composable：
   - `useSyncBasicConfig.js` - 飞书凭证、多维表格公共配置
   - `useSyncPushConfig.js` - 同步推送配置
   - `useSyncMappingRules.js` - 映射/规则
   - `useSyncSystemFields.js` - 系统字段模型
   - `useSyncOperations.js` - 手动操作（催办/汇总/群推送/重归类）
3. `index.vue` 变为组装层（~200 行 template + ~200 行 script）

## 执行状态

- [ ] SyncBasicConfig.vue
- [ ] SyncPushConfig.vue
- [ ] SyncMappingRules.vue
- [ ] SyncSystemFields.vue
- [ ] SyncOperations.vue
- [ ] useSyncBasicConfig.js
- [ ] useSyncPushConfig.js
- [ ] useSyncMappingRules.js
- [ ] useSyncSystemFields.js
- [ ] useSyncOperations.js
