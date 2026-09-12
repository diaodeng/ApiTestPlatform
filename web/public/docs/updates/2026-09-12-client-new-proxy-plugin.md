# 2026-09-12 桌面客户端拆分「抓包代理」插件 + 菜单按插件显隐（插件化阶段 2.5）

## 背景

插件化第二阶段（桌面测试/Web 测试插件）后，继续把 mitmproxy 相关依赖（约 15MB 压缩态）拆为第三个插件 `proxy`，并实现"菜单按插件显隐"。目标：主程序只保留 Agent 连接（httpx/websocket）、POS、SQLite、日志等核心能力。

## 变更内容

### 1. proxy 插件定义与打包（`plugins/manager.py`、`scripts/build_plugins.py`）
- 新增 `proxy` 插件（mitmproxy 12.2.3 + mitmproxy_rs/mitmproxy_windows 0.12.11 + tornado/aioquic/cryptography/pyOpenSSL/flask 全家/h2/hpack/wsproto/ldap3/argon2/attr(s)/pyparsing/sortedcontainers 等 36 个发行包）；
- 构建脚本支持 `entry_globs` 通配收集顶层 pyd（`_brotli.*.pyd`、`_cffi_backend.*.pyd`，文件名带 Python 版本标签）；
- **依赖甄别原则**：certifi/h11（httpx 共享）、Cryptodome（py7zr 使用）保留在主程序，不打入插件。

### 2. spec 排除清单扩充（`QTRClientNew.spec` / `QTRClientNewPortable.spec`）
- PLUGIN_EXCLUDES 增加 proxy 相关 33 项；
- **移除 `collect_data_files("mitmproxy"/"mitmproxy_windows")`**——mitmweb 静态资源与 WinDivert 二进制改由插件目录提供（mitmproxy 从自身模块位置读取数据）；
- hiddenimports 增加 6 个 stdlib 模块：`struct`、`http.cookies`、`logging.handlers`、`wsgiref.validate`、`wsgiref.types`、`xml.dom.minidom`——这些是插件导入链需要但主程序代码不可达、PyInstaller 因此不打包的标准库模块（xml.dom.minidom 缺失曾在冒烟中实际暴露）。

### 3. helper 子进程插件激活（`main.py`）
- `--mitm-helper` 分支在导入 helper_process 前调用 `activate_installed()`；
- **插件根目录改为 frozen 感知**（`plugins/manager.py`）：打包态按 exe 所在目录解析（原 cwd 相对路径在 helper 场景会指向 PyInstaller 临时解压目录导致找不到插件）。

### 4. tornado 懒导入（`services/mitmproxy_service/helper_process.py`）
- 顶层 `import tornado.*` 移入 `ManagedWebMaster.running()`（仅 mitmweb 模式触达），使主程序在不装 proxy 插件时也能正常导入该模块。

### 5. 菜单按插件显隐（`ui/main_window.py`）
- 新增 `_PLUGIN_GATED_NAV_ITEMS`（proxy → mitmproxy 页）与 `_resolve_nav_items()`：启动时按插件状态构建菜单，未安装抓包代理插件则「mitmproxy」菜单项隐藏；
- 过滤异常时保持完整菜单（防御性兜底）；
- Agent 页是平台连接核心，**常驻不隐藏**，页内桌面/Web 功能已有插件缺失降级提示。

## 验证

- 开发态自测 12 项全过：frozen 路径解析、proxy 定义、菜单完整/隐藏/异常兜底、tornado 懒导入、proxy.zip 回环安装（含 windows-redirector.exe 在包内确认）；
- **冻结态冒烟**：①无插件 `--mitm-helper` → `ModuleNotFoundError: No module named 'mitmproxy'` 并干净退出（预期）；②安装 proxy 插件后 → 插件激活日志 + `{"type": "ready"}` + 干净退出（exit=0）；
- 缺口分析方法论：`python -S` + 白名单模拟冻结环境逐模块探针；import 钩子记录导入链实际使用的 80 个 stdlib 模块；与 PYZ + base_library.zip + builtins + PKG 扩展求差 → 精确得出 hiddenimports 清单；
- 主程序 exe：**55MB**（插件化前 100+MB，两轮拆分共减少约 45%）；PKG 归档中 mitmproxy/tornado/cryptography/WinDivert 残留为 0；
- 插件包：`proxy.zip` 19.5MB、`web-test.zip` 38.0MB（回归无影响）、`desktop-test.zip` 63.4MB；
- 改动文件 py_compile 通过；ruff 较基线 +8 处为插件激活防御性盲捕获（BLE001，与既有风格一致）。

## 剩余风险

- dist 目录下残留两个无法终止的 QTRClientNew.exe 幽灵进程（冒烟测试被 timeout 启动的 GUI 进程，taskkill 报"没有此任务的实例"），不影响构建；系统重启后自动消失。
- stdlib hiddenimports 清单基于当前 mitmproxy 12.2.3 导入链分析；升级插件内 mitmproxy 大版本时需用 `tmp` 分析脚本（见更新记录方法论）重新校验 stdlib 与第三方依赖清单。
- 菜单显隐在安装插件后需重启客户端才刷新（与插件生效机制一致）。
- `QTRClientNewPortable.spec` 已同步修改但未单独构建验证。
- 真实抓包链路（local 模式 + 目标应用）未在冻结态端到端回归；windows-redirector 的 PE 子系统补丁会写入插件目录（可写，风险低）。
