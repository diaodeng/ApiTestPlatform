-- 工单群推送话题锚点独立建表 + AI 分析任务回帖幂等列
-- 背景：锚点（group_push_message_refs）与回帖幂等记录（ai_result_reply_task_ids）原存于
-- ticket.extra_data JSON，被外部同步更新等链路的 build_meta 白名单重建静默擦除，
-- 导致 AI 结果回帖因"无群消息锚点"被跳过（生产工单 INC00001934853 / INC00001934853R）。
-- 拆为独立表后锚点不再参与 extra_data 整包读改写，幂等由任务表列承担。
-- 注意：
-- 1. MySQL DDL 会隐式提交，请在维护窗口执行；
-- 2. 执行顺序：先执行本 DDL，再执行回填脚本
--    scripts/migrate_group_push_anchor.py（从 extra_data JSON 回填存量锚点与幂等标记），
--    最后部署新版服务端（新版读写全部走新表，extra_data 旧键停止读写）。

-- 1. 群推送话题锚点表：一条工单信息群消息一行（一工单可多行，发几个群记几条）
CREATE TABLE IF NOT EXISTS ticket_group_push_anchor (
    id BIGINT NOT NULL COMMENT '锚点ID',
    ticket_id BIGINT NOT NULL COMMENT '工单ID',
    chat_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '飞书群chat_id',
    message_id VARCHAR(64) NOT NULL COMMENT '飞书消息ID（回帖/入站匹配锚点）',
    root_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '飞书根消息ID（话题根）',
    thread_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '飞书话题ID',
    receive_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '发送目标ID',
    receive_id_type VARCHAR(20) NOT NULL DEFAULT '' COMMENT '发送目标类型：chat_id/email',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '写入时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_ticket_group_push_anchor_message (message_id),
    INDEX idx_ticket_group_push_anchor_ticket (ticket_id, create_time),
    INDEX idx_ticket_group_push_anchor_root (root_id),
    INDEX idx_ticket_group_push_anchor_thread (thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单群推送话题锚点表';

-- 2. AI 分析任务回帖幂等列：回帖成功时间与覆盖群审计
--    判定语义：result_replied_at IS NULL 即未回帖（原 extra_data.ai_result_reply_task_ids 列表的替代）
ALTER TABLE ticket_ai_analysis_task
    ADD COLUMN result_replied_at DATETIME NULL DEFAULT NULL COMMENT 'AI结果回帖成功时间，NULL表示未回帖' AFTER active_lock,
    ADD COLUMN result_replied_chat_ids VARCHAR(512) NULL DEFAULT NULL COMMENT '本次回帖覆盖的群chat_id列表，逗号分隔（审计用）' AFTER result_replied_at;
