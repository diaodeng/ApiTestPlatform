import ast
import base64
import io
import json
import os
import re
from functools import lru_cache
from io import BytesIO
from typing import Any

from loguru import logger
from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.engine.row import Row

from config.database import Base
from config.env import CachePathConfig


def worship():
    logger.info("""
////////////////////////////////////////////////////////////////////
//                          _ooOoo_                               //
//                         o8888888o                              //
//                         88" . "88                              //
//                         (| ^_^ |)                              //
//                         O\  =  /O                              //
//                      ____/`---'\____                           //
//                    .'  \\|     |//  `.                         //
//                   /  \\|||  :  |||//  \                        //
//                  /  _||||| -:- |||||-  \                       //
//                  |   | \\\  -  /// |   |                       //
//                  | \_|  ''\---/''  |   |                       //
//                  \  .-\__  `-`  ___/-. /                       //
//                ___`. .'  /--.--\  `. . ___                     //
//              ."" '<  `.___\_<|>_/___.'  >'"".                  //
//            | | :  `- \`.;`\ _ /`;.`/ - ` : | |                 //
//            \  \ `-.   \_ __\ /__ _/   .-` /  /                 //
//      ========`-.____`-.___\_____/___.-`____.-'========         //
//                           `=---='                              //
//      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^        //
//             佛祖保佑       永不宕机      永无BUG                  //
////////////////////////////////////////////////////////////////////
    """)


class CamelCaseUtil:
    """
    小驼峰形式(camelCase)与下划线形式(snake_case)互相转换工具方法
    """
    @classmethod
    def camel_to_snake(cls, camel_str):
        """
        小驼峰形式字符串(camelCase)转换为下划线形式字符串(snake_case)
        :param camel_str: 小驼峰形式字符串
        :return: 下划线形式字符串
        """
        # 在大写字母前添加一个下划线，然后将整个字符串转为小写
        words = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', words).lower()

    @classmethod
    def snake_to_camel(cls, snake_str):
        """
        下划线形式字符串(snake_case)转换为小驼峰形式字符串(camelCase)
        :param snake_str: 下划线形式字符串
        :return: 小驼峰形式字符串
        """
        # 分割字符串
        words = snake_str.split('_')
        # 小驼峰命名，第一个词首字母小写，其余词首字母大写
        return words[0] + ''.join(word.capitalize() for word in words[1:])

    @classmethod
    def transform_result(cls, result):
        """
        针对不同类型将下划线形式(snake_case)批量转换为小驼峰形式(camelCase)方法
        :param result: 输入数据
        :return: 小驼峰形式结果
        """
        if result is None:
            return result
        # 如果是字典，直接转换键
        elif isinstance(result, dict):
            return {cls.snake_to_camel(k): v for k, v in result.items()}
        # 如果是一组字典或其他类型的列表，遍历列表进行转换
        elif isinstance(result, list):
            return [cls.transform_result(row) if isinstance(row, (dict, Row)) else (cls.transform_result({c.name: getattr(row, c.name) for c in row.__table__.columns}) if row else row) for row in result]
        # 如果是sqlalchemy的Row实例，遍历Row进行转换
        elif isinstance(result, Row):
            data_dict_old = result._asdict()
            data_list = []
            for key, value in data_dict_old.items():
                if isinstance(value, Base):
                    data_list.append(
                        cls.transform_result({c.name: getattr(value, c.name) for c in value.__table__.columns}))
                else:
                    data_list.append({cls.snake_to_camel(key): value})
            return data_list
            # return [cls.transform_result(row) if isinstance(row, dict) else (cls.transform_result({c.name: getattr(row, c.name) for c in row.__table__.columns}) if row else row) for row in result]
        # 如果是其他类型，如模型实例，先转换为字典
        else:
            return cls.transform_result({c.name: getattr(result, c.name) for c in result.__table__.columns})


def bytes2human(n, format_str="%(value).1f%(symbol)s"):
    """Used by various scripts. See:
    http://goo.gl/zeJZl

    >>> bytes2human(10000)
    '9.8K'
    >>> bytes2human(100001221)
    '95.4M'
    """
    symbols = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i + 1) * 10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format_str % locals()
    return format_str % {'symbol': symbols[0], 'value': n}


