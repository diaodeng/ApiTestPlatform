-- AI Provider 能力模型重构
-- 执行前请备份 sys_ai_provider；本脚本不保留 provider_type / extra_config 等旧字段兼容。
-- 运行后，所有现有 Provider 必须在系统管理页面重新确认平台、协议、用途和执行器。
-- MySQL DDL 会隐式提交，不能依赖事务回滚；请在维护窗口执行并验证每个语句。

ALTER TABLE sys_ai_provider
    CHANGE COLUMN model_name default_model VARCHAR(128) NOT NULL DEFAULT '' COMMENT '默认模型名称',
    CHANGE COLUMN agent_code preferred_agent_code VARCHAR(64) NULL DEFAULT '' COMMENT '首选Agent编码',
    CHANGE COLUMN extra_config worker_env JSON NULL COMMENT 'Worker环境变量覆盖配置',
    ADD COLUMN platform_code VARCHAR(64) NULL COMMENT '平台编码' ,
    ADD COLUMN api_protocol VARCHAR(64) NULL COMMENT 'API调用协议' ,
    ADD COLUMN supported_usages JSON NULL COMMENT '允许的业务用途' ,
    ADD COLUMN supported_executors JSON NULL COMMENT '兼容的执行器' ,
    ADD COLUMN connection_config JSON NULL COMMENT '协议连接扩展配置' ;

-- 只迁移平台的明确部分；旧 llm/custom 不猜测其真实协议，统一要求管理员重新配置。
UPDATE sys_ai_provider
SET platform_code = CASE provider_type
    WHEN 'openai' THEN 'openai'
    WHEN 'azure_openai' THEN 'azure_openai'
    WHEN 'ollama' THEN 'ollama'
    ELSE 'custom'
END,
api_protocol = 'custom',
supported_usages = JSON_ARRAY(),
supported_executors = JSON_ARRAY();

-- 删除旧的混合类型字段。执行此语句后不可再依赖 provider_type。
ALTER TABLE sys_ai_provider
    DROP COLUMN provider_type,
    MODIFY COLUMN platform_code VARCHAR(64) COMMENT '平台编码',
    MODIFY COLUMN api_protocol VARCHAR(64) COMMENT 'API调用协议',
    MODIFY COLUMN supported_usages JSON COMMENT '允许的业务用途',
    MODIFY COLUMN supported_executors JSON COMMENT '兼容的执行器';

CREATE TABLE sys_ai_provider_model (
    provider_model_id INT NOT NULL AUTO_INCREMENT COMMENT '模型目录主键',
    provider_id INT NOT NULL COMMENT 'Provider主键',
    model_id VARCHAR(255) NOT NULL COMMENT '上游模型标识',
    display_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '模型展示名称',
    source VARCHAR(32) NOT NULL COMMENT '目录来源：remote/manual',
    enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否可选',
    capability_overrides JSON NULL COMMENT '模型级能力覆盖',
    discovered_at DATETIME NULL COMMENT '最近发现时间',
    last_seen_at DATETIME NULL COMMENT '最近一次出现在远端目录的时间',
    create_time DATETIME NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (provider_model_id),
    UNIQUE KEY uq_sys_ai_provider_model_provider_model (provider_id, model_id),
    CONSTRAINT fk_sys_ai_provider_model_provider
        FOREIGN KEY (provider_id) REFERENCES sys_ai_provider(provider_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI Provider模型目录缓存';

-- 必做：在系统管理页面逐条补齐以下字段后再启用Provider。
-- platform_code: openai / openai_compatible / azure_openai / anthropic / ollama / custom
-- api_protocol: openai_chat_completions / openai_responses / azure_openai_chat / anthropic_messages / ollama_chat / custom
-- supported_usages: 例如 ["ticket_light_text","provider_model_discovery"] 或 ["ticket_analysis_worker"]
-- supported_executors: 例如 ["direct_http"] 或 ["codex"]
-- Azure 需填写 connection_config：{"deployment":"部署名","apiVersion":"2024-10-21"}
