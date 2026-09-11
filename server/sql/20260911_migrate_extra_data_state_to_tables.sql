-- =============================================================================
-- 工单扩展字段状态数据迁移脚本（拆表回填，纯 SQL 版）
-- =============================================================================
-- 用途：把原存于 ticket.extra_data.external_sync.sync_state JSON 中的状态数据
--       回填到拆分后的三处结构化存储：
--   ① 话题锚点 group_push_message_refs   -> ticket_group_push_anchor 表（阶段一）
--   ② 回帖幂等 ai_result_reply_task_ids  -> ticket_ai_analysis_task.result_replied_at 列（阶段一）
--   ③ 发布/群推送执行状态 publish_* 等   -> ticket_sync_process_state 宽表（阶段 2b）
--
-- 前置条件（顺序不可颠倒）：
--   1. 已执行 sql/20260911_ticket_group_push_anchor.sql（锚点表 + 任务表加列）
--   2. 已执行 sql/20260911_ticket_sync_process_state.sql（宽表建表）
--   3. 本脚本（回填）
--   4. 部署阶段一 / 2b 服务层切换版本
--
-- 特性：
--   - 幂等可重跑：① 靠 message_id 唯一键冲突跳过；② 靠 result_replied_at IS NULL 条件；
--     ③ 靠 ticket_id 主键 ON DUPLICATE KEY 跳过；重复执行不产生重复数据。
--   - 与 scripts/migrate_group_push_anchor.py（Python 版）覆盖范围 ①② 等价，二者择一执行即可。
--   - 本脚本只做 INSERT/UPDATE 回填，不删除不修改 extra_data 原文（旧键由服务切换版本停止读写后自然失活）。
--   - 生产验证：OceanBase_CE 4.3.5.5（MySQL 模式）实测支持 JSON_TABLE，但不支持
--     DEFAULT ... ON EMPTY（缺失键返回 NULL 由外层 COALESCE 兜底）；extra_data 为
--     LONGTEXT 存 JSON 字符串，均经 CAST(... AS JSON) 解析。
--   - LONGTEXT 全表 LIKE 扫描超过 OB 默认 10 秒查询超时，各语句带 /*+ query_timeout(...) */
--     hint 放宽到 10 分钟（原生 MySQL 忽略未知优化器 hint，不影响兼容性）。
--
-- 执行后核对（只读）：
--   SELECT COUNT(*) FROM ticket_group_push_anchor;                          -- ① 锚点行数
--   SELECT COUNT(*) FROM ticket_ai_analysis_task WHERE result_replied_at IS NOT NULL;  -- ② 幂等标记数
--   SELECT COUNT(*) FROM ticket_sync_process_state;                          -- ③ 状态行数
-- =============================================================================


-- =============================================================================
-- ① 话题锚点回填：group_push_message_refs JSON 数组 -> ticket_group_push_anchor
-- =============================================================================
-- id 用固定迁移基数 + CRC32(message_id+ticket_id) 生成：同一条锚点重跑生成相同 id，
-- 配合 message_id 唯一键与 ON DUPLICATE 跳过，幂等且不与运行期雪花 ID 冲突
-- （基数 2.03e18 远大于当前雪花 ID 量级 2.05e15，BIGINT 上限 9.2e18 内）。
INSERT /*+ query_timeout(600000000) */ INTO ticket_group_push_anchor
    (id, ticket_id, chat_id, message_id, root_id, thread_id, receive_id, receive_id_type, create_time)
SELECT
    2026091100000000000 + CRC32(CONCAT(jt.ticket_id, ':', jt.message_id)) % 999999937 AS id,
    jt.ticket_id,
    jt.chat_id,
    jt.message_id,
    jt.root_id,
    jt.thread_id,
    jt.receive_id,
    jt.receive_id_type,
    COALESCE(NULLIF(jt.sent_at, ''), NOW())
FROM (
    SELECT s.ticket_id,
           TRIM(jt_raw.message_id) AS message_id,
           COALESCE(NULLIF(TRIM(jt_raw.chat_id), ''), '')      AS chat_id,
           COALESCE(NULLIF(TRIM(jt_raw.root_id), ''), '')      AS root_id,
           COALESCE(NULLIF(TRIM(jt_raw.thread_id), ''), '')    AS thread_id,
           COALESCE(NULLIF(TRIM(jt_raw.receive_id), ''), '')   AS receive_id,
           COALESCE(NULLIF(TRIM(jt_raw.receive_id_type), ''), '') AS receive_id_type,
           jt_raw.sent_at
    FROM (
        SELECT ticket_id, CAST(extra_data AS JSON) AS j
        FROM ticket
        WHERE del_flag = '0' AND extra_data LIKE '%group_push_message_refs%'
    ) s,
    JSON_TABLE(
        s.j,
        '$.external_sync.sync_state.group_push_message_refs[*]'
        COLUMNS (
            -- OceanBase 4.3 不支持 DEFAULT ... ON EMPTY，缺失键返回 NULL 由外层 COALESCE 兜底
            message_id      VARCHAR(64) PATH '$.messageId',
            root_id         VARCHAR(64) PATH '$.rootId',
            thread_id       VARCHAR(64) PATH '$.threadId',
            chat_id         VARCHAR(64) PATH '$.chatId',
            receive_id      VARCHAR(64) PATH '$.receiveId',
            receive_id_type VARCHAR(20) PATH '$.receiveIdType',
            sent_at         VARCHAR(40) PATH '$.sentAt'
        )
    ) jt_raw
) jt
WHERE jt.message_id IS NOT NULL AND jt.message_id <> ''
ON DUPLICATE KEY UPDATE id = ticket_group_push_anchor.id;


