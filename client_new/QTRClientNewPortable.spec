# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo,
    StringFileInfo, StringTable, StringStruct,
    VarFileInfo, VarStruct,
)


project_root = Path(SPEC).resolve().parent

# 从 version.py 读取版本号，作为 exe 文件属性中的版本元数据
sys.path.insert(0, str(project_root))
from version import __version__ as _app_version

_version_tuple = tuple(int(x) for x in _app_version.split("."))
while len(_version_tuple) < 4:
    _version_tuple = (*_version_tuple, 0)

icon_file = project_root / "assets" / "favicon.ico"

# 插件化瘦身：以下重依赖不再打入主程序，由「插件管理」按需安装到
# storage/plugins/<name>/，应用启动时由 plugins.manager 激活到 sys.path。
# 对应插件包由 scripts/build_plugins.py 构建到 dist_plugins/。
PLUGIN_EXCLUDES = [
    # desktop-test 插件
    "cv2",
    "numpy",
    "PIL",
    "pyautogui",
    "pyscreeze",
    "pymsgbox",
    "pytweening",
    "mouseinfo",
    "pygetwindow",
    "pynput",
    "pytesseract",
    # web-test 插件
    "playwright",
    # proxy 插件（mitmproxy 内核及其独占依赖；certifi/h11/sortedcontainers/pyparsing
    # 为 httpx 等主程序共享依赖必须保留，Cryptodome 被 py7zr 使用也保留）
    "mitmproxy",
    "mitmproxy_rs",
    "mitmproxy_windows",
    "aioquic",
    "pylsqpack",
    "service_identity",
    "pyasn1",
    "tornado",
    "flask",
    "werkzeug",
    "jinja2",
    "markupsafe",
    "itsdangerous",
    "click",
    "blinker",
    "cryptography",
    "cffi",
    "pycparser",
    "OpenSSL",
    "h2",
    "hyperframe",
    "wsproto",
    "msgpack",
    "zstandard",
    "brotli",
    "_brotli",
    "ldap3",
    "argon2",
    "bcrypt",
    "kaitaistruct",
    "publicsuffix2",
    "pyperclip",
    "ruamel",
    "urwid",
    "wcwidth",
    "pydivert",
    "asgiref",
    "pyparsing",
    "sortedcontainers",
    "attrs",
]

datas = []
if icon_file.exists():
    datas.append((str(icon_file), "assets"))

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # proxy 插件运行期需要的标准库（主程序不可达，PyInstaller 不会自动打包）
        "struct",
        "http.cookies",
        "logging.handlers",
        "wsgiref.validate",
        "wsgiref.types",
        "xml.dom.minidom",
        "server.agent_server",
        "controller.agent_controller",
        "ui.dialogs.agent_server_manage_dialog",
        "ui.dialogs.agent_browser_setting_dialog",
        "ui.dialogs.plugin_manager_dialog",
        "services.mitmproxy_service.helper_process",
        "services.mitmproxy_service.mock_handle",
        "services.mitmproxy_service.runtime_config",
        "services.mitmproxy_service.windows_redirector_util",
        "mitmproxy_windows",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=PLUGIN_EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QTRClientNew",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
    icon=str(icon_file) if icon_file.exists() else None,
    version=VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=_version_tuple,
            prodvers=_version_tuple,
            mask=0x3f,
            flags=0x0,
            OS=0x4,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo([
                StringTable('000004b0', [
                    StringStruct('CompanyName', 'QTR'),
                    StringStruct('FileDescription', 'QTRClientNew'),
                    StringStruct('FileVersion', _app_version),
                    StringStruct('InternalName', 'QTRClientNew'),
                    StringStruct('LegalCopyright', ''),
                    StringStruct('OriginalFilename', 'QTRClientNew.exe'),
                    StringStruct('ProductName', 'QTRClientNew'),
                    StringStruct('ProductVersion', _app_version),
                ])
            ]),
            VarFileInfo([VarStruct('Translation', [0, 1200])]),
        ],
    ),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="QTRClientNew_portable",
)
