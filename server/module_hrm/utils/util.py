import ast
import base64
import copy
import csv
import gzip
import importlib
import itertools
import json
import os
import platform
import re
import socket
import sys
import zlib
from datetime import datetime
from itertools import combinations

import psutil

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm import exceptions
from utils.log_util import logger


def obj_to_dict(data):
    new_data = {}
    _to_dict(data, new_data)
    return new_data


def _to_dict(datas, new_dict={}):
    print(datas)
    try:
        if isinstance(datas, (list, tuple)):
            data_li = []
            new_dict = data_li
            for data in datas:
                tmp_dict = {}
                data_li.append(tmp_dict)
                _to_dict(data, tmp_dict)
        elif isinstance(datas, dict):
            new_dict = datas
        else:
            for k in dir(datas):
                if k.startswith("_"):
                    continue
                print(k)
                if k not in ["objects"] and hasattr(getattr(datas, k), "__dict__") and not callable(getattr(datas, k)):
                    tmp_data = {}
                    new_dict[k] = tmp_data
                    _to_dict(getattr(datas, k), tmp_data)
                else:
                    new_dict[k] = getattr(datas, k)
    except:
        pass


def ensure_validate_v4(vali):
    """
    将断言转换成v4的格式
    """
    # 将自定义断言跟自带断言放一起
    old_vali = copy.deepcopy(vali)
    all_valis = []
    for cvli in old_vali:
        if "valicustom" in cvli.keys():
            cvlis = cvli["valicustom"]
            for cv in cvlis:
                expected_str: str = cv["expected"]
                if expected_str.startswith('$'):
                    cv["expected"] = expected_str
                else:
                    try:
                        expected = eval(expected_str)
                        cv["expected"] = json.dumps([[expect[0], expect[1]] for expect in expected], ensure_ascii=False)
                    except:
                        cv["expected"] = expected_str

                all_valis.append(cv)
            # all_valis.extend(cvli["valicustom"])
        else:
            all_valis.append(cvli)

    # 转换保存的老样式的数据，沿用老的保存逻辑，如果后面修改了保存逻辑，这里也需要修改
    # 将组装后的所有断言格式转换成4的格式
    all_new_valis = []
    for index, va in enumerate(all_valis):
        new_va = {}
        new_va["check"] = va["check"]
        new_va["assert"] = va["comparator"]
        new_va["expect"] = va["expected"]
        new_va["msg"] = ""
        all_new_valis.append(new_va)
    return all_new_valis


def replace_variables(text: str, variables: dict, is_func=False):
    """
    使用正则替换字符串中的变量为对应的值
    @param text: 含有变量的原始字符串
    @param variables: 包含所有变量和值的字典
    @param is_func:False处理变量，True处理函数
    @return:
    """
    if is_func:
        pattern = r'\$\{([a-zA-Z_]\w*)\(([\$\w\.\-/\s=,]*)\)\}'  # 匹配 ${variable} 或 $variable
    else:
        pattern = r'\$\{([^}^{^\$]\w+)\}|\$([a-zA-Z_]\w*)'  # 匹配 ${variable} 或 $variable

    def replace(match):
        variable_name = match.group(1) or match.group(2)
        variable_value = variables.get(variable_name)
        if variable_value is not None:
            return variable_value
            # return replace_variables(variable_value, variables)  # 递归替换嵌套变量
        else:
            return match.group(0)  # 找不到对应变量时返回原始字符串

    # result = re.sub(pattern, replace, text)
    result = text
    while True:
        result_tmp = re.sub(pattern, replace, result)

        if result_tmp == result:
            return result

        result = result_tmp
        if not re.findall(pattern, result):
            break
    return result


def ensure_str(text) -> str:
    if isinstance(text, bytes):
        return text.decode('utf8')
    if isinstance(text, str):
        return text
    if isinstance(text, (dict, list)):
        return json.dumps(text, ensure_ascii=False, indent=4)


def compress_text(text: str) -> str:
    """
    压缩文本内容
    """
    logger.info(f"压缩前大小：{len(text)}")
    # logger.debug(f"压缩前数据：{text}")
    # 压缩文本
    compressed_data = gzip.compress(text.encode('utf-8'))
    # logger.debug(f"解压后的数据：{gzip.decompress(compressed_data).decode('utf8')}")
    # logger.info(compressed_data)
    # 使用 base64 编码
    encoded_data = base64.b64encode(compressed_data).decode('utf8')
    # logger.info(f"编码后的数据：{encoded_data}")
    logger.info(f"压缩后大小：{len(encoded_data)}")
    return encoded_data


def decompress_text(encoded_data: str) -> str:
    """
    被压缩后再经过base64编码的数据，先base64解码再解压
    """

    decode_data = base64.b64decode(encoded_data.encode("utf-8"))
    if decode_data.startswith(b'x\x9c'):
        decompress_text = zlib.decompress(decode_data).decode("utf8")
    elif decode_data.startswith(b'x\x1f') or decode_data.startswith(b'\x1f\x8b'):
        decompress_text = gzip.decompress(decode_data).decode("utf-8")
    else:
        raise TypeError("解压失败")
    # decompress_text = gzip.decompress(decode_data).decode("utf-8")
    return decompress_text


def get_custom_func(module_name):
    custom_module = importlib.import_module('')


def un_import(module_name):
    module_name = "mymodule"
    if module_name in sys.modules:
        del sys.modules[module_name]


def get_func_names(module_obj: object) -> list:
    try:
        all_func_name = module_obj.__all__
    except AttributeError:
        all_func_name = [name for name in dir(module_obj) if not name.startswith('_')]
    return all_func_name


