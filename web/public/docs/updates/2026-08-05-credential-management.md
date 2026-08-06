# 2026-08-05 统一凭证管理

- 新增统一凭证、业务绑定、HTTP 投影、HTTP 刷新、审计日志和独占租约能力。
- 远端工单同步与日志拉取不再读取内联 Cookie 或 Authorization，改为凭证绑定 ID。
- 新增 `module_task.scheduler_maintenance.refresh_credentials` 定时任务入口。
- 旧 Web Session/Runtime Profile 数据不迁移；发布后请在统一凭证模块重新配置。
- 录制、回放、执行及新版客户端已停止读取、缓存或自动回写旧 Web Session/Runtime Profile；Web 用例统一选择浏览器凭证绑定。
- 修复绑定选项接口未识别 camelCase 查询参数 `businessType` 导致凭证管理和 Web 测试页面加载失败的问题。
