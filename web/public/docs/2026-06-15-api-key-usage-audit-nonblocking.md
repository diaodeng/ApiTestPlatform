# API Key 使用审计非阻断处理

## 背景

远端推送工单时偶发 MySQL `OperationalError: (2013, 'Lost connection to MySQL server during query (timed out)')`。
堆栈显示失败 SQL 为：

```sql
UPDATE sys_api_key
SET last_used_ip = ?, last_used_time = ?
WHERE sys_api_key.api_key_id = ? AND sys_api_key.del_flag = '0'
```

该操作发生在 API Key 鉴权阶段，用于记录最后使用 IP 和时间，属于审计字段更新，不是工单入库的必要业务数据。

## 结论

该异常不是正常业务异常，也不是典型的唯一键并发冲突；它是 MySQL 查询期间连接读超时。并发高、数据库慢查询、连接池压力或网络抖动都可能放大出现概率。

## 本次调整

- API Key 有效性读取和校验仍在主请求链路中执行，保证认证安全不降级。
- `last_used_ip/last_used_time` 更新改为独立数据库会话单独提交。
- 审计更新失败时只写 warning 日志并回滚审计会话，不再抛出异常，不影响远端推单入库。

## 影响范围

- 修改文件：`server/module_admin/service/api_key_service.py`
- 业务影响：远端推单不会再因为 API Key 最后使用时间更新失败而被 500 中断。
- 审计影响：极端情况下某次请求的 `last_used_ip/last_used_time` 可能没有更新，但 API Key 鉴权和工单数据入库不受影响。

## 后续建议

如果仍看到 API Key 读取阶段或工单入库阶段的 MySQL 2013，需要继续排查数据库负载、慢 SQL、连接池配置、MySQL `wait_timeout`/网络超时和公网推送并发量。
