import json
import os
import sys
import socket
import platform
import re
from typing import Any, Optional

import psutil
import requests
import subprocess
from loguru import logger


class DBHelper:
    def __init__(self, db):
        self.db = db


def resource_path(relative_path: str) -> str:
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)
    logger.debug(f"资源文件路径:{file_path}")
    if not os.path.exists(file_path):

        """获取资源文件绝对路径，兼容 PyInstaller 打包"""
        if hasattr(sys, '_MEIPASS'):  # PyInstaller 打包后执行路径
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
        print(f"目录 {dir_path} 已创建")
    else:
        print(f"目录 {dir_path} 已存在")


def kill_process_by_name(process_name) -> bool:
    """强制结束指定进程

    :param process_name: 进程名称
    :param log: 日志对象
    :return:
    """
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            logger.debug(f"当前进程:{proc.info}")
            if proc.info['name'] == process_name:
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
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            current_name = proc.info['name'].lower()
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
        r = requests.get(url)
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
        with open(file_path, 'r', encoding='utf-8') as f:
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
        with open(file_path, 'w', encoding='utf-8') as f:
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
    return ",".join([i.replace("-", "").lower() for i in set(macs) if i != "00-00-00-00-00-00"])


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
        for proc in psutil.process_iter(['pid', 'name', "exe", "ppid"]):
            # logger.debug(f"当前进程:{proc.info}")
            if proc.info['name'] == process_name:
                # logger.info(f"找到进程 {process_name}(PID:{proc.info['pid']})")
                res.append((proc.info['pid'], proc.info['exe']))
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
    disk = psutil.disk_usage('C:/')
    info["disk"] = f"{disk.percent}%"
    info["disk_total"] = f"{disk.total / 1024 / 1024 / 1024:.2f}GB"
    info["disk_used"] = f"{disk.used / 1024 / 1024 / 1024:.2f}GB"
    info["disk_free"] = f"{disk.free / 1024 / 1024 / 1024:.2f}GB"

    # 网络连接情况
    net = psutil.net_connections()
    # print(psutil.net_io_counters(pernic=True))
    info["net"] = len(net)

    return info



if __name__ == "__main__":
    # 示例用法
    # test_dir = "./test_folder"
    # ensure_directory_exists(test_dir)
    get_sys_info()
