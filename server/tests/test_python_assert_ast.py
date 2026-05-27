import importlib
import pathlib
import sys
import types
import unittest

SERVER_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from module_hrm.entity.vo.case_vo_detail_for_handle import CustomHooksParams, TStep


class _DummyLoguruLogger:
    """替代真实 loguru logger，避免测试导入时触发多进程日志初始化。"""

    def opt(self, *args, **kwargs):
        return self

    def debug(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def critical(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


def _load_case_run_utils():
    """在导入前注入假的日志模块，避免 Windows 权限环境下的日志副作用。"""
    fake_log_module = types.ModuleType("utils.log_util")
    fake_log_module.logger = _DummyLoguruLogger()
    sys.modules["utils.log_util"] = fake_log_module
    sys.modules.pop("module_hrm.utils.CaseRunLogHandle", None)
    sys.modules.pop("module_hrm.utils.case_run_utils", None)
    return importlib.import_module("module_hrm.utils.case_run_utils")


class ExecPythonAssertAstTests(unittest.TestCase):
    """覆盖任意用户 Python 断言的 AST 解析行为。"""

    @classmethod
    def setUpClass(cls):
        """统一加载被测模块，避免每个用例重复处理导入隔离。"""
        cls.case_run_utils = _load_case_run_utils()

    def _build_apt(self):
        """构造执行自定义 hook 所需的最小上下文。"""
        return CustomHooksParams(data=TStep(name="ast-step", step_id="step-1"))

    def test_and_reports_failed_compare_child(self):
        """and 表达式失败时，应定位到具体失败的 compare 子项。"""
        apt = self._build_apt()

        with self.assertRaises(AssertionError) as ctx:
            self.case_run_utils.exec_python(
                """
a = 1
b = 2
assert a == 1 and b == 3
                """,
                apt,
            )

        self.assertEqual("b == 3", str(ctx.exception))
        self.assertTrue(apt.failed)
        self.assertEqual(1, len(apt.error_events))
        self.assertEqual("equals", apt.error_events[0].error_subtype)
        self.assertEqual("b", apt.error_events[0].check_key)
        self.assertEqual("3", apt.error_events[0].expected_value)
        self.assertEqual("2", apt.error_events[0].actual_value)

    def test_or_returns_last_failure_when_all_children_fail(self):
        """or 全部失败时，应回落到最后一个最具体的失败子项。"""
        apt = self._build_apt()

        with self.assertRaises(AssertionError) as ctx:
            self.case_run_utils.exec_python(
                """
flag = False
count = 1
assert flag or count == 2
                """,
                apt,
            )

        self.assertEqual("count == 2", str(ctx.exception))
        self.assertTrue(apt.failed)
        self.assertEqual(1, len(apt.error_events))
        self.assertEqual("equals", apt.error_events[0].error_subtype)
        self.assertEqual("count", apt.error_events[0].check_key)
        self.assertEqual("2", apt.error_events[0].expected_value)
        self.assertEqual("1", apt.error_events[0].actual_value)

    def test_not_condition_reports_operand_truthy_state(self):
        """not 条件失败时，应保留被取反表达式的实际 truthy 值。"""
        apt = self._build_apt()

        with self.assertRaises(AssertionError) as ctx:
            self.case_run_utils.exec_python(
                """
items = [1]
assert not items
                """,
                apt,
            )

        self.assertEqual("not items", str(ctx.exception))
        self.assertTrue(apt.failed)
        self.assertEqual(1, len(apt.error_events))
        self.assertEqual("python_not_assert", apt.error_events[0].error_subtype)
        self.assertEqual("items", apt.error_events[0].check_key)
        self.assertEqual("False", apt.error_events[0].expected_value)
        self.assertEqual("[1]", apt.error_events[0].actual_value)

    def test_not_compare_reports_nested_expression(self):
        """not(compare) 失败时，应指向被取反的 compare 表达式。"""
        apt = self._build_apt()

        with self.assertRaises(AssertionError) as ctx:
            self.case_run_utils.exec_python(
                """
a = 1
b = 1
assert not (a == b)
                """,
                apt,
            )

        self.assertEqual("not a == b", str(ctx.exception))
        self.assertTrue(apt.failed)
        self.assertEqual(1, len(apt.error_events))
        self.assertEqual("python_not_assert", apt.error_events[0].error_subtype)
        self.assertEqual("a == b", apt.error_events[0].check_key)
        self.assertEqual("False", apt.error_events[0].expected_value)
        self.assertEqual("True", apt.error_events[0].actual_value)

    def test_or_keeps_short_circuit_semantics(self):
        """or 成功短路时，后续子表达式不应被执行。"""
        apt = self._build_apt()

        self.case_run_utils.exec_python(
            """
calls = []

def boom():
    calls.append("boom")
    return False

assert True or boom()
assert calls == []
            """,
            apt,
        )

        self.assertFalse(apt.failed)
        self.assertEqual([], apt.error_events)
        self.assertIn("断言成功: True or boom()", apt.logs.info)


if __name__ == "__main__":
    unittest.main()
