---
title: 客户端一键发版构建
date: 2026-09-13
tags: [client-new, 发版构建]
---

# 客户端一键发版构建

新增 `client_new/scripts/build_release.py` 一键构建脚本，把原先分散手工执行的
PyInstaller 主程序打包、插件包构建与发版产物整理编排为一条命令，并区分
「开发打包」与「正式发版」两种模式，发版打包带三道硬校验（工作区干净、
tag 与版本号一致且在当前提交上、Gitee 无同名 release），从流程上杜绝
"产物来历不明"和"覆盖已发版本"。

## 主要变化

- **构建模式**：`--mode dev`（默认）允许有未提交代码、不要求 tag，产物落
  `client_new/dist_dev/`；`--mode release` 三道闸门任一不满足直接拒绝，产物落
  `client_new/dist_release/`。可选 `--skip-exe`、`--skip-plugins` 分步执行。
- **发版操作顺序**：改 `version.py` → commit → 打 tag（如 `v1.1.1.0`）→
  跑 release 构建 → 建 Gitee release 按清单上传产物。
- **构建信息注入**：进 git 的 `version_build.py` 是固定不变的加载器（未生成构建信息时
  回退空值），构建时实际值由脚本写入 gitignore 的 `version_build_local.py`（多机构建
  互不干扰、不弄脏工作区）；关于页在版本号旁展示构建信息（如「正式版 · tag v1.1.1.0 ·
  commit 7ab2bc27 · 时间」），插件包 manifest 同步写入 `build_mode` / `build_commit`。
- **产物命名与自更新兼容**：正式包命名为 `QTRClientNew.exe` 与
  `QTRClientNew_portable.zip`（zip 根即 exe + `_internal`，与 PowerShell 自更新
  解压逻辑兼容），各产物附 `.sha256` 校验文件；生成 `release-manifest.json`
  （版本、tag、commit、全部文件 sha256 清单），上传 release 时照单核对。
- **升级比对确认**：客户端版本比对按数字归一化（`v` 前缀无影响），但 tag
  禁止带「字母+数字」后缀（如 `-rc1` 会被误判为更高版本触发全员升级），
  且必须保持四段纯数字。

## 版本与代码管理约定（成文）

- 版本号唯一来源 `client_new/version.py`，纯数字四段式，第四段留给 hotfix；
  tag 格式 `v{版本号}`，tag 打出后不可挪动，撤版修复用新 hotfix 版本号。
- 同一 tag 的 Gitee release 上传：主程序 exe、便携 zip、三个插件 zip 及各自
  `.sha256`，与 `release-manifest.json` 清单一致。

## 版本库跟踪清理（本次同步完成）

以下构建产物退出 git 跟踪（`git rm --cached` + ignore，磁盘文件保留），分发统一走
Gitee release 附件：`client_new/dist_plugins/`（插件 zip + sha256，约 121MB）、
`client_new/build_webview/`（PyInstaller 中间产物）、`client_new/dist_webview/`（打包
exe）、`client_new/build_log*.txt`、`.codeweaver/`（代码索引）。此前插件 zip 被跟踪，
每次发版都要把二进制 blob 提交进历史，且与发版闸门「工作区干净」冲突；退出后
发版提交只含纯源码变更。

详细设计见 wiki《客户端一键发版构建》。
