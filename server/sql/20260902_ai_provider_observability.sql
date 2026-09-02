-- AI Provider 可观测上报配置
-- 为 sys_ai_provider 增加 OTLP 可观测上报字段，用于工单 AI 分析任务级 span 上报
-- 与本地 AI CLI（Codex / Claude Code）的原生 OpenTelemetry 遥测注入。
-- 密文使用与 api_key_cipher_text 相同的 Fernet 加密方案，可复用 Provider 密钥查看入口的解密逻辑。
-- MySQL DDL 会隐式提交，请在维护窗口执行。

ALTER TABLE sys_ai_provider
    ADD COLUMN observability_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否启用可观测上报',
    ADD COLUMN observability_endpoint VARCHAR(500) NULL DEFAULT '' COMMENT 'OTLP上报端点基础地址，如https://agents.dmall.com/observe',
    ADD COLUMN observability_auth_type VARCHAR(32) NULL DEFAULT 'bearer' COMMENT '可观测鉴权类型：bearer/basic',
    ADD COLUMN observability_api_key_prefix VARCHAR(128) NULL DEFAULT '' COMMENT '可观测密钥掩码前缀',
    ADD COLUMN observability_api_key_cipher_text TEXT NULL COMMENT '可观测鉴权密钥密文；bearer存Agent API Key，basic存publicKey:secretKey',
    ADD COLUMN observability_service_name VARCHAR(128) NULL DEFAULT '' COMMENT 'OTLP service.name，留空使用默认值',
    ADD COLUMN observability_cli_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否向本地AI CLI注入原生OpenTelemetry遥测配置';

-- 存量数据无需回填：默认全部关闭，不影响现有任务执行。
