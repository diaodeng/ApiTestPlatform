# client_new 优化与 Go 迁移分阶段实施方案

> 2026-09-12 制定。背景：client_new（PySide6 桌面客户端，约 3.5 万行）在系统代理模式下全机器流量过代理时出现请求排队响应慢，且 PyInstaller 打包体积 100+MB。本文档记录评估结论与分阶段实施路线，供后续会话接续。

## 一、现状评估结论

### 1. 代理模块（约 3000 行）
- mitmproxy 以两种形态运行：进程内线程（`services/mitmproxy_service/proxy_core.py`）与独立 helper 子进程 + stdout JSON 行协议（`services/mitmproxy_service/helper_process.py` + `mitm_helper_main.py`），支持 dump / mitmweb 两种启动模式。
- 实际只用了 mitmproxy 的 `request`/`response` 两个 hook + local capture（`--mode local:CPOS-DF.exe`，按进程透明拦截）+ 动态 CA 证书 + ssl_insecure。
- Mock、断点、延迟、流量上报全部是自有代码（`services/mitmproxy_service/mock_handle.py`），与 mitmproxy API 耦合浅，可近乎 1:1 迁移到任意语言。

### 2. "系统代理全流量排队慢"的根因（2026-09-12 定位）
1. 每条流量（含无关系统流量）全量构造 FlowItem（headers/cookies/form/body 格式化）；
2. 每条流量 JSON 序列化 → stdout → Qt 信号 → 表格逐条插入 + 统计刷新 + 选中恢复，UI 线程饱和；
3. mock 探测每个请求新建 `httpx.AsyncClient`（新连接池 + TLS 握手）；
4. Python GIL 使上述 CPU 工作与 mitmproxy 事件循环同进程竞争。

### 3. 体积构成（venv 解压后实测）
PySide6 运行时约 60-80MB（压缩后）、cv2 113MB、playwright 106MB（含 node driver）、numpy 45MB、PIL 15MB、mitmproxy 全家桶约 20MB、Python 运行时约 15MB。打包为 onefile。

### 4. Go 迁移可行性（对照《Go代理工具替代方案》讨论）
- goproxy / go-mitmproxy / mitmproxy-go 可覆盖 MITM + Hook + Mock + 延迟 + 断点；
- **最大缺口是 local capture（按进程透明拦截）没有 Go 现成等价物**，需复用 mitmproxy 的 windows-redirector.exe（Rust 独立二进制）或自写 WinDivert 重定向（参考 mitmproxy platform/windows.py、ProxyBridge）；
- 迁移成本大头不在代理：playwright（Go 版成熟度低）、pyautogui/opencv/pytesseract 桌面自动化（Go 生态弱、需 cgo）才是重写风险最高的部分。

## 二、分阶段实施路线

### 阶段 1：代理三项性能优化（纯 Python，不动架构）✅ 已实施（2026-09-12）
1. **入口过滤**：`flow_filter_enabled` / `flow_filter_pattern` 配置项，命中静态资源规则（后缀或子串）的流量完全放行——不记录 UI、不参与 mock 探测、不做延迟；
2. **httpx.AsyncClient 会话级复用**：MockHandle 实例持有单个 AsyncClient（连接池上限 50 / keepalive 20），跨事件循环自动重建，探测前清 cookie，会话结束显式关闭；
3. **UI 节流**：新增 `ui/widgets/flow_event_buffer.py` 缓冲层——普通流量 250ms 定时批量写入（模型新增 `add_flows`/`update_flows` 整块插入），缓冲超 500 条立即落盘；断点流量旁路缓冲立即写入，保证放行按钮即时可点。移除 add_flow 中的逐条 debug 日志。

预期：系统代理模式下无关流量不再进入 Python 处理链，目标应用流量 UI 刷新恒定为每 250ms 一次。

### 阶段 2：插件化瘦身（不动业务逻辑）⏳ 未开始
- cv2 + numpy + pytesseract（只有 `desktop_test_service.py` 使用）拆为"桌面测试插件包"；
- playwright（只有 web 测试 / agent 模块使用）拆为"Web 测试插件包"；
- 插件形态：zip 内含 site-packages 子目录，下载解压到 `%APPDATA%\QTRClientNew\plugins\<name>\`，启用时加入 `sys.path`（共享主程序解释器）；桌面测试建议子进程隔离（复用 helper JSON 协议）；
- 下载通道 HTTPS + sha256 校验 + 版本清单；UI 上功能页检查插件 → 无则"下载启用"；
- 打包 onefile → onedir（启动提速）；spec 中 `collect_data_files("playwright")` 随拆分移除。
- 预期：主程序（PySide6 + mitmproxy + mitmproxy_rs/windows-redirector + PIL）压缩后约 45-60MB。

### 阶段 3：UI 迁 pywebview + Vue ⏳ 未开始
- 用 pywebview（Windows 自带 Edge WebView2，本体几 MB）替换 PySide6，前端用 Vue3（团队已有 web/ 经验），本地 API 用 FastAPI/aiohttp + WebSocket 推流量；
- 窗口形态为原生应用窗口 + 最小化托盘（pystray），无"关浏览器找不到入口"问题；WebView2 缺失时回退系统浏览器；
- 预期主程序再降：约 35-50MB；叠加阶段 2 后不装插件约 30MB。

### 阶段 4（长期选项）：Go 迁移 ⏳ 未开始
- 前置 POC：WinDivert 按 PID 重定向 → 本地 Go MITM 解密 → 原样返回（打通后整个链路即通）；
- 若 POC 通过：Wails + Vue3 壳 + goproxy/mitmproxy-go MITM + windows-redirector.exe（过渡）或自写 WinDivert（终极）；
- 插件在 Go 下天然变为独立 exe，与现有 helper JSON 协议同构。
- 仅当"单二进制分发 + 性能"两项收益都确认值得时启动。

## 三、相关文档
- 用户说明：`web/public/docs/client/mitm-proxy.md`
- 更新记录：`web/public/docs/updates/2026-09-12-client-new-mitm-performance-optimization.md`
