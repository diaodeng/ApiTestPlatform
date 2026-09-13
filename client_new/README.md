# QTRClientNew（桌面客户端，pywebview）

## 运行

```bash
uv sync
uv run python main.py
```

## 构建打包（scripts/build_release.py）

一键编排 PyInstaller 主程序打包（单文件版 + 便携目录版）、插件包构建（build_plugins.py）与产物整理。

```bash
# 开发打包（默认）：允许未提交代码，产物在 dist_dev/
uv run python scripts/build_release.py

# 正式发版打包：三道硬闸门（工作区干净、HEAD 上有 tag v{version.py 版本}、Gitee 无同名 release），
# 任一不满足拒绝构建；产物在 dist_release/（exe、portable.zip、插件、sha256、release-manifest.json）
uv run python scripts/build_release.py --mode release

# 可选：--skip-exe 只构建插件；--skip-plugins 只构建主程序
```

发版操作顺序：改 `version.py` → commit → `git tag v1.1.1.0` → 跑 `--mode release` 构建 →
建 Gitee release 按 `release-manifest.json` 清单上传产物。

构建信息（模式/tag/commit/时间）由构建脚本写入 gitignore 的 `version_build_local.py`，
进 git 的 `version_build.py` 是固定加载器（多机构建互不干扰），关于页在版本号旁展示。
插件 zip 等构建产物不入 git，分发走 Gitee release 附件。详细设计见仓库
`wiki/entities/components/client-release-build.md`。

## 插件包（可单独执行）

```bash
uv run python scripts/build_plugins.py              # 默认输出 dist_plugins/
uv run python scripts/build_plugins.py --out <目录>  # 指定输出目录
```
