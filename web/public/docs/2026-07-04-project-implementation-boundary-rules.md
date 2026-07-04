# 项目实现边界规则

## 日期

2026-07-04

## 目的

固化 api-test-platform 的实现规则，避免后续新增功能再次把业务、接口、配置、通知、外部调用和工具方法堆进同一个大文件。后续 AI 或人工实现功能时，应先按本规则判断职责归属，再写代码。

## 总体原则

1. 先按作用域拆分，再实现业务逻辑。
2. 一个文件只承接一个清晰职责，不因为调用方便把无关方法塞入已有大 service。
3. 跨链路共享能力下沉到独立子服务或 util，不通过函数内导入、延迟代理、主服务门面规避依赖。
4. 拆分时必须同步更新所有调用方和测试，不保留只做转发的兼容 shim。
5. 修改已有业务链路时，要对照历史分支、现有测试或当前文档，确认字段语义和副作用不变。
6. 子服务对外提供的方法必须使用公开命名，不允许以 `_` 开头；`_xxx` 只表示类内部私有辅助方法，外部调用私有方法必须在本次改动中改名或下沉。

## 后端分层职责

| 层级 | 允许职责 | 禁止事项 |
|---|---|---|
| controller | 路由、权限、参数模型、异步接口里的 `run_in_threadpool`、响应包装 | 写业务状态机、调用外部 API、拼复杂 payload |
| service | 单一业务能力编排，如同步入库、主动拉取、评论同步、通知任务、AI 分类 | 一个 service 同时承接多个业务域；通过主服务做兼容转发 |
| dao | 查询、插入、更新、删除和必要的数据库表达式 | 调外部系统、发通知、执行 AI、解析复杂业务字段 |
| util | 无数据库和无网络副作用的纯工具，如字段归一化、哈希、时间解析、JSON 安全转换 | 读取系统参数、写数据库、发 HTTP 请求 |
| scheduler | 解析任务参数、停止标记、创建会话、调用 service | 在任务函数里实现大段业务逻辑 |

## 文件规模与拆分触发条件

出现以下任一情况时，应优先新建或拆出子服务，而不是继续扩充原文件：

1. 新能力有独立入口，例如新 API、新定时任务、新外部事件、新后台任务。
2. 新能力的配置、字段映射、外部 API 或状态机可以独立命名。
3. 方法需要被多个服务复用，但本身不依赖上层主服务。
4. 同一文件已经包含多个业务主题，例如同步、通知、评论、AI、日志、远端拉取混在一起。
5. 为了解决循环引用而想在函数内 import 上层服务。

推荐命名方式：

1. 配置归一和系统参数：`*_config_service.py`
2. 主动拉取或远端拉取：`*_pull_service.py`、`*_remote_sync_service.py`
3. 通知任务编排：`*_notification_job_service.py`
4. 评论和消息同步：`*_comment_service.py`、`*_message_sync_service.py`
5. 无副作用字段转换：`*_util.py`

## 工单域当前约束

1. `TicketSyncService` 只保留外部同步入库、远端拉取、延后后处理和核心同步编排的未拆部分。
2. 飞书多维表格主动拉取由 `TicketBitablePullService` 承接。
3. 人员催办和汇总统计通知任务由 `TicketSyncNotificationJobService` 承接。
4. 外部推送按 recordId 查询飞书多维表格补齐人员邮箱由 `TicketExternalBitableEmailService` 承接。
5. 同步配置由 `TicketSyncConfigService` 承接。
6. 评论同步由 `TicketSyncCommentService` 和 `TicketCommentCoreService` 承接。
7. 群推送和发布状态由 `TicketSyncGroupPushService` 承接。
8. 新增工单同步相关能力时，不能再往 `TicketSyncService` 里直接堆新主题；应先判断是否属于上述子服务或新建子服务。

## 验证要求

1. 每次拆分后用 `rg` 确认旧入口没有生产调用残留。
2. 至少执行改动文件的 `ruff check`。
3. 至少执行覆盖被迁移边界的单测；没有单测时补充最小边界测试。
4. 若涉及 async FastAPI 接口，确认同步服务调用仍通过 `run_in_threadpool` 或后台任务执行。
5. 同步更新 `web/public/docs`、`wiki/entities`、`wiki/flows` 或 `wiki/log.md` 中相关内容。