def bytes2file_response(bytes_info):
    yield bytes_info


def export_list2excel(list_data: list):
    """
    工具方法：将需要导出的list数据转化为对应excel的二进制数据
    :param list_data: 数据列表
    :return: 字典信息对应excel的二进制数据
    """
    if not list_data:
        return b""

    wb = Workbook()
    ws = wb.active

    # 表头 = dict key
    headers = list(list_data[0].keys())
    ws.append(headers)

    # 数据行
    for row in list_data:
        ws.append([row.get(h) for h in headers])

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()

    # df = pd.DataFrame(list_data)
    # binary_data = io.BytesIO()
    # df.to_excel(binary_data, index=False, engine='openpyxl')
    # binary_data = binary_data.getvalue()
    #
    # return binary_data


def load_excel2data():
    pass


def get_excel_template(header_list: list, selector_header_list: list, option_list: list[dict]):
    """
    工具方法：将需要导出的list数据转化为对应excel的二进制数据
    :param header_list: 表头数据列表
    :param selector_header_list: 需要设置为选择器格式的表头数据列表
    :param option_list: 选择器格式的表头预设的选项列表
    :return: 模板excel的二进制数据
    """
    # 创建Excel工作簿
    wb = Workbook()
    # 选择默认的活动工作表
    ws = wb.active

    # 设置表头文字
    headers = header_list

    # 设置表头背景样式为灰色，前景色为白色
    header_fill = PatternFill(start_color="ababab", end_color="ababab", fill_type="solid")

    # 将表头写入第一行
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        # 设置列宽度为16
        ws.column_dimensions[chr(64 + col_num)].width = 12
        # 设置水平居中对齐
        cell.alignment = Alignment(horizontal='center')

    # 设置选择器的预设选项
    options = option_list

    # 获取selector_header的字母索引
    for selector_header in selector_header_list:
        column_selector_header_index = headers.index(selector_header) + 1

        # 创建数据有效性规则
        header_option = []
        for option in options:
            if option.get(selector_header):
                header_option = option.get(selector_header)
        dv = DataValidation(type="list", formula1=f'"{",".join(header_option)}"')
        # 设置数据有效性规则的起始单元格和结束单元格
        dv.add(
            f'{get_column_letter(column_selector_header_index)}2:{get_column_letter(column_selector_header_index)}1048576')
        # 添加数据有效性规则到工作表
        ws.add_data_validation(dv)

    # 保存Excel文件为字节类型的数据
    file = io.BytesIO()
    wb.save(file)
    file.seek(0)

    # 读取字节数据
    excel_data = file.getvalue()

    return excel_data


def get_filepath_from_url(url: str):
    """
    工具方法：根据请求参数获取文件路径
    :param url: 请求参数中的url参数
    :return: 文件路径
    """
    file_info = url.split("?")[1].split("&")
    task_id = file_info[0].split("=")[1]
    file_name = file_info[1].split("=")[1]
    task_path = file_info[2].split("=")[1]
    filepath = os.path.join(CachePathConfig.PATH, task_path, task_id, file_name)

    return filepath


class WhitelistJsonParser:
    __slots__ = ("_cache", "_whitelist")

    def __init__(self, whitelist: set[str] = None):
        self._cache = set()
        self._whitelist = whitelist

    # ---------- 内部工具 ----------

    @staticmethod
    def _fast_json_candidate(s: str) -> bool:
        if not s:
            return False

        s = s.strip()
        if len(s) < 2:
            return False

        if (s[0], s[-1]) not in {("{", "}"), ("[", "]")}:
            return False

        # 半截 JSON 快速排除
        if s.count("{") != s.count("}") or s.count("[") != s.count("]"):
            return False

        # 引号数量异常
        if s.count('"') % 2 != 0:
            return False

        return True

    @staticmethod
    def _safe_load(s: str):
        try:
            val = json.loads(s)
            if isinstance(val, (dict, list)):
                return val
        except Exception:
            pass
        return s

    # ---------- 主逻辑 ----------

    def parse(self, obj: Any):
        oid = id(obj)
        if oid in self._cache:
            return obj
        self._cache.add(oid)

        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and (not self._whitelist or k in self._whitelist):
                    if self._fast_json_candidate(v):
                        parsed = self._safe_load(v)
                        if parsed is not v:
                            obj[k] = self.parse(parsed)
                            continue
                obj[k] = self.parse(v)
            return obj

        if isinstance(obj, list):
            for i in range(len(obj)):
                obj[i] = self.parse(obj[i])
            return obj

        return obj


