# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path(SPEC).resolve().parent
icon_file = project_root / "assets" / "favicon.ico"

datas = collect_data_files("playwright")
datas += collect_data_files("mitmproxy")
datas += collect_data_files("mitmproxy_windows")
if icon_file.exists():
    datas.append((str(icon_file), "assets"))

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "playwright.async_api",
        "playwright._impl._driver",
        "server.agent_server",
        "controller.agent_controller",
        "ui.dialogs.agent_server_manage_dialog",
        "ui.dialogs.agent_browser_setting_dialog",
        "services.mitmproxy_service.helper_process",
        "services.mitmproxy_service.mock_handle",
        "services.mitmproxy_service.runtime_config",
        "services.mitmproxy_service.windows_redirector_util",
        "mitmproxy_windows",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
