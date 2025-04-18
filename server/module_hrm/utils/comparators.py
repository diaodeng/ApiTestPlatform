"""
Built-in validate comparators.
"""
import json
import re
from typing import Text, Any, Union


def equals(check_value: Any, expect_value: Any, message: Text = ""):
    """
    check_value == expect_value, message
    """
    assert check_value == expect_value, f"{message}:{check_value} == {expect_value}"


def equals_as_int(check_value: Any, expect_value: Any, message: Text = ""):
    """
    int(check_value) == int(expect_value), message or f"{check_value} == {expect_value}"
    """
    assert int(check_value) == int(expect_value), f"{message}:{int(check_value)} == {int(expect_value)}"


def equals_as_str(check_value: Text, expect_value: Any, message: Text = ""):
    """
    if isinstance(check_value, (dict, list, tuple)):
        check_value = json.dumps(check_value, ensure_ascii=False)

    if isinstance(expect_value, (dict, list, tuple)):
        check_value = json.dumps(expect_value, ensure_ascii=False)

    str(check_value) == str(expect_value), message
    """
    if isinstance(check_value, (dict, list, tuple)):
        check_value = json.dumps(check_value, ensure_ascii=False)
    if isinstance(expect_value, (dict, list, tuple)):
        expect_value = json.dumps(expect_value, ensure_ascii=False)

    assert str(check_value) == str(expect_value),(
            f"{message}:{str(check_value)} == {str(expect_value)}")


def greater_than(
        check_value: Union[int, float], expect_value: Union[int, float], message: Text = ""
):
    """
    check_value > expect_value, message
    """
    assert check_value > expect_value, f"{message}:{check_value} > {expect_value}"


def less_than(
        check_value: Union[int, float], expect_value: Union[int, float], message: Text = ""
):
    """
    check_value < expect_value, message
    """
    assert check_value < expect_value, f"{message}:{check_value} < {expect_value}"


def greater_or_equals(
        check_value: Union[int, float], expect_value: Union[int, float], message: Text = ""
):
    """
    check_value >= expect_value, message
    """
    assert check_value >= expect_value, f"{message}:{check_value} >= {expect_value}"


def less_or_equals(
        check_value: Union[int, float], expect_value: Union[int, float], message: Text = ""
):
    """
    check_value <= expect_value, message
    """
    assert check_value <= expect_value, f"{message}:{check_value} <= {expect_value}"


def not_equals(check_value: Any, expect_value: Any, message: Text = ""):
    """
    check_value != expect_value, message
    """
    assert check_value != expect_value, f"{message}:{check_value} != {expect_value}"


def string_not_equals(check_value: Text, expect_value: Any, message: Text = ""):
    """
    str(check_value) == str(expect_value), message
    """
    assert str(check_value) != str(
        expect_value), f"{message}:{str(check_value)} != {str(expect_value)}"


def length_equals(check_value: Text, expect_value: int, message: Text = ""):
    """
    len(check_value) == expect_value, message
    """
    assert isinstance(expect_value, int), "expect_value should be int type"
    assert len(check_value) == expect_value, f"{message}:{len(check_value)} == {expect_value}"


def length_greater_than(
        check_value: Text, expect_value: Union[int, float], message: Text = ""
):
    """
    len(check_value) > expect_value, message
    """
    assert isinstance(
        expect_value, (int, float)
    ), "expect_value should be int/float type"
    assert len(check_value) > expect_value, f"{message}:{len(check_value)} > {expect_value}"


def length_greater_or_equals(
        check_value: Text, expect_value: Union[int, float], message: Text = ""
):
    """
    len(check_value) >= expect_value, message
    """
    assert isinstance(
        expect_value, (int, float)
    ), "expect_value should be int/float type"
    assert len(check_value) >= expect_value, f"{message}:{len(check_value)} >= {expect_value}"


def length_less_than(
        check_value: Text, expect_value: Union[int, float], message: Text = ""
):
    """
    len(check_value) < expect_value, message
    """
    assert isinstance(
        expect_value, (int, float)
    ), "expect_value should be int/float type"
    assert len(check_value) < expect_value, f"{message}:{len(check_value)} < {expect_value}"


def length_less_or_equals(
        check_value: Text, expect_value: Union[int, float], message: Text = ""
):
    """
    len(check_value) <= expect_value, message
    """
    assert isinstance(
        expect_value, (int, float)
    ), "expect_value should be int/float type"
    assert len(check_value) <= expect_value, f"{message}:{len(check_value)} <= {expect_value}"


def contains(check_value: Any, expect_value: Any, message: Text = ""):
    """
    expect_value in check_value, message
    """
    assert isinstance(
        check_value, (list, tuple, dict, str, bytes)
    ), "expect_value should be list/tuple/dict/str/bytes type"
    assert expect_value in check_value, f"{message}:{expect_value} in {check_value}"


def contained_by(check_value: Any, expect_value: Any, message: Text = ""):
    """
    check_value in expect_value, message
    """
    assert isinstance(
        expect_value, (list, tuple, dict, str, bytes)
    ), "expect_value should be list/tuple/dict/str/bytes type"
    assert check_value in expect_value, f"{message}:{check_value} in {expect_value}"


def type_match(check_value: Any, expect_value: Any, message: Text = ""):
    """
    type(check_value) == get_type(expect_value), message
    """

    def get_type(name):
        if isinstance(name, type):
            return name
        elif isinstance(name, str):
            try:
                return __builtins__[name]
            except KeyError:
                raise ValueError(name)
        else:
            raise ValueError(name)

    if expect_value in ["None", "NoneType", None]:
        assert check_value is None, message
    else:
        assert type(check_value) == get_type(expect_value), message


def regex_match(check_value: Text, expect_value: Any, message: Text = ""):
    """
    re.match(expect_value, check_value), message
    """
    assert isinstance(expect_value, str), "expect_value should be Text type"
    assert isinstance(check_value, str), "check_value should be Text type"
    assert re.match(expect_value, check_value), message


def startswith(check_value: Any, expect_value: Any, message: Text = ""):
    """
    str(check_value).startswith(str(expect_value)), message
    """
    assert str(check_value).startswith(str(expect_value)), message


def endswith(check_value: Text, expect_value: Any, message: Text = ""):
    """
    str(check_value).endswith(str(expect_value)), message
    """
    assert str(check_value).endswith(str(expect_value)), message


def contain_any(check_value: Text, expect_value: list, message: Text = ""):
    """
    any([va in check_value for va in expect_value])
    """

    assert any([va in check_value for va in expect_value]), f"{message}:{expect_value} not in {check_value}"


def contain_all(check_value: Text, expect_value: list, message: Text = ""):
    """
    all([va in check_value for va in expect_value])
    """

    assert all([va in check_value for va in expect_value]), f"{message}:{expect_value} not in {check_value}"


__all__ = ["equals", "equals_as_int", "equals_as_str", "greater_than", "less_than", "greater_or_equals",
           "less_or_equals", "not_equals",
           "length_equals", "length_greater_than", "length_greater_or_equals", "length_less_than",
           "length_less_or_equals", "contains", "contained_by", "contain_any", "contain_all", "type_match", "startswith", "endswith"]
