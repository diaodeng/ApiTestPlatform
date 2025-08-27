# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/tools_config.json', './'),      # 配置文件放在 exe 同级目录
        ('src/storage', 'storage'),        # storage 目录下的文件打包到 dist/MyApp/storage/
    ],
    hiddenimports=[
        'flet',
        'flet_core',
        'tkinter',   # Flet 内部 UI 依赖
        'grpc',
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
    a.binaries,
    a.datas,
    [],
    name='MyApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='D:\\ALLTMP\\91f21e28-b18b-4465-bc49-6f6cf0da1b9b',
)
