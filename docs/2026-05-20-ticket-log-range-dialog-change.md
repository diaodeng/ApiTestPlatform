# 2026-05-20 工单日志查看与时间范围约束调整

## 变更目标
- 将日志内容查看从详情页内联展示改为弹窗展示。
- 强制日志拉取必须填写时间范围，避免无边界抓取整包日志。
- 收紧日志解析范围，仅处理 `*_pos.log*` 日志文件。
- 日志查看支持在弹窗里切换查看来源，默认返回入库内容；仅在查看原始文档时基于已归档 ZIP 实时重新截取，提交入库逻辑保持不变。

## 变更内容
- 前端日志查看改为弹窗模式，支持在弹窗内查看摘要、关键字过滤和刷新日志内容。
- 弹窗内默认展示入库内容，并展示当前“本次截取范围”；切换到“原始文档”后才会按当前时间范围重新截取 ZIP。
- 在原始文档模式下可直接调整开始/结束时间后重新查看。
- 日志时间范围改为必填，页面支持两种录入方式：
  - 开始时间 + 结束时间
  - 时间点 + 前后分钟范围
- 后端创建日志拉取任务时统一将两种录入方式解析为 `log_begin_time` 和 `log_end_time`。
- 后端解析 ZIP 时只读取文件名包含 `_pos.log` 的日志文件，其他文件不再参与日志文本提取。
- 后端查看日志接口新增实时重截能力，仅在请求原始文档时使用归档 ZIP 重新切片，默认仍返回已入库内容。

## 验证记录
- `cd server && uv run python -m compileall modules/ticket/entity/vo/ticket_log_pull_vo.py modules/ticket/service/ticket_log_pull_service.py`：通过
- `cd server && uv run ruff check modules/ticket/entity/vo/ticket_log_pull_vo.py modules/ticket/service/ticket_log_pull_service.py`：通过
- `cd web && npm run build:prod`：通过

## 风险与后续
- 当前 `_pos.log` 过滤依赖文件名包含关系；如果外部平台后续调整命名规范，需要同步调整匹配规则。
- 时间范围收紧后，历史依赖“空时间范围抓全量日志”的使用方式将失效，需要同步通知使用方。
- 如果归档 ZIP 被清理，实时重截会回退到已入库内容，无法再按新时间范围重算。
