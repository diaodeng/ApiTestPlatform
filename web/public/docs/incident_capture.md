# 服务端故障自动取证（incident_capture.py）

## 功能说明

服务端发生重启、OOM、异常后，一条命令自动收集现场证据，替代人工打开部署平台 xterm 终端逐条敲命令。产物统一写入 `server/scripts/output/incident_<时间戳>/` 目录，供事后复盘或交给 AI 分析。

取证内容（全部只读操作，不修改容器内任何数据）：

1. **部署平台实例信息**（`pod_info.json`）：pod 名称、镜像版本（v636 等）、git commitId、启动时间、podIP/宿主机 IP；
2. **容器内终端取证**（WebSocket 执行只读命令）：
   - `terminal_pods.txt`：supervisor 托管的进程状态（fastapi/beat/worker 是否存活）；
   - `terminal_cgroup.txt`：容器内存上限、当前用量、`memory.events`（oom_kill 计数）；
   - `terminal_dmesg_oom.txt`：内核 dmesg 中的 OOM / killed process 记录；
   - `terminal_app_log_tail.txt`：最新一天应用日志尾部 2000 行（覆盖重启窗口）；
   - `terminal_error_log_tail.txt`：最新错误日志尾部 300 行；
   - `terminal_supervisord_log.txt`：supervisord 日志尾部 100 行（进程被拉起的记录）；
3. **VM 指标取证**（`vm_summary.txt` + `vm_*.json`）：按 Pod 启动时间对齐窗口，查询各进程 RSS/USS、容器内存用量/anon/file/上限、OOM 计数、API 线程数，并附近 N 小时容器 anon 内存历史趋势（默认 26 小时，覆盖上一次发布前基线）。

## 使用方法

前置条件（一次性）：

- `server/.env.prod` 中已配置 `VM_URL` / `VM_USER` / `VM_PASSWORD`（VM 查询）；
- `server/.env.prod` 中配置 `DEPLOY_LOGIN_TOKEN`：值为浏览器访问部署平台时 Cookie 中 `login_token` 的 **URL 解码值**（`Bearer eyJ...` 开头的 JWT）。获取方式：部署平台页面 → F12 → Application → Cookies → 复制 `login_token` 值并做一次 URL 解码（`%20` 还原为空格）。**该 token 有过期时间（约 7 天），过期后脚本会报 `getAppInstances 失败`，重新从浏览器取一次即可。**

运行：

```bash
cd server
uv run python scripts/incident_capture.py                    # 全量取证（终端 + VM）
uv run python scripts/incident_capture.py --memory-hours 48  # anon 历史窗口拉长到 48 小时
uv run python scripts/incident_capture.py --skip-vm          # 只拉容器内日志
uv run python scripts/incident_capture.py --skip-terminal    # 只查 VM 指标
```

## 技术实现要点（维护参考）

- 部署平台两个接口：`getAppInstances`（实例列表）与 `getAppOperations`（终端地址）。`loginToken` 查询参数需要**二次 URL 编码**，Cookie 里的 `login_token` 是一次编码；
- xterm 终端的真实 WebSocket 协议是从终端页面 HTML/JS 逆向得到的：`getAppOperations` 返回的 `bash` 地址只是给人打开的页面，页面 JS 实际连接 `ws://testapi2-symphony.rta-os.com/api/cluster/<clusterCode>/terminal?namespace=&pod=&container=&cmd=sh&cmd=-c&cmd=<URL编码的命令>`，**连接后第一帧必须发送 `___` + JSON（cols/rows/type=resize）**，否则服务端立即以 1000 关闭；后续帧就是命令输出（含终端转义序列，脚本已清洗）；
- 页面模板里的 `testapi-sym.rta-os.com` 是无效占位域名，实际可用的是 `testapi2-symphony.rta-os.com`；
- 终端命令经外层 `sh -c` 执行，`$(...)` 子命令嵌套会被转义破坏，因此日志路径定位使用 `find ... -newer` 方式；
- VM 查询默认以 Pod 的 `startTime` 往前推 30 分钟为窗口起点，保证覆盖发布前基线。

## 与内存排查流程的关系

本脚本是 `web/public/docs/memory-monitoring.md` 排查流程的取证环节：发生重启后先跑本脚本，`vm_summary.txt` 判断是否 OOM（内存钉死上限 / oom_kill 增长 / 进程 uptime 归零），`terminal_*` 日志定位被杀时刻的任务，再结合 `celery_task_execution_log` 与应用日志做归因。若内存诊断快照（memory-monitoring.md 同页配置）有触发，`logs/<日期>/memory_snapshot_*.txt` 与本脚本产物配合使用。
