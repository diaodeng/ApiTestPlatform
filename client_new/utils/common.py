import base64
import gzip
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any, Optional

import httpx
import psutil
import win32api
from loguru import logger

from common import appState
from utils.http_defaults import DEFAULT_HTTP_TIMEOUT
from utils import VERSION


class DBHelper:
    def __init__(self, db):
        self.db = db


def resource_path(relative_path: str) -> str:
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)
    logger.debug(f"资源文件路径:{file_path}")
    if not os.path.exists(file_path):
        """获取资源文件绝对路径，兼容 PyInstaller 打包"""
        if hasattr(sys, "_MEIPASS"):  # PyInstaller 打包后执行路径
            path = os.path.join(sys._MEIPASS, relative_path)
            logger.debug(f"PyInstaller 打包后资源路径: {path}")
            return path
    else:
        return file_path
    logger.warning(f"{relative_path} 不存在")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)


def ensure_directory_exists(dir_path):
    """
    检查目录是否存在，不存在则创建
    :param dir_path: 要检查的目录路径
    :return: None
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        logger.info(f"目录 {dir_path} 已创建")
    else:
        logger.info(f"目录 {dir_path} 已存在")


def kill_process_by_id(process_id) -> bool:
    os.kill(process_id, signal.SIGTERM)  # 或者 signal.SIGKILL 以强制终止


def kill_by_port(port):
    for conn in psutil.net_connections():
        if conn.laddr and conn.laddr.port == port:
            pid = conn.pid
            if pid:
                try:
                    p = psutil.Process(pid)
                    print(f"kill pid={pid}, name={p.name()}")
                    p.kill()
                except Exception as e:
                    print(e)


def kill_process_by_name(process_name) -> bool:
    """强制结束指定进程

    :param process_name: 进程名称
    :param log: 日志对象
    :return:
    """
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            logger.debug(f"当前进程:{proc.info}")
            if proc.info["name"] == process_name:
                proc.terminate()  # 优雅终止
                logger.info(f"进程 {process_name}(PID:{proc.info['pid']}) 已终止")
                # return True
        # logger.info(f"没有运行中的进程：{process_name}")
        logger.debug(f"进程已终止：{process_name}")
        return True
    except Exception as e:
        logger.error(f"结束进程:{process_name} 失败,异常:{e}")
        return False


def check_process(process_name, log, exact_match=True):
    """检查指定名称的进程是否存在

    Args:
        process_name: 目标进程名（不区分大小写）
        log: 日志对象
        exact_match: 是否精确匹配（False时支持模糊匹配）
    Returns:
        bool: 进程存在返回True
    """
    target = process_name.lower()
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            current_name = proc.info["name"].lower()
            if exact_match:
                if current_name == target:
                    log.info(f"精确匹配，找到进程名为: {target}的进程")
                    return True
            else:
                if target in current_name:
                    log.info(f"模糊匹配，找到进程包含: {target}的进程")
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            log.error(f"查找进程名为:{target}时发生异常，继续查找")
            continue
    log.info(f"未查找到进程名为:{target}的进程")
    return False


def check_offline_service_status(log):
    """检查离线服务状态"""
    url = "http://127.0.0.1:8081/static/index.html"
    try:
        with httpx.Client(timeout=DEFAULT_HTTP_TIMEOUT) as client:
            r = client.get(url)
        if r.status_code == 200:
            log.info(f"离线服务已启动")
            return True
        else:
            log.info(f"离线服务未启动")
            return False
    except Exception as ex:
        log.error(f"检查离线服务失败,请求异常:{ex}")
        return False


def run_bat(file_path, log):
    """
    执行bat文件
    :param file_path: bat文件路径
    :param log:
    :return:
    """
    result = subprocess.run([file_path], shell=True, capture_output=True, text=True)
    print(result.stdout)  # 输出标准输出
    log.info(f"bat文件执行结果:{result.stdout}")
    print(result.stderr)  # 输出错误信息
    log.error(f"bat文件执行错误信息:{result.stderr}")


def load_json(file_path: str) -> Optional[Any]:
    """安全读取JSON文件
    Args:
        file_path: JSON文件路径
    Returns:
        dict/list: 解析后的数据
        None: 文件不存在/格式错误时返回None
    """
    if not file_path.endswith(".json"):
        print("Error: 文件扩展名需为.json")
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: 文件不存在 {file_path}")
    except json.JSONDecodeError:
        print(f"Error: JSON格式错误 {file_path}")
    except Exception as e:
        print(f"Error: 读取失败 {str(e)}")
    return None


def write_json(file_path: str, data: Any, indent: int = 4) -> bool:
    """安全写入JSON文件
    Args:
        file_path: 输出文件路径
        data: 要写入的数据（需可序列化）
        indent: 缩进空格数
    Returns:
        bool: 是否写入成功
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except TypeError:
        print("Error: 数据包含不可序列化的对象")
    except PermissionError:
        print(f"Error: 无写入权限 {file_path}")
    except Exception as e:
        print(f"Error: 写入失败 {str(e)}")
    return False


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        return f"无法获取 IP: {e}"


