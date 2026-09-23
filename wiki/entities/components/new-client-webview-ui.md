---
title: 新版客户端 pywebview 界面
type: entity
entity_category: component
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-09-20
created: 2026-09-13
updated: 2026-09-20
related_files:
  - client_new/main.py
  - client_new/ui_web/app.py
  - client_new/ui_web/event_bus.py
  - client_new/ui_web/dialog_bridge.py
  - client_new/ui_web/api/bridge.py
  - client_new/ui_web/static/index.html
  - client_new/services/agent_client_service.py
---

# 新版客户端 pywebview 界面

新版客户端界面已由 PySide6 迁移到 pywebview（分支 `client_pywebview` 起为正式实现）：Python 侧以 pywebview 承载原生窗口（WebView2），前端为 `ui_web/static` 下无构建步骤的原生 HTML/CSS/JS SPA；业务服务层（services/server/managers/utils/plugins）全部复用，与 Qt 相关的壳层代码已删除。

```mermaid
graph TD
  A[main.py] --> B[异常处理/插件激活/AppUserModelID]
  B --> C[单实例互斥体]
  C --> D[ui_web/app.py webview.create_window]
  D --> E[Bridge js_api 门面]
  D --> F[static 前端 SPA]
  E --> G[api/agent|pos|sqlite|mitm|log|about|app]
  G --> H[services / server / managers]
  G -.EventBus.evaluate_js 推送事件.-> F
```

## 关键机制

- **事件推送**：`ui_web/event_bus.py` 的模块级单例 `event_bus`，后台线程通过 `push(event, payload)` → `window.evaluate_js("window.__qtrDispatch(...)")` 推送；前端 `index.html` 内联脚本先入队，`js/core.js` 的 `Bus` 消费，各页面模块订阅。事件名与原 Qt Signal 语义一一对应（如 `mitm_flow_new`、`agent_state`、`pos_status`、`log_tail`、`update_progress`）。
- **JS 调用**：前端统一经 `QTR.call(...)` 调 `window.pywebview.api.<namespace>.<method>`；`Bridge`（`api/bridge.py`）聚合 `app/agent/pos/sqlite/mitm/log/about` 七个子 API，另把 `resolve_dialog/choose_file/choose_dir/quit_app` 平铺到顶层。
- **弹窗桥**：`ui_web/dialog_bridge.py` 的 `WebDialogService` 把 POS 启动引擎等业务的后端确认弹窗改为"推送 `ui_dialog` 事件 + threading.Event 等待 + 前端模态框回传 `resolve_dialog`"，confirm/choice 语义与原 Qt DialogUtil 一致（超时/退出按取消处理）。
- **线程模型**：原 QThread/QTimer/QThreadPool 全部替换为 `threading.Thread`、`threading.Timer` 与 `concurrent.futures.ThreadPoolExecutor`（POS 上限 4，与原一致）；mitm helper 的子进程 JSON 行协议管理与状态机完整保留，仅把 QTimer 轮询换成监控线程。
- **单实例**：Windows 用命名互斥体 + FindWindow 激活旧窗口；非 Windows 用临时目录锁文件（`ui_web/utils/single_instance.py`）。
- **主题**：原 ThemeTokens/QPalette 改为 CSS 变量（light/dark 两套 + `prefers-color-scheme` auto），模式持久化沿用 `ThemeConfig`。
- **日志页双路 tail**：`api/log_api.py` 按 source（`local`=本地日志 / `app`=程序日志）各自维护独立的 `LogTailThread`，`start_tail(source, path)` / `stop_tail(source)` 互不影响（停止/重启其中一路不影响另一路）；`log_tail` 事件携带 `source` 字段供前端分发到对应页签；`shutdown()` 供 Bridge 在应用退出时停止全部 tail。
- **Agent 服务器配置契约**：`AgentConfigModel.server_list` 结构为 `{服务地址: 服务名称}`、`current_server` 存服务地址（与旧 PySide6 版一致，pywebview 迁移时曾写反已修正）；Agent 页用下拉框按名称选择服务，连接中禁用切换；连接地址只在应用日志中记录，状态提示与界面均不展示。
- **Agent AI 配置契约**：`AgentConfigModel` 的 `ticket_ai_workspace_root`（AI 工作区根目录，留空用 `storage/ticket_ai_analysis`）、`ticket_ai_local_repo_path`（AI 本地仓库，留空回退任务映射）、`ticket_ai_codex_cli_path`（Codex CLI 可执行文件，留空按 PATH 查找）三字段由 Agent 页「AI 设置」弹窗维护（2026-09-20 补齐，迁移时曾遗漏前两项）；保存走 `agent.save_config` 全量链路，消费点在 `services/ticket_ai_analysis_service.py`（工作区解析与 Codex CLI 解析；`ticket_ai_local_repo_path` 当前 client_new 后端暂无直接消费点，仅保留配置入口）。
- **文件对话框契约**：`app.choose_file` 的 `file_types` 过滤串（形如 `"日志文件 (*.log;*.txt)|所有文件 (*.*)"`）解析为 pywebview 要求的**字符串列表** `"描述 (*.a;*.b)"`；pywebview 内部用正则对每项做字符串匹配，传元组会抛 `TypeError`。目录选择使用 `webview.FileDialog.FOLDER`（`FOLDER_DIALOG` 常量已弃用）。
- **前端错误上报**：`index.html` 全局 error/unhandledrejection 钩子经 `app.log_js_error` 写后端日志，便于排查页面问题。

## 服务层的同步改造

- `services/agent_client_service.py`：QObject + Signal 剥离为纯 Python 回调注册（`add_listener/remove_listener/_emit`），事件名不变；这是唯一有 Qt 依赖的 service。
- `services/mitmproxy_service/mock_handle.py`：`_emit_flow` 移除对 Qt emitter 的兜底导入，无分发器时仅记 debug 日志。
- `services/desktop_test_service.py`：桌面录制覆盖层（透明高亮/批注窗口）依赖 PySide6，随旧 UI 退役置为 None，调用点按"无覆盖层"降级；桌面测试执行本身不受影响。

## 已删除的 Qt 层

`ui/`（主窗口/页面/对话框/widgets/theme_manager/单实例/icon_util/overlay）、`controller/`（三个 Qt 控制器）、`workers/`、`emitter/`、`models/pos_models.py`、`models/mitmproxy_models.py`（QAbstractTableModel）、`scripts/qt_slim.py`（PySide6 打包裁剪）已删除；`QTRClientNew.spec`/`QTRClientNewPortable.spec` 移除 qt_slim 引用并新增 `ui_web/static` → `ui_web_static` 的 datas 收集。

## 参见

- [新版客户端壳层](new-client-shell.md)（Qt 版历史实现）
- [新版 PySide6 客户端](../services/new-pyside-client.md)
- [新版客户端运行时](new-client-runtime.md)
