# 工单群推送 — 自定义条件表达式

## 变更日期
2026-07-25（v2: 移除旧条件）

## 背景
工单入库后是否发送到群里，原来只能通过 `autoPushStatuses` 状态白名单和 `autoSendAfterTime` 提交时间过滤。现已实现完整的条件表达式引擎，并彻底移除旧的两种配置项。

## 变更内容

### 1. 条件表达式引擎
- **文件**: `server/modules/ticket/service/sync/ticket_sync_condition_evaluator.py`
- 实现安全受限的布尔表达式求值器（词法分析 → Pratt 语法分析 → AST 求值）
- 支持字段引用、比较运算、成员运算、空值判断、`has()` 函数、逻辑运算、括号分组

### 2. `autoPushCondition` 是唯一过滤条件
- 配置项 `autoPushCondition` 为空 = 不限制，全部推送
- 填写表达式 = 只有满足条件的工单才自动推送
- 语法错误会被安全捕获并跳过，不会中断流程

### 3. 已移除的配置项
- `autoPushStatuses` — 旧状态白名单，已完全删除
- `autoSendAfterTime` — 旧提交时间起始点，已完全删除
- 新版本不支持这两个配置，需用 `autoPushCondition` 表达式重写

### 4. 前端帮助完善
- "推送条件"输入框带 `?` 帮助图标，点击显示完整帮助
- 包含：语法说明、6 个常用示例、按分类列出的全部可用字段

## 表达式语法

| 类型 | 写法 | 说明 |
|------|------|------|
| 比较 | `status == '3. 待产研处理'` | 支持 `==`、`!=`、`>`、`<`、`>=`、`<=` |
| 成员 | `status in ['2. 1.5线处理', '3. 待产研处理']` | 值在列表中 |
| 排除 | `status not in ['5. 已关闭', '6. 已取消']` | 值不在列表中 |
| 有值 | `has(module_id)` | 字段非 None 且非空字符串 |
| 空值 | `module_id is None` | 字段为 None |
| 非空 | `module_id is not None` | 字段不为 None |
| 逻辑 | `and` / `or` / `not` + `( )` | 与/或/非，括号分组 |
| 时间比较 | `submit_time >= '2026-01-01'` | 日期时间可用引号括起来比较 |

## 常用示例

```
# 旧 autoPushStatuses 等效写法
status in ['2. 1.5线处理', '3. 待产研处理', '4. 产研处理中']

# 旧 autoSendAfterTime 等效写法
submit_time >= '2026-07-01 00:00:00'

# 状态 + 高优先级
status in ['3. 待产研处理', '4. 产研处理中'] and internal_priority in ['P0', 'P1']

# 有模块归属才推送
status in ['2. 1.5线处理', '3. 待产研处理'] and has(module_id)

# 有商家的 P1 工单
has(merchant_name) and internal_priority == 'P1'

# 指定时间后 + 有模块
submit_time >= '2026-07-01' and has(module_id)

# 排除关闭 + 有分析结果
status not in ['5. 已关闭', '6. 已取消'] and has(problem_pattern_code)
```

## 影响范围
- 后端：删除 ~200 行旧过滤逻辑，简化过滤链到仅 4 步（条件 → 发布就绪 → 去重 → 并发锁）
- 前端：删除 2 个旧表单项（状态选择器 + 时间选择器），替换为带完整帮助的表达式输入框
- 已配置 `autoPushStatuses` 或 `autoSendAfterTime` 的用户，需要改用 `autoPushCondition` 重写

## 验证
- 后端 ruff 检查通过
- 表达式引擎 11 项单元测试全部通过
- 前端 `npm run build:prod` 构建成功
