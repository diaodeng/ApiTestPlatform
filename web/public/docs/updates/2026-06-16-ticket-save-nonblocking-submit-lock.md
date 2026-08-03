# 工单保存非阻塞与按钮防重复提交

## 背景

工单新增/编辑弹窗保存时，后端保存链路可能同步执行轻量 AI 翻译、自动分类、日志拉取任务创建等耗时操作。接口本身是 `async def`，如果直接在事件循环中执行同步数据库、网络或文件逻辑，会导致保存期间其他接口响应变慢。

同时，编辑弹窗的“确定”按钮没有提交中状态，用户在接口发起到响应返回前可以重复点击，可能造成重复请求或重复提示。

## 变更

1. `POST /ticket` 和 `PUT /ticket` 保持异步接口形态，内部通过 `run_in_threadpool` 执行业务保存。
2. 保存业务在线程池内创建独立 SQLAlchemy Session，避免把 FastAPI 依赖注入的请求 Session 跨线程复用。
3. 原接口响应语义保持不变：仍等待新增/编辑业务完成后返回成功或失败，不改为后台排队提交。
4. 工单编辑弹窗新增 `formSubmitting` 状态；保存请求发起后，“确定”按钮进入 loading 且禁用，“取消”按钮也临时禁用，接口响应后恢复。
5. 弹窗关闭或重置表单时会清理 `formSubmitting`，避免异常关闭后残留提交状态。

## 影响范围

- 后端：仅影响工单新增和编辑接口的同步业务调度方式。
- 前端：仅影响工单新增/编辑弹窗底部按钮状态。
- 不改变工单字段、保存校验、操作日志和返回数据结构。

## 验证

- 已执行 `uv run python -m py_compile modules\ticket\controller\ticket_controller.py`。
- 已执行 `uv run ruff check modules\ticket\controller\ticket_controller.py`。
- 已执行 `cd web && npm run build:prod`。
