# 配置任务阶段审批、产物与报告归档切片

## 变更

- 新增 `configuration_task_stage`（版本阶段定义，随版本冻结）、`configuration_task_run_stage`（运行阶段快照）、`configuration_task_artifact`（运行产物引用）三张表；迁移脚本 `server/sql/20260919_configuration_task_stage_artifact.sql`。
- 版本阶段切分接口（草稿可改，最多 20 个阶段，步骤索引不重叠）；运行创建时快照阶段，`WRITE` 模式创建即进入 `WAITING_APPROVAL`。
- 审批接口：通过后阶段回到 `PENDING` 等待执行；拒绝则阶段与运行收敛 `CANCELLED`（`STAGE_REJECTED`）。阶段失败自动跳过后续阶段；重试接口对 `WRITE` 阶段强制重新审批。
- 产物链路：Agent 失败步骤自动截图（Base64 事件上报 `web_run_artifact`），服务端登记 `agent_local` READY 资源并写入产物引用；同内容重复上报幂等。
- 报告归档：读取运行/阶段/产物数据生成 Word 兼容 HTML 文件（`.doc`），保存到服务端 `storage/configuration-task-reports/`，登记为资源（provider_execution_side=server）并关联产物；可选飞书机器人通知（复用统一飞书配置，失败不影响归档）。
- 新增权限码：`configuration_task:task:approve`、`configuration_task:artifact:upload`、`configuration_task:report:generate`。

## 边界

- Agent 截图为失败步骤自动触发，成功步骤截图和执行日志产物预留类型但未在 Agent 端默认开启；
- 报告产物文件的下载/预览接口未提供（资源下载链路属于后续切片）；
- 阶段执行当前为"运行整体一次性下发、阶段按步骤事件推进状态"，阶段间暂停（审批）依赖审批完成前运行仍在执行窗口内，跨进程长挂起场景需配合运行超时和孤儿恢复任务使用；
- 定时触发运行、批量编排、飞书文档在线预览仍未实现。

## 验证

- 新增 6 项测试：单阶段兜底快照、审批拒绝取消运行、审批通过重置状态、失败跳过后续阶段、WRITE 重试重新审批、截图产物登记与幂等；全量相关 36 项测试通过。
- Ruff、Python 编译、前端生产构建通过；真实 Agent 端到端联调仍待执行。
