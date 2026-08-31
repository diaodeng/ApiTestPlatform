---
title: 工单轻量AI测试工作台
date: 2026-08-31
type: feature
scope: server/modules/ticket, web/src
---

# 工单轻量AI测试工作台

## 功能说明

新增轻量 AI 手动测试工作台，支持对信息提取、分类统计、翻译、标题总结、知识提炼五类轻量 AI 任务做试运行：选择工单、Provider、模型和提示词（可临时编辑），查看模型原始输出、解析 JSON、归一化结果、机台校验告警、Token 用量和耗时。

用户说明见 [轻量AI测试工作台](../ticket_ai_test.md)。

## 设计要点

- **测试与生产同构**：提示词变量渲染、机台编号归一化、分类结构化归一化直接复用 `TicketLightAiService` 的生产方法，测试结论对生产行为有参考性。
- **测试与生产隔离**：不读取场景开关、不读写提取缓存、不回写工单业务字段；审计记录任务类型追加 `_test` 后缀，来源类型 `ai_test`。
- **按工程边界拆分**：测试编排独立为 `service/ai/ticket_light_ai_test_service.py`，接口契约独立为 `entity/vo/ticket_ai_test_vo.py`，控制器独立为 `controller/ticket_ai_test_controller.py`，不膨胀既有服务文件。

## 接口

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/ticket/ai-test/options` | 任务类型、Provider、模型目录、提示词模板选项 | `ticket:ai:test:run` |
| GET | `/ticket/ai-test/tickets?keyword=` | 工单号/标题关键字搜索 | 同上 |
| GET | `/ticket/ai-test/context?ticketNo=` | 工单测试上下文（标题/描述/原始入参/当前字段） | 同上 |
| GET | `/ticket/ai-test/prompt-content?templateCode=` | 按编码取模板内容供回填编辑 | 同上 |
| POST | `/ticket/ai-test/run` | 执行一次测试（Pydantic 契约 `TicketAiTestRunModel`） | 同上 |

所有接口均 `run_in_threadpool` 包装模型调用与数据库访问，不阻塞事件循环。

## 变更文件

- 新增 `server/modules/ticket/service/ai/ticket_light_ai_test_service.py`
- 新增 `server/modules/ticket/entity/vo/ticket_ai_test_vo.py`
- 新增 `server/modules/ticket/controller/ticket_ai_test_controller.py`
- 新增 `web/src/api/ticket/aiTest.js`、`web/src/views/ticket/aiTest/index.vue`
- 修改 `server/server.py`（注册路由）、`server/modules/ticket/perms.py`（新增菜单 `ticket.ai.test` 与权限 `ticket:ai:test:run`）

## 验证

- `uv run ruff check` 新增文件全部通过；`server.py` 存量 I001 与本次无关。
- 后端完整导入验证通过（server 模块 + 测试服务 + 5 类任务定义）。
- 前端 `npx vite build --mode production` 构建成功，页面代码进入产物。
- 首次上线修复：`/ticket/ai-test/options` 曾报 500（`string indices must be integers`），原因是构建模板任务类型归属时把 `TASK_DEFAULT_PROMPT_CODES.items()` 解包出的字符串误当字典取键；已修复并用真实数据库连接验证任务类型、Provider、模型目录和提示词模板均正常返回。新增回归测试 `tests/test_ticket_ai_test_options.py` 覆盖该结构。

## 注意事项

- 菜单在服务启动时经 `sync_registered_menus` 自动同步，角色需在角色管理中勾选"轻量AI测试"后可见。
- 测试真实调用 Provider 接口并消耗 Token。
