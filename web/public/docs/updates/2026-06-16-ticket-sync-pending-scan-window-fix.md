# 2026-06-16 工单 pending 拉取候选窗口修复

## 背景

2026-06-16 上午 10 点后，公网服务可以正常接收外部推送并入库，但内网服务每分钟执行远端拉取后没有同步到新增工单。

排查环境关系：

- `dev` 为公网环境，负责接收飞书 webhook 并提供 `/ticket/sync/pending`。
- `prod` 为内网环境，定时任务 `module_task.scheduler_maintenance.pull_public_ticket_sync` 每分钟拉取公网 pending 数据。

## 根因

公网 `ticket` 表中 10 点后新增工单的 `external_sync.revision`、`publish_ready`、consumer 状态都正常，属于可同步数据。

问题出在 `TicketDao.get_tickets_for_sync`：原逻辑先按 `update_time ASC` 只取 `limit * 4` 条候选，再在 Python 中判断 revision、consumer、租约和发布状态。当旧工单数量超过候选窗口时，10 点后的新工单没有进入内存过滤集合，导致实际 consumer `public-ticket-pull` 查询 pending 返回 0。

## 修复

`TicketDao.get_tickets_for_sync` 改为按原排序分批扫描，直到凑够 `limit` 条待同步数据或扫描完候选数据。

保留原有同步语义：

- 仍按 `revision > delivered_revision` 判断是否需要同步。
- 仍保留 30 分钟 `pulled` 租约。
- 仍跳过不可发布状态，仅允许 `processing_ai` 进入后续自愈判断。
- 不改变 `/ticket/sync/pending` 返回后写入 `pulled`、`/ticket/sync/ack` 成功后推进 `delivered_revision` 的行为。

## 验证

在公网 `dev` 环境只读调用 DAO：

- 修复前：`consumer=public-ticket-pull` 返回 0 条。
- 修复后：返回 27 条 pending 工单，包含 2026-06-16 10:00 后新增的工单。

执行检查：

- `uv run python -m py_compile modules\ticket\dao\ticket_dao.py`
- `uv run ruff check modules\ticket\dao\ticket_dao.py`

均通过。

