# 2026-09-12 桌面客户端 mitmproxy 抓包性能优化（三项）

## 背景

桌面客户端（client_new）mitmproxy 抓包在系统代理模式下所有机器流量过代理，出现应用请求排队响应慢。定位到三个瓶颈：每条流量（含无关系统流量）全量构造 FlowItem 上报 UI；mock 探测每个请求新建 `httpx.AsyncClient`（每条都重建连接 + TLS 握手）；UI 层每条流量逐条触发表格插入 + 统计刷新 + 选中恢复，UI 线程饱和。

## 变更内容

### 1. 流量入口过滤（`services/mitmproxy_service/mock_handle.py` + `model/config.py`）
- 新增配置 `flow_filter_enabled`（默认开）/ `flow_filter_pattern`（默认常见静态资源后缀）。
- 命中规则的流量**完全放行**：不记录到列表、不参与 mock 探测、不参与断点与延迟；request/response 两个钩子都旁路。
- 规则按逗号/换行分隔；`.` 开头按路径后缀匹配（忽略大小写、剔除 query），否则按子串匹配。
- 设置弹窗「路径匹配」组新增「过滤静态资源流量」开关与「过滤路径」编辑框，保存后走既有 update 命令热生效，无需重启代理。

### 2. mock 探测连接复用（`mock_handle.py` + `helper_process.py` + `proxy_core.py`）
- MockHandle 按代理会话持有单个 `httpx.AsyncClient`（连接池上限 50、keepalive 20、30s 过期），探测前清理 cookie，避免 mock 服务端会话状态跨请求残留；探测超时改为单请求参数。
- 事件循环变化（代理重启换 loop）时自动重建客户端，防止绑定已关闭的 loop。
- helper 与进程内两种运行形态在代理会话结束时显式关闭连接池。

### 3. UI 节流（`ui/widgets/flow_event_buffer.py` 新增 + `mitmproxy_models.py` + `mitm_flow_table_widget.py`）
- 新增 `FlowEventBuffer` 缓冲层：普通流量 250ms 定时批量写入模型（定时器制而非计数器制，低频流量最多延迟一个间隔即显示）；缓冲超 500 条立即落盘。
- 模型新增 `add_flows` / `update_flows` 批量接口：整块插入/更新只触发一次 `changed` 信号（统计刷新与选中恢复从每条一次降为每批一次）。
- **断点流量旁路缓冲立即写入**，进入旁路前先落盘存量事件保证顺序，确保暂停中的请求第一时间显示、放行按钮即时可点。
- 批量插入裁剪修正：一次插入超过保留上限时先裁旧行、再丢弃新数据头部，保证总量不超过上限（原 `_trim_before_add` 只能裁现有行，批量场景会超限）。
- 移除 `add_flow` 中逐条格式化整个 FlowItem 的 debug 日志。

## 文档

- 用户说明：`web/public/docs/client/mitm-proxy.md`（新增，含全部配置项与过滤规则语义）。
- 分阶段方案（代理优化 → 插件化瘦身 → pywebview UI → Go 迁移评估）：`wiki/features/client-new-optimization-and-go-migration-plan.md`。

## 验证

- 功能自测 25 项全过：过滤规则 11 项（后缀/子串/大小写/query 剔除/关闭开关）、批量写入 6 项（批量新增/更新、单次信号、裁剪与索引重建）、缓冲层 8 项（定时 flush、断点旁路、更新合并、discard、先增后更顺序）。
- 全部改动文件 `py_compile` 通过，`helper_process` / `proxy_core` 导入正常。
- `uvx ruff check`：改动文件共 53 处告警，其中 48 处为存量基线（项目无 ruff 强制配置），新增 5 处为与周边代码风格一致的盲捕获（BLE001）。
- 未执行：真实抓包链路（需启动 local/系统代理模式连真实应用）手工回归。

## 剩余风险

- 过滤默认开启：存量用户升级后静态资源请求不再出现在抓包列表，需阅读设置项说明（可一键关闭）。
- 批量刷新间隔 250ms 为固定值，暂未做成配置；如有更低延迟需求需调整 `flow_event_buffer.py` 的 `DEFAULT_FLUSH_INTERVAL_MS`。
- 断点流量旁路批量缓冲，理论上断点流量与普通流量极高并发时旁路路径仍有单条信号开销（断点流量本身极少，影响可忽略）。
