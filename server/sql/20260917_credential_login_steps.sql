-- 统一凭证多步登录链配置
-- 为 auth_credential_auth_config 增加 login_steps 字段，支持两步及以上认证流程
-- （例如：账号密码登录 -> 从响应提取一次性 ticket -> TOTP 验证 -> 从 Set-Cookie 提取最终凭证）。
-- 存量数据无需回填：login_steps 为 NULL 时继续走原有单步登录/刷新模板逻辑，行为完全不变。
-- MySQL DDL 会隐式提交，请在维护窗口执行。

ALTER TABLE auth_credential_auth_config
    ADD COLUMN login_steps JSON NULL COMMENT '多步登录链配置；为空时回退单步登录模板';
