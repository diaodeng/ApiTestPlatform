# 统一凭证新增「大数据查询」业务场景

- 统一凭证管理的业务绑定新增「大数据查询」（`external_data_query`）业务场景选项。
- 后端绑定契约 `CredentialBindingSaveModel.business_type` 与 `CredentialBindingOptionQueryModel.business_type` 枚举加入 `external_data_query`；`CredentialBindingService.validate_binding` 允许该场景使用 `http_header / http_cookie` 投影。
- 前端 `web/src/views/system/credential/index.vue` 的业务场景下拉新增「大数据查询」选项。
- 本阶段仅打通"纳入统一凭证 + 创建业务绑定"，尚未接通到具体的大数据查询执行链路；`workbenchCode` 等非敏感参数和查询请求组装留待下一阶段。