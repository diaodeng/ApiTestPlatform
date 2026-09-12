# 2026-09-12 桌面客户端插件化瘦身（阶段 2）

## 背景

client_new 打包体积 100+MB，其中 cv2/numpy/pytesseract（仅桌面测试使用）与 playwright（仅 Web 测试/Agent 使用）合计约 220MB（解压后）。按既定分阶段方案（`wiki/features/client-new-optimization-and-go-migration-plan.md` 阶段 2）实施插件化：主程序不再内置这两类依赖，改为"本地有就直接用、没有就按需下载安装"，且插件异常只提示、不影响主进程。

## 变更内容

### 1. 插件管理基础设施（`plugins/__init__.py` + `plugins/manager.py` 新增）
- 插件目录约定：`storage/plugins/<name>/` 下直接放置 site-packages 内容，激活时插入 `sys.path` 前端并 `invalidate_caches`。
- 内置两个插件定义：`desktop-test`（cv2/numpy/pytesseract/pyautogui/pygetwindow/pynput/PIL）、`web-test`（playwright）。
- 状态机：active（模块当前可导入）/ installed（目录+manifest 合法，待重启）/ missing。
- `install_from_zip`：校验 manifest.json（名称匹配）→ 路径安全校验（拒绝绝对路径与 `..` 越级）→ 临时目录解压 → 备份旧目录原子替换 → 失败自动回滚。
- `download_and_install`：从配置的下载源拉 `{base}/{name}.zip`，存在 `.sha256` 时强校验；未配置下载源给友好提示。阻塞操作，由 UI 放后台线程调用。
- **所有公开方法只返回 `(ok, message)`、不向外抛异常**，异常一律 `logger.exception`/`warning` 记录——满足"插件异常不影响主进程"。
- 配置：`model/config.py` 新增 `PluginConfigModel`（download_base_url），`do/config.py` 新增 `PluginsConfig`（storage/data/config_plugins.json，含 makedirs 与读取容错）。

### 2. 启动激活（`main.py`）
- 在导入任何业务模块之前调用 `plugin_manager.activate_installed()`；激活失败仅记 warning，不阻塞启动。

### 3. 特性层降级与提示
- `desktop_test_service.handle_request`：入口检查核心依赖（cv2/np/pyautogui/pytesseract，按守卫导入的全局名映射 + find_spec 兜底），缺失时直接返回结构化失败消息，引导到「插件管理」安装。
- `playwright_browser_runtime`：playwright 包/驱动缺失的 RuntimeError 文案改为指向「插件管理」安装「Web 测试」插件。
- `agent_server` 既有每请求类型 try/except 边界保持不变，插件异常最终以结构化 Error 回传远端。

### 4. 插件管理 UI
- `ui/dialogs/plugin_manager_dialog.py`（新增）：下载源配置行 + 插件表格（名称/说明/状态/操作），支持在线下载与本地 zip 安装；安装动作在后台线程执行，结果经 Qt 信号回 UI 线程弹窗。
- `ui/main_window.py`：头部栏新增「插件」按钮（theme 按钮左侧），打开对话框的异常仅记日志。

### 5. 打包改造
- `QTRClientNew.spec` / `QTRClientNewPortable.spec`：新增 `PLUGIN_EXCLUDES`（cv2、numpy、playwright、PIL、pyautogui 及其传递依赖 pyscreeze/pymsgbox/pytweening/mouseinfo、pygetwindow、pynput、pytesseract），移除 playwright 的 collect_data_files 与 hiddenimports，hiddenimports 增加 `ui.dialogs.plugin_manager_dialog`。
- `scripts/build_plugins.py`（新增）：从 .venv 收集插件条目（含 pyautogui 的传递依赖 pyscreeze/pymsgbox/pytweening/mouseinfo/six 与 dist-info）生成 `dist_plugins/<name>.zip` + `.sha256`，zip 根目录含 manifest.json（名称/版本/模块清单/构建时间）。

## 验证

- 功能自测 15 项全过（offscreen Qt）：开发态状态 active 2 项、空目录激活 no-op、zip 安装校验 7 项（缺 manifest/名称不符/越级路径被拒、正常安装、覆盖安装、无 bak 残留）、未配置下载源友好提示、桌面守卫通过、对话框实例化与状态渲染。
- 改动文件 `py_compile` 全过；新增文件 ruff 告警 10 处均为有意盲捕获（插件隔离要求）与代码库既有风格一致。
- **主程序构建验证通过**：`uv run pyinstaller QTRClientNew.spec` 成功，产物 `dist/QTRClientNew.exe` **71MB**（原 100+MB）；PKG 归档中 cv2/numpy/playwright/PIL/pyautogui 条目数为 0（排除生效），对照 shiboken=10 正常保留。
- **冻结态冒烟通过**：`dist/QTRClientNew.exe --mitm-helper` 正常输出 ready 协议消息并干净退出，冻结环境导入链路完好。
- **插件包构建与安装回环通过**：`scripts/build_plugins.py web-test` 产出 37.9MB（playwright-1.62.0，含 driver/node.exe），用 `install_from_zip` 真实安装成功、manifest 与驱动文件齐全。

## 剩余风险

- 打包排除 numpy/cv2 等后，若主程序其他依赖存在隐藏引用会在运行时才暴露（守卫会兜住并记日志）；首份正式包发布前建议完整回归 Agent 桌面/Web 测试链路（含本地安装插件包后的真实桌面/Web 测试执行）。
- 插件首次安装后需重启客户端才生效（守卫导入发生在启动期）；后续可改造为调用期动态导入免重启。
- 在线下载源尚未有实际托管地址，当前依赖维护方部署静态文件服务；未配置时 UI 有明确提示。`desktop-test.zip` 已实构建（63.4MB，numpy 2.5.2 / pillow 12.3.0 等以 venv 实际版本为准），回环安装验证通过。
- `QTRClientNewPortable.spec` 与主 spec 同步修改但本次未单独构建验证。
- 桌面插件不包含 tesseract.exe 本体，OCR 仍要求系统安装 Tesseract（与原行为一致）。
- 构建脚本修复（2026-09-12）：dist-info 改为按发行包名动态解析（venv 依赖升级后无需改脚本）；顺带修复 `rsplit('-', 1)` 会切在 `dist-info` 连字符上导致永远匹配不到的缺陷。
