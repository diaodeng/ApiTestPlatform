import os
import fnmatch
from typing import List
import argparse


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
