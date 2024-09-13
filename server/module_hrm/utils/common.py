import json
import os


def type_change(type, value):
    """
    数据类型转换
    :param type: str: 类型
    :param value: object: 待转换的值
    :return: ok or error
    """
    try:
        if type == 'float':
            value = float(value)
        elif type == 'int':
            value = int(value)
        elif type == "json":
            value = json.loads(value)
        elif type == 'boolean':
            if value == 'False':
                value = False
            elif value == 'True':
                value = True
            else:
                raise TypeError(f"类型【{type}】不支持")
    except ValueError:
        raise TypeError('{value}转换{type}失败'.format(value=value, type=type))

    return value


def key_value_list(keyword, cover_list: list):
    """
    [{"key": "key1", "value": "value1", "type": "sting"}，{"key": "key2", "value": "123", "type": "int"}] =>
    [{"key": "key1", "value": "value1"}，{"key": "key2", "value": 123}]
    [{"key": "key1", "value": "value1"}] => [{"key1": "value1"}]
    将列表中数据按指定类型转换，并转换成指定格式，比如校验器数据key转换
    dict change to list
    :param keyword: str: 关键字标识
    :param kwargs: dict: 待转换的字典
    :return: ok or tips
    """
    lists = []
    for value in cover_list:
        if keyword == 'setup_hooks':
            return cover_list
        elif keyword == 'teardown_hooks':
            return cover_list
        else:
            key = value.pop('key')
            val = value.pop('value')
            type = value.pop('type', "str")

            tips = '{keyword}: {val}格式错误,不是{type}类型'.format(keyword=keyword, val=val, type=type)
            if key != '':
                if keyword == 'validate':
                    value['check'] = key
                    msg = type_change(type, val)
                    if msg == 'exception':
                        return tips
                    value['expected'] = msg
                elif keyword == 'extract':
                    value[key] = val
                elif keyword == 'variables':
                    msg = type_change(type, val)
                    if msg == 'exception':
                        return tips
                    value[key] = msg
                elif keyword == 'parameters':
                    try:
                        if not isinstance(eval(val), list):
                            # 参数化支持变量形似，不是列表则原样表留，可能是变量，例如：${test}
                            value['value'] = val
                        else:
                            value['value'] = eval(val)

                        # return '{keyword}: {val}格式错误'.format(keyword=keyword, val=val)
                    except Exception as e:
                        value['value'] = val
                        # logging.error('{val}->eval 异常'.format(val=val))
                        # return '{keyword}: {val}格式错误'.format(keyword=keyword, val=val)
                    value['type'] = int(type)
                    value['key'] = key

            lists.append(value)
    return lists


def key_value_dict(cover_list: list[dict] | dict, ignore_type=False, checkEnable=True):
    """
    根据数据类型处理字典数据,如果参数cover_list不是列表则原样返回
    [{"key": "key1", "value": "value1", "type": "sting"}，{"key": "key2", "value": "value2", "type": "int"}] => {"key1": "value1", "key2": value2}
    [{"key": "key1", "value": "value1"}] => {"key1": "value1"}
    :param keyword: str: 是否忽略类型
    :param kwargs: dict: 原字典值
    :return: ok or tips
    """
    if not isinstance(cover_list, list):
        return cover_list
    dicts = {}
    for value in cover_list:
        if checkEnable and not value.get("enable", False): continue
        key = value.get('key')
        if not key:
            continue
        val = value.get('value')
        if not ignore_type:
            type = value.get("type", "str")
            val = type_change(type, val)

        dicts[key] = val
    return dicts


def dict2list(datas: dict, ignore_type=False):
    """
    {"key1": "value1", "key2": value2} => [{"key": "key1", "value": "value1", "type": "sting"}，{"key": "key2", "value": "value2", "type": "int"}]
    """
    new_data = []
    if isinstance(datas, list):return datas
    for key, value in datas.items():
        if ignore_type:
            data_type = "any"
        elif isinstance(value, (dict, list, tuple)):
            data_type = "json"
        elif isinstance(value, str):
            data_type = "string"
        elif isinstance(value, int):
            data_type = "int"
        elif isinstance(value, float):
            data_type = "float"
        elif isinstance(value, bool):
            data_type = "boolean"
        else:
            data_type = "string"
        new_data.append({"key": key, "value": value, "type": data_type, "enable": True})
    return new_data


def list_dict2list(datas: list[dict]):
    """
    [{"key1": "value1"}，{"key2": "vlaue2"}] => [{"key": "key1", "value": "value1", "type": "sting"}，{"key": "key2", "value": "value2", "type": "int"}]
    """
    new_dict = {}
    for data in datas:
        new_dict.update(data)
    new_data = dict2list(new_dict)
    return new_data


def update_or_extend_list(old_dict_list: list[dict],
                          new_dict_list: list[dict],
                          key: str = "key",
                          check_enable: bool = True):
    """
    更新列表中的字典
    """
    if not new_dict_list:
        return
    list1_dict = {d[key]: d for d in old_dict_list if d.get("key", None)}

    for item in new_dict_list:
        if check_enable and not item.get("enable", False): continue
        # 如果list2中的key在list1中存在，则更新list1中的字典
        if item[key] in list1_dict:
            list1_dict[item[key]].update(item)
        else:
            # 如果list1中没有该key，则将item添加到list1中
            old_dict_list.append(item)


def relative_path(path_str: str):
    """
    获取指定路径相对度项目路径的相对路径
    """
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    re_path = path_str
    if path_str.startswith(project_dir):
        re_path = re_path.replace(project_dir, "")

    if re_path.startswith("/"):
        re_path = re_path[1:]
    if re_path.startswith("\\"):
        re_path = re_path[2:]
    return re_path


def ensure_path(path_str: str):
    path_str = path_str.replace('\\', os.sep)
    path_str = path_str.replace("/", os.sep)
    return path_str
