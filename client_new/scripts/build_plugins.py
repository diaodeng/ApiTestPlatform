"""
插件包构建脚本：从当前虚拟环境 .venv 收集重依赖打包为可分发的插件 zip。

产物：<输出目录>/<name>.zip 与 <name>.zip.sha256（默认 client_new/dist_plugins/，
可由 build_release.py 通过 --out 指定到 dist_dev/plugins、dist_release/plugins）
用法：cd client_new && uv run python scripts/build_plugins.py [--out 目录] [插件名...]
说明：插件 zip 根目录包含 manifest.json 与对应包目录（如 cv2/、numpy/、playwright/），
客户端「插件管理」支持在线下载（配合 .sha256 校验文件）或本地安装该 zip。
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
OUTPUT_DIR = PROJECT_ROOT / "dist_plugins"

# manifest 需要记录客户端应用版本号，脚本可能以任意 cwd 运行，显式把项目根加入搜索路径
sys.path.insert(0, str(PROJECT_ROOT))
# 构建信息：version_build.py 为进 git 的固定加载器，实际值由 build_release.py 构建时
# 写入 version_build_local.py（gitignore），记录进 manifest 便于追溯包体来源；
# 未走构建脚本时各字段为空值，详见 version_build.py
from version_build import BUILD_COMMIT_SHORT, BUILD_MODE  # noqa: E402

from version import __version__ as APP_VERSION  # noqa: E402

# 各插件包含的 site-packages 条目（目录或 .py 文件，不含 dist-info）；
# dist-info 按 distributions 列出的发行包名动态解析，避免硬编码版本号
PLUGIN_PACKAGE_MAP: dict[str, dict] = {
    "desktop-test": {
        "display_name": "桌面测试",
        "version_packages": ("opencv-python-headless", "numpy", "pytesseract"),
        "entries": [
            "cv2",
            "numpy",
            "numpy.libs",
            "pytesseract",
            "pyautogui",
            "pygetwindow",
            "pynput",
            "pyscreeze",
            "pymsgbox",
            "pytweening",
            "mouseinfo",
            "six.py",
            "PIL",
        ],
        "distributions": [
            "opencv-python-headless",
            "numpy",
            "pytesseract",
            "pyautogui",
            "pygetwindow",
            "pynput",
            "pyscreeze",
            "pymsgbox",
            "pytweening",
            "mouseinfo",
            "six",
            "pillow",
        ],
        "modules": ["cv2", "numpy", "pytesseract", "pyautogui", "pygetwindow", "pynput", "PIL"],
    },
    "web-test": {
        "display_name": "Web 测试",
        "version_packages": ("playwright",),
        "entries": [
            "playwright",
            # playwright 的传递依赖（uv.lock：playwright dependencies = greenlet + pyee），
            # 缺少时 import playwright 报 ModuleNotFoundError: No module named 'pyee'，
            # 守卫导入只会提示"插件缺失"误导用户重装插件。
            "pyee",
            "greenlet",
        ],
        "distributions": [
            "playwright",
            "pyee",
            "greenlet",
        ],
        "modules": ["playwright"],
    },
    "proxy": {
        "display_name": "抓包代理",
        "version_packages": ("mitmproxy", "mitmproxy_rs", "mitmproxy_windows"),
        "entries": [
            "mitmproxy",
            "mitmproxy_rs",
            "mitmproxy_windows",
            "aioquic",
            "pylsqpack",
            "service_identity",
            "pyasn1",
            "pyasn1_modules",
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
            "hpack",
            "hyperframe",
            "wsproto",
            "msgpack",
            "zstandard",
            "brotli.py",
            "kaitaistruct.py",
            "ldap3",
            "argon2",
            "_argon2_cffi_bindings",
            "bcrypt",
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
            "attr",
        ],
        # brotli/cffi 的顶层 .pyd 文件名带 Python 版本标签，动态收集
        "entry_globs": ["_brotli.*.pyd", "_cffi_backend.*.pyd"],
        "distributions": [
            "mitmproxy",
            "mitmproxy-rs",
            "mitmproxy-windows",
            "aioquic",
            "pylsqpack",
            "service-identity",
            "pyasn1",
            "pyasn1_modules",
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
            "pyopenssl",
            "h2",
            "hpack",
            "hyperframe",
            "wsproto",
            "msgpack",
            "zstandard",
            "brotli",
            "kaitaistruct",
            "ldap3",
            "argon2-cffi",
            "bcrypt",
            "publicsuffix2",
            "pyperclip",
            "ruamel.yaml",
            "urwid",
            "wcwidth",
            "pydivert",
            "asgiref",
            "pyparsing",
            "sortedcontainers",
            "attrs",
        ],
        "modules": ["mitmproxy", "mitmproxy_windows", "tornado", "aioquic"],
    },
}


def _find_dist_info(dist_name: str) -> Path | None:
    """
    在 site-packages 中按发行包名定位 dist-info 目录（大小写与分隔符不敏感）。
    :param dist_name: 发行包名（如 opencv-python-headless）
    :return: dist-info 目录路径，找不到返回 None
    """
    normalized = re.sub(r"[^\w\d.]+", "_", dist_name).lower()
    for candidate in SITE_PACKAGES.glob("*.dist-info"):
        # 先去掉 .dist-info 后缀再切版本号（否则会切在 dist-info 的连字符上）
        stem = candidate.name.removesuffix(".dist-info")
        name_part = stem.rsplit("-", 1)[0].lower()
        if name_part in (dist_name.lower(), normalized):
            return candidate
    return None


def _resolve_version(package_name: str) -> str:
    try:
        return package_version(package_name)
    except PackageNotFoundError:
        return "unknown"


def build_plugin(name: str, spec: dict, out_dir: Path) -> Path:
    """
    构建单个插件 zip。
    :param name: 插件标识
    :param spec: 插件打包配置
    :param out_dir: 产物输出目录
    :return: 生成的 zip 路径
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    missing = [entry for entry in spec["entries"] if not (SITE_PACKAGES / entry).exists()]

    # 通配条目（如带 Python 版本标签的 .pyd），逐个展开为实际文件
    globbed_entries: list[Path] = []
    for pattern in spec.get("entry_globs", []):
        matched = sorted(SITE_PACKAGES.glob(pattern))
        if not matched:
            missing.append(pattern)
        globbed_entries.extend(matched)

    # dist-info 按发行包名动态解析（跟随 venv 实际版本，避免硬编码）
    dist_info_dirs: list[Path] = []
    for dist_name in spec.get("distributions", []):
        dist_info = _find_dist_info(dist_name)
        if dist_info is None:
            missing.append(f"{dist_name} 的 dist-info")
        else:
            dist_info_dirs.append(dist_info)
    if missing:
        raise FileNotFoundError(f"虚拟环境缺少插件条目: {missing}，请先 uv sync")

    work_dir = out_dir / "_work" / name
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    for entry in spec["entries"]:
        source = SITE_PACKAGES / entry
        target = work_dir / entry
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)

    for source in globbed_entries:
        shutil.copy2(source, work_dir / source.name)

    for dist_info in dist_info_dirs:
        shutil.copytree(dist_info, work_dir / dist_info.name)

    versions = {pkg: _resolve_version(pkg) for pkg in spec["version_packages"]}
    manifest = {
        "name": name,
        "display_name": spec["display_name"],
        "version": "+".join(f"{pkg}-{ver}" for pkg, ver in versions.items()),
        "modules": spec["modules"],
        # .pyd 等编译产物只兼容构建时的 CPython 大.小版本，客户端安装前据此强校验
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        # 构建时配套的客户端应用版本，仅供参考（软约束，跨版本安装时界面会提示）
        "app_version": APP_VERSION,
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }
    # 构建模式与 commit（由 build_release.py 注入 version_build.py），便于追溯包体来源
    if BUILD_MODE:
        manifest["build_mode"] = BUILD_MODE
    if BUILD_COMMIT_SHORT:
        manifest["build_commit"] = BUILD_COMMIT_SHORT
    (work_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    zip_path = out_dir / f"{name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file_path in sorted(work_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(work_dir))

    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (out_dir / f"{name}.zip.sha256").write_text(f"{sha256}\n", encoding="utf-8")

    shutil.rmtree(out_dir / "_work", ignore_errors=True)
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"[OK] {zip_path.name}  {size_mb:.1f} MB  manifest={manifest['version']}")
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="插件包构建脚本（从 .venv 收集重依赖打包为 zip）")
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help=f"产物输出目录（默认 {OUTPUT_DIR}）",
    )
    parser.add_argument(
        "plugins",
        nargs="*",
        help="要构建的插件名，留空构建全部",
    )
    args = parser.parse_args()

    if not SITE_PACKAGES.exists():
        print(f"未找到虚拟环境 site-packages: {SITE_PACKAGES}")
        sys.exit(1)

    requested = args.plugins or list(PLUGIN_PACKAGE_MAP)
    for name in requested:
        spec = PLUGIN_PACKAGE_MAP.get(name)
        if spec is None:
            print(f"未知插件: {name}，可选: {list(PLUGIN_PACKAGE_MAP)}")
            sys.exit(1)
        build_plugin(name, spec, args.out)


if __name__ == "__main__":
    main()
