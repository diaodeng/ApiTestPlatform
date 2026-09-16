"""插件化基础设施：重依赖（桌面测试 / Web 测试 / 代理）按插件包按需安装与激活。"""

import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from loguru import logger

from do.config import PluginsConfig
from utils.gitee_release import (
    fetch_release_list_sync,
    find_release_asset,
    find_release_by_version,
)
from version import __version__ as APP_VERSION


def _frozen_base_dir() -> Path:
    """
    打包态基准目录：exe 所在目录（默认插件安装位置的基准）。
    :return: 基准目录
    """
    return Path(sys.executable).resolve().parent


def _plugin_base_dir() -> Path:
    """
    插件默认根目录的基准：开发态为 client_new 目录，打包态为 exe 所在目录。

    不能用 cwd：mitmproxy helper 子进程在打包态下 cwd 可能是 PyInstaller
    临时解压目录，用 cwd 会导致 helper 找不到已安装插件。
    :return: 基准目录
    """
    if getattr(sys, "frozen", False):
        return _frozen_base_dir()
    return Path(__file__).resolve().parents[1]


# 插件默认根目录（用户可通过插件管理页面自定义，见 PluginManager.get_plugin_root）
DEFAULT_PLUGIN_ROOT_DIR = _plugin_base_dir() / "storage" / "plugins"

# 历史版本的插件存放位置（用于启动时自动迁移到当前根目录）
def _legacy_plugin_roots() -> list[Path]:
    roots: list[Path] = []
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        roots.append(Path(local_app) / "QTRClientNew" / "storage" / "plugins")
    if getattr(sys, "frozen", False):
        roots.append(_frozen_base_dir() / "storage" / "plugins")
    return roots

# zip 包内清单文件名
MANIFEST_FILE = "manifest.json"


@dataclass(frozen=True)
class PluginDefinition:
    """单个插件的静态定义。"""

    name: str  # 插件标识，同时是插件目录名与下载文件名
    display_name: str  # 界面展示名
    description: str  # 功能说明
    modules: tuple[str, ...] = field(default_factory=tuple)  # 判定可用的顶层模块名


# 内置插件定义：与其余代码的依赖守卫（desktop_test_service / playwright_browser_runtime）一一对应
PLUGIN_DEFINITIONS: dict[str, PluginDefinition] = {
    definition.name: definition
    for definition in (
        PluginDefinition(
            name="desktop-test",
            display_name="桌面测试",
            description="桌面自动化与图像识别依赖（cv2 / numpy / pytesseract / pyautogui / pynput / pillow），"
            "缺少时桌面测试与自动化录制不可用，其他功能不受影响",
            modules=("cv2", "numpy", "pytesseract", "pyautogui", "pygetwindow", "pynput", "PIL"),
        ),
        PluginDefinition(
            name="web-test",
            display_name="Web 测试",
            description="浏览器自动化依赖（playwright，含浏览器驱动）；缺少时 Web 测试与浏览器操作不可用，"
            "其他功能不受影响",
            modules=("playwright",),
        ),
        PluginDefinition(
            name="proxy",
            display_name="抓包代理",
            description="mitmproxy 抓包内核（含 HTTP/HTTPS 解密、mock、断点）与本地重定向组件；"
            "缺少时「mitmproxy」页不可用，其他功能不受影响",
            modules=("mitmproxy", "mitmproxy_windows", "tornado", "aioquic"),
        ),
    )
}


