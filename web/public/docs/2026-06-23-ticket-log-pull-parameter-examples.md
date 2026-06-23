# 工单日志拉取参数示例与日期预填

## 背景

日志拉取弹窗中 `modifyTime` 和 `path` 都依赖人工记忆填写。`path` 尤其存在多种路径写法，手动输入容易出错。本次在参数配置中新增示例列表，并在日志拉取弹窗中提供下拉选择，选中后直接填入当前显示的参数框。

## 参数配置

新增系统参数：

- 参数键名：`ticket.logPull.parameterExamples`
- 参数值格式：JSON 数组
- 数组元素：字典，包含 `name` 和 `value`

示例：

```json
[
  {
    "name": "modifyTime 日期示例",
    "value": "2026-06-23"
  },
  {
    "name": "path 路径示例",
    "value": "/path/to/log_or_database"
  }
]
```

后端通过日志拉取商家/门店选项接口一并返回 `parameterExamples`，前端日志拉取详情弹窗和独立日志拉取管理页共用同一个配置。

## 交互规则

1. 日志数据类型显示 `modifyTime` 时，选择参数示例会把示例值填入 `modifyTime`。
2. 数据库数据类型显示 `path` 时，选择参数示例会把示例值填入 `path`。
3. 切换数据类型时会清空当前示例选择，避免上一次选择状态误导用户。
4. 参数示例只负责快速填入，用户仍可在输入框内继续修改。

## 工单日期预填

工单同步链路已支持在提取门店、POS/SCO 编号时同步提取日志日期，并写入 `extra_data.log_pull_hints.modifyTime`。本次补齐前端使用：从工单详情打开添加日志拉取界面时，会优先读取 `logPullHints.modifyTime/logDate` 并自动填入 `modifyTime`。

若当前工单没有提取到日期，前端仍保持空值，由用户手动选择或通过参数示例填入。

## 影响范围

- `ticket.logPull.parameterExamples` 由后端自动初始化，旧环境首次打开日志拉取页面时会自动补齐参数配置。
- 现有日志拉取提交参数不变，仍只提交当前数据类型对应的 `modifyTime` 或 `path`。
- 新字段只追加到选项接口响应中，不影响既有商家/门店联动逻辑。