-- =============================================================================
-- ② 回帖幂等回填：ai_result_reply_task_ids JSON 数组 -> result_replied_at 列
-- =============================================================================
-- 仅标记尚未标记的任务（result_replied_at IS NULL），重跑安全；
-- 非数字任务 ID 元素 CAST 后为 0，JOIN 不中任何任务行，自动忽略。
UPDATE /*+ query_timeout(600000000) */ ticket_ai_analysis_task t
JOIN (
    SELECT jt.ticket_id, CAST(jt.task_id_text AS UNSIGNED) AS task_id_num
    FROM (
        SELECT ticket_id, CAST(extra_data AS JSON) AS j
        FROM ticket
        WHERE del_flag = '0' AND extra_data LIKE '%ai_result_reply_task_ids%'
    ) s,
    JSON_TABLE(
        s.j,
        '$.external_sync.sync_state.ai_result_reply_task_ids[*]'
        COLUMNS (task_id_text VARCHAR(32) PATH '$')
    ) jt
    WHERE jt.task_id_text IS NOT NULL AND jt.task_id_text REGEXP '^[0-9]+$'
) m ON m.task_id_num = t.task_id AND m.ticket_id = t.ticket_id
SET t.result_replied_at = NOW()
WHERE t.result_replied_at IS NULL;


-- =============================================================================
-- ③ 发布/群推送执行状态回填：sync_state 状态键 -> ticket_sync_process_state 宽表
-- =============================================================================
-- 仅回填状态键非默认的工单：无任何状态键的工单不建行（DAO 按默认态处理：
-- publish_ready=1、未推送过）；状态键值缺失时按原 build_meta 默认值回填。
-- 时间字段为 ISO 字符串（如 2026-09-08T09:46:43.222571），REPLACE T 后 CAST DATETIME(6)。
INSERT /*+ query_timeout(600000000) */ INTO ticket_sync_process_state
    (ticket_id,
     publish_ready, publish_status, publish_reason, publish_updated_at, ai_task_status,
     push_sent_once, push_sent_at, push_scene, push_revision,
     push_processing, push_processing_at, push_processing_scene, push_processing_revision,
     update_by)
SELECT
    s.ticket_id,
    -- publish_ready：JSON 布尔，'false' -> 0，其余（含缺失）-> 1
    CASE WHEN JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.publish_ready')) = 'false'
         THEN 0 ELSE 1 END,
    -- publish_status：空/缺失回退 ready（对齐 build_meta 默认）
    COALESCE(
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.publish_status')), ''),
        'ready'
    ),
    COALESCE(
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.publish_reason')), ''),
        ''
    ),
    -- publish_updated_at / push_sent_at / push_processing_at：ISO 时间字符串转 DATETIME
    CAST(REPLACE(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.publish_updated_at')), 'T', ' ') AS DATETIME(6)),
    COALESCE(
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.ai_task_status')), ''),
        ''
    ),
    CASE WHEN JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.group_push_sent_once')) = 'true'
         THEN 1 ELSE 0 END,
    CAST(REPLACE(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.group_push_sent_at')), 'T', ' ') AS DATETIME(6)),
    COALESCE(
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.group_push_scene')), ''),
        ''
    ),
    COALESCE(CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.group_push_revision')), '') AS SIGNED), 0),
    CASE WHEN JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.group_push_processing')) = 'true'
         THEN 1 ELSE 0 END,
    CAST(REPLACE(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.group_push_processing_at')), 'T', ' ') AS DATETIME(6)),
    COALESCE(
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.group_push_processing_scene')), ''),
        ''
    ),
    COALESCE(CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(s.j, '$.external_sync.sync_state.group_push_processing_revision')), '') AS SIGNED), 0),
    'migration_20260911'
FROM (
    SELECT ticket_id, CAST(extra_data AS JSON) AS j
    FROM ticket
    WHERE del_flag = '0'
      AND (extra_data LIKE '%"publish_ready":false%'
           OR extra_data LIKE '%group_push_sent_once%'
           OR extra_data LIKE '%group_push_processing%'
           OR extra_data LIKE '%ai_task_status%')
) s
ON DUPLICATE KEY UPDATE ticket_id = ticket_sync_process_state.ticket_id;
