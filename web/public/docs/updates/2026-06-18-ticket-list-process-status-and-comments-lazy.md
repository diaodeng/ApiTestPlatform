# 2026-06-18 工单列表处理状态与详情评论按需加载

## 背景

工单列表原“日志拉取”列只能看到最新日志任务状态，无法承载 AI 分析等整体处理进度。工单详情页原文描述和翻译同时展开时内容过长，评论也放在历史页内部，不利于快速查看。

## 改动

1. 工单列表“日志拉取”列调整为“处理状态”，优先展示最新 AI 分析状态，其次展示最新日志拉取阶段。
2. 处理状态筛选枚举新增日志拉取中间态：待执行、提交申请中、轮询处理中、下载中、解析中，并支持聚合筛选“日志拉取中”。
3. 工单详情页描述与翻译支持展开/收起，默认展开描述、收起翻译；收起时保留一行内容预览，避免误以为没有内容。
4. 评论从历史页二级 tab 提升为详情页一级 tab，位置在历史前面。
5. 新增 `GET /ticket/{ticket_id}/comments` 评论查询接口，评论 tab 首次点击时才请求；历史时间线接口不再给前端返回评论，避免进入详情或历史页时拉取评论大文本。

## 接口与性能

- `GET /ticket/{ticket_id}/comments` 复用时间线查看权限 `ticket:ticket:timeline`，仅返回评论列表。
- 新接口在异步控制器中通过 `run_in_threadpool` 执行同步服务查询，避免阻塞 FastAPI 事件循环。
- `TicketDao.get_timeline(..., include_comments=True)` 默认仍保留评论，供 AI 分析和知识提炼内部上下文复用；前端时间线服务显式传 `include_comments=False`。

## 验证

1. `uv run ruff check modules/ticket/dao/ticket_dao.py modules/ticket/service/ticket_service.py modules/ticket/controller/ticket_controller.py`
2. `npm run build:prod`