class PluginManager:
    """
    插件管理器。

    目录约定：storage/plugins/<name>/ 下直接放置该插件的 site-packages 内容
    （如 cv2/、numpy/ 等），激活时把该目录插入 sys.path 即可被 import。

    所有公开方法只返回结果、不向外抛异常：任何插件异常都记录日志并转为
    (ok, message) 结果，保证主进程与主功能不受插件影响。
    """

    STATUS_ACTIVE = "active"  # 模块当前即可导入（内置或已激活）
    STATUS_INSTALLED = "installed"  # 插件目录存在，但当前进程尚未激活（需重启）
    STATUS_MISSING = "missing"  # 未安装

    def __init__(self):
        self._activated: set[str] = set()

    # ===== 查询 =====

    def get_plugin_root(self) -> Path:
        """
        获取当前插件根目录：配置了自定义安装目录则使用之，否则用默认目录
        （打包态为 exe 所在目录下 storage/plugins，开发态为 client_new 下）。
        :return: 插件根目录
        """
        try:
            custom = str(PluginsConfig.read().install_dir or "").strip()
        except Exception as e:
            logger.warning(f"读取自定义插件目录失败，回退默认目录: {e}")
            custom = ""
        if not custom:
            return DEFAULT_PLUGIN_ROOT_DIR
        return Path(custom).expanduser()

    def plugin_dir(self, name: str) -> Path:
        """
        获取指定插件目录路径。
        :param name: 插件标识
        :return: 插件目录
        """
        return self.get_plugin_root() / name

    def set_install_dir(self, new_dir: str, migrate: bool) -> tuple[bool, str]:
        """
        设置自定义插件安装目录并按需迁移已安装插件。

        :param new_dir: 新的插件根目录（绝对路径）；传空字符串恢复默认目录
        :param migrate: 是否把当前目录下已安装的插件搬到新目录
        :return: (是否成功, 结果消息)
        """
        import shutil

        try:
            current_root = self.get_plugin_root()
            normalized = str(new_dir or "").strip()
            new_root = (
                Path(normalized).expanduser() if normalized else DEFAULT_PLUGIN_ROOT_DIR
            )
            if normalized and not new_root.is_absolute():
                return False, "插件安装目录必须是绝对路径"

            config = PluginsConfig.read()
            config.install_dir = normalized
            PluginsConfig.write(config)
            logger.info(f"插件安装目录已保存: {new_root}")

            migrated = 0
            if migrate:
                for name in PLUGIN_DEFINITIONS:
                    src = current_root / name
                    dst = self.plugin_dir(name)
                    if not src.exists() or dst.exists():
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                    migrated += 1
                if migrated:
                    logger.info(f"已迁移 {migrated} 个插件到 {new_root}")

            suffix = f"，已迁移 {migrated} 个插件" if migrate and migrated else ""
            return True, f"插件安装目录已设置为 {new_root}{suffix}，重启客户端后生效"
        except Exception as e:
            logger.exception(f"设置插件安装目录失败: {e}")
            return False, f"设置插件安装目录失败: {e}"

    def get_status(self, name: str) -> str:
        """
        查询插件状态：active / installed / missing。
        :param name: 插件标识
        :return: 状态常量
        """
        definition = PLUGIN_DEFINITIONS.get(name)
        if definition and self._modules_resolvable(definition.modules):
            return self.STATUS_ACTIVE
        if self._is_installed(name):
            return self.STATUS_INSTALLED
        return self.STATUS_MISSING

    def describe_status(self, name: str) -> str:
        """
        状态的中文描述，供界面直接展示。
        :param name: 插件标识
        :return: 状态文本
        """
        status = self.get_status(name)
        if status == self.STATUS_ACTIVE:
            return "已启用"
        if status == self.STATUS_INSTALLED:
            return "已安装，重启客户端后生效"
        return "未安装"

    # ===== 激活 =====

    def activate_installed(self) -> None:
        """
        应用启动时调用：把所有已安装插件目录加入 sys.path。

        必须在任何业务模块导入之前调用（main.py 最早阶段），
        这样 desktop_test_service / playwright 的守卫导入才能找到插件包。
        """
        self._migrate_legacy_plugin_dirs()
        for name in PLUGIN_DEFINITIONS:
            plugin_dir = self.plugin_dir(name)
            if not self._is_installed(name):
                continue
            self._activate(name, plugin_dir)

    def _migrate_legacy_plugin_dirs(self) -> None:
        """
        启动时迁移：把历史版本存放位置的插件搬到当前根目录（当前根目录已有同名插件时跳过），
        覆盖两个场景——①旧版本固定装在 exe 目录/LOCALAPPDATA；②用户修改过自定义目录后又改回。
        """
        import shutil

        current_root = self.get_plugin_root()
        for legacy_root in _legacy_plugin_roots():
            if legacy_root == current_root or not legacy_root.exists():
                continue
            for name in PLUGIN_DEFINITIONS:
                legacy_dir = legacy_root / name
                new_dir = current_root / name
                if not legacy_dir.exists() or new_dir.exists():
                    continue
                try:
                    new_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(legacy_dir), str(new_dir))
                    logger.info(f"插件目录已迁移至 {new_dir}")
                except Exception as e:
                    logger.warning(f"插件目录迁移失败 name={name}: {e}")

    def _activate(self, name: str, plugin_dir: Path) -> bool:
        """
        把插件目录插入 sys.path 并刷新导入缓存。
        :param name: 插件标识
        :param plugin_dir: 插件目录
        :return: 目录是否已加入 sys.path
        """
        import importlib
        import sys

        dir_text = str(plugin_dir.resolve())
        if dir_text in sys.path:
            self._activated.add(name)
            return True

        sys.path.insert(0, dir_text)
        importlib.invalidate_caches()
        self._activated.add(name)
        logger.info(f"插件目录已激活 name={name}, dir={dir_text}")
        return True

    def _modules_resolvable(self, modules: tuple[str, ...]) -> bool:
        """
        判断插件要求的模块当前是否都能定位到（不真正导入，避免副作用）。
        :param modules: 顶层模块名列表
        :return: 是否全部可定位
        """
        import importlib.util

        for module_name in modules:
            try:
                if importlib.util.find_spec(module_name) is None:
                    return False
            except Exception:
                return False
        return True

    def _is_installed(self, name: str) -> bool:
        """
        判断插件目录是否存在且包含合法清单。
        :param name: 插件标识
        :return: 是否已安装
        """
        manifest_path = self.plugin_dir(name) / MANIFEST_FILE
        if not manifest_path.exists():
            return False
        try:
            import json

            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            return str(manifest.get("name") or "") == name
        except Exception as e:
            logger.warning(f"插件清单读取失败 name={name}: {e}")
            return False

    # ===== 安装 =====

    def install_from_zip(self, name: str, zip_path: str | Path) -> tuple[bool, str]:
        """
        从本地 zip 安装插件（覆盖式更新）。

        zip 根目录必须包含 manifest.json 且 name 与目标插件一致；
        解压到临时目录校验通过后原子替换旧目录。
        :param name: 插件标识
        :param zip_path: zip 文件路径
        :return: (是否成功, 结果消息)
        """
        import json
        import tempfile
        import zipfile

        definition = PLUGIN_DEFINITIONS.get(name)
        if definition is None:
            return False, f"未知插件: {name}"

        zip_file = Path(zip_path)
        if not zip_file.exists():
            return False, f"插件包不存在: {zip_file}"

        try:
            with zipfile.ZipFile(zip_file) as archive:
                names = archive.namelist()
                if MANIFEST_FILE not in names:
                    return False, "插件包缺少 manifest.json，格式不合法"

                manifest = json.loads(archive.read(MANIFEST_FILE).decode("utf-8"))
                if str(manifest.get("name") or "") != name:
                    return False, (
                        f"插件包与目标不一致: 包={manifest.get('name')}, 目标={name}"
                    )

                # Python 版本硬校验：编译产物跨解释器版本必然导入失败，不兼容直接拒绝
                compat_error = self._manifest_compatibility_error(manifest)
                if compat_error:
                    logger.warning(
                        f"插件包与运行时 Python 版本不兼容 name={name}, "
                        f"package_python={manifest.get('python_version')}"
                    )
                    return False, compat_error

                # 路径安全校验：拒绝绝对路径与越级路径
                for entry in names:
                    candidate = Path(entry)
                    if candidate.is_absolute() or ".." in candidate.parts:
                        return False, f"插件包包含非法路径条目: {entry}"

                temp_dir = Path(tempfile.mkdtemp(prefix=f"qtr-plugin-{name}-"))
                archive.extractall(temp_dir)

            extracted_root = self._resolve_extract_root(temp_dir, MANIFEST_FILE)
            self._replace_plugin_dir(name, extracted_root)

            logger.info(
                f"插件安装成功 name={name}, version={manifest.get('version')}, "
                f"package_app={manifest.get('app_version') or '未记录'}, src={zip_file}"
            )
            # app_version 为软约束参考：跨版本安装不拦截，仅在结果中提示用户关注兼容性
            manifest_app = str(manifest.get("app_version") or "").strip()
            version_note = (
                f"（插件包配套应用版本 {manifest_app}，与当前客户端版本不同，建议关注兼容性）"
                if manifest_app and manifest_app != APP_VERSION
                else ""
            )
            return True, (
                f"{definition.display_name} 插件安装成功（版本 {manifest.get('version', '未知')}），"
                f"重启客户端后生效{version_note}"
            )
        except Exception as e:
            logger.exception(f"插件安装失败 name={name}: {e}")
            return False, f"插件安装失败: {e}"

    @staticmethod
    def _manifest_compatibility_error(manifest: dict) -> str:
        """
        校验插件包 manifest 与当前运行时的兼容性。

        python_version 是硬约束：插件包内的 .pyd 等编译产物只能被构建时的
        CPython 大.小版本导入，不一致时必须拒绝安装；字段缺失（旧格式包）
        或无法解析时跳过校验，保持对历史包的向后兼容。
        :param manifest: manifest 字典
        :return: 不兼容原因，兼容返回空串
        """
        package_python = str(manifest.get("python_version") or "").strip()
        if not package_python:
            return ""
        parts = re.findall(r"\d+", package_python)
        if len(parts) < 2:
            return ""
        package = (int(parts[0]), int(parts[1]))
        current = (sys.version_info.major, sys.version_info.minor)
        if package == current:
            return ""
        return (
            f"插件包由 Python {package[0]}.{package[1]} 构建，"
            f"与当前客户端运行时（Python {current[0]}.{current[1]}）不兼容，已拒绝安装；"
            "请下载与当前客户端配套版本的插件包。"
        )

    def _resolve_extract_root(self, temp_dir: Path, manifest_file: str) -> Path:
        """
        定位解压后的插件根目录（兼容 zip 内多一层目录的情况）。
        :param temp_dir: 解压临时目录
        :param manifest_file: 清单文件名
        :return: 包含清单文件的根目录
        """
        if (temp_dir / manifest_file).exists():
            return temp_dir
        for child in temp_dir.iterdir():
            if child.is_dir() and (child / manifest_file).exists():
                return child
        raise ValueError("插件包解压后未找到 manifest.json")

    def _replace_plugin_dir(self, name: str, staged_dir: Path) -> None:
        """
        用暂存目录原子替换插件目录：先备份旧目录，替换失败自动回滚，保证旧版本仍可用。
        :param name: 插件标识
        :param staged_dir: 已准备好的新插件内容目录（会被移动为插件目录）
        """
        import shutil

        target_dir = self.plugin_dir(name)
        backup_dir = target_dir.with_name(f"{target_dir.name}.bak")
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        if target_dir.exists():
            shutil.move(str(target_dir), str(backup_dir))
        try:
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_dir), str(target_dir))
        except Exception:
            # 替换失败时回滚旧目录，保证旧版本仍可用
            if backup_dir.exists() and not target_dir.exists():
                shutil.move(str(backup_dir), str(target_dir))
            raise
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)

    def download_and_install(self, name: str) -> tuple[bool, str]:
        """
        在线下载并安装插件。

        下载源优先级：
        1. 配置了自定义下载源（PluginsConfig.download_base_url）时，从 {下载源}/{name}.zip 下载；
        2. 未配置时，从 Gitee releases 定位：优先取 tag 与当前客户端版本一致的 release，
           下载其中的 {name}.zip 附件；该 release 缺附件时回退到其他 release 中
           第一个含附件的（Python 版本兼容性由 manifest 在安装前强校验兜底）。

        可选 {name}.zip.sha256 校验文件：存在时强校验，防止下载损坏。
        该方法为阻塞操作，调用方应放到后台线程执行。
        :param name: 插件标识
        :return: (是否成功, 结果消息)
        """
        import hashlib

        definition = PLUGIN_DEFINITIONS.get(name)
        if definition is None:
            return False, f"未知插件: {name}"

        config = PluginsConfig.read()
        base_url = str(config.download_base_url or "").strip().rstrip("/")
        source_note = ""
        if base_url:
            zip_url = f"{base_url}/{name}.zip"
            sha_url: str | None = f"{zip_url}.sha256"
        else:
            zip_url, sha_url, source_note, resolve_error = self._resolve_gitee_plugin_urls(name)
            if not zip_url:
                return False, resolve_error

        temp_file: Path | None = None
        try:
            logger.info(f"开始下载插件 name={name}, url={zip_url}")
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                with client.stream("GET", zip_url) as response:
                    if response.status_code != 200:
                        return False, (
                            f"下载插件失败: HTTP {response.status_code}（{zip_url}）"
                        )
                    fd, temp_name = tempfile.mkstemp(prefix=f"qtr-{name}-", suffix=".zip")
                    temp_file = Path(temp_name)
                    downloaded = 0
                    with os.fdopen(fd, "wb") as handle:
                        for chunk in response.iter_bytes(chunk_size=1024 * 256):
                            handle.write(chunk)
                            downloaded += len(chunk)

                # 可选 sha256 校验：存在校验文件时强校验，防止下载损坏
                if sha_url:
                    try:
                        sha_response = client.get(sha_url)
                        if sha_response.status_code == 200:
                            expected = sha_response.text.strip().split()[0].lower()
                            actual = hashlib.sha256(temp_file.read_bytes()).hexdigest()
                            if expected != actual:
                                return False, "插件包校验失败（sha256 不一致），已放弃安装"
                    except Exception as e:
                        logger.warning(f"插件校验文件获取失败（跳过强校验）: {e}")

            logger.info(f"插件下载完成 name={name}, size={downloaded} bytes")
            ok, message = self.install_from_zip(name, temp_file)
            if ok and source_note:
                message = f"{message}{source_note}"
            return ok, message
        except Exception as e:
            logger.exception(f"插件下载失败 name={name}: {e}")
            return False, f"插件下载失败: {e}"
        finally:
            if temp_file is not None:
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def _resolve_gitee_plugin_urls(
        self, name: str
    ) -> tuple[str | None, str | None, str, str]:
        """
        从 Gitee releases 中定位插件包下载地址。

        策略：优先取 tag 与当前客户端版本一致的 release（发版配套、经过一起测试的组合）；
        该 release 未上传插件附件时，回退到其他 release 中第一个含附件的——
        跨版本包的 Python 版本兼容性由 manifest 的 python_version 在安装前强校验兜底，
        不兼容会被 install_from_zip 拒绝，因此回退不会装上解释器版本错误的包。
        :param name: 插件标识
        :return: (插件 zip 下载地址, sha256 校验地址或 None, 成功后的来源提示, 失败原因)
        """
        try:
            releases = fetch_release_list_sync()
        except Exception as e:
            logger.exception(f"获取 Gitee releases 列表失败: {e}")
            return None, None, "", f"获取 Gitee 版本列表失败: {e}"

        paired = find_release_by_version(releases, APP_VERSION)
        if paired is None:
            tag_names = [str(item.get("tag_name") or "") for item in releases[:5]]
            logger.warning(
                f"Gitee 未找到与客户端版本一致的 release version={APP_VERSION}, 已见 tag={tag_names}"
            )

        # 排序：同版本 release 优先，其余按接口返回顺序（最新在前）作为回退候选
        ordered = ([paired] if paired is not None else []) + [
            release for release in releases if release is not paired
        ]

        for index, release in enumerate(ordered):
            asset = find_release_asset(release, f"{name}.zip")
            if asset is None:
                continue
            zip_url = str(asset.get("browser_download_url") or "").strip()
            if not zip_url:
                continue
            sha_asset = find_release_asset(release, f"{name}.zip.sha256")
            sha_url = (
                str(sha_asset.get("browser_download_url") or "").strip()
                if sha_asset
                else None
            )
            tag = str(release.get("tag_name") or "").strip()
            if index == 0 and paired is not None:
                logger.info(
                    f"已定位 Gitee 插件包（同版本配套） version={APP_VERSION}, name={name}, url={zip_url}"
                )
                return zip_url, sha_url, "", ""
            source_note = f"（插件包来自 release {tag}，非当前版本配套包，已校验 Python 版本兼容）"
            logger.info(
                f"同版本 release 缺少插件附件或不存在，已回退 tag={tag}, name={name}, url={zip_url}"
            )
            return zip_url, sha_url, source_note, ""

        logger.warning(
            f"Gitee 各 release 均未找到插件附件 version={APP_VERSION}, asset={name}.zip"
        )
        return (
            None,
            None,
            "",
            (
                f"Gitee 的 release 中均未上传 {name}.zip 附件，"
                "请联系维护方确认发版产物，或使用「本地安装」。"
            ),
        )

    def read_download_base_url(self) -> str:
        """
        读取当前配置的插件下载源。
        :return: 下载源根地址
        """
        return PluginsConfig.read().download_base_url

    def save_download_base_url(self, base_url: str) -> tuple[bool, str]:
        """
        保存插件下载源配置。
        :param base_url: 下载源根地址
        :return: (是否成功, 结果消息)
        """
        try:
            config = PluginsConfig.read()
            config.download_base_url = str(base_url or "").strip()
            PluginsConfig.write(config)
            logger.info(f"插件下载源已保存: {config.download_base_url}")
            return True, "下载源已保存"
        except Exception as e:
            logger.exception(f"插件下载源保存失败: {e}")
            return False, f"下载源保存失败: {e}"


plugin_manager = PluginManager()
