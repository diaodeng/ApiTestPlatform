---
title: 插件安装新增 Pip 模式（内置 Python 运行时 + 可配置包索引源）
date: 2026-09-13
category: client
---

# 插件安装新增 Pip 模式（内置 Python 运行时 + 可配置包索引源）

## 背景

插件内容本质是第三方依赖库，此前只能通过「在线下载 zip」或「本地安装 zip」获取。部分场景（Gitee 附件下载慢、内网有私有 PyPI 源、希望直接从包索引源安装）需要一种直接走 pip 的安装方式。

关键前提：PyInstaller 打包的应用**不包含 pip 模块**，冻结进程无法直接执行 pip。因此本功能先给客户端配了一个**内置嵌入式 Python 运行时**（Windows embeddable + pip），开发态与打包态共用同一条执行路径，不依赖也不修改用户的 venv。

## 变更内容

### 内置 Python 运行时

- 新增 `scripts/setup_pip_runtime.py`：下载嵌入式 Python（默认华为云镜像 3.14.6，与构建主程序的 venv 主版本一致）解压到 `client_new/runtime/python/`，启用 `._pth` 的 `import site`，并经 get-pip.py（清华源）引导 pip；幂等可重跑，`--force` 重建。
- 两个打包 spec（`QTRClientNew.spec` / `QTRClientNewPortable.spec`）在 `runtime/python/python.exe` 存在时将该目录整体打包到 `runtime/python`（运行期经 `_MEIPASS` 或 exe 目录定位），不存在时跳过打包并打印提示——Pip 安装按钮会明确报错引导。

### 插件管理配置与界面

- `PluginConfigModel` 新增 `pip_index_url`（留空默认清华源 `https://pypi.tuna.tsinghua.edu.cn/simple`，与项目 uv index-url 一致）；界面新增「Pip 源」配置行，内网可填私有 PyPI 源。
- 每个插件行新增「Pip安装」按钮，与在线下载/本地安装共用后台线程与运行状态互斥逻辑。

### pip 安装链路（`plugins/manager.py`）

- `_locate_pip_python`：定位执行 pip 的解释器——内置运行时（exe 目录 → `_MEIPASS`）优先，回退当前解释器（仅当其自带 pip，如手工 venv），全部缺失返回明确错误。
- `install_from_pip`：执行 `<python> -m pip install --disable-pip-version-check --no-warn-script-location --target <暂存目录> -i <源> <锁版本清单>`；成功后校验插件要求的模块在暂存目录可定位（`_check_modules_in_dir`，仅 find_spec 不导入）、补写与 zip 安装格式一致的 manifest（含 `install_mode: pip`）、原子替换插件目录（复用 `_replace_plugin_dir`，含备份回滚）。超时上限 15 分钟，pip 失败时展示 stderr 尾部 2000 字符。
- 锁版本清单：新增 `plugins/pip_pins.py`（由 `scripts/build_plugins.py` 构建时自动从构建 venv 的实际版本生成，`PLUGIN_PIP_REQUIREMENTS`），保证 pip 安装与插件 zip 是**同一组经过测试的包版本**，不会漂移到未经测试的最新版；传递依赖由 pip 解析。

### 结构调整

- `install_from_zip` 中"备份→替换→回滚"的目录替换逻辑抽取为 `_replace_plugin_dir`，zip 与 pip 两条安装路径共用。

## 发版流程影响

1. 构建插件包前先确保 `runtime/python` 已就绪（执行 `scripts/setup_pip_runtime.py`，目录已加入 `.gitignore`，脚本可重建）；
2. `build_plugins.py` 每次运行会自动刷新 `plugins/pip_pins.py`（随代码提交）；
3. PyInstaller 打包时 spec 自动包含 `runtime/python`，目录版位于 `_internal/runtime/python`，单文件版位于解压缓存——**体积代价：目录版实测 87MB→128MB（+41MB，datas 不压缩）；单文件版经压缩约增加 15~20MB**。

## 验证

- `setup_pip_runtime.py` 实跑通过：嵌入式 Python 3.14.6 + pip 26.2.1 就绪；
- 真实冒烟：内置运行时经清华源 `pip install --target` 安装 `playwright==1.62.0`（含传递依赖 greenlet/pyee/typing-extensions 的 cp314 wheel），模块校验无缺失；
- 单测（gitee_release、manifest 兼容校验）全部通过；ruff（I001/ISC004/F/E9）通过；
- QTRClientNewPortable spec 全量打包通过，`_internal/runtime/python/python.exe` 确认打入。

## 剩余风险

- 单文件版（onefile）的内置运行时随 exe 解压到临时目录，首次启动解压时间略增；
- pip 安装的传递依赖版本未逐个锁定（仅锁定插件直接依赖），与 zip 包在传递依赖小版本上可能存在差异；
- `runtime/python` 若被杀毒软件误报拦截，Pip 安装会失败，可回退在线下载/本地安装。
