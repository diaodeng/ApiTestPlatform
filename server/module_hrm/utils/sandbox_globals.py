import base64
import binascii
import bisect
import collections
import configparser
import csv
import datetime
import decimal
import difflib
import fractions
import functools
import hashlib
import heapq
import hmac
import ipaddress
import itertools
import json
import math
import operator
import os
import random
import re
import statistics
import string
import textwrap
import time
import uuid
from types import SimpleNamespace

import jmespath
from jsonpath import jsonpath

SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,

    "str": str,
    "int": int,
    "float": float,
    "bool": bool,

    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,

    "enumerate": enumerate,
    "zip": zip,

    "Exception": Exception,
    "ValueError": ValueError,
    "AssertionError": AssertionError,
}

SAFE_STD_MODULES = {
    # ===== 基础数据处理 =====
    "math": math,
    "decimal": decimal,
    "fractions": fractions,
    "statistics": statistics,

    # ===== 文本 / 解析 =====
    "re": re,
    "string": string,
    "textwrap": textwrap,
    "difflib": difflib,

    # ===== 时间（只读）=====
    "datetime": datetime,
    "time": time,  # ⚠️ 仅用于 time.time / sleep 可禁

    # ===== 编解码 =====
    "base64": base64,
    "binascii": binascii,
    "hashlib": hashlib,
    "hmac": hmac,

    # ===== 数据格式 =====
    "json": json,
    "csv": csv,
    "configparser": configparser,

    # ===== 集合 / 算法 =====
    "itertools": itertools,
    "functools": functools,
    "operator": operator,
    "collections": collections,
    "heapq": heapq,
    "bisect": bisect,

    # ===== 随机（非加密）=====
    "random": random,

    # ===== 校验 =====
    "uuid": uuid,
    "ipaddress": ipaddress,
}

SAFE_OS_PATH = SimpleNamespace(
    join=os.path.join,
    basename=os.path.basename,
    dirname=os.path.dirname,
    split=os.path.split,
    splitext=os.path.splitext,
    normpath=os.path.normpath,
)

SANDBOX_GLOBALS = {
    "__builtins__": SAFE_BUILTINS,

    # 安全子集
    "os_path": SAFE_OS_PATH,

    # 第三方
    "jmespath": jmespath,
    "jsonpath": jsonpath,

    # 平台能力
    # "logger": logger,
    # "assertC": assertC,
}