def get_all_macs():
    system = platform.system().lower()
    if system == "windows":
        cmd = "getmac"
    else:
        cmd = "ifconfig -a"

    output = os.popen(cmd).read()

    macs = re.findall(r"([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})", output)
    return ",".join(
        [i.replace("-", "").lower() for i in set(macs) if i != "00-00-00-00-00-00"]
    )


def get_active_mac():
    local_ip = get_local_ip()

    # 遍历所有网卡，找到包含这个 IP 的那个网卡
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == local_ip:
                # 找到后返回它的 MAC 地址
                for addr2 in addrs:
                    if addr2.family == psutil.AF_LINK:
                        return addr2.address.replace("-", "").lower()
    return None


def get_process_by_name(process_name) -> list[(int, str)]:
    """
    获取指定进程名称的进程ID
    """
    res = []
    try:
        for proc in psutil.process_iter(["pid", "name", "exe", "ppid"]):
            # logger.debug(f"当前进程:{proc.info}")
            if proc.info["name"] == process_name:
                # logger.info(f"找到进程 {process_name}(PID:{proc.info['pid']})")
                res.append((proc.info["pid"], proc.info["exe"]))
    except psutil.NoSuchProcess:
        return []
    return res


def get_memory_usage(pid=None):
    """
    计算指定进程及其所有后代进程的内存占用（单位：字节）
    如果 pid=None，则使用当前进程
    """
    if pid is None:
        pid = os.getpid()

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return 0

    # 当前进程的内存
    total = proc.memory_info().rss

    # 加上所有后代进程的内存
    for child in proc.children(recursive=True):
        try:
            total += child.memory_info().rss
        except psutil.NoSuchProcess:
            pass  # 子进程可能在此时已经退出

    return f"{total / 1024 / 1024:.2f}MB"  # 转换为MB


def get_process_memory_usage(process_name: str) -> float:
    """
    获取指定进程名称的内存占用（单位：MB）
    """
    pids = get_process_by_name(process_name)
    if pids is None:
        return 0
    res = 0
    for pid, exe in pids:
        res += get_memory_usage(pid)
    return res


def get_sys_info() -> dict:
    info = {}
    # CPU 使用率（百分比）
    info["cpu"] = f"{psutil.cpu_percent(interval=1)}%"
    # 每个 CPU 核心使用率
    info["cpu_percent"] = psutil.cpu_percent(interval=1, percpu=True)
    # CPU 逻辑核 / 物理核数
    info["cpu_count"] = f"{psutil.cpu_count(logical=True)}"
    info["cpu_count_physical"] = f"{psutil.cpu_count(logical=False)}"
    # 内存使用情况
    mem = psutil.virtual_memory()
    info["mem"] = f"{mem.percent}%"
    info["mem_total"] = f"{mem.total / 1024 / 1024:.2f}MB"
    info["mem_used"] = f"{mem.used / 1024 / 1024:.2f}MB"
    info["mem_available"] = f"{mem.available / 1024 / 1024:.2f}MB"
    info["mem_free"] = f"{mem.free / 1024 / 1024:.2f}MB"

    # 交换分区（虚拟内存）
    swap = psutil.swap_memory()
    info["swap"] = f"{swap.percent}%"
    info["swap_total"] = f"{swap.total / 1024 / 1024:.2f}MB"
    info["swap_used"] = f"{swap.used / 1024 / 1024:.2f}MB"

    # 磁盘使用情况
    disk = psutil.disk_usage("C:/")
    info["disk"] = f"{disk.percent}%"
    info["disk_total"] = f"{disk.total / 1024 / 1024 / 1024:.2f}GB"
    info["disk_used"] = f"{disk.used / 1024 / 1024 / 1024:.2f}GB"
    info["disk_free"] = f"{disk.free / 1024 / 1024 / 1024:.2f}GB"

    # 网络连接情况
    net = psutil.net_connections()
    # print(psutil.net_io_counters(pernic=True))
    info["net"] = len(net)

    return info


def compress_text(text: str) -> str:
    """
    压缩文本内容
    """
    # print(f"压缩前大小：{len(text)}")
    # 压缩文本
    compressed_data = gzip.compress(text.encode("utf-8"))
    # 使用 base64 编码
    encoded_data = base64.b64encode(compressed_data).decode("utf8")
    # print(f"压缩后大小：{len(encoded_data)}")
    return encoded_data


