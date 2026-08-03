# 客户端 POS 启动日志与任务生命周期保护

## 背景

2026-07-21 启动 POS 后，`client_new` 的 Python 进程发生 `Qt6Core.dll` 访问违规（Windows 事件 `APPCRASH`，异常码 `0xc0000005`），而独立启动的 `CPOS-DF.exe` 继续运行。

排查发现，客户端在拉起 POS 前会调用 `pos/init` 获取远端参数。该调用此前将完整响应写入客户端日志，单条日志约 60 万字符。实时日志页虽然默认关闭，但开启时会将文件中的每行通过 Qt 信号传递给 `QTextEdit`，超大单行会放大 Qt UI 处理风险。

## 改动

- `client_new/utils/pos_network.py`
  - `pos/init` 只记录响应摘要：状态码、成功标记、商家、门店、POS 标识、POS 类型和响应字节数。
  - 成功日志和失败异常均不再写入完整配置正文，避免敏感配置泄露及超大单行日志。
- `client_new/ui/pages/log_view_page.py`
  - 文件实时监控发送到 UI 前，将单条日志限制为 16 KiB；超过限制时保留前缀并标记截断字符数。
- `client_new/controller/pos_controller.py`
  - POS 启动 Worker 在成功或失败信号完成前由控制器持有，随后释放，避免 QRunnable 仅依赖局部引用。

## 验证

- 对 `client_new` 运行 Ruff 静态检查。
- 对 POS 启动、实时日志开关和超大 `pos/init` 响应进行人工回归。

## 风险

本次保护降低了超大日志和 Worker 生命周期带来的风险，但无法替代 Qt 原生崩溃转储分析。若仍出现 `Qt6Core.dll` 访问违规，应保留 Windows WER dump，结合符号分析定位 Qt/PySide6 调用栈。
