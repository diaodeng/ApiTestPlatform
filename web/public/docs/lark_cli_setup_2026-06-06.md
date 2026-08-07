# Lark CLI 配置记录

- 日期：2026-06-06
- 结果：已将本机 `lark-cli` 配置切换为新的飞书应用
- 配置方式：`lark-cli config init --app-id cli_a9523b9e7f389cb0 --app-secret-stdin --brand feishu`
- 配置落点：`C:\Users\xj\.lark-cli\config.json`

## 说明

- 仅写入本机 CLI 配置，不改动项目业务代码。
- 这次没有执行登录授权流程，因为当前需求只要求完成应用配置。
- 如果后续需要在项目里读取该应用凭证，建议再补一层环境变量或服务端配置映射，避免把密钥写入代码仓库。
