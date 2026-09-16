---
title: 桌面客户端移除插件 Pip 安装模式
---

# 桌面客户端移除插件 Pip 安装模式（2026-09-13）

## 变更主题

应体积要求，移除 2026-09-13 早些时候加入的插件「Pip 安装」模式。该模式需要在客户端内捆绑一套独立的嵌入式 Python 运行时（`runtime/python`，约几十 MB），仅服务于这一种安装方式，收益体积比不划算。插件安装回归两种方式：**在线下载**（Gitee 按版本自动回退 / 自定义下载源）与**本地 zip 安装**，功能与此前完全一致。

## 移除内容

- `plugins/manager.py`：删除 `install_from_pip`、`read_pip_index_url` / `save_pip_index_url`、`_locate_pip_python`、`_runtime_python_version`、`_check_modules_in_dir`、`_write_pip_manifest` 及默认 Pip 源常量；`_replace_plugin_dir`（zip/pip 两路共用的原子替换）保留，zip 安装路径继续使用。
- `plugins/pip_pins.py`：删除（pip 锁版本清单，仅 pip 模式使用；`build_plugins.py` 也不再生成）。
- `scripts/setup_pip_runtime.py`：删除（嵌入式 Python 运行时准备脚本）；本地 `runtime/` 目录一并清理。
- `model/config.py`：`PluginConfigModel.pip_index_url` 字段移除（旧配置文件中的残留键会被 Pydantic 忽略，无需手工清理）。
- 打包：两个 spec 移除 `runtime/python` datas 打包块（体积回退数十 MB）。
- 界面：插件管理弹窗移除「Pip 源」配置行与每行「Pip安装」按钮（`ui_web/api/app_api.py` 与 `ui_web/static/js/plugins.js`）。

## 保留不变

- manifest 的 `python_version` / `app_version` 兼容校验（zip 安装前的强校验）不受影响——那是独立于 pip 模式的版本配套机制。
- 在线下载的 Gitee 按版本回退、sha256 校验、安装失败自动回滚等能力不变。

## 验证

- ruff（F/E9）通过；`plugins.manager` 导入链正常，`install_from_pip` / `read_pip_index_url` 等入口确认不存在，`install_from_zip` / `download_and_install` 保留。
- `PluginConfigModel` 不再含 `pip_index_url`；Bridge `get_plugin_settings` 返回中无 pip 字段；三个插件状态读取正常。
- 前端 `plugins.js` 语法检查通过，Pip 相关 UI 与调用点清零。

## 影响

- 已通过 Pip 模式安装过的插件目录无需处理（manifest 结构与 zip 安装一致，仍可正常激活、被在线下载/本地安装覆盖重装）。
- 打包产物体积较含内置运行时的版本减少约 15~40MB（视运行时版本而定）。
