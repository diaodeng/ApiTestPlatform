# 由 scripts/build_plugins.py 自动生成，请勿手工编辑。
# 各插件「pip 安装」模式的锁定版本清单（与构建插件 zip 的虚拟环境版本一致）。
PLUGIN_PIP_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "desktop-test": ("opencv-python-headless==5.0.0.93", "numpy==2.5.2", "pytesseract==0.3.13", "pyautogui==0.9.54", "pygetwindow==0.0.9", "pynput==1.8.2", "pyscreeze==1.0.1", "pymsgbox==2.0.1", "pytweening==1.2.0", "mouseinfo==0.1.3", "six==1.17.0", "pillow==12.3.0",),
    "web-test": ("playwright==1.62.0",),
    "proxy": ("mitmproxy==12.2.3", "mitmproxy-rs==0.12.11", "mitmproxy-windows==0.12.11", "aioquic==1.2.0", "pylsqpack==0.3.24", "service-identity==24.2.0", "pyasn1==0.6.4", "pyasn1_modules==0.4.2", "tornado==6.5.5", "flask==3.1.0", "werkzeug==3.1.8", "jinja2==3.1.6", "markupsafe==3.0.3", "itsdangerous==2.2.0", "click==8.4.2", "blinker==1.9.0", "cryptography==44.0.3", "cffi==2.1.1", "pycparser==3.0", "pyopenssl==25.0.0", "h2==4.3.0", "hpack==4.2.0", "hyperframe==6.1.0", "wsproto==1.2.0", "msgpack==1.1.2", "zstandard==0.25.0", "brotli==1.2.0", "kaitaistruct==0.10", "ldap3==2.9.1", "argon2-cffi==23.1.0", "bcrypt==5.0.0", "publicsuffix2==2.20191221", "pyperclip==1.9.0", "ruamel.yaml==0.18.10", "urwid==2.6.16", "wcwidth==0.8.2", "pydivert==2.1.0", "asgiref==3.8.1", "pyparsing==3.2.1", "sortedcontainers==2.4.0", "attrs==26.1.0",),
}
