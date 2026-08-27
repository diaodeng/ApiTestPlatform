---
title: 工单模块 Controller 异步阻塞修复
type: update
source_type: mixed
updated: 2026-08-19
---

# 工单模块 Controller 异步阻塞修复

## 问题背景

工单模块（ticket）的 9 个 Controller 文件中，存在大量 `async def` 路由函数直接使用同步 `Session`（`Depends(get_db)`）且未通过 `run_in_threadpool` 包装同步 DB 调用的情况。这会导致同步数据库操作在 FastAPI 异步事件循环线程中执行，阻塞整个事件循环，造成应用在高并发下卡死。

## 变更内容

对工单模块 6 个 Controller 文件中共 64 个阻塞接口进行修复，统一使用 `run_in_threadpool` 包装所有同步 DB 调用。

### 改造方式

在每个阻塞接口中，将同步 Service 调用从：
```python
result = TicketService.some_method(query_db, ...)
```
改为：
```python
result = await run_in_threadpool(TicketService.some_method, query_db, ...)
```

### 涉及文件

| 文件 | 修复接口数 |
|------|-----------|
| `server/modules/ticket/controller/ticket_crud_controller.py` | 19 |
| `server/modules/ticket/controller/ticket_issue_controller.py` | 11 |
| `server/modules/ticket/controller/ticket_ai_controller.py` | 6 |
| `server/modules/ticket/controller/ticket_config_controller.py` | 11 |
| `server/modules/ticket/controller/ticket_sync_controller.py` | 8 |
| `server/modules/ticket/controller/ticket_log_pull_controller.py` | 9 |

### 无需改动的文件

以下 Controller 在本次改造前已正确使用 `run_in_threadpool`，无需修改：

- `ticket_controller.py`（1 个接口，已安全）
- `ticket_release_controller.py`（2 个接口，已安全）
- `ticket_version_controller.py`（7 个接口，已安全）

### 特殊处理

`extract_ticket_knowledge` 接口（`ticket_crud_controller.py`）在 async 函数中直接调用了 `query_db.commit()` 和 `query_db.rollback()`，改为通过 `run_in_threadpool` 包装。

## 影响范围

- 仅改动 Controller 层，不改动 Service 层和 DAO 层
- 不影响数据库 Session 的生命周期管理
- 不影响接口的请求/响应契约
- 所有接口行为语义不变，仅 DB 调用从阻塞事件循环改为放入线程池执行

## 验证结果

- `ruff check` 全部通过，无代码规范问题