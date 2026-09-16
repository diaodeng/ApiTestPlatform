# 2026-09-12 插件运行数据目录与构建产物解耦（修复重打包 PermissionError）

## 问题现象

插件化后重新打包 portable 版报错：
`PermissionError: [WinError 5] 拒绝访问: 'dist\QTRClientNew_portable\storage\plugins\proxy\mitmproxy_windows\WinDivert64.sys'`（插件化之前无此问题）。

## 根因（两个因素叠加）

1. **运行数据写进了构建输出目录**：frozen 态插件根目录原设计为「exe 所在目录/storage/plugins」，而 portable 版 exe 就在 PyInstaller 的 COLLECT 输出目录里——在构建产物目录直接运行客户端并安装插件后，`dist/QTRClientNew_portable/storage/plugins/proxy` 成为运行数据。
2. **驱动文件被内核锁定**：用户使用 local 模式抓包后，mitmproxy 的 WinDivert 内核驱动（`WinDivert64.sys`）保持 RUNNING 状态（`sc query WinDivert` 可见），被加载的驱动文件无法删除；重新打包时 PyInstaller 清理输出目录（`--noconfirm`）即报 WinError 5。

## 修复（`plugins/manager.py`）

1. **frozen 态插件根目录改存 `%LOCALAPPDATA%\QTRClientNew\storage\plugins`**：运行数据与 exe 目录/构建产物彻底解耦，重新打包不再受运行时残留影响；无 LOCALAPPDATA 时回退 exe 目录；开发态仍为 client_new 目录。
2. **旧位置自动迁移**：`activate_installed()` 启动时检测 exe 同级的旧 `storage/plugins/<name>`，存在且新位置没有时自动搬到新位置（避免已安装用户重新下载）。

## 处置步骤（本次现场处理）

- 结束 QTRClientNew.exe / windows-redirector.exe 进程；`sc stop WinDivert`（需管理员权限，本次环境无管理员权限未执行）；
- 删除被污染的 `dist/QTRClientNew_portable/storage`（驱动文件此时已可删除）；
- 重新执行 `uv run pyinstaller QTRClientNewPortable.spec --noconfirm` → **构建成功**，输出目录仅含 `QTRClientNew.exe + _internal`（128MB），无运行数据残留。

## 验证

- `plugins/manager.py` py_compile 通过；ruff 较基线 +1（迁移函数防御性盲捕获，符合插件异常隔离方针）；
- portable 构建成功且输出目录干净；onefile 构建不受影响（55MB）。

## 剩余风险

- 已在旧位置（exe 目录）安装过插件的用户：首次启动新版本时自动迁移；若迁移因文件占用失败会记日志，需手动处理。
- WinDivert 驱动停止需要管理员权限；普通权限下若驱动残留锁定，用户手动删除构建目录仍可能失败——已写入插件管理文档的"重新打包注意事项"。
- 其他 storage 运行数据（config json、logs）仍为 cwd 相对路径，双击启动时同样会写进输出目录，但均为普通文件可正常清理，不阻塞打包；后续可一并迁到 LOCALAPPDATA。
