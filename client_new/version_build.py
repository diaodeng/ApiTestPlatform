"""客户端构建信息加载器（本文件进 git，构建过程不修改本文件）。

scripts/build_release.py 打包前会把实际构建信息写入 version_build_local.py
（已 gitignore，多机/多人构建互不干扰、不污染工作区状态），本模块负责加载并
对外暴露常量，供 utils / 关于页 / build_plugins 使用：

- PyInstaller 打包时 version_build_local.py 已在磁盘上，随静态分析一起打入产物，
  关于页可展示构建模式 / tag / commit / 时间，用于追溯包体来源；
- 源码直跑或未走构建脚本时 local 文件不存在，回退为空值，导入不失败；
- 构建信息不参与升级版本比较，比对始终以 version.py 的纯数字四段版本为准。
"""

try:
    from version_build_local import (  # noqa: F401
        BUILD_COMMIT,
        BUILD_COMMIT_SHORT,
        BUILD_DIRTY,
        BUILD_MODE,
        BUILD_TAG,
        BUILD_TIME,
        BUILD_VERSION,
    )
except ImportError:
    BUILD_MODE = ""
    BUILD_VERSION = ""
    BUILD_TAG = ""
    BUILD_COMMIT = ""
    BUILD_COMMIT_SHORT = ""
    BUILD_TIME = ""
    BUILD_DIRTY = False
