# 工单同步重启恢复与远端拉取重试修复

## 背景

外部工单推送后，主接口会先入库并把 `extraData.external_sync.sync_state.publish_ready` 标记为 `false`，等待后台 AI/自动化后处理完成后再发布给内网拉取。若服务在该窗口重新部署或异常重启，后台任务可能没有机会把状态恢复为可发布，导致内网拉取长期拿不到新版本。

另外，远端 pending 接口原来在返回数据时会先写入消费方 `delivered_revision`。如果内网已经拿到远端数据，但本地入库失败或进程被重启打断，远端可能认为该 revision 已交付，下一次不再返回，表现为“远端推送能更新，内部拉取后内部数据没有更新”。

## 变更

1. `GET /ticket/sync/pending` 拉取前增加发布状态自愈：当工单处于 `processing_ai` 且没有活动 AI 任务时，自动恢复为 `publish_ready=true`，允许内网继续拉取。
2. DAO 候选查询不再直接过滤 `processing_ai` 数据，让服务层有机会判断是否可恢复，避免卡死在未发布状态。
3. `/ticket/sync/pending` 返回数据时只写入 `status=pulled` 和 `last_revision` 租约，不再直接确认 `delivered_revision`；30 分钟内避免重复返回，超过租约未成功回执则允许重试。
4. `/ticket/sync/ack` 处理 failed 回执时不推进 `delivered_revision`，只记录失败状态、失败 revision 和错误信息；只有 `delivered/success/succeeded` 才推进交付版本。
5. 内网远端拉取入库判断优先使用远端 `syncRevision/sourceRevision`：远端有有效 revision 且本地缺少 sourceRevision 时允许覆盖一次，避免因本地导入时间较新而误判跳过更新。

## 影响范围

- 影响公网 pending 拉取、ack 回执和内网远端拉取入库判断。
- 不改变 `/ticket/sync/external` 外部推送字段契约。
- 成功 ack 后的幂等逻辑不变；未 ack 或 failed ack 的版本会保留重试机会。

## 验证

- `python -m py_compile server/modules/ticket/service/ticket_sync_service.py server/modules/ticket/dao/ticket_dao.py`
- `uv run ruff check modules/ticket/service/ticket_sync_service.py modules/ticket/dao/ticket_dao.py`
