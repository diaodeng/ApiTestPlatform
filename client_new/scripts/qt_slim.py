"""PyInstaller spec 共用的 Qt 运行时裁剪工具。

背景：
    本应用是纯 QtWidgets 桌面程序，但 PyInstaller 官方 PySide6 hook 会按
    "包目录" 级别连带收集大量用不到的 Qt 运行时：
    1. 收集 platforminputcontexts 虚拟键盘插件 -> 拖入 Qt6VirtualKeyboard.dll
       -> 其依赖 Qt6Quick.dll -> Quick 再拖入 Qt6Qml 全家（约 17MB）；
    2. 收集 imageformats 全目录，其中 qpdf.dll 拖入 Qt6Pdf.dll（约 5MB）；
    3. 默认携带 opengl32sw.dll 软件 OpenGL 渲染回退（约 20MB）；
    4. 全量收集 96 个 Qt 翻译文件（约 7MB，中文环境只用到 zh_CN）。

    本模块在 Analysis 完成后对 a.binaries / a.datas 做统一过滤，两个 spec
    （QTRClientNew.spec 单文件版、QTRClientNewPortable.spec 目录版）共用，
    避免规则重复维护。预计可减少约 45MB。

使用方式（spec 文件中，Analysis 之后调用）：
    from scripts.qt_slim import apply_qt_slim
    a = Analysis(...)
    apply_qt_slim(a)

注意事项：
    - 只剔除确证无引用链的文件（已用 pefile 分析过打包产物 DLL 导入表），
      qwindows 平台插件、Qt6Network、Qt6OpenGL 等必需组件全部保留；
    - 若未来新增 QML/Quick 界面或 QtPdf 能力，必须同步删除对应过滤规则。
"""

import fnmatch

# 需要剔除的 Qt DLL（按打包产物内的小写路径精确匹配）
_QT_DROP_DLLS = {
    "pyside6/opengl32sw.dll",          # 软件 OpenGL 渲染回退，有 GPU 驱动时用不到
    "pyside6/qt6quick.dll",            # QML/Quick 引擎，纯 Widgets 应用不使用
    "pyside6/qt6qml.dll",
    "pyside6/qt6qmlmeta.dll",
    "pyside6/qt6qmlmodels.dll",
    "pyside6/qt6qmlworkerscript.dll",
    "pyside6/qt6virtualkeyboard.dll",  # 虚拟键盘，仅触屏输入上下文插件使用
    "pyside6/qt6pdf.dll",              # 仅被 imageformats/qpdf.dll 引用
}

# 需要剔除的插件目录/文件（这些插件的存在是上述 DLL 被连带收集的根因）
_QT_DROP_PLUGIN_PATTERNS = [
    "pyside6/plugins/platforminputcontexts/*",   # 虚拟键盘输入上下文 -> 拖入 Quick/Qml 全家
    "pyside6/plugins/imageformats/qpdf.dll",     # PDF 图片插件 -> 拖入 Qt6Pdf
]

# 翻译文件只保留简体中文，其余语言全部剔除
_QT_TRANSLATION_DIR = "pyside6/translations/"


def _norm(name: str) -> str:
    """归一化 PyInstaller TOC 条目名：统一正斜杠并转小写，便于匹配。"""
    return name.replace("\\", "/").lower()


def _should_drop(name: str) -> bool:
    """判断一个打包条目（dest_name）是否命中裁剪规则。

    参数:
        name: PyInstaller TOC 条目的目标路径，如 "PySide6/Qt6Quick.dll"。
    返回:
        True 表示应从打包结果中剔除。
    """
    n = _norm(name)
    # 1. 明确剔除的 Qt DLL
    if n in _QT_DROP_DLLS:
        return True
    # 2. 命中插件剔除模式的文件
    for pattern in _QT_DROP_PLUGIN_PATTERNS:
        if fnmatch.fnmatch(n, pattern):
            return True
    # 3. 非简体中文的 Qt 翻译文件（保留 *_zh_CN.qm）
    return (
        n.startswith(_QT_TRANSLATION_DIR)
        and n.endswith(".qm")
        and not n.endswith("_zh_cn.qm")
    )


def _filter_toc(toc, kind: str) -> int:
    """原位过滤一个 PyInstaller TOC 列表（binaries 或 datas）。

    参数:
        toc: Analysis 产出的 TOC 列表，元素为 (dest_name, src_path, typecode)。
        kind: 日志标识（"binaries" / "datas"）。
    返回:
        剔除的条目数量。
    """
    kept = [entry for entry in toc if not _should_drop(entry[0])]
    removed = len(toc) - len(kept)
    if removed:
        for entry in toc:
            if _should_drop(entry[0]):
                print(f"[qt_slim] 剔除 {kind}: {entry[0]}")
        toc[:] = kept
    return removed


def apply_qt_slim(a) -> None:
    """对 Analysis 结果执行 Qt 运行时裁剪（原位修改）。

    参数:
        a: PyInstaller Analysis 对象，本函数会过滤其 binaries 与 datas
           属性，后续 EXE / COLLECT 引用的是过滤后的结果。
    """
    removed = _filter_toc(a.binaries, "binaries") + _filter_toc(a.datas, "datas")
    print(f"[qt_slim] 共剔除 {removed} 个 Qt 运行时条目")
