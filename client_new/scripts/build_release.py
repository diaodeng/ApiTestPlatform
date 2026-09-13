"""
一键发版构建脚本：编排主程序打包（PyInstaller 两个 spec）、插件包构建与发版产物整理。

两种模式：
- dev（默认）：开发过程打包，允许存在未提交代码、不要求打 tag，产物落到 dist_dev/，
  包含主程序 exe / 便携目录与插件 zip，构建信息标记 mode=dev，便于追溯来源；
- release：正式发版打包，设三道硬闸门，任一不满足直接拒绝构建：
    1. 工作区干净（git status --porcelain 为空，含未跟踪文件）；
    2. HEAD 上存在与 version.py 一致的 tag（即 v{版本号}）；
    3. Gitee 上不存在同名 tag 的 release（防覆盖已发布分发包）。
  产物落到 dist_release/，额外生成 QTRClientNew_portable.zip 便携升级包、
  各产物 .sha256 校验文件与 release-manifest.json（版本、tag、commit、全部文件清单）。

构建信息注入：打包前把实际构建信息写入 version_build_local.py（已加入 .gitignore），
记录构建模式、commit、构建时间、tag 与工作区是否 dirty；进 git 的 version_build.py
是固定不变的加载器（负责 try-import local 文件并暴露常量，未生成时回退空值），
关于页读取后展示，用于追溯包体来源。构建信息不参与升级版本比较——升级比对
始终以 version.py 的纯数字四段版本为准。

产物命名与自更新兼容：主程序包命名为 QTRClientNew.exe 与 QTRClientNew_portable.zip，
与 utils/common 的更新资产匹配规则（精确名/便携提示词打分）对齐，可获得最高匹配分；
插件 zip 沿用 build_plugins.py 的插件名命名（如 desktop-test.zip），
.sha256 附件不会被更新器误认为升级包（_parse_release_asset_name 不识别该后缀）。

用法：
  cd client_new
  uv run python scripts/build_release.py                 # 开发打包
  uv run python scripts/build_release.py --mode release  # 发版打包
可选参数：--skip-exe 跳过主程序打包；--skip-plugins 跳过插件打包。
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 发版/开发两套产物目录（均已在 .gitignore 忽略）；PyInstaller 中间文件放 build/<mode>/
DIST_BASE = PROJECT_ROOT / "dist_release"
DIST_DEV = PROJECT_ROOT / "dist_dev"
BUILD_WORK_BASE = PROJECT_ROOT / "build"

EXE_NAME = "QTRClientNew.exe"
PORTABLE_DIR_NAME = "QTRClientNew_portable"
PORTABLE_ZIP_NAME = "QTRClientNew_portable.zip"
MANIFEST_NAME = "release-manifest.json"
# 实际构建信息写入 local 文件（gitignore）；进 git 的 version_build.py 是固定加载器
VERSION_BUILD_LOCAL_PATH = PROJECT_ROOT / "version_build_local.py"

# 四段纯数字版本（项目发版约定）；升级比较、tag、exe 元数据均基于它
VERSION_RE = re.compile(r"^\d+(\.\d+)*$")


def _run_git(args: list[str], check: bool = True) -> str:
    """
    在项目内执行 git 命令并返回 stdout。
    :param args: git 子命令参数列表
    :param check: 非零退出码是否抛异常（False 用于探测性命令）
    :return: stdout 文本（已去除首尾空白）
    """
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {result.stderr.strip()}")
    return result.stdout.strip()


def _read_version() -> str:
    """从 version.py 读取客户端版本号并校验为纯数字段（tag 与升级比较的唯一来源）。"""
    sys.path.insert(0, str(PROJECT_ROOT))
    from version import __version__  # noqa: E402

    version = str(__version__ or "").strip()
    if not VERSION_RE.match(version):
        raise RuntimeError(f"version.py 版本号非法: {version!r}，必须是纯数字段（如 1.1.1.0）")
    return version


def _collect_git_info() -> dict:
    """
    收集构建时的 git 信息（commit、工作区状态、HEAD 上的精确 tag）。
    :return: 包含 commit / commit_short / dirty_files / tag 的字典
    """
    commit = _run_git(["rev-parse", "HEAD"])
    commit_short = _run_git(["rev-parse", "--short", "HEAD"])
    status_output = _run_git(["status", "--porcelain"])
    dirty_files = [line for line in status_output.splitlines() if line.strip()]
    # 精确匹配当前提交的 tag；没有 tag 时返回空串（开发打包允许）
    tag = _run_git(["describe", "--tags", "--exact-match", "HEAD"], check=False)
    return {
        "commit": commit,
        "commit_short": commit_short,
        "dirty_files": dirty_files,
        "tag": tag,
    }


def _check_release_gates(version: str, git_info: dict) -> None:
    """
    发版模式三道硬闸门，任一失败即抛异常终止构建。
    :param version: version.py 中的版本号
    :param git_info: _collect_git_info 的结果
    """
    # 闸门 1：工作区必须干净（含未跟踪文件），保证产物可精确对应到某个提交
    if git_info["dirty_files"]:
        preview = "\n".join(git_info["dirty_files"][:20])
        raise RuntimeError(
            "发版构建要求工作区干净，但存在未提交改动（先 commit 或 stash）：\n" f"{preview}"
        )

    # 闸门 2：HEAD 上必须有与版本号一致的 tag（v 前缀四段式）
    expected_tag = f"v{version}"
    if git_info["tag"] != expected_tag:
        actual = git_info["tag"] or "（无 tag）"
        raise RuntimeError(
            f"发版构建要求 HEAD 上存在 tag {expected_tag}，当前为 {actual}；"
            f"请先 commit 版本号并打 tag（git tag {expected_tag}）"
        )

    # 闸门 3：Gitee 上不允许已存在同名 release（防覆盖已发布分发包）
    from utils.gitee_release import fetch_release_list_sync  # noqa: E402

    try:
        releases = fetch_release_list_sync()
    except Exception as e:  # noqa: BLE001 —— 网络失败按发版闸门失败处理，宁可不打也不带病打包
        raise RuntimeError(f"查询 Gitee release 失败，无法确认 {expected_tag} 是否已发布: {e}") from e
    for release in releases:
        if str(release.get("tag_name") or "").strip() == expected_tag:
            raise RuntimeError(
                f"Gitee 上已存在 tag 为 {expected_tag} 的 release，禁止重复发版；"
                f"如需修复请使用新的第四段 hotfix 版本号"
            )
    print(f"[闸门] 三项发版校验全部通过（tag={expected_tag}）")


def _write_version_build(meta: dict) -> None:
    """
    生成构建信息文件 version_build_local.py（gitignore，不进 git）。
    version_build.py 是进 git 的固定加载器，PyInstaller 打包时会把两者一起打入产物
    供关于页展示；本文件随构建实时变化，多机构建互不影响。
    :param meta: 构建元数据（mode/version/tag/commit 等）
    """
    content = (
        "# 本文件由 scripts/build_release.py 自动生成，勿手工修改（已加入 .gitignore）\n"
        f'BUILD_MODE = "{meta["mode"]}"\n'
        f'BUILD_VERSION = "{meta["version"]}"\n'
        f'BUILD_TAG = "{meta["tag"]}"\n'
        f'BUILD_COMMIT = "{meta["commit"]}"\n'
        f'BUILD_COMMIT_SHORT = "{meta["commit_short"]}"\n'
        f'BUILD_TIME = "{meta["built_at"]}"\n'
        f'BUILD_DIRTY = {meta["dirty"]}\n'
    )
    VERSION_BUILD_LOCAL_PATH.write_text(content, encoding="utf-8")
    print(
        f"[OK] 生成构建信息 {VERSION_BUILD_LOCAL_PATH.name}"
        f"（mode={meta['mode']}, commit={meta['commit_short']}）"
    )


def _sha256_file(path: Path) -> str:
    """计算文件 sha256（大文件流式读取）。"""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_exe(dist_dir: Path, work_dir: Path) -> None:
    """
    依次执行两个 PyInstaller spec：单文件版（QTRClientNew.spec）与便携目录版
    （QTRClientNewPortable.spec），产物输出到指定 dist 目录。
    """
    if find_spec("PyInstaller") is None:
        raise RuntimeError("当前虚拟环境未安装 PyInstaller，请先执行 uv sync")

    for spec_name in ("QTRClientNew.spec", "QTRClientNewPortable.spec"):
        print(f"[构建] PyInstaller {spec_name} ...（可能需要数分钟）", flush=True)
        result = subprocess.run(
            [
                sys.executable, "-m", "PyInstaller", "--noconfirm",
                "--distpath", str(dist_dir),
                "--workpath", str(work_dir),
                str(PROJECT_ROOT / spec_name),
            ],
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            raise RuntimeError(f"PyInstaller 构建 {spec_name} 失败（退出码 {result.returncode}）")

    exe_path = dist_dir / EXE_NAME
    if not exe_path.exists():
        raise RuntimeError(f"构建完成但未找到产物: {exe_path}")
    print(f"[OK] {exe_path.name}  {exe_path.stat().st_size / 1024 / 1024:.1f} MB")


def _package_release_assets(dist_dir: Path) -> None:
    """
    发版产物整理：把便携目录压缩为 QTRClientNew_portable.zip（zip 根目录即
    exe + _internal，与自更新 Expand-Archive 后的 Resolve-SourceDir 兼容），
    并为 exe / zip 生成 .sha256 校验文件。
    """
    portable_dir = dist_dir / PORTABLE_DIR_NAME
    if not portable_dir.is_dir():
        raise RuntimeError(f"未找到便携目录: {portable_dir}")

    zip_path = dist_dir / PORTABLE_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file_path in sorted(portable_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(portable_dir))
    print(f"[OK] {zip_path.name}  {zip_path.stat().st_size / 1024 / 1024:.1f} MB")

    for asset in (dist_dir / EXE_NAME, zip_path):
        sha = _sha256_file(asset)
        (dist_dir / f"{asset.name}.sha256").write_text(f"{sha}\n", encoding="utf-8")
        print(f"[OK] {asset.name}.sha256  {sha[:16]}...")


def _build_plugins(plugins_dir: Path) -> None:
    """调用 build_plugins.py 构建三个插件 zip 到指定目录（沿用其 site-packages 收集逻辑）。"""
    script = PROJECT_ROOT / "scripts" / "build_plugins.py"
    print(f"[构建] 插件包 -> {plugins_dir} ...（可能需要数分钟）", flush=True)
    result = subprocess.run(
        [sys.executable, str(script), "--out", str(plugins_dir)],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"插件包构建失败（退出码 {result.returncode}）")


def _write_manifest(dist_dir: Path, meta: dict) -> None:
    """
    生成 release-manifest.json：版本/tag/commit 等元数据 + dist 目录下全部产物的
    sha256 与大小清单，上传 release 时照单核对，防传漏、防传错。
    """
    files = []
    for file_path in sorted(dist_dir.rglob("*")):
        if not file_path.is_file() or file_path.name == MANIFEST_NAME:
            continue
        files.append(
            {
                "path": file_path.relative_to(dist_dir).as_posix(),
                "sha256": _sha256_file(file_path),
                "size": file_path.stat().st_size,
            }
        )
    manifest = {
        **meta,
        "files": files,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
    (dist_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] {MANIFEST_NAME}（{len(files)} 个文件）")


def main() -> None:
    """入口：解析参数 -> 收集 git 信息 -> 发版闸门 -> 生成构建信息 -> 打包 -> 产物整理。"""
    parser = argparse.ArgumentParser(description="QTRClientNew 一键发版构建脚本")
    parser.add_argument(
        "--mode", choices=("dev", "release"), default="dev",
        help="构建模式：dev 开发打包 / release 正式发版",
    )
    parser.add_argument("--skip-exe", action="store_true", help="跳过主程序 PyInstaller 打包")
    parser.add_argument("--skip-plugins", action="store_true", help="跳过插件包构建")
    args = parser.parse_args()

    version = _read_version()
    if args.mode == "release" and len(version.split(".")) != 4:
        raise RuntimeError(f"发版版本号必须是四段式: {version}")
    git_info = _collect_git_info()

    if args.mode == "release":
        _check_release_gates(version, git_info)
    else:
        if git_info["dirty_files"]:
            print(f"[提示] 开发打包：工作区有 {len(git_info['dirty_files'])} 处未提交改动，已记录到构建信息")
        else:
            print("[提示] 开发打包：工作区干净")

    dist_dir = DIST_BASE if args.mode == "release" else DIST_DEV
    work_dir = BUILD_WORK_BASE / args.mode
    meta = {
        "mode": args.mode,
        "version": version,
        "tag": git_info["tag"],
        "commit": git_info["commit"],
        "commit_short": git_info["commit_short"],
        "dirty": bool(git_info["dirty_files"]),
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dist": dist_dir.name,
    }

    _write_version_build(meta)
    dist_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_exe:
        _build_exe(dist_dir, work_dir)
    else:
        print("[跳过] 主程序打包（--skip-exe）")

    if not args.skip_plugins:
        _build_plugins(dist_dir / "plugins")
    else:
        print("[跳过] 插件包构建（--skip-plugins）")

    if args.mode == "release":
        if not args.skip_exe:
            _package_release_assets(dist_dir)
        else:
            print("[跳过] 便携升级包压缩（--skip-exe）")

    _write_manifest(dist_dir, meta)

    print(f"[完成] mode={meta['mode']} version={version} tag={meta['tag'] or '-'} 产物目录: {dist_dir}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"[失败] {e}")
        sys.exit(1)
