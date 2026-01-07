import os
import platform


def is_linux():
    return platform.system().lower() == "linux"


def is_windows():
    return platform.system().lower() == "windows"


def file_exists(path: str) -> bool:
    return os.path.exists(path)