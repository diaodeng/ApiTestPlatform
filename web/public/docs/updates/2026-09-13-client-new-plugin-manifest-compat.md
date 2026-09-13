---
title: 插件包 manifest 版本兼容信息与跨版本回退下载
date: 2026-09-13
category: client
---

# 插件包 manifest 版本兼容信息与跨版本回退下载

## 背景

上一轮"插件 Gitee 按版本下载"落地后，在线下载要求 release 中存在插件附件，且版本配对完全依赖"同 release 发布"的约定——`manifest.json` 没有记录构建时的 Python 版本与应用版本，客户端无法自行判断一个插件包能不能装。

两点技术事实决定了演进方向：

1. **Python 版本是硬约束**：插件包内的 `.pyd` 等编译产物只能被构建时的 CPython 大.小版本导入，跨解释器版本必然 import 失败；
2. **应用版本是软约定**：插件包内是第三方依赖而非主程序代码，"哪个 release 的插件包"技术上不重要，同 release 发版的真正价值是"经过一起测试的组合"背书。

因此把这两个信息写进 manifest，让"Python 版本必须匹配"变成客户端可自行校验的硬门槛，"应用版本一致"从硬绑定降级为推荐项。

## 变更内容

### 构建脚本（`scripts/build_plugins.py`）

manifest 新增两个字段：

- `python_version`：构建时的 CPython 大.小版本（如 `3.11`，`.pyd` 兼容粒度）；
- `app_version`：构建时配套的客户端版本号（读 `version.py`），仅供参考。

### 安装校验（`plugins/manager.py`）

- 新增 `_manifest_compatibility_error`：manifest 的 `python_version` 与当前运行时（打包态即 PyInstaller 内嵌解释器）大.小版本不一致时**拒绝安装**，字段缺失或无法解析时跳过校验以兼容旧格式包；该校验在 `install_from_zip` 入口执行，**在线下载、配置源下载、本地安装三条路径统一生效**，且拒绝发生在解压/替换之前，不动已有插件目录。
- 安装成功的返回消息中，若 manifest 的 `app_version` 与当前客户端版本不同，追加"插件包配套应用版本 x.x.x.x，与当前客户端版本不同，建议关注兼容性"的软提示。

### 下载回退策略（`_resolve_gitee_plugin_urls`）

未配置下载源时，Gitee 定位策略从"仅同版本 release"放宽为：

1. 优先取 tag 与当前客户端版本一致的 release（发版配套组合）；
2. 该 release 缺插件附件（或当前版本尚无 release）时，按最新在前回退到其他 release 中第一个含 `{name}.zip` 附件的；Python 版本兼容性由上述安装前强校验兜底，回退不会装上解释器版本错误的包；
3. 安装成功消息中注明回退来源（"插件包来自 release vX.Y.Z.Z，非当前版本配套包，已校验 Python 版本兼容"）；所有 release 均无附件时给出明确提示。

## 验证

- 新增 `tests/test_plugin_manifest_compat.py`：匹配通过（含带微版本写法）、不匹配拒绝、字段缺失/异常跳过，全部通过；
- 端到端：构造 `python_version=3.8` 的 zip 调 `install_from_zip`，正确拒绝且插件目录未被改动；
- 本地执行 `build_plugins.py web-test`，产物 manifest 正确包含 `python_version`/`app_version`；
- 真实 Gitee 冒烟：当前版本无 release 且各 release 均无插件附件时，回退扫描与失败提示正确；
- ruff（I001/ISC004/F/E9）通过，`plugins.manager` 导入链正常。

## 剩余风险

- 跨版本回退安装的插件包不是发版时一起测试的组合，主程序对库的调用方式与旧插件包库版本可能不兼容（失败时业务功能返回明确报错，可重装配套版本解决）；
- `build_plugins.py` 若在不同 Python 版本的虚拟环境中执行，产物 `python_version` 会跟随执行环境——**构建插件包必须使用与打包主程序相同的虚拟环境**（即 `client_new/.venv`），发版流程需保持这一约束。
