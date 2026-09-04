# 2026-09-04 客户端 Agent 页面：连接服务器点击卡死修复（按钮即时置灰）

## 问题背景

新版客户端（client_new）Agent 菜单中，点击"连接服务器"后整个页面会卡住（白屏、无响应），
直到连接成功或失败后才恢复。连接目标不可达时卡顿尤其明显，期间无法进行任何界面操作。

## 根因分析

点击"连接服务器"在 UI 线程（主线程）上同步执行了两类阻塞操作：

1. **重型模块首次导入（实测约 1.5 秒）**：`AgentClientService.start()` 在启动连接线程前
   会调用 `_agent_server_module()` 首次导入 `server.agent_server`。该模块顶部级联导入了
   `services.web_test_service`（含 playwright.async_api）、`services.desktop_test_service`
   （含 pyautogui、cv2、pyscreeze）、`services.ticket_ai_analysis_service`（含 py7zr）等
   重依赖，首次导入耗时约 1458 ms（`python -X importtime` 实测：httpx 754ms、
   ticket_ai_analysis_service 674ms、pyautogui 415ms、cv2 209ms 等）。
2. **MAC 解析与配置读取**：`AgentController.start()` 在 UI 线程同步调用
   `get_active_mac()`（创建 UDP socket 连接 8.8.8.8 探测出口 IP + psutil 枚举全部网卡，
   网络不佳时秒级阻塞）与 `AgentConfig.read_config()`（磁盘 IO）。

两者叠加导致点击后 UI 线程被占死，Qt 事件循环无法刷新，页面表现为"卡住"。

## 修复内容

### agent_client_service.py（services/agent_client_service.py）

- `start()` 不再在调用线程（UI 线程）导入重型模块，只做状态标记、信号发射和后台线程启动；
  首次导入与 `MAX_MESSAGE_SIZE` 设置全部移入 `_thread_main`（agent-client-loop 后台线程）执行。
- `_agent_server_module()` 增加双重检查锁（`_AGENT_SERVER_LOCK`），保证首次导入全局只发生
  一次且只发生在后台线程；已导入时无锁直接返回。
- 新增 `is_running()`：供 controller 区分"连接准备中（尚无连接线程）"与"连接线程已启动"。
- `update_runtime_config()` 增加模块已加载守卫：模块未加载（从未连接过）时跳过分片配置同步，
  不再因保存配置等动作在 UI 线程误触发 1.5 秒的首次导入；客户端属性（重试参数）同步不受影响。

### agent_controller.py（controller/agent_controller.py）

- 新增 `_ConnectPrepareThread`（QThread）：把 `get_active_mac()`、`AgentConfig.read_config()`
  两项阻塞准备工作移出 UI 线程；完成后通过 `done` 信号回到主线程执行 `_on_connect_prepared`。
- `start()` 改为两段式：UI 线程只做状态校验与置灰（同步耗时 0.4ms），立即进入
  `starting` 状态并同步 UI（连接按钮置灰、停止按钮可用、状态徽标"连接中"），
  随后启动准备线程；准备完成后在主线程回调里真正调用 `service.start()` 发起 WebSocket 连接。
- 防重入：`start()` 前置检查连接状态与准备线程是否存活，连点不会重复发起。
- `stop()` 补齐"连接准备阶段"分支：准备线程尚未启动连接时直接取消启动落回 `stopped`；
  准备完成回调 `_on_connect_prepared` 检测到状态已离开 `starting`（如用户已点停止）时放弃本次启动。
- `shutdown()` 增加 `_connect_thread` 的退出等待，应用退出时不再遗留准备线程。

## 交互效果

- 点击"连接服务器"：按钮立即置灰，状态徽标变"连接中"，状态信息提示"正在准备连接..."，
  页面全程可响应（可切页、可看日志）。
- 连接成功：徽标变"已连接"，停止按钮可用。
- 连接失败：徽标落回"未连接"，连接按钮恢复可点，状态信息展示失败原因（原有行为不变）。
- 准备阶段点"停止"：直接取消本次连接，无需等待准备完成。

## 验证结果

- 新增 `client_new/tests/test_agent_start_nonblocking.py`（可直接 `python` 运行的验证脚本）：
  - `update_runtime_config` 在模块未加载时不触发导入：通过；
  - 完整链路（FakeWidget + QCoreApplication 事件循环）：`controller.start()` 同步耗时 0.4 ms，
    主线程卡顿监控（>200ms 记录）全程零记录，重型模块导入仅发生在后台线程，
    连接被拒后最终状态正确落回 `stopped`：通过。
- `ruff check`（server 工程配置）：改动文件 4 个告警（I001×2、B009、F821）与改动前基线完全一致，
  本次零新增；曾引入的 F823（`global` 丢失）已在验证中发现并修复。
- 既有 `tests/test_ticket_ai_task_cancel.py`（unittest）3 用例通过。

## 剩余风险

- 首次点击后到连接发起前，后台导入仍需约 1.5 秒（从"点击即卡"变为"后台静默准备"），
  极端情况下用户在 1~2 秒内点"停止"会取消本次连接，属预期行为。
- 未验证真实 GUI 下的手写连点场景（需人工在运行环境确认），逻辑上已通过状态机防重入。
