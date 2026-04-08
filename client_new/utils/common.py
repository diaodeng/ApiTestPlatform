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


def is_frozen_client_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_client_root_dir() -> Path:
    if is_frozen_client_runtime():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


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


def _select_release_asset(release: dict[str, Any]) -> tuple[str | None, str | None]:
    exe_url = None
    zip_url = None
    for item in release.get("assets") or []:
        name = item.get("name")
        url = item.get("browser_download_url")
        if not url:
            continue
        if name == "QTRClient.exe":
            exe_url = url
        elif name == "QTRClient.zip":
            zip_url = url
    if exe_url:
        return exe_url, ".exe"
    if zip_url:
        return zip_url, ".zip"
    return None, None


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
    if download_process_call:
        download_process_call("正在获取版本信息...")

    releases = await _fetch_release_list()
    if not releases:
        return None

    latest_release = releases[0]
    new_version = str(latest_release.get("tag_name") or "").strip()
    if not force and not _has_newer_version(new_version):
        logger.info(f"当前版本 {VERSION} 已是最新版本，无需下载")
        return None

    asset_url, file_suffix = _select_release_asset(latest_release)
    if not asset_url or not file_suffix:
        logger.info("没有找到升级文件")
        return None

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
            async with client.stream("GET", asset_url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0) or 0)
                logger.info(f"开始下载更新包，文件大小：{total_size / 1024 / 1024:.2f} MB")
                downloaded = 0
                with temp_path.open("wb") as file_obj:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        if not chunk:
                            continue
                        file_obj.write(chunk)
                        downloaded += len(chunk)

                        if not download_process_call:
                            continue
                        if total_size > 0:
                            percent = downloaded / total_size * 100
                            download_process_call(
                                f"新包大小：{total_size / 1024 / 1024:.2f}MB, 下载进度: {percent:.2f}%"
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

Write-Host "=== QTRClient Update ==="
Write-Host "Target directory: $CurrentDir"
Write-Host "Main exe path: $MainExePath"
Write-Host "New file: $NewFile"

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

    if ($FileExtension -eq ".exe") {
        Write-Host "Replacing EXE file only..."

        $CurrentExePath = $MainExePath
        $BackupExePath = "$CurrentExePath.backup"

        if (Test-Path $CurrentExePath) {
            if (Test-Path $BackupExePath) {
                Remove-Item $BackupExePath -Force
            }
            Move-Item -LiteralPath $CurrentExePath -Destination $BackupExePath -Force
            Write-Host "EXE backup created: $BackupExePath"
        }

        Copy-Item -LiteralPath $NewFile -Destination $CurrentExePath -Force
        Write-Host "EXE file replaced"

    } elseif ($FileExtension -eq ".zip") {
        Write-Host "Replacing EXE and _internal directory..."

        $TempDir = "$CurrentDir.temp"
        if (Test-Path $TempDir) {
            Remove-Item $TempDir -Recurse -Force
        }
        New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

        Write-Host "Extracting ZIP package..."
        Expand-Archive -Path $NewFile -DestinationPath $TempDir -Force

        $SourceDir = $TempDir
        $UnzippedItems = Get-ChildItem -Path $TempDir -Directory
        if ($UnzippedItems.Count -eq 1) {
            $SourceDir = $UnzippedItems[0].FullName
            Write-Host "Found subdirectory: $SourceDir"
        }

        $CurrentExePath = $MainExePath
        $NewExePath = Join-Path $SourceDir $MainExeName

        if (Test-Path $NewExePath) {
            $BackupExePath = "$CurrentExePath.backup"
            if (Test-Path $CurrentExePath) {
                if (Test-Path $BackupExePath) {
                    Remove-Item $BackupExePath -Force
                }
                Move-Item -LiteralPath $CurrentExePath -Destination $BackupExePath -Force
                Write-Host "EXE backup created"
            }
            Copy-Item -LiteralPath $NewExePath -Destination $CurrentExePath -Force
            Write-Host "EXE file replaced"
        }

        $CurrentInternalDir = Join-Path $CurrentDir "_internal"
        $NewInternalDir = Join-Path $SourceDir "_internal"

        if (Test-Path $NewInternalDir) {
            $BackupInternalDir = "$CurrentInternalDir.backup"
            if (Test-Path $CurrentInternalDir) {
                if (Test-Path $BackupInternalDir) {
                    Remove-Item $BackupInternalDir -Recurse -Force
                }
                Move-Item -LiteralPath $CurrentInternalDir -Destination $BackupInternalDir -Force
                Write-Host "_internal backup created"
            }
            New-Item -ItemType Directory -Path $CurrentInternalDir -Force | Out-Null
            Copy-Item -Path (Join-Path $NewInternalDir "*") -Destination $CurrentInternalDir -Recurse -Force
            Write-Host "_internal directory replaced"
        }

        Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "ZIP update completed"

    } else {
        throw "Unsupported file type: $FileExtension. Only .exe and .zip are supported."
    }

    Remove-Item $NewFile -Force

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

    $CurrentExePath = $MainExePath
    $BackupExePath = "$CurrentExePath.backup"
    $CurrentInternalDir = Join-Path $CurrentDir "_internal"
    $BackupInternalDir = "$CurrentInternalDir.backup"

    if (Test-Path $BackupExePath) {
        Write-Host "Restoring EXE from backup..."
        if (Test-Path $CurrentExePath) {
            Remove-Item $CurrentExePath -Force -ErrorAction SilentlyContinue
        }
        Move-Item -LiteralPath $BackupExePath -Destination $CurrentExePath -Force
        Write-Host "EXE restored from backup"
    }

    if (Test-Path $BackupInternalDir) {
        Write-Host "Restoring _internal from backup..."
        if (Test-Path $CurrentInternalDir) {
            Remove-Item $CurrentInternalDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        Move-Item -LiteralPath $BackupInternalDir -Destination $CurrentInternalDir -Force
        Write-Host "_internal restored from backup"
    }

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
    if not is_frozen_client_runtime():
        return False, "当前为源码运行模式，不支持自更新，请使用打包版客户端"

    current_exe_path = Path(sys.executable).resolve()
    current_dir = str(current_exe_path.parent)
    logger.info(f"current_exe: {current_exe_path}")

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
