---
title: 桌面客户端界面由 PySide6 迁移到 pywebview
---

# 桌面客户端界面由 PySide6 迁移到 pywebview（2026-09-13）

## 变更主题

`client_new` 的图形界面从 PySide6（Qt Widgets）整体迁移到 **pywebview**：原生窗口 + 系统 WebView2 渲染的无构建原生 HTML/CSS/JS 前端，服务层（services / server / managers / utils / plugins）零改动复用。分支：`client_pywebview`。

## 主要内容

### 新增 ui_web 包（界面桥接层）

- `ui_web/app.py`：装配 pywebview 窗口（`http_server=True` 托管静态资源，ES module 在 file:// 下会被 WebView 拦截）；关闭时执行统一清理。
- `ui_web/event_bus.py`：EventBus 单例，后台线程经 `window.evaluate_js` 向前端推送事件；事件名与原 Qt Signal 一一对应（`mitm_flow_new/update`、`agent_state/status/request/response/error`、`pos_status/log`、`log_tail`、`update_progress/done`、`ui_dialog`、`ui_toast` 等）。
- `ui_web/dialog_bridge.py`：WebDialogService 把业务确认弹窗桥接为前端模态框（推送 ui_dialog + threading.Event 等待 + resolve_dialog 回传），confirm/choice 语义与原 Qt DialogUtil 一致，超时 5 分钟按取消处理。
- `ui_web/api/`：Bridge 门面聚合 7 个子 API（app / agent / pos / sqlite / mitm / log / about），并平铺 `resolve_dialog / choose_file / choose_dir / quit_app` 顶层方法。
- `ui_web/utils/single_instance.py`：Windows 命名互斥体 + FindWindow 激活旧窗口；非 Windows 锁文件兜底。
- 前端 `ui_web/static/`：index.html + css/app.css（CSS 变量双主题 + prefers-color-scheme auto）+ js/core.js（Bus/Modal/Toast/表单工具）+ app.js（导航路由/主题/状态栏）+ 6 个页面模块 + plugins.js 弹窗；前端运行时错误经 `app.log_js_error` 写后端日志。

### 服务层同步改造（唯一 Qt 依赖点）

- `services/agent_client_service.py`：QObject + Signal 剥离为回调注册制（add_listener / _emit），事件名不变。
- `services/mitmproxy_service/mock_handle.py`：`_emit_flow` 移除 Qt emitter 兜底导入。
- `services/desktop_test_service.py`：桌面录制覆盖层（Qt 透明窗口高亮/批注）随旧 UI 退役置 None，按"无覆盖层"降级，桌面测试执行不受影响。

### 删除的 Qt 层

`ui/`、`controller/`、`workers/`、`emitter/`、`models/pos_models.py`、`models/mitmproxy_models.py`、`scripts/qt_slim.py`、Qt 版单实例/主题/图标/overlay；`tests/test_agent_start_nonblocking.py`（Qt 依赖）一并删除。依赖 `pyside6` 移除、`pywebview>=5.4` 新增。

### 打包

两个 spec 移除 `apply_qt_slim` 引用，新增 `ui_web/static` → `ui_web_static` 的 datas 收集（运行期 `ui_web.app.get_static_dir` 按 _MEIPASS 解析）。

## 行为变化

- 关闭窗口不再弹退出确认，直接退出（退出前自动停止 mitmproxy helper、Agent 连接与日志 tail）。
- 日志页移除旧版"未实现"的 SSH 占位页签。
- 桌面测试的屏幕高亮覆盖层暂不可用（见上）。
- 配置文件与旧版完全共用（`storage/data/*.json`），升级无缝。

## 验证

- `uv sync` 通过（pyside6 卸载、pywebview 安装）；ruff（F/E9 级）无新增问题。
- Bridge 冒烟：agent/sqlite/mitm/log/about/app 各子 API 初始化与读取正常，shutdown 链路正常。
- GUI 冒烟（仪器化）：窗口拉起、前端模块加载、6 个页面逐一切换渲染正常（元素计数与导航项符合预期）、插件管理弹窗打开正常、`get_global_status` 轮询持续工作、无前端 js_error/js_rejection 上报。

## 风险与后续

- 桌面录制覆盖层（高亮/批注）待用 pywebview 透明窗口补齐。
- 深交互链路（mitm 断点编辑、POS 启动确认全流程、自更新）为代码级移植，建议日常使用中重点回归。

## 打包修复（同日追加）

- 首次打包运行报 `RuntimeError: Failed to create a .NET runtime`：根因是插件化瘦身时 `cffi`/`pycparser` 被列入 spec 的 PLUGIN_EXCLUDES（当时仅 proxy 插件使用），而 pywebview 的 WinForms 后端依赖链 pythonnet → clr_loader → cffi 需要在主程序内直接可用；且旧 hiddenimports 还引用了已删除的 Qt 模块（controller.agent_controller、ui.dialogs.*）。
- 修复：`cffi>=2.0.0` 加入主依赖；两个 spec 从排除清单移除 cffi/pycparser，hiddenimports 改为 ui_web.api.bridge + webview.platforms.winforms/edgechromium + pythonnet + clr_loader（netfx/ffi/hostfxr）+ cffi/pycparser；webview/lib（WebView2Loader.dll 等）由 hooks-contrib 的 hook-webview 自动收集。
- 验证：便携版全量重新打包通过，`_internal` 中确认包含 _cffi_backend/clr_loader/pythonnet/webview；打包 exe 实测启动正常（窗口出现、运行稳定、退出清理正常）。

## 界面交互修正（同日追加，对照原 PySide6 版还原）

- Agent 服务器管理弹窗改为原版「新增 / 修改 / 删除」三按钮交互（修改/删除需先选中列表行，新增/修改弹出子表单）。
- POS 页工具栏还原原版布局：模式与目录配置全部收纳进「工作目录」弹窗（含扫描模式分节），页面仅保留「工作目录 / 扫描」入口与启动前勾选、过滤；设置弹窗按“服务地址 / 环境文件清单 / 缓存文件清单 / 环境分组 / 商家配置 / 配置拉取”分节展示。
- 切换 POS 弹窗修复指定 POS_ID 模式下的两列排版异常（POS_ID 行改为与其它行一致的两列网格，随模式显隐）。
- 日志页恢复三个页签：SSH日志（原版占位行为一致）/ 本地日志 / 程序日志（勾选“监控日志”跟踪最新应用日志）。
- 修复 Agent 页无法显示请求/响应日志：core.js 的 checkbox 辅助函数把 input 重复 append 且返回外层 label，导致勾选状态读取恒为 undefined、show_logs 保存始终为 false，后端因此不推送 agent_request/agent_response 事件；修正节点顺序与返回结构，agent.js 改为经 querySelector 读取勾选状态。
- 修复程序日志页勾选「监控日志」后无内容：监控目标改为后端 get_app_log_file 解析（当天日期命名日志优先、回退最新 .log，与原版一致），勾选后立即渲染最近 500 行，新增内容经 log_tail 事件实时推送。
- 日志页页签增加明确选中样式（tab-btn.active），并将监控会话改为模块级持久状态：切换到其它页面不中断日志监控，回到日志页自动恢复当前页签、监控状态与已累计内容。
