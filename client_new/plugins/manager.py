"""插件化基础设施：重依赖（桌面测试 / Web 测试 / 代理）按插件包按需安装与激活。"""

import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from do.config import PluginsConfig


def _plugin_base_dir() -> Path:
    """
    插件根目录的基准目录：开发态为 client_new 目录，打包态为 exe 所在目录。

    不能用 cwd：mitmproxy helper 子进程在打包态下 cwd 可能是 PyInstaller
    临时解压目录，用 cwd 会导致 helper 找不到已安装插件。
    :return: 基准目录
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


# 插件包根目录：storage/plugins/<name>/
PLUGIN_ROOT_DIR = _plugin_base_dir() / "storage" / "plugins"

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

    def plugin_dir(self, name: str) -> Path:
        """
        获取指定插件目录路径。
        :param name: 插件标识
        :return: 插件目录
        """
        return PLUGIN_ROOT_DIR / name

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
        for name in PLUGIN_DEFINITIONS:
            plugin_dir = self.plugin_dir(name)
            if not self._is_installed(name):
                continue
            self._activate(name, plugin_dir)

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
        import shutil
        import tempfile
        import zipfile

        definition = PLUGIN_DEFINITIONS.get(name)
        if definition is None:
            return False, f"未知插件: {name}"

        zip_file = Path(zip_path)
        if not zip_file.exists():
            return False, f"插件包不存在: {zip_file}"

        target_dir = self.plugin_dir(name)
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

                # 路径安全校验：拒绝绝对路径与越级路径
                for entry in names:
                    candidate = Path(entry)
                    if candidate.is_absolute() or ".." in candidate.parts:
                        return False, f"插件包包含非法路径条目: {entry}"

                temp_dir = Path(tempfile.mkdtemp(prefix=f"qtr-plugin-{name}-"))
                archive.extractall(temp_dir)

            extracted_root = self._resolve_extract_root(temp_dir, MANIFEST_FILE)

            backup_dir = target_dir.with_name(f"{target_dir.name}.bak")
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            if target_dir.exists():
                shutil.move(str(target_dir), str(backup_dir))
            try:
                PLUGIN_ROOT_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(extracted_root), str(target_dir))
            except Exception:
                # 替换失败时回滚旧目录，保证旧版本仍可用
                if backup_dir.exists() and not target_dir.exists():
                    shutil.move(str(backup_dir), str(target_dir))
                raise
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)

            logger.info(
                f"插件安装成功 name={name}, version={manifest.get('version')}, src={zip_file}"
            )
            return True, (
                f"{definition.display_name} 插件安装成功（版本 {manifest.get('version', '未知')}），"
                "重启客户端后生效"
            )
        except Exception as e:
            logger.exception(f"插件安装失败 name={name}: {e}")
            return False, f"插件安装失败: {e}"

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

    def download_and_install(self, name: str) -> tuple[bool, str]:
        """
        从配置的下载源在线下载并安装插件。

        下载地址为 {download_base_url}/{name}.zip，可选 {name}.zip.sha256 校验文件。
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
        if not base_url:
            return False, "未配置插件下载源，请在插件管理中先填写下载地址"

        import httpx

        zip_url = f"{base_url}/{name}.zip"
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
                sha_url = f"{zip_url}.sha256"
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
            return self.install_from_zip(name, temp_file)
        except Exception as e:
            logger.exception(f"插件下载失败 name={name}: {e}")
            return False, f"插件下载失败: {e}"
        finally:
            if temp_file is not None:
                try:
                    temp_file.unlink()
                except Exception:
                    pass

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
