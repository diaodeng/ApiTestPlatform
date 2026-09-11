-- 工单同步过程状态宽表（阶段 2b 存储地基：发布域 + 群推送执行域）
-- 背景：发布状态（publish_*）与群推送执行状态（group_push_*）原存于
-- ticket.extra_data.external_sync.sync_state JSON，任何链路写 extra_data 均为整包读改写，
-- AI 终态回调与后处理批次并发时互相覆盖（生产 INC00001934853R 17:32:05/07 实测）；
-- 且群推送去重锁依赖锁 ticket 行，外部同步更新被迫争同一把锁。
-- 拆为一工单一行的宽表后：状态更新为列级 UPDATE 不再互相覆盖；去重锁锁状态行不再锁工单行。
-- 注意：
-- 1. MySQL DDL 会隐式提交，请在维护窗口执行；
-- 2. 本表为阶段 2b 服务层切换的前置存储，建表后即部署无行为影响（新表无人读写）；
-- 3. 服务层切换版本部署前需执行回填脚本（规划中 migrate_sync_process_state.py，
--    从 extra_data.sync_state 的 publish_*/group_push_* 键回填）；
-- 4. automation 步骤状态（sync_state.automation.steps）按设计保留在 JSON，
--    其为白名单透传 dict 非擦除受害者，写入频率低，列化收益不足，不在本表范围。

CREATE TABLE IF NOT EXISTS ticket_sync_process_state (
    ticket_id BIGINT NOT NULL COMMENT '工单ID（一工单一行）',
    -- 发布域：AI 终态/后处理写，delivery 拉取与详情读
    publish_ready TINYINT NOT NULL DEFAULT 1 COMMENT '是否允许对外发布（内网拉取/群推送），1允许 0不允许',
    publish_status VARCHAR(32) NOT NULL DEFAULT 'ready' COMMENT '发布状态编码：ready/processing_ai',
    publish_reason VARCHAR(255) NOT NULL DEFAULT '' COMMENT '状态说明',
    publish_updated_at DATETIME NULL DEFAULT NULL COMMENT '发布状态更新时间',
    ai_task_status VARCHAR(16) NOT NULL DEFAULT '' COMMENT '最近一次AI任务终态状态',
    -- 群推送执行域：群推送链路写（去重与并发锁）
    push_sent_once TINYINT NOT NULL DEFAULT 0 COMMENT '工单信息群消息是否已成功发送过（工单级仅一次标记）',
    push_sent_at DATETIME NULL DEFAULT NULL COMMENT '最近一次群推送成功时间',
    push_scene VARCHAR(32) NOT NULL DEFAULT '' COMMENT '最近一次群推送触发场景',
    push_revision INT NOT NULL DEFAULT 0 COMMENT '群推送状态修订号',
    push_processing TINYINT NOT NULL DEFAULT 0 COMMENT '群推送处理锁标记',
    push_processing_at DATETIME NULL DEFAULT NULL COMMENT '群推送处理锁获取时间',
    push_processing_scene VARCHAR(32) NOT NULL DEFAULT '' COMMENT '群推送处理锁场景',
    push_processing_revision INT NOT NULL DEFAULT 0 COMMENT '群推送处理锁修订号',
    update_by VARCHAR(100) NOT NULL DEFAULT 'system' COMMENT '最近更新人',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (ticket_id),
    INDEX idx_ticket_sync_process_ready (publish_ready, publish_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单同步过程状态表（发布+群推送执行，一工单一行）';
