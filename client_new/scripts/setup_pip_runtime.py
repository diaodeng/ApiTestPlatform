"""
内置 Python 运行时准备脚本：为「pip 安装」插件模式准备嵌入式 Python + pip。

产物：client_new/runtime/python/（含 python.exe 与 pip 模块）。
两个打包 spec 会将该目录条件打包进发布产物（_internal/runtime/python 或解压目录），
打包态插件管理「Pip安装」据此执行；目录不存在时打包不受影响（运行时明确报错引导）。

用法：cd client_new && uv run python scripts/setup_pip_runtime.py [--force]
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / "runtime" / "python"

# 嵌入式 Python 下载地址：默认华为云镜像（国内可达），版本需与构建主程序的 venv 主版本一致
PYTHON_VERSION = "3.14.6"
EMBEDDED_URL = (
    f"https://mirrors.huaweicloud.com/python/{PYTHON_VERSION}/"
    f"python-{PYTHON_VERSION}-embed-amd64.zip"
)
# pip 引导脚本（官方地址，仅准备运行时时使用一次）
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
# get-pip 引导使用的包索引（国内镜像）
BOOTSTRAP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"


def download(url: str, target: Path) -> None:
    """
    下载文件到指定路径（httpx 流式写入，失败时清理残留）。
    :param url: 下载地址
    :param target: 目标文件路径
    """
    import httpx

    print(f"[下载] {url}")
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(target, "wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    handle.write(chunk)


def enable_site_packages(python_dir: Path) -> None:
    """
    启用嵌入式 Python 的 site 处理：._pth 中取消 import site 注释，
    否则 pip 模块安装后无法被 import。
    :param python_dir: 嵌入式 Python 目录
    """
    pth_file = next(python_dir.glob("python*._pth"))
    content = pth_file.read_text(encoding="utf-8")
    if "#import site" in content:
        content = content.replace("#import site", "import site")
        pth_file.write_text(content, encoding="utf-8")
        print(f"[OK] 已启用 site 处理: {pth_file.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="准备内置 Python 运行时（pip 安装模式）")
    parser.add_argument(
        "--force", action="store_true", help="已存在时删除重建"
    )
    args = parser.parse_args()

    python_exe = RUNTIME_DIR / "python.exe"
    if python_exe.exists() and not args.force:
        # 幂等：已就绪则直接校验 pip 可用性
        probe = subprocess.run(
            [str(python_exe), "-m", "pip", "--version"], capture_output=True, timeout=60
        )
        if probe.returncode == 0:
            print(f"[SKIP] 运行时已就绪: {RUNTIME_DIR}")
            return
        print("[WARN] 运行时存在但 pip 不可用，将重建")
        shutil.rmtree(RUNTIME_DIR)

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qtr-runtime-") as tmp:
        tmp_dir = Path(tmp)

        # 1. 下载并解压嵌入式 Python
        zip_file = tmp_dir / "python-embed.zip"
        download(EMBEDDED_URL, zip_file)
        with zipfile.ZipFile(zip_file) as archive:
            archive.extractall(RUNTIME_DIR)
        print(f"[OK] 嵌入式 Python 已解压: {RUNTIME_DIR}")

        # 2. 启用 site 处理
        enable_site_packages(RUNTIME_DIR)

        # 3. 引导 pip（使用国内镜像）
        get_pip = tmp_dir / "get-pip.py"
        download(GET_PIP_URL, get_pip)
        completed = subprocess.run(
            [
                str(python_exe),
                str(get_pip),
                "--no-warn-script-location",
                "-i",
                BOOTSTRAP_INDEX,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        if completed.returncode != 0:
            print(f"[FAIL] pip 引导失败: {(completed.stderr or '')[-2000:]}")
            sys.exit(1)

    # 4. 校验 pip 可用
    probe = subprocess.run(
        [str(python_exe), "-m", "pip", "--version"], capture_output=True, text=True
    )
    if probe.returncode != 0:
        print("[FAIL] 运行时 pip 校验失败")
        sys.exit(1)
    print(f"[OK] pip 就绪: {(probe.stdout or '').strip()}")
    print(f"[ALL PASS] 内置 Python 运行时已就绪: {RUNTIME_DIR}")


if __name__ == "__main__":
    main()
