# 2026-09-12 桌面客户端 Qt 运行时二次瘦身（-46MB）

## 背景

插件化拆分后主程序仍偏大：目录版 `_internal` 实测 122MB，用户预期"Python 二十多 MB + 基础依赖 + 源码"不该有这个体量。逐层统计定位：PySide6 一个目录占 92MB，是绝对大头；插件化已排除的重依赖（cv2/numpy/playwright/mitmproxy 等）确实没进来，剩余体积全部来自 Qt 运行时被 PyInstaller 过度收集。

用 pefile 解析打包产物全部 DLL/PYD 导入表，定位到四条"连带收集链"，全部是 PyInstaller 官方 PySide6 hook 的行为，与项目代码无关：

1. hook 检测到 import 了 `QtGui`，收集 `plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll`（虚拟键盘输入上下文插件）→ 其依赖 `Qt6VirtualKeyboard.dll` → 又依赖 `Qt6Quick.dll` → Quick 再拖入 `Qt6Qml` 全家（Qml/QmlMeta/QmlModels/QmlWorkerScript），一个不到 1MB 的插件拖进约 17MB 的 QML/Quick 引擎，而本应用是纯 QtWidgets，源码零 QML 使用；
2. `plugins/imageformats/` 全目录收集，其中 `qpdf.dll` 拖入 `Qt6Pdf.dll`（约 5MB）；
3. hook 默认携带 `opengl32sw.dll` 软件 OpenGL 渲染回退（约 20MB），有 GPU 驱动的桌面环境永远用不到；
4. 全量收集 96 个 Qt 翻译文件（约 7MB），中文环境只用到 zh_CN。

## 变更内容

新增 `client_new/scripts/qt_slim.py`（两个 spec 共用的裁剪工具），`QTRClientNew.spec`（单文件版）与 `QTRClientNewPortable.spec`（目录版）在 Analysis 完成后调用 `apply_qt_slim(a)` 对 `a.binaries`/`a.datas` 原位过滤：

- 剔除 DLL：`opengl32sw.dll`、`Qt6Quick.dll`、`Qt6Qml*.dll`（3 个）、`Qt6VirtualKeyboard.dll`、`Qt6Pdf.dll`；
- 剔除插件：`plugins/platforminputcontexts/` 整目录、`plugins/imageformats/qpdf.dll`（消除上述 DLL 被连带收集的根因）；
- 翻译只保留 `*_zh_CN.qm`（qt/qtbase/qt_help 三个），其余 93 个语言文件剔除。

必需组件全部保留：`qwindows`/`qdirect2d` 平台插件、Qt6Network、Qt6OpenGL、Qt6Svg、imageformats 其余格式、tls 插件等。

## 效果

- 目录版 `_internal`：122MB → 76MB（-46MB，-38%），共剔除 103 个条目；
- 单文件版 exe：55MB → 37.6MB（压缩比不变，构成一致）；
- 若后续启用 QML/Quick 界面或 QtPdf 能力，需同步删除 `scripts/qt_slim.py` 中对应规则。

## 验证

- 重新打包目录版与单文件版均成功（exit=0）；
- pefile 全量依赖一致性检查：产物内所有 DLL/PYD 的非系统依赖全部存在，无因剔除产生的新断链（`Qt6Core` 对 `icuuc.dll` 为 Qt 延迟加载可选项，与瘦身前状态一致）；
- 冒烟测试：便携版 exe 正常启动运行（进程存活、fatal_error.log 无异常输出），测试后结束进程；
- 单文件版未做启动冒烟（与目录版同一套 Analysis 产物与裁剪规则，风险一致）。

## 剩余风险

- 极少数无 GPU 驱动的远程桌面/虚拟机环境下，Qt 窗口渲染可能因缺少 `opengl32sw.dll` 软件回退而异常（如需兼容，删除 `scripts/qt_slim.py` 中 opengl32sw 的剔除规则重打即可）；
- 系统语言若不是 zh_CN，Qt 自带的标准对话框文案将显示英文（应用自身文案不受影响，全部内置中文）；
- 体积进一步下降（75MB 以下）需要换打包方案（Qt 模块裁剪/静态构建），不属于本次范围。
