"""
验证插件包 manifest 与运行时的兼容性校验逻辑。

python_version 是硬约束（.pyd 编译产物只兼容构建时的 CPython 大.小版本），
不匹配必须拒绝安装；字段缺失/无法解析时跳过校验以兼容旧格式包。
app_version 为软约束参考，仅用于安装结果提示，不在本用例范围。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugins.manager import PluginManager

_check = PluginManager._manifest_compatibility_error

CURRENT = f"{sys.version_info.major}.{sys.version_info.minor}"
OTHER = "3.8" if CURRENT != "3.8" else "3.12"


def test_matching_python_version_passes():
    assert _check({"python_version": CURRENT}) == ""
    # 带微版本号的写法同样按大.小版本比较
    assert _check({"python_version": f"{CURRENT}.9"}) == ""


def test_mismatched_python_version_rejected():
    error = _check({"python_version": OTHER})
    assert OTHER in error
    assert "不兼容" in error and "拒绝安装" in error


def test_missing_or_invalid_field_skips_check():
    # 旧格式包没有该字段，保持向后兼容
    assert _check({}) == ""
    assert _check({"python_version": ""}) == ""
    # 无法解析的字段不误伤
    assert _check({"python_version": "unknown"}) == ""


def main():
    test_matching_python_version_passes()
    test_mismatched_python_version_rejected()
    test_missing_or_invalid_field_skips_check()
    print(f"[ALL PASS] manifest 兼容性校验验证通过（当前运行时 Python {CURRENT}）")


if __name__ == "__main__":
    main()