class SmartJsonParser:
    """智能 JSON 解析器，可以处理各种异常格式的 JSON"""

    @staticmethod
    def fix_json_string(json_str: str) -> str:
        """修复 JSON 字符串中的常见问题"""
        if not json_str:
            return json_str

        # 移除 BOM 标记（如果有）
        if json_str.startswith('\ufeff'):
            json_str = json_str[1:]

        # 移除尾部的逗号（对象或数组中的最后一个逗号）
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

        # 修复单引号字符串（将单引号转为双引号，但要避开转义的单引号）
        # 先处理最外层的单引号
        json_str = SmartJsonParser._fix_single_quotes_safe(json_str)

        # 修复没有引号的键（只修复简单的键）
        # 匹配 { key: value } 中的 key
        json_str = re.sub(r'{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', lambda m: f'{{"{m.group(1)}":', json_str)

        # 修复布尔值和null值（JavaScript风格）
        json_str = re.sub(r':\s*true\b', ': true', json_str)
        json_str = re.sub(r':\s*false\b', ': false', json_str)
        json_str = re.sub(r':\s*null\b', ': null', json_str)

        return json_str

    @staticmethod
    def _fix_single_quotes_safe(json_str: str) -> str:
        """安全地修复单引号字符串"""
        if not json_str:
            return json_str

        # 方法1: 使用状态机方法
        result = []
        in_single_quote = False
        in_double_quote = False
        escape_next = False
        i = 0

        while i < len(json_str):
            char = json_str[i]

            # 处理转义字符
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue

            if char == '\\':
                escape_next = True
                result.append(char)
                i += 1
                continue

            # 处理引号
            if char == "'" and not in_double_quote:
                if in_single_quote:
                    # 结束单引号字符串
                    in_single_quote = False
                    result.append('"')
                else:
                    # 开始单引号字符串
                    in_single_quote = True
                    result.append('"')
            elif char == '"' and not in_single_quote:
                if in_double_quote:
                    in_double_quote = False
                else:
                    in_double_quote = True
                result.append('"')
            else:
                # 处理单引号字符串内的双引号
                if in_single_quote and char == '"':
                    result.append('\\"')
                else:
                    result.append(char)

            i += 1

        return ''.join(result)

    @staticmethod
    def _fix_single_quotes_with_regex(json_str: str) -> str:
        """使用正则表达式修复单引号字符串（备选方法）"""
        if not json_str:
            return json_str

        # 方法2: 使用递归的正则表达式处理
        # 注意：这个方法可能不完美，但可以处理大部分情况

        def convert_single_quotes(text: str) -> str:
            """将单引号字符串转换为双引号字符串"""
            # 查找所有单引号字符串
            pattern = r"'([^'\\]*(?:\\.[^'\\]*)*)'"

            def replace_match(match):
                content = match.group(1)
                # 修复内容中的转义
                content = SmartJsonParser._fix_string_content(content)
                return f'"{content}"'

            return re.sub(pattern, replace_match, text)

        # 多次处理，处理嵌套的单引号
        max_iterations = 3
        for _ in range(max_iterations):
            new_str = convert_single_quotes(json_str)
            if new_str == json_str:
                break
            json_str = new_str

        return json_str

    @staticmethod
    def _fix_string_content(content: str) -> str:
        """修复字符串内容中的转义字符"""
        if not content:
            return content

        # 处理转义字符
        # 1. 将已经转义的双引号（\"）替换为临时标记
        content = content.replace(r'\"', '\x01')
        # 2. 将转义的单引号（\'）替换为普通单引号
        content = content.replace(r"\'", "'")
        # 3. 将转义的反斜杠（\\）替换为普通反斜杠
        content = content.replace(r'\\', '\x02')
        # 4. 将普通双引号转义
        content = content.replace('"', r'\"')
        # 5. 恢复临时标记
        content = content.replace('\x01', '"')
        content = content.replace('\x02', '\\')

        return content

    @staticmethod
    def fix_escapes(json_str: str) -> str:
        """修复转义字符问题"""
        if not json_str:
            return json_str

        result = []
        i = 0
        while i < len(json_str):
            if json_str[i] == '\\':
                # 统计连续反斜杠的数量
                slash_count = 1
                j = i + 1
                while j < len(json_str) and json_str[j] == '\\':
                    slash_count += 1
                    j += 1

                # 根据后续字符决定如何修复
                if j < len(json_str):
                    next_char = json_str[j]
                    # 如果是转义字符
                    if next_char in '"\\/bfnrtu':
                        # 对于双引号，保留一个反斜杠
                        if next_char == '"':
                            if slash_count % 2 == 1:
                                # 奇数个反斜杠，最后一个用于转义双引号
                                result.append('\\' * ((slash_count - 1) // 2) + '\\"')
                            else:
                                # 偶数个反斜杠，一半用于转义，一半是字面反斜杠
                                result.append('\\' * (slash_count // 2) + '"')
                        # 对于其他转义字符，保留一个反斜杠
                        else:
                            if slash_count % 2 == 1:
                                result.append('\\' * ((slash_count - 1) // 2) + '\\' + next_char)
                            else:
                                result.append('\\' * (slash_count // 2) + next_char)
                        i = j + 1
                    else:
                        # 不是转义字符，只保留一半的反斜杠
                        result.append('\\' * (slash_count // 2))
                        i = j
                else:
                    # 字符串以反斜杠结尾，只保留一半
                    result.append('\\' * (slash_count // 2))
                    i = j
            else:
                result.append(json_str[i])
                i += 1

        return ''.join(result)

    @staticmethod
    @lru_cache(maxsize=128)
    def fix_escapes_new(json_str: str) -> str:
        """
        修复JSON字符串中的转义问题
        处理多层转义：\\\\" -> \\" -> \"
        """
        if not json_str:
            return json_str

        # 记录初始状态用于调试
        original = json_str

        # 方法1: 递归处理多层转义
        def process_escapes(s: str) -> str:
            # 先处理四个反斜杠的情况
            while '\\\\\\\\' in s:
                s = s.replace('\\\\\\\\', '\\\\')

            # 再处理两个反斜杠加双引号的情况
            while '\\\\"' in s:
                s = s.replace('\\\\"', '\\"')

            # 处理转义的单引号
            s = s.replace("\\'", "'")

            # 处理转义的反斜杠（将 \\ 替换为 \）
            while r'\\' in s:
                s = s.replace(r'\\', '\\')

            return s

        # 多次处理以确保完全修复
        max_iterations = 5
        for i in range(max_iterations):
            new_str = process_escapes(json_str)
            if new_str == json_str:
                break
            json_str = new_str

        # 检查修复效果
        backslash_count_original = original.count('\\')
        backslash_count_fixed = json_str.count('\\')
        if backslash_count_original != backslash_count_fixed:
            logger.info(f"修复转义: 反斜杠数量从 {backslash_count_original} 减少到 {backslash_count_fixed}")

        return json_str

    @staticmethod
    def extract_json_substring(json_str: str) -> str:
        """尝试提取有效的 JSON 子串"""
        if not json_str:
            return ""

        # 尝试找到最长的有效 JSON 前缀
        for i in range(len(json_str), 0, -1):
            substring = json_str[:i]
            try:
                # 尝试解析
                json.loads(substring)
                return substring
            except:
                continue

        # 如果找不到完整的 JSON，尝试提取第一个有效的 JSON 对象/数组
        # 查找第一个 { 或 [
        start_idx = -1
        for i, char in enumerate(json_str):
            if char in '{[':
                start_idx = i
                break

        if start_idx == -1:
            return ""

        # 尝试匹配大括号或中括号
        stack = []
        end_idx = -1

        for i in range(start_idx, len(json_str)):
            char = json_str[i]
            if char == '{' or char == '[':
                stack.append(char)
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                else:
                    break
            elif char == ']':
                if stack and stack[-1] == '[':
                    stack.pop()
                else:
                    break

            if not stack:
                end_idx = i + 1
                break

        if end_idx > start_idx:
            return json_str[start_idx:end_idx]

        return ""

    @staticmethod
    def parse_with_ast(py_str: str) -> Any:
        """使用 Python 的 ast 模块解析 Python 字面量"""
        try:
            # 使用 ast.literal_eval 安全地解析 Python 字面量
            return ast.literal_eval(py_str)
        except (SyntaxError, ValueError, TypeError):
            return None

    @staticmethod
    def try_repair_json(json_str: str) -> str:
        """尝试修复 JSON 字符串"""
        if not json_str:
            return json_str

        repaired = json_str

        # 修复步骤1：处理转义字符
        repaired = SmartJsonParser.fix_escapes(repaired)

        # 修复步骤2：修复 JSON 格式问题
        repaired = SmartJsonParser.fix_json_string(repaired)

        # 修复步骤3：确保最外层是对象或数组
        repaired = repaired.strip()
        if not repaired.startswith(('{', '[')):
            # 尝试包装成对象
            repaired = f'{{"data": {repaired}}}'

        return repaired

    @classmethod
    def smart_parse(cls, json_str: str, max_attempts: int = 5) -> Any:
        """
        智能解析 JSON 字符串

        Args:
            json_str: 要解析的字符串
            max_attempts: 最大尝试次数

        Returns:
            解析后的对象，如果解析失败返回原始字符串
        """
        if not json_str:
            return json_str

        # try:
        #     return json.loads(json_str)
        # except json.JSONDecodeError:
        #     pass

        attempts = [
            cls._attempt_standard_parse,
            cls._attempt_fix_and_parse,
            cls._attempt_extract_and_parse,
            cls._attempt_python_parse,
            cls._attempt_partial_parse
        ]

        for i, attempt_func in enumerate(attempts[:max_attempts]):
            try:
                result = attempt_func(json_str)
                if result is not None:
                    logger.info(f"✓ 使用第 {i + 1} 种方法解析成功")
                    return result
            except Exception:
                continue

        logger.info("✗ 所有解析方法都失败了")
        return json_str

    @staticmethod
    def _attempt_standard_parse(json_str: str) -> Any:
        """尝试标准 JSON 解析"""
        return json.loads(json_str)

    @staticmethod
    def _attempt_fix_and_parse(json_str: str) -> Any:
        """尝试修复后解析"""
        repaired = SmartJsonParser.try_repair_json(json_str)
        return json.loads(repaired)

    @staticmethod
    def _attempt_extract_and_parse(json_str: str) -> Any:
        """尝试提取有效 JSON 后解析"""
        extracted = SmartJsonParser.extract_json_substring(json_str)
        if extracted:
            # 递归尝试解析提取的部分
            return SmartJsonParser.smart_parse(extracted, max_attempts=3)
        return None

    @staticmethod
    def _attempt_python_parse(json_str: str) -> Any:
        """尝试使用 Python 字面量解析"""
        return SmartJsonParser.parse_with_ast(json_str)

    @staticmethod
    def _attempt_partial_parse(json_str: str) -> Any:
        """
        部分解析JSON（使用正则表达式）
        当JSON不完整时尝试提取尽可能多的键值对
        """
        if not json_str:
            return {}

        result = {}

        # 简单模式：提取 key: value 对
        # 支持多种格式：'key': value, "key": value, key: value
        patterns = [
            # 双引号键
            r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*:\s*(?:"([^"\\]*(?:\\.[^"\\]*)*)"|(\d+\.?\d*|true|false|null))',
            # 单引号键
            r"'([^'\\]*(?:\\.[^'\\]*)*)'\s*:\s*(?:'([^'\\]*(?:\\.[^'\\]*)*)'|(\d+\.?\d*|true|false|null))",
            # 无引号键（只包含字母数字和下划线）
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'|(\d+\.?\d*|true|false|null))',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, json_str, re.DOTALL)
            for match in matches:
                # 根据模式提取键和值
                if pattern.startswith('"'):
                    key = match[0]
                    str_val = match[1]
                    other_val = match[2]
                elif pattern.startswith("'"):
                    key = match[0]
                    str_val = match[1]
                    other_val = match[2]
                else:
                    key = match[0]
                    str_val = match[1] or match[2]
                    other_val = match[3]

                # 修复键中的转义
                key = key.replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')

                # 处理值
                if str_val:
                    value = str_val.replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')
                elif other_val:
                    if other_val.lower() == 'true':
                        value = True
                    elif other_val.lower() == 'false':
                        value = False
                    elif other_val.lower() == 'null':
                        value = None
                    elif '.' in other_val:
                        try:
                            value = float(other_val)
                        except ValueError:
                            value = other_val
                    else:
                        try:
                            value = int(other_val)
                        except ValueError:
                            value = other_val
                else:
                    value = None

                # 添加到结果
                if key not in result:
                    result[key] = value

        return result if result else json_str

    @classmethod
    def parse_nested_json_strings(cls, obj: Any) -> Any:
        """递归解析嵌套的 JSON 字符串"""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                result[key] = cls.parse_nested_json_strings(value)
            return result
        elif isinstance(obj, list):
            return [cls.parse_nested_json_strings(item) for item in obj]
        elif isinstance(obj, str):
            # 如果字符串看起来像 JSON，尝试解析
            obj_stripped = obj.strip()
            if (obj_stripped.startswith('{') and obj_stripped.endswith('}')) or \
                    (obj_stripped.startswith('[') and obj_stripped.endswith(']')):
                try:
                    parsed = cls.smart_parse(obj)
                    if parsed != obj:  # 如果解析成功且结果不同
                        return cls.parse_nested_json_strings(parsed)
                except:
                    pass
        return obj


# 使用示例
def test_smart_parser():
    """测试智能解析器"""

    # 测试用例
    test_cases = [
        # 1. 标准 JSON
        ('{"name": "John", "age": 30}', '标准 JSON'),

        # 2. 单引号 JSON
        ("{'name': 'John', 'age': 30}", '单引号 JSON'),

        # 3. 多余的转义符
        ('{\\"name\\": \\"John\\", \\"age\\": 30}', '多余转义符'),

        # 4. 更多转义符
        ('{\\\\"name\\\\": \\\\\\"John\\\\\\", \\\\\\"age\\\\\\": 30}', '更多转义符'),

        # 5. 不完整的 JSON
        ('{"name": "John", "age": 30, "hobbies": ["reading", "swimming"', '不完整 JSON'),

        # 6. 混合单双引号
        ("{'name': \"John\", 'age': 30}", '混合引号'),

        # 7. 没有引号的键
        ('{name: "John", age: 30}', '无引号键'),

        # 8. Python 字典
        ("{'name': 'John', 'data': {'nested': 'value'}}", 'Python 字典'),

        # 9. 尾部逗号
        ('{"name": "John", "age": 30,}', '尾部逗号'),

        # 10. 包含转义字符的值
        ('{"path": "C:\\\\Users\\\\John\\\\file.txt"}', '包含转义字符'),
    ]

    parser = SmartJsonParser()

    for test_str, description in test_cases:
        logger.info(f"\n{'=' * 50}")
        logger.info(f"测试: {description}")
        logger.info(f"输入: {test_str[:50]}...")

        try:
            result = parser.smart_parse(test_str)
            logger.info(f"结果类型: {type(result)}")
            logger.info(f"结果: {result}")
        except Exception as e:
            logger.info(f"解析失败: {e}")


# 更强大的版本：包含自动检测和修复
class AdvancedJsonParser(SmartJsonParser):
    """高级 JSON 解析器，包含更多自动检测功能"""

    @staticmethod
    def detect_and_fix(json_str: str) -> str:
        """检测并修复 JSON 字符串"""
        if not json_str:
            return json_str

        # 1. 检测编码问题
        # 尝试不同的编码
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        for encoding in encodings:
            try:
                json_str.encode(encoding).decode('utf-8')
                break
            except:
                pass

        # 2. 检测是否是 base64（自动解码）
        if len(json_str) % 4 == 0 and re.match(r'^[A-Za-z0-9+/]*={0,2}$', json_str):
            try:
                decoded = base64.b64decode(json_str).decode('utf-8')
                logger.info("检测到 base64 编码，已自动解码")
                json_str = decoded
            except:  # noqa: E722
                pass

        # 3. 移除不可见字符
        json_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', json_str)

        # 4. 修复常见的 JSON 问题
        # 修复注释（移除 // 和 /* */ 注释）
        json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

        # 修复 JavaScript 风格的函数
        json_str = re.sub(r':\s*function\s*\([^)]*\)\s*\{[^}]*\}', ': null', json_str)

        # 5. 尝试平衡括号
        stack = []
        result = []

        i = 0
        while i < len(json_str):
            char = json_str[i]

            if char in '{[':
                stack.append(char)
                result.append(char)
            elif char in '}]':
                if stack:
                    stack.pop()
                result.append(char)
            else:
                result.append(char)

            i += 1

        # 如果栈不为空，添加缺失的括号
        while stack:
            missing = '}' if stack[-1] == '{' else ']'
            result.append(missing)
            stack.pop()

        return ''.join(result)

    @classmethod
    def advanced_parse(cls, json_str: str) -> Any:
        """高级解析方法"""
        if not json_str:
            return json_str

        # 先进行检测和修复
        fixed_str = cls.detect_and_fix(json_str)

        # 然后使用智能解析
        return cls.smart_parse(fixed_str)


# 专门处理您遇到的多层转义问题
class MultiEscapeJsonParser:
    """专门处理多层转义JSON的解析器"""

    @staticmethod
    def normalize_escapes(json_str: str) -> str:
        """
        标准化转义字符
        将多层转义减少到正确的一层
        """
        if not json_str:
            return json_str

        # 使用有限状态机处理转义
        result = []
        i = 0
        n = len(json_str)

        while i < n:
            char = json_str[i]

            # 统计连续反斜杠的数量
            if char == '\\':
                slash_count = 1
                j = i + 1
                while j < n and json_str[j] == '\\':
                    slash_count += 1
                    j += 1

                # 检查下一个字符
                if j < n:
                    next_char = json_str[j]
                    # 如果是需要转义的字符
                    if next_char in '"\\/bfnrtu':
                        # 对于双引号，保留一个反斜杠用于转义
                        if next_char == '"':
                            # 如果反斜杠数量是奇数，最后一个用于转义双引号
                            if slash_count % 2 == 1:
                                result.append('\\' * ((slash_count - 1) // 2))
                                result.append('\\"')
                            else:
                                # 偶数个反斜杠，一半用于转义反斜杠本身
                                result.append('\\' * (slash_count // 2))
                                result.append('"')
                        else:
                            # 其他转义字符，保留一个反斜杠
                            result.append('\\' * (slash_count // 2))
                            result.append('\\' + next_char)
                        i = j + 1
                    else:
                        # 不是转义字符，保留一半的反斜杠
                        result.append('\\' * (slash_count // 2))
                        i = j
                else:
                    # 字符串以反斜杠结尾
                    result.append('\\' * (slash_count // 2))
                    i = j
            else:
                result.append(char)
                i += 1

        return ''.join(result)

    @staticmethod
    def smart_decode(json_str: str) -> Any:
        """
        智能解码多层转义的JSON
        """
        if not json_str:
            return json_str

        # 方法1: 直接解析
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # 方法2: 标准化转义后解析
        normalized = MultiEscapeJsonParser.normalize_escapes(json_str)
        if normalized != json_str:
            try:
                return json.loads(normalized)
            except json.JSONDecodeError:
                pass

        # 方法3: 使用简化方法处理多层转义
        # 逐步减少转义层数
        max_iterations = 10
        current = json_str

        for iteration in range(max_iterations):
            # 尝试解析当前字符串
            try:
                return json.loads(current)
            except json.JSONDecodeError:
                pass

            # 减少转义层数
            new_str = current

            # 将四个反斜杠替换为两个
            new_str = new_str.replace('\\\\\\\\', '\\\\')

            # 将两个反斜杠加双引号替换为一个反斜杠加双引号
            new_str = new_str.replace('\\\\"', '\\"')

            # 如果没有变化，停止迭代
            if new_str == current:
                break

            current = new_str

        # 最后一次尝试
        try:
            return json.loads(current)
        except json.JSONDecodeError:
            return json_str


if __name__ == "__main__":
    # 运行测试
    test_smart_parser()