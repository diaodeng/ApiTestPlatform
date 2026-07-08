-- 2026-07-08 工单真实问题实例归因层
-- 说明：
-- 1. ticket_issue 承载一个真实问题实例；
-- 2. ticket.issue_id / issue_relation_type / issue_confirmed 保存工单主归因；
-- 3. ticket_relation 仅保存补充关系，不替代主归因字段。

SET @db_name = DATABASE();

SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'CREATE TABLE ticket_issue (
            issue_id BIGINT NOT NULL COMMENT ''问题实例ID'',
            issue_no VARCHAR(64) NOT NULL COMMENT ''问题实例编号'',
            title VARCHAR(500) NOT NULL COMMENT ''问题标题'',
            summary LONGTEXT NULL COMMENT ''问题摘要'',
            status VARCHAR(32) NOT NULL DEFAULT ''open'' COMMENT ''问题状态'',
            severity VARCHAR(50) NULL DEFAULT '''' COMMENT ''严重等级'',
            project_id BIGINT NULL COMMENT ''所属项目ID'',
            project_name VARCHAR(200) NULL DEFAULT '''' COMMENT ''所属项目名称'',
            module_id BIGINT NULL COMMENT ''所属模块ID'',
            module_name VARCHAR(128) NULL DEFAULT '''' COMMENT ''所属模块名称'',
            root_cause_type VARCHAR(128) NULL DEFAULT '''' COMMENT ''根因分类'',
            problem_pattern_code VARCHAR(128) NULL DEFAULT '''' COMMENT ''细分问题类型编码'',
            problem_pattern_name VARCHAR(256) NULL DEFAULT '''' COMMENT ''细分问题类型名称'',
            owner_id BIGINT NULL COMMENT ''负责人ID'',
            owner_name VARCHAR(100) NULL DEFAULT '''' COMMENT ''负责人名称'',
            first_ticket_id BIGINT NULL COMMENT ''首张工单ID'',
            affected_ticket_count INT NOT NULL DEFAULT 0 COMMENT ''影响工单数'',
            del_flag CHAR(1) NOT NULL DEFAULT ''0'' COMMENT ''删除标志（0存在 2删除）'',
            create_by VARCHAR(100) NULL DEFAULT '''' COMMENT ''创建者'',
            update_by VARCHAR(100) NULL DEFAULT '''' COMMENT ''更新者'',
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT ''创建时间'',
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT ''更新时间'',
            PRIMARY KEY (issue_id),
            UNIQUE KEY uk_ticket_issue_no (issue_no),
            KEY idx_ticket_issue_del_status_update (del_flag, status, update_time, issue_id),
            KEY idx_ticket_issue_del_project_module (del_flag, project_id, module_id, issue_id),
            KEY idx_ticket_issue_del_pattern (del_flag, problem_pattern_code, issue_id)
        ) COMMENT=''工单真实问题实例表''',
        'SELECT ''ticket_issue already exists'''
    )
    FROM information_schema.tables
    WHERE table_schema = @db_name AND table_name = 'ticket_issue'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'CREATE TABLE ticket_relation (
            relation_id BIGINT NOT NULL COMMENT ''关系ID'',
            source_ticket_id BIGINT NOT NULL COMMENT ''源工单ID'',
            target_ticket_id BIGINT NOT NULL COMMENT ''目标工单ID'',
            relation_type VARCHAR(32) NOT NULL DEFAULT ''similar'' COMMENT ''关系类型'',
            confidence DOUBLE NULL COMMENT ''关系置信度，0-1'',
            source VARCHAR(32) NOT NULL DEFAULT ''manual'' COMMENT ''关系来源'',
            confirmed TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''是否人工确认'',
            remark TEXT NULL COMMENT ''备注'',
            del_flag CHAR(1) NOT NULL DEFAULT ''0'' COMMENT ''删除标志（0存在 2删除）'',
            create_by VARCHAR(100) NULL DEFAULT '''' COMMENT ''创建者'',
            update_by VARCHAR(100) NULL DEFAULT '''' COMMENT ''更新者'',
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT ''创建时间'',
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT ''更新时间'',
            PRIMARY KEY (relation_id),
            UNIQUE KEY uk_ticket_relation_pair_type (source_ticket_id, target_ticket_id, relation_type),
            KEY idx_ticket_relation_source (source_ticket_id, relation_type, del_flag),
            KEY idx_ticket_relation_target (target_ticket_id, relation_type, del_flag)
        ) COMMENT=''工单补充关系表''',
        'SELECT ''ticket_relation already exists'''
    )
    FROM information_schema.tables
    WHERE table_schema = @db_name AND table_name = 'ticket_relation'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE ticket ADD COLUMN issue_id BIGINT NULL COMMENT ''归属问题实例ID'' AFTER problem_pattern_verified_at',
        'SELECT ''ticket.issue_id already exists'''
    )
    FROM information_schema.columns
    WHERE table_schema = @db_name AND table_name = 'ticket' AND column_name = 'issue_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE ticket ADD COLUMN issue_relation_type VARCHAR(32) NULL DEFAULT '''' COMMENT ''问题实例归属类型'' AFTER issue_id',
        'SELECT ''ticket.issue_relation_type already exists'''
    )
    FROM information_schema.columns
    WHERE table_schema = @db_name AND table_name = 'ticket' AND column_name = 'issue_relation_type'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE ticket ADD COLUMN issue_confirmed TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''问题归因是否人工确认'' AFTER issue_relation_type',
        'SELECT ''ticket.issue_confirmed already exists'''
    )
    FROM information_schema.columns
    WHERE table_schema = @db_name AND table_name = 'ticket' AND column_name = 'issue_confirmed'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'CREATE INDEX idx_ticket_del_issue ON ticket (del_flag, issue_id, ticket_id)',
        'SELECT ''idx_ticket_del_issue already exists'''
    )
    FROM information_schema.statistics
    WHERE table_schema = @db_name AND table_name = 'ticket' AND index_name = 'idx_ticket_del_issue'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