def decompress_text(encoded_data: str) -> str:
    """
    被压缩后再经过base64编码的数据，先base64解码再解压
    """
    decode_data = base64.b64decode(encoded_data.encode("utf-8"))
    if decode_data.startswith(b"x\x9c"):
        decompress_text = zlib.decompress(decode_data).decode("utf8")
    elif decode_data.startswith(b"x\x1f") or decode_data.startswith(b"\x1f\x8b"):
        decompress_text = gzip.decompress(decode_data).decode("utf-8")
    else:
        raise TypeError("解压失败")
    return decompress_text


def compress_dict_to_str(data: dict) -> str:
    return compress_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def decompress_str_to_dict(data: str) -> dict:
    data = decompress_text(data)
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        string_bytes = data.encode("utf-8")
        encoded_bytes = base64.b64decode(string_bytes)
        return json.loads(encoded_bytes.decode("utf-8"))


def get_all_process() -> list[dict]:
    current_pid = os.getpid()
    all_process = []
    # 查找所有子进程
    for proc in psutil.process_iter(["pid", "ppid", "name", "exe"]):
        try:
            # logger.info(f"进程： {proc.info['name']}  路径:{proc.info["exe"]}")
            if proc.info["ppid"] == current_pid:
                proc.info["is_current_child"] = True
            all_process.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return all_process


_RELEASES_API_URL = "https://gitee.com/api/v5/repos/panda26/api-test-platform/releases?page=1&per_page=20&direction=desc"
_RUNTIME_PRESERVE_NAMES = {"storage", "logs", ".update_backup"}
_RELEASE_PACKAGE_SUFFIXES = {".exe", ".zip"}
_RELEASE_SPLIT_ASSET_RE = re.compile(
    r"^(?P<base>.+(?P<suffix>\.(?:exe|zip)))(?:\.(?P<digits>\d{3,4})|\.part(?P<part>\d{1,4}))$",
    re.IGNORECASE,
)


def is_frozen_client_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_client_root_dir() -> Path:
    if is_frozen_client_runtime():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_client_package_mode() -> str:
    """
    返回客户端当前运行形态:
    - source: 源码运行
    - standalone: 单文件独立打包
    - portable_dir: 非独立目录打包
    """
    if not is_frozen_client_runtime():
        return "source"

    exe_dir = Path(sys.executable).resolve().parent
    if (exe_dir / "_internal").is_dir():
        return "portable_dir"

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        try:
            bundle_root_path = Path(bundle_root).resolve()
            if bundle_root_path == exe_dir or bundle_root_path.parent == exe_dir:
                return "portable_dir"
        except Exception:
            pass

    return "standalone"


def get_client_update_runtime_profile() -> dict[str, Any]:
    package_mode = get_client_package_mode()
    client_root = get_client_root_dir()
    current_exe = Path(sys.executable).resolve() if is_frozen_client_runtime() else None
    main_exe_name = current_exe.name if current_exe else ""
    main_exe_stem = current_exe.stem if current_exe else ""

    label_map = {
        "source": "源码运行",
        "standalone": "独立打包",
        "portable_dir": "非独立打包",
    }
    preferred_suffixes = [".exe", ".zip"]
    preferred_asset_label = "exe"
    if package_mode == "portable_dir":
        preferred_suffixes = [".zip", ".exe"]
        preferred_asset_label = "zip"

    return {
        "package_mode": package_mode,
        "package_mode_label": label_map.get(package_mode, package_mode),
        "preferred_suffixes": preferred_suffixes,
        "preferred_asset_label": preferred_asset_label,
        "client_root": client_root,
        "current_exe": current_exe,
        "main_exe_name": main_exe_name,
        "main_exe_stem": main_exe_stem,
    }


def _normalize_version_tuple(value: str | None) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(value or ""))
    if not parts:
        return (0,)
    return tuple(int(part) for part in parts)


def _has_newer_version(candidate: str | None, current: str = VERSION) -> bool:
    return _normalize_version_tuple(candidate) > _normalize_version_tuple(current)


def _safe_release_suffix(value: str | None) -> str:
    suffix = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value or "").strip())
    return suffix or "latest"


