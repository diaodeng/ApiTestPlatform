-- 2026-08-30 工单相似度画像、精确信号、案例生命周期和向量用途隔离
-- 说明：脚本按 MySQL 8 语法编写；执行前请在目标环境确认字段、索引和表不存在。

ALTER TABLE embedding_record
    ADD COLUMN embedding_scope VARCHAR(32) NOT NULL DEFAULT 'symptom' COMMENT '向量用途：symptom/case_draft/case_verified' AFTER object_id,
    ADD COLUMN metadata_snapshot JSON NULL COMMENT '生成向量时的检索信号快照' AFTER content_hash,
    ADD COLUMN quality_status VARCHAR(20) NOT NULL DEFAULT 'ready' COMMENT '索引质量状态' AFTER metadata_snapshot,
    ADD COLUMN source_revision INT NULL COMMENT '来源内容版本' AFTER quality_status,
    ADD COLUMN verified_at DATETIME NULL COMMENT '案例确认时间' AFTER source_revision,
    ADD COLUMN verified_by VARCHAR(100) NULL COMMENT '案例确认人' AFTER verified_at;

ALTER TABLE embedding_record
    DROP INDEX uk_embedding_object_model_version,
    ADD UNIQUE INDEX uk_embedding_object_scope_model_version
        (object_type, object_id, embedding_scope, embedding_model, embedding_version),
    ADD INDEX idx_embedding_ticket_scope_model
        (object_type, embedding_scope, embedding_model, embedding_version);

CREATE TABLE ticket_similarity_profile (
    profile_id BIGINT NOT NULL COMMENT '画像ID',
    ticket_id BIGINT NOT NULL COMMENT '工单ID',
    environment VARCHAR(64) NULL DEFAULT '' COMMENT '运行环境',
    normalized_version_key VARCHAR(128) NULL DEFAULT '' COMMENT '归一化版本',
    extraction_source VARCHAR(32) NOT NULL DEFAULT 'rule' COMMENT '提取来源',
    extraction_confidence DECIMAL(5,4) NULL COMMENT '提取置信度',
    profile_revision INT NOT NULL DEFAULT 1 COMMENT '画像版本',
    content_hash VARCHAR(128) NOT NULL DEFAULT '' COMMENT '画像内容哈希',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (profile_id),
    UNIQUE KEY uk_ticket_similarity_profile_ticket (ticket_id),
    KEY idx_ticket_similarity_profile_environment (environment, ticket_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单相似检索画像';

CREATE TABLE ticket_similarity_signal (
    signal_id BIGINT NOT NULL COMMENT '信号ID',
    ticket_id BIGINT NOT NULL COMMENT '工单ID',
    signal_type VARCHAR(32) NOT NULL COMMENT '信号类型',
    signal_value VARCHAR(512) NOT NULL COMMENT '归一化信号值',
    raw_value VARCHAR(512) NULL DEFAULT '' COMMENT '原始信号值',
    source VARCHAR(32) NOT NULL DEFAULT 'rule' COMMENT '信号来源',
    confidence DECIMAL(5,4) NULL COMMENT '信号置信度',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (signal_id),
    UNIQUE KEY uk_ticket_similarity_signal_value (ticket_id, signal_type, signal_value),
    KEY idx_ticket_similarity_signal_lookup (signal_type, signal_value, ticket_id),
    KEY idx_ticket_similarity_signal_ticket_type (ticket_id, signal_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单相似检索精确信号';

CREATE TABLE ticket_similarity_case (
    case_id BIGINT NOT NULL COMMENT '案例ID',
    ticket_id BIGINT NOT NULL COMMENT '工单ID',
    case_status VARCHAR(20) NOT NULL DEFAULT 'none' COMMENT '案例状态：none/draft/verified/rejected',
    case_source VARCHAR(32) NOT NULL DEFAULT '' COMMENT '案例来源',
    case_revision INT NOT NULL DEFAULT 1 COMMENT '案例版本',
    content_hash VARCHAR(128) NOT NULL DEFAULT '' COMMENT '案例文本哈希',
    root_cause_summary LONGTEXT NULL COMMENT '根因摘要',
    solution_summary LONGTEXT NULL COMMENT '解决方案摘要',
    evidence_summary LONGTEXT NULL COMMENT '证据摘要',
    investigation_summary LONGTEXT NULL COMMENT '排查摘要',
    verify_summary LONGTEXT NULL COMMENT '验证摘要',
    reusable TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否可复用',
    verified_by VARCHAR(100) NULL DEFAULT '' COMMENT '确认人',
    verified_at DATETIME NULL COMMENT '确认时间',
    rejected_by VARCHAR(100) NULL DEFAULT '' COMMENT '驳回人',
    rejected_at DATETIME NULL COMMENT '驳回时间',
    reject_reason TEXT NULL COMMENT '驳回原因',
    last_index_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '索引状态',
    last_index_error TEXT NULL COMMENT '最近索引错误',
    last_indexed_at DATETIME NULL COMMENT '最近索引时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (case_id),
    UNIQUE KEY uk_ticket_similarity_case_ticket (ticket_id),
    KEY idx_ticket_similarity_case_status (case_status, reusable, ticket_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单相似处理案例';