def get_func_map(module_obj: object) -> dict:
    # all_func_name = module_obj.__dict__.keys()
    func_map = {}
    all_func_name = get_func_names(module_obj)

    for func_name in all_func_name:
        func_map[func_name] = getattr(module_obj, func_name)
    return func_map


def get_func_doc_map(module_obj: object, filter=None) -> dict:
    """
    从对象中获取包含的方法名及方法的注释
    :param module_obj:
    :param filter: 过滤函数，返回true/false
    :return:
    """
    func_map = {}
    all_func_name = get_func_names(module_obj)
    for func_name in all_func_name:
        filter_result = True
        if filter:
            filter_result = filter(func_name)
        if not filter_result:
            continue
        get_obj = getattr(module_obj, func_name)
        func_map[func_name] = get_obj.__doc__
    return func_map


def find_source_repeat(sources: list) -> list:
    """
    查找给定的两两列表中是否存在相同的元素并返回有重复的元素
    """
    all_symbols = []
    for source in sources:
        all_symbols.append(get_defined_symbols(source))

    duplicate_values = []
    for list_a, list_b in combinations(all_symbols, 2):
        duplicates = set(list_a) & set(list_b)
        duplicate_values.extend(duplicates)
    return duplicate_values


def get_defined_symbols(source: str) -> set:
    """
    找出python源码中所有的方法和类
    """
    tree = ast.parse(source)

    symbols = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            symbols.add(node.name)
        elif isinstance(node, ast.ClassDef):
            symbols.add(node.name)

    return symbols


def get_platform() -> dict:
    return {
        "python_version": "{} {}".format(
            platform.python_implementation(),
            platform.python_version()
        ),
        "platform": platform.platform(),
    }


def get_os_environ(variable_name) -> str:
    """get value of environment variable.

    Args:
        variable_name(str): variable name

    Returns:
        value of environment variable.

    Raises:
        exceptions.EnvNotFound: If environment variable not found.

    """
    try:
        return os.environ[variable_name]
    except KeyError:
        raise exceptions.EnvNotFound(variable_name)


def gen_cartesian_product(*args: list[dict]) -> list[dict]:
    """generate cartesian product for lists

    Args:
        args (list of list): lists to be generated with cartesian product

    Returns:
        list: cartesian product in list

    Examples:

        >>> arg1 = [{"a": 1}, {"a": 2}]
        >>> arg2 = [{"x": 111, "y": 112}, {"x": 121, "y": 122}]
        >>> args = [arg1, arg2]
        >>> gen_cartesian_product(*args)
        >>> # same as below
        >>> gen_cartesian_product(arg1, arg2)
            [
                {'a': 1, 'x': 111, 'y': 112},
                {'a': 1, 'x': 121, 'y': 122},
                {'a': 2, 'x': 111, 'y': 112},
                {'a': 2, 'x': 121, 'y': 122}
            ]

    """
    if not args:
        return []
    elif len(args) == 1:
        return args[0]

    product_list = []
    for product_item_tuple in itertools.product(*args):
        product_item_dict = {}
        for item in product_item_tuple:
            product_item_dict.update(item)

        product_list.append(product_item_dict)

    return product_list


def load_csv_file(csv_file) -> list[dict]:
    """load csv file and check file content format

    Args:
        csv_file (str): csv file path, csv file content is like below:

    Returns:
        list: list of parameters, each parameter is in dict format

    Examples:
        >>> cat csv_file
        username,password
        test1,111111
        test2,222222
        test3,333333

        >>> load_csv_file(csv_file)
        [
            {'username': 'test1', 'password': '111111'},
            {'username': 'test2', 'password': '222222'},
            {'username': 'test3', 'password': '333333'}
        ]

    """

    if not os.path.isfile(csv_file):
        # file path not exist
        raise exceptions.CSVNotFound(csv_file)

    csv_content_list = []

    with open(csv_file, encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            csv_content_list.append(row)

    return csv_content_list


def load_csv_file_to_test(keys, path):
    keys = keys.split('-')

    if not os.path.isfile(path):
        raise exceptions.CSVNotFound(path)
    csv_content_list = []

    with open(path, encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=keys)
        for row in reader:
            csv_content_list.append(row)
        # reader = csv.reader(csvfile)
        # for index, row in enumerate(reader):
        #     row_data = {}
        #     if len(row) < len(keys):
        #         raise TypeError(f"csv列数与变量{keys}不匹配")
        #     if index == 0:
        #         row[-1] =
        #     csv_content_list.append(row)

    return csv_content_list


def get_local_ip():
    local_ip = ""
    try:
        socket_objs = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]
        ip_from_ip_port = [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in socket_objs][0][1]
        ip_from_host_name = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if
                             not ip.startswith("127.")][:1]
        local_ip = [l for l in (ip_from_ip_port, ip_from_host_name) if l][0]
    except (Exception) as e:
        print("get_local_ip found exception : %s" % e)
    return local_ip if ("" != local_ip and None != local_ip) else socket.gethostbyname(socket.gethostname())


class PermissionHandler(object):
    """
    权限处理器
    """
    @classmethod
    def check_is_self(cls, user: CurrentUserModel, data):
        manager = getattr(data, "manager", None)

        if user and user.user.user_id and (not user.user.admin) and manager and user.user.user_id != manager:
            raise PermissionError("只能处理自己的数据")


def get_system_stats():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    stats = {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used": memory.used / (1024 ** 2),  # MB
        "memory_total": memory.total / (1024 ** 2),  # MB
        "disk_percent": disk.percent,
        "disk_used": disk.used / (1024 ** 3),  # GB
        "disk_total": disk.total / (1024 ** 3),  # GB
        "timestamp": datetime.now().isoformat(),
    }
    logger.info(f"系统状态信息: {stats}")
    return stats