---
title: 客户端一键发版构建
type: entity
entity_category: component
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-09-13
created: 2026-09-13
updated: 2026-09-13
related_files:
  - client_new/scripts/build_release.py
  - client_new/scripts/build_plugins.py
  - client_new/version.py
  - client_new/version_build.py
  - client_new/utils/__init__.py
  - client_new/ui_web/api/about_api.py
  - client_new/QTRClientNew.spec
  - client_new/QTRClientNewPortable.spec
---

# 客户端一键发版构建

桌面客户端（client_new）的发版/开发打包统一走 `client_new/scripts/build_release.py`：
编排 PyInstaller 两个 spec（单文件版 + 便携目录版）、插件包构建（build_plugins.py）与发版产物整理，
并注入构建信息供关于页追溯包体来源。

```mermaid
flow TD
  A[build_release.py] --> B{mode?}
  B -->|dev| C[dist_dev/：宽松，允许脏工作区]
  B -->|release| D[三道闸门] --> E[dist_release/：exe + portable.zip + 插件 + manifest]
  A --> F[生成 version_build.py] --> G[PyInstaller 两个 spec]
  A --> H[build_plugins.py --out]
```

## 版本与发版约定

- 版本号唯一来源：`client_new/version.py`，纯数字四段式（主.次.修.附，第四段留 hotfix）。
- tag 约定：`v{版本号}`（如 `v1.1.1.0`），打在 master_params 发版提交上；tag 不可挪，撤版用新 hotfix 版本。
- 客户端升级比对（`utils/gitee_release.py: normalize_release_version`）用 `re.findall(r"\d+")` 抽数字，
  `v` 前缀无影响；tag 禁止带「字母+数字」后缀（如 `-rc1` 会被当成更大版本触发全员升级），且段数必须恒为四段。
- 三端版本（client_new / server / web package.json）保持一致，发版时手工同步（当前无自动回写）。

## 构建模式与闸门

| | dev（默认） | release |
|---|---|---|
| 工作区干净 | 不要求 | 硬闸门（`git status --porcelain` 为空，含未跟踪文件） |
| tag == v{version.py} 且在 HEAD | 不要求 | 硬闸门（`git describe --tags --exact-match HEAD`） |
| Gitee 无同名 release | 不要求 | 硬闸门（`fetch_release_list_sync` 查询，网络失败即拒绝） |
| 产物目录 | `client_new/dist_dev/` | `client_new/dist_release/` |
| 便携升级包 zip / .sha256 | 不生成 | 生成（`QTRClientNew_portable.zip` + 各产物 sha256） |
| release-manifest.json | 生成 | 生成 |

发版操作顺序：**改 version.py → commit → 打 tag → 跑 release 构建 → 建 Gitee release 按清单上传产物**。
tag 先于构建：tag 代表代码状态，产物有问题重跑同一个 tag，不允许挪 tag。

## 产物命名（与自更新资产匹配规则对齐）

- `QTRClientNew.exe`：单文件版（`utils/common.py: _asset_match_score` 精确名 300 分）。
- `QTRClientNew_portable.zip`：便携目录版压缩（zip 根即 exe + `_internal`，与 PowerShell 更新脚本
  `Expand-Archive` 后 `Resolve-SourceDir` 兼容；命中 `_portable_zip_exact_names` 340 分 + portable 提示分）。
- `plugins/<插件名>.zip` + `.sha256`：插件包，沿用插件名命名；`.sha256` 后缀不被
  `_parse_release_asset_name` 识别，不会干扰升级资产选择。

## 构建信息注入

采用「进 git 的固定加载器 + gitignore 的动态值文件」两层设计（适配多机构建）：

- **`version_build.py`（进 git，构建过程不修改）**：固定加载器，try-import 下面的
  local 文件并对外暴露 `BUILD_MODE / BUILD_VERSION / BUILD_TAG / BUILD_COMMIT /
  BUILD_COMMIT_SHORT / BUILD_TIME / BUILD_DIRTY`，local 不存在时回退空值。
- **`version_build_local.py`（gitignore，随构建实时生成）**：build_release.py 打包前
  写入实际构建值；PyInstaller 打包时两者随静态分析一起打入产物。

消费方：
- `utils/__init__.py` 直接 import 加载器并暴露 `get_build_label()`，源码直跑回退空串；
- 关于页 `about.get_info` 返回 `build_label`，前端展示在版本号旁（如「正式版 · tag v1.1.1.0 · commit xxx」）；
- `build_plugins.py` 把 `build_mode / build_commit` 写进插件 manifest；
- 构建信息**不参与升级版本比较**，比对始终以 version.py 纯数字版本为准（即使标签
  泄漏进比对串，归一化结果不变）。

> 为什么动态值不直接写进 version_build.py 并提交：BUILD_COMMIT 记录的哈希在逻辑上
> 不可能等于包含它自己的提交（自指悖论），且每次构建改写会弄脏工作区、与发版闸门
> 「工作区干净」直接冲突、多机构建产生假 diff——可推导的动态值属于生成物，不入库。

## 版本库跟踪约定（2026-09-13 清理）

以下产物已退出 git 跟踪（`git rm --cached` + ignore），分发统一走 Gitee release 附件：
`client_new/dist_plugins/`（插件 zip + sha256）、`client_new/build_webview/`、
`client_new/dist_webview/`、`client_new/build_log*.txt`、`.codeweaver/`。
插件 zip 此前被跟踪导致每次发版都要把 ~121MB 二进制 blob 提交进历史，且与发版闸门
「工作区干净」冲突；退出后发版流程为：改 version.py → commit（纯源码）→ 打 tag →
release 构建 → 按 release-manifest.json 清单上传 Gitee release。

## 注意事项

- version_build_local.py 必须在 PyInstaller 运行前生成（build_release.py 已保证），
  否则包内构建信息为空；不要手工删除后直接用 spec 打包。
- dev 构建会把 dirty 状态写进构建信息（关于页显示「含未提交改动」），此类产物禁止上传 release。
- 插件 zip 体积大（含 opencv/playwright/mitmproxy），构建耗时数分钟属正常。
