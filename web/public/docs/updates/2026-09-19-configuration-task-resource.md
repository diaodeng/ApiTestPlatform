# 配置任务资源元数据切片

## 变更

- 新增 `configuration_task_resource_object` 资源元数据表及 Snowflake BIGINT 主键。
- 新增资源创建、查询、详情和 `ready` 元数据确认契约。
- 首期 Provider 固定为 `agent_local`；服务端资源接口只登记元数据，不接收文件正文。Agent 本地 manifest、受控分片发布协议和 Web `upload_file` 动作已有最小可验证实现；服务端到 Agent 的完整传输编排、SFTP 和任务级资源绑定仍未实现。
- 资源响应的 `resourceId` 统一序列化为字符串。

## 边界

该切片只负责服务端资源身份、校验元数据和状态登记；Agent 本地存储协议和 Web `upload_file` 的客户端最小子集已落地。服务端传输编排、下载授权、截图归档和 SFTP 仍属于后续能力。

## 验证

服务端资源单元测试覆盖 BIGINT ID 字符串化、objectKey 路径校验、SHA-256 归一化及 ready 元数据不匹配失败状态。
