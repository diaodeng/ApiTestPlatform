-- 工单 AI 分析失败响应结构化错误码。
-- 生产环境可在发布前执行；服务启动时也会通过 get_db.py 兼容补齐。

ALTER TABLE ticket_ai_analysis_task
    ADD COLUMN error_code VARCHAR(100) NULL COMMENT '失败错误码';

ALTER TABLE sys_ai_task_execution
    ADD COLUMN error_code VARCHAR(100) NULL COMMENT '失败错误码';
