---
title: 插件在线下载支持 Gitee 按版本自动下载
date: 2026-09-13
category: client
---

# 插件在线下载支持 Gitee 按版本自动下载

## 背景

插件化架构下，插件在线下载此前完全依赖手动配置的下载源根地址（`config_plugins.json` 的 `download_base_url`），未配置时「在线下载」直接提示无法使用，默认体验断裂。

而主程序的「检查更新」早已通过 Gitee API v5 拉取 releases 列表（`utils/common.py`），发版时主程序包就挂在 release 附件上。插件包（含与主程序 Python 版本绑定的 `.pyd` 编译产物）本就必须与主程序版本配对发布，因此把插件 zip 与主程序放进同一个 release 附件、客户端按当前版本自动定位下载，是更合理的默认路径。

## 变更内容

### 下载源优先级（`plugins/manager.py`）

`download_and_install` 的地址解析改为两级：

1. **配置了自定义下载源**：行为不变，从 `{下载源}/{插件名}.zip` 下载（兼容企业内网静态文件服务场景）；
2. **未配置下载源**：从 Gitee releases 中查找 tag 与当前客户端版本号（`version.py`）归一化后一致的 release，下载其中的 `{插件名}.zip` 附件；`{插件名}.zip.sha256` 附件存在时同样强校验。

找不到对应版本 release 或 release 中未上传插件附件时，给出明确中文提示（等待发版 / 配置下载源 / 本地安装），不静默失败。

### 共享逻辑下沉（新增 `utils/gitee_release.py`）

Gitee releases API 地址、版本号归一化、release/附件定位逻辑原本只存在于 `utils/common.py`（私有函数），现下沉为独立 util，供主程序更新检查（async）与插件下载（sync）两个链路共用，消除 URL 双份硬编码漂移风险：

- `GITEE_RELEASES_API_URL`：releases 列表接口地址；
- `normalize_release_version`：版本号/tag 归一化为数字元组（兼容 `v1.1.1.0` 与 `1.1.1.0`）；
- `fetch_release_list` / `fetch_release_list_sync`：异步/同步拉取 release 列表；
- `find_release_by_version`：按客户端版本精确匹配 release；
- `find_release_asset`：按文件名精确定位 release 附件。

`utils/common.py` 中的 `_RELEASES_API_URL`、`_fetch_release_list`、`_normalize_version_tuple` 已删除，调用方同步切换，无旧入口残留。

### 界面调整（`ui/dialogs/plugin_manager_dialog.py`）

- 移除「在线下载」前"必须先填写下载源"的前置拦截；
- 下载源输入框占位文案更新为"留空时自动从 Gitee 下载与当前客户端版本一致的插件包"。

## 发版约定（重要）

发布 release 时需满足：

1. **tag 名与 `version.py` 的 `__version__` 一致**（如 `v1.1.1.0`，带不带 `v` 均可，匹配时忽略）；
2. **同一 release 上传三个插件附件**：`desktop-test.zip`、`web-test.zip`、`proxy.zip`，以及可选的对应 `.sha256` 校验文件（由 `scripts/build_plugins.py` 产出，位于 `client_new/dist_plugins/`）。

插件包内的 `.pyd` 等编译产物与构建时的 Python 版本绑定，**禁止跨版本混用插件包**，这正是按版本精确匹配（而非取最新 release）的原因。

## 验证

- 新增 `tests/test_gitee_release.py`（版本归一化 / release 匹配 / 附件定位，含 assets 结构异常分支），运行通过；
- 真实 Gitee 接口实测：API 可达，当前版本 `1.1.1.0` 尚未发布 release（最新 `v1.1.0.0`），未匹配时提示正确；`v1.1.0.0` 的 release 定位与附件清单读取正常；
- `uvx ruff check`（I001/ISC004/F 规则）通过；`plugins.manager`、`utils.common`、`ui.dialogs.plugin_manager_dialog` 导入链路正常。

## 剩余风险

- manifest.json 目前未记录构建时的应用版本与 Python 版本，版本配对完全依赖"同 release 发布"的约定，后续可在 `build_plugins.py` 中补充字段；
- Gitee release 附件有单文件大小上限（desktop-test.zip 当前 64MB），附件膨胀需关注；
- releases 列表接口每次取 20 条（`per_page=20`），若积压超过 20 个 release 且目标版本不在其中会匹配不到，属极端场景。
