schedule 表（主表）

CREATE TABLE schedules (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    task VARCHAR(255) NOT NULL,
    cron_expr VARCHAR(100) NOT NULL,
    args JSON,
    enabled BOOLEAN DEFAULT TRUE,

    type VARCHAR(20) NOT NULL,       -- single / chain
    template_code VARCHAR(50),        -- 可选：任务模板

    project_id BIGINT,
    owner VARCHAR(50),

    created_at DATETIME,
    updated_at DATETIME
);

执行历史表（强烈推荐）
CREATE TABLE schedule_runs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    schedule_id BIGINT,
    task_id VARCHAR(50),
    status VARCHAR(20),
    started_at DATETIME,
    finished_at DATETIME
);
