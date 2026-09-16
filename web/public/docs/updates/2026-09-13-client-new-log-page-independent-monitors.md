# 2026-09-13 客户端日志页双路独立监听与文件对话框修复

## 变更背景

- 日志页「本地日志」与「程序日志」共用同一条后端 tail 线程：启动其中一路会停掉另一路，且本地日志在「选择文件」后会立即自动开始监听，无法先选中再手动控制。
- 启动程序时文件选择报错：`TypeError: expected string or bytes-like object, got 'tuple'`，原因是 `app.choose_file` 把过滤项解析成 `[("描述", "*.a")]` 元组列表，而 pywebview 内部 `parse_file_type` 用正则对每个过滤项做**字符串**匹配。
- 目录选择出现 `FOLDER_DIALOG is deprecated` 告警。

## 变更内容

### 后端 `ui_web/api/log_api.py`

- `LogTailThread` 增加 `source` 参数（`local`=本地日志 / `app`=程序日志），`log_tail` 事件携带 `source` 字段。
- `LogApi` 由单一线程改为按 source 隔离的线程字典：
  - `start_tail(source, path)`：启动指定来源的 tail，同来源重复启动先停旧线程，不同来源互不影响；
  - `stop_tail(source)`：仅停指定来源；`stop_tail()` / `shutdown()` 停止全部（供应用退出清理）；
  - `get_tail_status()`：返回各来源当前监听状态。

### 前端 `ui_web/static/js/pages/logs.js`

- 监控会话按来源拆分：`session.local` 与 `session.app` 各自持有监听文件、监听状态与已累计日志行，页签内容与事件分发互不串扰。
- 本地日志：「选择文件」只选中不监听；首次进入默认选中当前程序日志文件（不监听）；勾选「监听日志」开始监听，取消勾选停止；监听中换选文件自动切到新文件继续监听。
- 程序日志：独立的「监听日志」开关，完全监听当前程序自身日志（当天日志优先）。
- 复制：日志输出区允许鼠标选中文字；「复制」按钮优先复制选中文本，无选区时复制全部内容。

### 其它

- `ui_web/static/css/app.css`：`pre.panel` 显式声明 `user-select: text`。
- `ui_web/api/app_api.py`：
  - `_parse_file_types` 改为返回 pywebview 要求的字符串列表 `"描述 (*.a;*.b)"`，修复文件选择 TypeError；
  - `choose_dir` 改用 `webview.FileDialog.FOLDER`，消除弃用告警。

## 验证

- 后端冒烟：同时启动 local/app 两路 tail，各自收到带 source 的事件；停止 local 后 app 继续推送；`get_tail_status`/`shutdown` 行为符合预期。
- `_parse_file_types` 输出全部通过 pywebview `parse_file_type` 正则校验。
- `node --check` 通过；改动文件 ruff 检查无新增告警（存量 BLE001 为旧代码既有）。