async def _fetch_release_list() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(
        timeout=DEFAULT_HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        response = await client.get(_RELEASES_API_URL)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("版本接口返回格式异常")
    return data


def _build_release_markdown(releases: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for info in releases[:6]:
        tag_name = str(info.get("tag_name") or "-").strip()
        body = str(info.get("body") or "").strip()
        if body:
            parts.append(f"# {tag_name}\n{body}")
        else:
            parts.append(f"# {tag_name}")
    return "\n\n".join(parts)


def _parse_release_asset_name(asset_name: str) -> dict[str, Any] | None:
    normalized_name = str(asset_name or "").strip()
    if not normalized_name:
        return None

    lower_name = normalized_name.lower()
    for suffix in _RELEASE_PACKAGE_SUFFIXES:
        if lower_name.endswith(suffix):
            return {
                "package_name": normalized_name,
                "suffix": suffix,
                "part_index": None,
            }

    match = _RELEASE_SPLIT_ASSET_RE.match(normalized_name)
    if not match:
        return None

    suffix = str(match.group("suffix") or "").lower()
    part_value = match.group("digits") or match.group("part")
    if suffix not in _RELEASE_PACKAGE_SUFFIXES or not part_value:
        return None

    part_index = int(part_value)
    if part_index <= 0:
        return None

    return {
        "package_name": str(match.group("base") or "").strip(),
        "suffix": suffix,
        "part_index": part_index,
    }


def _iter_release_assets(release: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for item in release.get("assets") or []:
        name = str(item.get("name") or "").strip()
        url = str(item.get("browser_download_url") or "").strip()
        if not name or not url:
            continue
        parsed_name = _parse_release_asset_name(name)
        if not parsed_name:
            continue

        try:
            asset_size = int(item.get("size") or 0)
        except (TypeError, ValueError):
            asset_size = 0

        assets.append(
            {
                "name": name,
                "url": url,
                "size": max(asset_size, 0),
                **parsed_name,
            }
        )
    return assets


def _build_release_asset_packages(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    split_groups: dict[tuple[str, str], dict[str, Any]] = {}

    for asset in assets:
        if asset["part_index"] is None:
            packages.append(
                {
                    "name": asset["package_name"],
                    "display_name": asset["name"],
                    "suffix": asset["suffix"],
                    "is_split": False,
                    "part_count": 1,
                    "total_size": int(asset.get("size") or 0),
                    "parts": [asset],
                }
            )
            continue

        key = (str(asset["package_name"]).lower(), str(asset["suffix"]).lower())
        group = split_groups.setdefault(
            key,
            {
                "name": asset["package_name"],
                "suffix": asset["suffix"],
                "parts": [],
            },
        )
        group["parts"].append(asset)

    for group in split_groups.values():
        parts = sorted(group["parts"], key=lambda item: int(item["part_index"]))
        if not parts:
            continue

        expected_indices = list(range(1, len(parts) + 1))
        actual_indices = [int(item["part_index"]) for item in parts]
        if actual_indices != expected_indices:
            logger.warning(
                "忽略不完整的更新分片组: {}，分片序号={}",
                group["name"],
                actual_indices,
            )
            continue

        packages.append(
            {
                "name": group["name"],
                "display_name": f"{group['name']}（共{len(parts)}个分片）",
                "suffix": group["suffix"],
                "is_split": True,
                "part_count": len(parts),
                "total_size": sum(int(item.get("size") or 0) for item in parts),
                "parts": parts,
            }
        )

    return packages


def _asset_match_score(asset_name: str, suffix: str, runtime_profile: dict[str, Any]) -> int:
    lower_name = asset_name.lower()
    stem = Path(asset_name).stem.lower()
    current_exe_name = str(runtime_profile.get("main_exe_name") or "").lower()
    current_exe_stem = str(runtime_profile.get("main_exe_stem") or "").lower()

    if suffix == ".exe":
        if current_exe_name and lower_name == current_exe_name:
            return 300
        if current_exe_stem and stem == current_exe_stem:
            return 260
        if current_exe_stem and current_exe_stem in stem:
            return 220
        if lower_name in {"qtrclientnew.exe", "qtrclient.exe"}:
            return 200
    elif suffix == ".zip":
        expected_zip_name = f"{current_exe_stem}.zip" if current_exe_stem else ""
        if expected_zip_name and lower_name == expected_zip_name:
            return 300
        if current_exe_stem and stem == current_exe_stem:
            return 260
        if current_exe_stem and current_exe_stem in stem:
            return 220
        if lower_name in {"qtrclientnew.zip", "qtrclient.zip"}:
            return 200

    if stem in {"qtrclientnew", "qtrclient"}:
        return 160
    if "qtrclientnew" in stem or "qtrclient" in stem:
        return 120
    return 10


def _select_release_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    runtime_profile = get_client_update_runtime_profile()
    assets = _build_release_asset_packages(_iter_release_assets(release))
    if not assets:
        return None

    for suffix in runtime_profile["preferred_suffixes"]:
        candidates = [item for item in assets if item["suffix"] == suffix]
        if not candidates:
            continue
        ranked = sorted(
            candidates,
            key=lambda item: (
                -_asset_match_score(item["name"], item["suffix"], runtime_profile),
                item["is_split"],
                item["name"].lower(),
            ),
        )
        return ranked[0]

    return None


async def check_app_has_new() -> tuple[bool | str, str]:
    releases = await _fetch_release_list()
    if not releases:
        return False, ""
    latest_release = releases[0]
    latest_version = str(latest_release.get("tag_name") or "").strip()
    has_new = latest_version if _has_newer_version(latest_version) else False
    return has_new, _build_release_markdown(releases)


async def download_new_app(
    download_process_call=None, force: bool = False
) -> str | None:
    logger.info("开始下载新包")
    runtime_profile = get_client_update_runtime_profile()
    logger.info(
        "当前升级运行形态: {}，优先更新包类型: {}",
        runtime_profile["package_mode_label"],
        runtime_profile["preferred_asset_label"],
    )
    if download_process_call:
        download_process_call(
            f"正在获取版本信息... 当前运行形态: {runtime_profile['package_mode_label']}，"
            f"优先选择 {runtime_profile['preferred_asset_label']} 包"
        )

    releases = await _fetch_release_list()
    if not releases:
        return None

    latest_release = releases[0]
    new_version = str(latest_release.get("tag_name") or "").strip()
    if not force and not _has_newer_version(new_version):
        logger.info(f"当前版本 {VERSION} 已是最新版本，无需下载")
        return None

    selected_asset = _select_release_asset(latest_release)
    if not selected_asset:
        logger.info("没有找到升级文件")
        return None
    file_suffix = selected_asset["suffix"]
    asset_name = selected_asset["name"]
    display_name = selected_asset.get("display_name") or asset_name
    logger.info(f"已选择更新包: {display_name}")
    if download_process_call:
        download_process_call(f"已选择更新包: {display_name}")

    download_dir = Path(tempfile.gettempdir()) / "QTRClient" / "updates"
    download_dir.mkdir(parents=True, exist_ok=True)
    target_path = download_dir / f"QTRClient_{_safe_release_suffix(new_version)}{file_suffix}"
    temp_path = target_path.with_suffix(target_path.suffix + ".part")

    if temp_path.exists():
        temp_path.unlink()

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_HTTP_TIMEOUT,
            follow_redirects=True,
        ) as client:
            downloaded = 0
            total_size = int(selected_asset.get("total_size") or 0)
            parts = selected_asset.get("parts") or []
            part_count = max(int(selected_asset.get("part_count") or len(parts) or 1), 1)
            if total_size > 0:
                logger.info(f"开始下载更新包，文件大小：{total_size / 1024 / 1024:.2f} MB")

            with temp_path.open("wb") as file_obj:
                for index, part in enumerate(parts, start=1):
                    part_name = str(part.get("name") or "")
                    part_url = str(part.get("url") or "")
                    if not part_url:
                        raise RuntimeError(f"更新分片地址为空: {part_name or index}")

                    part_downloaded = 0
                    part_size = int(part.get("size") or 0)
                    logger.info(
                        "开始下载更新{}: {}/{} {}",
                        "分片" if selected_asset["is_split"] else "包",
                        index,
                        part_count,
                        part_name,
                    )

                    async with client.stream("GET", part_url) as response:
                        response.raise_for_status()
                        header_size = int(response.headers.get("content-length", 0) or 0)
                        if header_size > 0 and part_size <= 0:
                            part_size = header_size

                        async for chunk in response.aiter_bytes(1024 * 1024):
                            if not chunk:
                                continue
                            file_obj.write(chunk)
                            chunk_size = len(chunk)
                            downloaded += chunk_size
                            part_downloaded += chunk_size

                            if not download_process_call:
                                continue

                            if total_size > 0:
                                percent = downloaded / total_size * 100
                                if selected_asset["is_split"]:
                                    download_process_call(
                                        "下载分片 {}/{}: {}，总进度 {:.2f}% ({:.2f}/{:.2f}MB)".format(
                                            index,
                                            part_count,
                                            part_name,
                                            percent,
                                            downloaded / 1024 / 1024,
                                            total_size / 1024 / 1024,
                                        )
                                    )
                                else:
                                    download_process_call(
                                        f"新包大小：{total_size / 1024 / 1024:.2f}MB, 下载进度: {percent:.2f}%"
                                    )
                            elif selected_asset["is_split"] and part_size > 0:
                                percent = part_downloaded / part_size * 100
                                download_process_call(
                                    "下载分片 {}/{}: {}，分片进度 {:.2f}%".format(
                                        index,
                                        part_count,
                                        part_name,
                                        percent,
                                    )
                                )
                            else:
                                download_process_call(
                                    f"已下载：{downloaded / 1024 / 1024:.2f}MB"
                                )

        if target_path.exists():
            target_path.unlink()
        temp_path.replace(target_path)
        logger.info(f"更新包下载完成: {target_path}")
        return str(target_path.resolve())
    except Exception as e:
        logger.error(f"新包下载失败：{e}")
        temp_path.unlink(missing_ok=True)
        return None


def create_powershell_update_script_new():
    script_dir = Path(tempfile.gettempdir()) / "QTRClient" / "updater"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / "update_powershell.ps1"

    ps_script = """param(
    [string]$CurrentDir,
    [string]$MainExePath,
    [string]$NewFile,
    [int]$CurrentPid = 0
)
$ErrorActionPreference = "Stop"
$LogPath = Join-Path ([System.IO.Path]::GetDirectoryName($NewFile)) "update.log"
Start-Transcript -Path $LogPath -Append | Out-Null

$MainExeName = [System.IO.Path]::GetFileName($MainExePath)
$ProcessName = [System.IO.Path]::GetFileNameWithoutExtension($MainExePath)
$BackupRoot = Join-Path $CurrentDir ".update_backup"
$PreserveNames = @("storage", "logs", ".update_backup")
$ReplacedItems = New-Object System.Collections.ArrayList
$CreatedItems = New-Object System.Collections.ArrayList

Write-Host "=== QTRClient Update ==="
Write-Host "Target directory: $CurrentDir"
Write-Host "Main exe path: $MainExePath"
Write-Host "New file: $NewFile"

function Add-ReplacedItem {
    param(
        [string]$Destination,
        [string]$Backup
    )
    [void]$ReplacedItems.Add([PSCustomObject]@{
        Destination = $Destination
        Backup = $Backup
    })
}

function Add-CreatedItem {
    param([string]$Path)
    [void]$CreatedItems.Add($Path)
}

function Backup-ExistingItem {
    param([string]$DestinationPath)

    if (-not (Test-Path $DestinationPath)) {
        return $false
    }

    $ItemName = [System.IO.Path]::GetFileName($DestinationPath)
    $BackupPath = Join-Path $BackupRoot $ItemName
    if (Test-Path $BackupPath) {
        Remove-Item $BackupPath -Recurse -Force -ErrorAction SilentlyContinue
    }
    Move-Item -LiteralPath $DestinationPath -Destination $BackupPath -Force
    Add-ReplacedItem -Destination $DestinationPath -Backup $BackupPath
    return $true
}

function Resolve-SourceDir {
    param([string]$TempDir)

    $TopFiles = @(Get-ChildItem -Path $TempDir -Force -File -ErrorAction SilentlyContinue)
    $TopDirs = @(Get-ChildItem -Path $TempDir -Force -Directory -ErrorAction SilentlyContinue)
    if ($TopFiles.Count -eq 0 -and $TopDirs.Count -eq 1) {
        return $TopDirs[0].FullName
    }
    return $TempDir
}

function Find-MainExeInPackage {
    param(
        [string]$SourceDir,
        [string]$PreferredName
    )

    $ExactPath = Join-Path $SourceDir $PreferredName
    if (Test-Path $ExactPath) {
        return $ExactPath
    }

    $Candidates = @(Get-ChildItem -Path $SourceDir -Filter *.exe -File -ErrorAction SilentlyContinue | Sort-Object Name)
    if ($Candidates.Count -eq 0) {
        return $null
    }

    $PrimaryCandidates = @($Candidates | Where-Object { $_.BaseName -match "(?i)^QTRClient" -and $_.Name -notmatch "(?i)helper" })
    if ($PrimaryCandidates.Count -gt 0) {
        return $PrimaryCandidates[0].FullName
    }

    $NonHelperCandidates = @($Candidates | Where-Object { $_.Name -notmatch "(?i)helper" })
    if ($NonHelperCandidates.Count -gt 0) {
        return $NonHelperCandidates[0].FullName
    }

    return $Candidates[0].FullName
}

function Copy-PackageItem {
    param(
        [System.IO.FileSystemInfo]$SourceItem,
        [string]$DestinationRoot
    )

    $DestinationPath = Join-Path $DestinationRoot $SourceItem.Name
    $DestinationExisted = Test-Path $DestinationPath
    [void](Backup-ExistingItem -DestinationPath $DestinationPath)

    if ($SourceItem.PSIsContainer) {
        Copy-Item -LiteralPath $SourceItem.FullName -Destination $DestinationRoot -Recurse -Force
    } else {
        Copy-Item -LiteralPath $SourceItem.FullName -Destination $DestinationPath -Force
    }

    if (-not $DestinationExisted -and (Test-Path $DestinationPath)) {
        Add-CreatedItem -Path $DestinationPath
    }
}

function Restore-Backups {
    if ($CreatedItems.Count -gt 0) {
        foreach ($CreatedPath in @($CreatedItems) | Sort-Object Length -Descending) {
            if (Test-Path $CreatedPath) {
                Remove-Item $CreatedPath -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }

    if ($ReplacedItems.Count -gt 0) {
        foreach ($Entry in @($ReplacedItems) | Sort-Object { $_.Destination.Length } -Descending) {
            if (Test-Path $Entry.Destination) {
                Remove-Item $Entry.Destination -Recurse -Force -ErrorAction SilentlyContinue
            }
            if (Test-Path $Entry.Backup) {
                Move-Item -LiteralPath $Entry.Backup -Destination $Entry.Destination -Force
            }
        }
    }

    if (Test-Path $BackupRoot) {
        Remove-Item $BackupRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

try {
    if (-not (Test-Path $NewFile)) {
        throw "Cannot find new file: $NewFile"
    }
    if (-not (Test-Path $CurrentDir)) {
        throw "Cannot find target directory: $CurrentDir"
    }
    if (-not (Test-Path $MainExePath)) {
        throw "Cannot find main exe: $MainExePath"
    }

    if ($CurrentPid -gt 0) {
        try {
            Write-Host "Wait for current process PID $CurrentPid to exit..."
            Wait-Process -Id $CurrentPid -Timeout 30 -ErrorAction Stop
            Write-Host "Program exited"
        } catch {
            $stillRunning = Get-Process -Id $CurrentPid -ErrorAction SilentlyContinue
            if ($stillRunning) {
                throw "Timeout waiting for current process exit: PID $CurrentPid"
            }
            Write-Host "Program already exited"
        }
    } else {
        Write-Host "Wait for program $ProcessName to exit..."
        $WaitCount = 0
        $MaxWait = 30
        while ($WaitCount -lt $MaxWait) {
            $process = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
            if (-not $process) {
                Write-Host "Program exited"
                break
            }
            $WaitCount++
            Write-Host "Waiting... ($WaitCount/$MaxWait)"
            Start-Sleep -Seconds 1
        }
        if ($WaitCount -ge $MaxWait) {
            throw "Timeout waiting for process exit: $ProcessName"
        }
    }

    Write-Host "Start updating..."
    $FileExtension = [System.IO.Path]::GetExtension($NewFile).ToLower()
    Write-Host "File type: $FileExtension"
    if (-not (Test-Path $BackupRoot)) {
        New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    }

    if ($FileExtension -eq ".exe") {
        Write-Host "Replacing main EXE only..."

        $CurrentExePath = $MainExePath
        $CurrentExeExists = Test-Path $CurrentExePath
        [void](Backup-ExistingItem -DestinationPath $CurrentExePath)

        Copy-Item -LiteralPath $NewFile -Destination $CurrentExePath -Force
        if (-not $CurrentExeExists -and (Test-Path $CurrentExePath)) {
            Add-CreatedItem -Path $CurrentExePath
        }
        Write-Host "EXE file replaced"

    } elseif ($FileExtension -eq ".zip") {
        Write-Host "Replacing packaged application files from ZIP..."

        $TempDir = "$CurrentDir.temp"
        if (Test-Path $TempDir) {
            Remove-Item $TempDir -Recurse -Force
        }
        New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

        Write-Host "Extracting ZIP package..."
        Expand-Archive -Path $NewFile -DestinationPath $TempDir -Force

        $SourceDir = Resolve-SourceDir -TempDir $TempDir
        Write-Host "Resolved source directory: $SourceDir"

        $PackageMainExePath = Find-MainExeInPackage -SourceDir $SourceDir -PreferredName $MainExeName
        if (-not $PackageMainExePath) {
            throw "Cannot find main exe inside ZIP package"
        }
        $PackageMainExeName = [System.IO.Path]::GetFileName($PackageMainExePath)
        Write-Host "Detected package main exe: $PackageMainExeName"

        $PackageItems = @(Get-ChildItem -Path $SourceDir -Force -ErrorAction SilentlyContinue)
        foreach ($Item in $PackageItems) {
            if ($PreserveNames -contains $Item.Name) {
                Write-Host "Skip runtime item: $($Item.Name)"
                continue
            }
            if (-not $Item.PSIsContainer -and $Item.FullName -eq $PackageMainExePath) {
                continue
            }
            Copy-PackageItem -SourceItem $Item -DestinationRoot $CurrentDir
            Write-Host "Copied package item: $($Item.Name)"
        }

        $CurrentExePath = $MainExePath
        $CurrentExeExists = Test-Path $CurrentExePath
        [void](Backup-ExistingItem -DestinationPath $CurrentExePath)
        Copy-Item -LiteralPath $PackageMainExePath -Destination $CurrentExePath -Force
        if (-not $CurrentExeExists -and (Test-Path $CurrentExePath)) {
            Add-CreatedItem -Path $CurrentExePath
        }
        Write-Host "Main EXE replaced"

        Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "ZIP update completed"

    } else {
        throw "Unsupported file type: $FileExtension. Only .exe and .zip are supported."
    }

    Remove-Item $NewFile -Force
    if (Test-Path $BackupRoot) {
        Remove-Item $BackupRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (-not (Test-Path $MainExePath)) {
        throw "Cannot find main program after update: $MainExePath"
    }

    Write-Host "File update complete"
    Write-Host "Starting new version..."
    $Process = Start-Process -FilePath $MainExePath -PassThru

    if ($Process) {
        Write-Host "New version started (PID: $($Process.Id))"
    } else {
        Write-Host "Start command sent, but process status unknown"
    }
} catch {
    Write-Host "Update failed: $($_.Exception.Message)"
    Restore-Backups
    exit 1
} finally {
    try {
        Stop-Transcript | Out-Null
    } catch {
    }
}
"""
    try:
        with script_path.open("w", encoding="gbk") as file_obj:
            file_obj.write(ps_script)
    except UnicodeEncodeError:
        with script_path.open("w", encoding="ascii", errors="ignore") as file_obj:
            file_obj.write(ps_script)
    return str(script_path.resolve())


async def perform_update_with_powershell(
    download_process_call=None, force: bool = False
) -> tuple[bool, str]:
    """使用 PowerShell 执行更新"""
    runtime_profile = get_client_update_runtime_profile()
    if runtime_profile["package_mode"] == "source":
        return False, "当前为源码运行模式，不支持自更新，请使用打包版客户端"

    current_exe_path = runtime_profile["current_exe"]
    current_dir = str(runtime_profile["client_root"])
    if current_exe_path is None:
        return False, "未识别到当前客户端主程序路径，无法执行自更新"
    logger.info(f"current_exe: {current_exe_path}")
    logger.info(
        "开始执行自更新，当前运行形态: {}，优先更新包类型: {}",
        runtime_profile["package_mode_label"],
        runtime_profile["preferred_asset_label"],
    )

    new_app_path = await download_new_app(download_process_call, force=force)
    if not new_app_path:
        return False, "更新未执行或下载失败"

    script_path = create_powershell_update_script_new()

    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
                "-CurrentDir",
                current_dir,
                "-MainExePath",
                str(current_exe_path),
                "-NewFile",
                str(Path(new_app_path).resolve()),
                "-CurrentPid",
                str(os.getpid()),
            ]
        )
        logger.info("更新程序已启动，即将退出...")
        return True, "更新程序已启动，应用即将退出"
    except Exception as e:
        logger.info(f"启动更新失败: {e}")
        return False, f"启动更新失败: {e}"


class ExeVersionReader:
    def __init__(self, exe_path):
        self.exe_path = exe_path
        self.version_info = {}

    def get_basic_version(self):
        """获取基本版本号"""
        try:
            info = win32api.GetFileVersionInfo(self.exe_path, "\\")
            ms = info["FileVersionMS"]
            ls = info["FileVersionLS"]
            return f"{win32api.HIWORD(ms)}.{win32api.LOWORD(ms)}.{win32api.HIWORD(ls)}.{win32api.LOWORD(ls)}"
        except Exception as e:
            return None

    def get_all_version_info(self):
        """获取所有版本信息"""
        try:
            language_codepage = win32api.GetFileVersionInfo(
                self.exe_path, "\\VarFileInfo\\Translation"
            )
            if not language_codepage:
                return {}

            lang, codepage = language_codepage[0]

            fields = [
                "CompanyName",
                "FileDescription",
                "FileVersion",
                "InternalName",
                "LegalCopyright",
                "OriginalFilename",
                "ProductName",
                "ProductVersion",
            ]

            for field in fields:
                try:
                    string_path = f"\\StringFileInfo\\{lang:04X}{codepage:04X}\\{field}"
                    value = win32api.GetFileVersionInfo(self.exe_path, string_path)
                    self.version_info[field] = value
                except:
                    self.version_info[field] = None

            return self.version_info
        except Exception as e:
            return {}

    def print_version_info(self):
        """打印版本信息"""
        if not self.version_info:
            self.get_all_version_info()

        print(f"文件: {os.path.basename(self.exe_path)}")
        print("=" * 50)
        for key, value in self.version_info.items():
            if value:
                print(f"{key}: {value}")

    def get_exe_file_version(self) -> str | None:
        if not self.version_info:
            self.get_all_version_info()
        return self.version_info.get("FileVersion", None)


def get_sys_info_view():

    try:
        info = get_sys_info()
        process_men = get_memory_usage()
        pos = get_process_by_name("CPOS-DF.exe")
        pos_mem = 0
        pos_dir = ""
        if pos:
            pos_dir = pos[0][1]
            pos_mem = get_memory_usage(int(pos[0][0]))
        appState.client_info.current_pos = pos_dir
        appState.client_info.toolbar_info = f"CPU:{info['cpu']}/内存:{info['mem']}/磁盘:{info['disk']}/进程:{process_men}/CPOS-DF:{pos_mem}/{pos_dir}"
    except Exception as e:
        logger.error(f"获取系统信息异常:{e}")
        appState.client_info.toolbar_info = f"获取系统信息异常:{e}"


if __name__ == "__main__":
    # 示例用法
    # test_dir = "./test_folder"
    # ensure_directory_exists(test_dir)
    # get_sys_info()
    ExeVersionReader(
        "C:\\POS\\client\\CPOS-DF-SG711-PRO\\CPOS-DF.exe"
    ).print_version_info()
