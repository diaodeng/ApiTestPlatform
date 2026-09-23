# 配置任务运行域最小闭环

## 变更

- 新增 `configuration_task`、`configuration_task_version`、`configuration_task_run` 三张表及 ORM/DAO；生产迁移脚本为 `server/sql/20260919_configuration_task_version.sql` 和 `server/sql/20260919_configuration_task_run.sql`。
- 新增任务 CRUD、版本草稿、版本发布接口；发布校验步骤非空、绑定资源 `READY` 且资源 Agent 与任务执行 Agent 一致，发布成功后更新任务当前版本指针。
- 新增运行接口：创建运行时冻结版本快照和输入资源摘要，按既有 `run_case` 协议下发 Agent，输入绑定注入 `runtimeOptions.resourceBindings`，由 Agent 端 `upload_file` 受控解析；终态 `SUCCESS/FAILED` 落库。
- 权限码新增 `configuration_task:task:list/query/add/edit/publish/run`，路由注册于 `server.py`。

## 边界

本切片不提供阶段编排、`PREPARE_WRITE/WRITE` 审批闸门、截图/日志产物登记、Word/飞书报告归档、运行取消/恢复/定时触发；运行同步等待 Agent 返回。生产环境写操作仍需人工确认。

## 验证

- 服务端测试覆盖：发布拒绝未就绪/跨 Agent 资源、发布成功更新版本指针、运行拒绝未发布版本和未就绪资源、运行成功/失败终态与 `resourceBindings` 注入，全部通过（含既有资源、传输、会话回归共 23 项）。
- 运行执行链路的同步 DB 段（前置校验/建记录、成功终态、失败终态）通过 `run_in_threadpool` 在线程池执行，事件循环内只做 await，不阻塞其他异步接口；Agent 等待段为 Future 异步等待，并配置 30 分钟运行超时避免长任务被默认 120 秒误杀。
- 相关 Ruff、Python 编译通过；前端生产构建通过。
- 真实 Agent 端到端联调仍未执行。
