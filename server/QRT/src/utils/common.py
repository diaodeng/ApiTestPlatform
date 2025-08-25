import json
import os
from typing import Any, Optional

import psutil
import requests
import subprocess


class DBHelper:
    def __init__(self, db):
        self.db = db


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


def kill_process_by_name(process_name, log):
    """强制结束指定进程

    :param process_name: 进程名称
    :param log: 日志对象
    :return:
    """
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == process_name:
            proc.terminate()  # 优雅终止
            print(f"进程 {process_name}(PID:{proc.info['pid']}) 已终止")
            log.info(f"进程 {process_name}(PID:{proc.info['pid']}) 已终止")


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


if __name__ == "__main__":
    # 示例用法
    test_dir = "./test_folder"
    ensure_directory_exists(test_dir)
