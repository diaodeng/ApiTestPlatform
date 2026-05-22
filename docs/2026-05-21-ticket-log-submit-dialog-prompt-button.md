# 2026-05-21 工单日志提交弹窗与通用提示按钮

## 变更目标
- 简化工单日志拉取区域的页面布局，避免提交表单与记录列表同屏占满空间。
- 把参数配置说明改成通用提示按钮，便于后续在其他页面复用。

## 变更内容
- 工单详情的“日志拉取”标签页仅保留拉取记录列表、刷新入口和“拉取日志”按钮。
- 提交拉取任务改为弹窗表单，点击“拉取日志”后打开。
- 参数配置入口改为通用提示按钮组件 `PromptButton`，默认以按钮形式触发，点击后展示提示内容。
- 新增全局通用提示按钮组件，后续可在其他页面直接复用。

## 验证记录
- `cd server && uv run python -m compileall modules/ticket/entity/vo/ticket_log_pull_vo.py modules/ticket/service/ticket_log_pull_service.py modules/ticket/controller/ticket_controller.py`：通过
- `cd server && uv run ruff check modules/ticket/entity/vo/ticket_log_pull_vo.py modules/ticket/service/ticket_log_pull_service.py modules/ticket/controller/ticket_controller.py`：通过
- `cd web && npm run build:prod`：通过

## 风险与后续
- 提交表单弹窗和日志内容弹窗并存，后续如果还要继续简化，可以把“查看日志”也收敛成抽屉或二级弹窗流程。
- `PromptButton` 目前以 popover 形式承载提示内容，内容过长时仍建议保持结构化简短说明。
