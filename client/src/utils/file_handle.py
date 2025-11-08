import os
import fnmatch
from typing import List
import argparse
import platform
from loguru import logger
import subprocess
import configparser

class FileBackup:
    def __init__(self, src_path: str, backup_path: str = None, env: str = None):
        self.src_path = src_path
        self.backup_path = backup_path if backup_path else f"{src_path}_backup"

    def backup(self):
        if os.path.exists(self.file_path):
            if os.path.exists(self.backup_path):
                os.remove(self.backup_path)
            os.rename(self.file_path, self.backup_path)

    def restore(self):
        if os.path.exists(self.backup_path):
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            os.rename(self.backup_path, self.file_path)

    def backup_and_restore(self):
        self.backup()
        self.restore()

class IniFileHandel:
    def __init__(self, ini_file_path: str):
        self.ini_file_path = ini_file_path
        self.config = configparser.ConfigParser()
        self.config.read(ini_file_path, encoding='gbk')

    def get_section(self, section: str) -> dict:
        """
        获取指定section的所有键值对
        :param section: 要获取的section名称
        :return: 包含键值对的字典
        """
        if self.config.has_section(section):
            return dict(self.config.items(section))
        else:
            logger.warning(f"未找到section: {section}")
            return {}

    def get_value(self, section: str, key: str) -> str:
        """
        获取指定section下的指定key的值
        :param section: 要获取的section名称
        :param key: 要获取的key名称
        :return: key对应的值
        """
        if self.config.has_section(section) and self.config.has_option(section, key):
            return self.config.get(section, key)
        else:
            logger.warning(f"未找到section: {section} 或 key: {key}")
            return ""

    def set_value(self, section: str, key: str, value: str):
        """
        设置指定section下的指定key的值
        :param section: 要设置的section名称
        :param key: 要设置的key名称
        :param value: 要设置的值
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)

    def write(self):
        with open(self.ini_file_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

def search_files(
        directory: str,
        target_file: str,
        case_sensitive: bool = False,
        use_wildcard: bool = False
) -> List[str]:
    """
    搜索目录及其子目录下的目标文件
    :param directory: 要搜索的根目录
    :param target_file: 要查找的文件名(支持通配符)
    :param case_sensitive: 是否区分大小写
    :param use_wildcard: 是否启用通配符匹配
    :return: 包含所有匹配文件路径的列表
    """
    if not os.path.isdir(directory):
        raise ValueError(f"无效的目录路径: {directory}")

    found_files = []
    target = target_file if case_sensitive else target_file.lower()

    for root, _, files in os.walk(directory):
        for filename in files:
            current = filename if case_sensitive else filename.lower()

            if use_wildcard:
                if fnmatch.fnmatch(current, target):
                    found_files.append(os.path.join(root, filename))
            else:
                if current == target:
                    found_files.append(os.path.join(root, filename))

    return found_files


def open_file(path: str) -> bool:
    """打开文件"""
    logger.info(f"正在打开文件: {path}")
    try:
        if platform.system() == "Windows":
            os.startfile(path,cwd=os.path.dirname(path))
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:  # Linux
            subprocess.run(["xdg-open", path])
        return True
    except Exception as e:
        logger.error(f"打开:{path} 文件失败: {str(e)}")
        return False


def start_file_independent(file_path, env_vars=None):
    """
    独立启动文件，主程序终止后子进程继续运行
    """
    # 合并环境变量
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    # 使用 CREATE_NEW_PROCESS_GROUP 和 DETACHED_PROCESS
    creation_flags = (
            subprocess.DETACHED_PROCESS |
            subprocess.CREATE_NEW_PROCESS_GROUP
            # subprocess.CREATE_BREAKAWAY_FROM_JOB
    )
    # ['cmd', '/c', 'start', '', file_path],
    logger.info(f"启动的应用路径：{file_path}")
    process = subprocess.Popen(
        file_path,
        cwd=os.path.dirname(file_path),
        env=env,
        creationflags=creation_flags,
        close_fds=True
    )
    return process



def open_file_location(path: str) -> bool:
    """打开文件所在目录"""
    dir_path = os.path.dirname(path)
    return open_file(dir_path)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="文件搜索工具")
    parser.add_argument("directory", help="要搜索的根目录路径")
    parser.add_argument("filename", help="要查找的文件名(支持通配符)")
    parser.add_argument("-c", "--case-sensitive", action="store_true", help="区分大小写匹配")
    parser.add_argument("-w", "--wildcard", action="store_true", help="启用通配符匹配")
    args = parser.parse_args()

    try:
        results = search_files(
            args.directory,
            args.filename,
            args.case_sensitive,
            args.wildcard
        )

        if results:
            print(f"找到 {len(results)} 个匹配文件:")
            for path in results:
                print(f" - {path}")
        else:
            print("未找到匹配文件")
    except Exception as e:
        print(f"发生错误: {str(e)}")
