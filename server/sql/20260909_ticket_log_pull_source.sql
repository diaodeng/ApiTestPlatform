-- 日志拉取记录新增拉取来源字段
-- 区分记录由自动化链路自动创建还是人工在页面创建，用于列表"拉取人"列展示与来源筛选。
-- 注意：MySQL DDL 会隐式提交，请在维护窗口执行。

ALTER TABLE ticket_log_pull_record
    ADD COLUMN pull_source VARCHAR(20) NOT NULL DEFAULT 'manual' COMMENT '拉取来源：manual人工，automation自动化链路' AFTER status_desc,
    ADD COLUMN pull_source_scene VARCHAR(50) NULL DEFAULT NULL COMMENT '自动拉取触发场景：external_sync/remote_pull/bitable_pull/manual_create' AFTER pull_source;

-- 存量数据无需回填：默认 manual，展示层按 command_content._automation.autoCreated 兜底识别历史自动记录。
