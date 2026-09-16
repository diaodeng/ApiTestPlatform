from version_build import BUILD_COMMIT_SHORT, BUILD_DIRTY, BUILD_MODE, BUILD_TAG, BUILD_TIME

from version import __version__ as VERSION

# 构建信息说明：version_build.py 为进 git 的固定加载器，实际构建信息在构建时由
# scripts/build_release.py 写入 version_build_local.py（gitignore），随 PyInstaller
# 打入产物供关于页追溯包体来源；未走构建脚本时各字段为空值，详见 version_build.py。


def get_build_label() -> str:
    """
    组装构建信息展示标签，关于页在版本号旁展示，用于追溯包体来源。
    :return: 如「正式版 · tag v1.1.1.0 · commit 7ab2bc27 · 2026-09-13 12:00:00」，
             未走构建脚本时返回空串
    """
    parts: list[str] = []
    if BUILD_MODE == "release":
        parts.append("正式版")
        if BUILD_TAG:
            parts.append(f"tag {BUILD_TAG}")
    elif BUILD_MODE == "dev":
        parts.append("开发版")
    if BUILD_COMMIT_SHORT:
        parts.append(f"commit {BUILD_COMMIT_SHORT}")
    if BUILD_TIME:
        parts.append(BUILD_TIME)
    if BUILD_DIRTY:
        parts.append("含未提交改动")
    return " · ".join(parts)
