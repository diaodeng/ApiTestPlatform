import ast
import datetime
import json
import re
import textwrap
import traceback

import httpx
import jmespath
import quickjs
from jsonpath import jsonpath

from module_hrm.entity.vo import case_vo_detail_for_run as caseVoForRun
from module_hrm.entity.vo.case_vo_detail_for_handle import CustomHooksParams, HooksModel, Result, StepLogs, TStep
from module_hrm.enums.enums import CodeTypeEnum, DataType
from module_hrm.service.runner.run_error_service import (
    build_assertion_error_event,
    build_exception_error_event,
    stringify_error_value,
)
from module_hrm.utils.CaseRunLogHandle import CustomStackLevelLogger
from module_hrm.utils.common import dict2list, key_value_dict, update_or_extend_list
from module_hrm.utils.sandbox_globals import SANDBOX_GLOBALS

# 初始化一个 JS 运行环境（默认是 Node.js）
js_code = """
    console.log(apt)
    apt.a = 2
    apt.b = 3
"""


COMPARE_OPERATOR_LABELS = {
    ast.Eq: ("equals", "=="),
    ast.NotEq: ("not_equals", "!="),
    ast.Gt: ("greater_than", ">"),
    ast.Lt: ("less_than", "<"),
    ast.GtE: ("greater_or_equals", ">="),
    ast.LtE: ("less_or_equals", "<="),
    ast.In: ("contains", "in"),
    ast.NotIn: ("not_contains", "not in"),
    ast.Is: ("is_identity", "is"),
    ast.IsNot: ("is_not_identity", "is not"),
}


class StructuredPythonAssertTransformer(ast.NodeTransformer):
    """
    把用户脚本中的 assert 和 raise AssertionError 重写成结构化采集调用。
    """

    def visit_Assert(self, node: ast.Assert):
        self.generic_visit(node)
        assert_source = ast.unparse(node.test)
        msg_factory = self._build_msg_factory(node.msg)
        call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="__ast_assert_expression__", ctx=ast.Load()),
                args=[
                    self._build_assert_expr_spec(node.test),
                    msg_factory,
                    ast.Constant(value=assert_source),
                ],
                keywords=[],
            )
        )
        return ast.copy_location(call, node)

    def visit_Raise(self, node: ast.Raise):
        self.generic_visit(node)
        if node.cause is not None:
            return node
        if isinstance(node.exc, ast.Name) and node.exc.id == "AssertionError":
            call = ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="__ast_raise_assertion__", ctx=ast.Load()),
                    args=[
                        ast.Constant(value=None),
                        ast.Constant(value="AssertionError"),
                    ],
                    keywords=[],
                )
            )
            return ast.copy_location(call, node)
        if not isinstance(node.exc, ast.Call):
            return node
        if not isinstance(node.exc.func, ast.Name) or node.exc.func.id != "AssertionError":
            return node
        message_expr = node.exc.args[0] if node.exc.args else None
        call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="__ast_raise_assertion__", ctx=ast.Load()),
                args=[
                    self._build_msg_factory(message_expr),
                    ast.Constant(value=ast.unparse(node.exc)),
                ],
                keywords=[],
            )
        )
        return ast.copy_location(call, node)

    @staticmethod
    def _build_msg_factory(message_expr: ast.expr | None) -> ast.expr:
        if message_expr is None:
            return ast.Constant(value=None)
        return ast.Lambda(
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=message_expr,
        )

    def _build_assert_expr_spec(self, expr_node: ast.expr) -> ast.expr:
        source = ast.Constant(value=ast.unparse(expr_node))

        if isinstance(expr_node, ast.Compare):
            return ast.Dict(
                keys=[
                    ast.Constant(value="kind"),
                    ast.Constant(value="source"),
                    ast.Constant(value="left_source"),
                    ast.Constant(value="operator_names"),
                    ast.Constant(value="comparator_sources"),
                    ast.Constant(value="left_factory"),
                    ast.Constant(value="comparator_factories"),
                ],
                values=[
                    ast.Constant(value="compare"),
                    source,
                    ast.Constant(value=ast.unparse(expr_node.left)),
                    ast.List(
                        elts=[ast.Constant(value=type(operator).__name__) for operator in expr_node.ops],
                        ctx=ast.Load(),
                    ),
                    ast.List(
                        elts=[ast.Constant(value=ast.unparse(comparator)) for comparator in expr_node.comparators],
                        ctx=ast.Load(),
                    ),
                    self._build_zero_arg_lambda(expr_node.left),
                    ast.List(
                        elts=[self._build_zero_arg_lambda(comparator) for comparator in expr_node.comparators],
                        ctx=ast.Load(),
                    ),
                ],
            )

        if isinstance(expr_node, ast.BoolOp):
            return ast.Dict(
                keys=[
                    ast.Constant(value="kind"),
                    ast.Constant(value="source"),
                    ast.Constant(value="op_name"),
                    ast.Constant(value="children"),
                ],
                values=[
                    ast.Constant(value="boolop"),
                    source,
                    ast.Constant(value=type(expr_node.op).__name__),
                    ast.List(
                        elts=[self._build_assert_expr_spec(child) for child in expr_node.values],
                        ctx=ast.Load(),
                    ),
                ],
            )

        if isinstance(expr_node, ast.UnaryOp) and isinstance(expr_node.op, ast.Not):
            return ast.Dict(
                keys=[
                    ast.Constant(value="kind"),
                    ast.Constant(value="source"),
                    ast.Constant(value="operand"),
                ],
                values=[
                    ast.Constant(value="unary_not"),
                    source,
                    self._build_assert_expr_spec(expr_node.operand),
                ],
            )

        return ast.Dict(
            keys=[
                ast.Constant(value="kind"),
                ast.Constant(value="source"),
                ast.Constant(value="value_factory"),
            ],
            values=[
                ast.Constant(value="condition"),
                source,
                self._build_zero_arg_lambda(expr_node),
            ],
        )

    @staticmethod
    def _build_zero_arg_lambda(expr_node: ast.expr) -> ast.expr:
        return ast.Lambda(
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=expr_node,
        )


def _transform_python_assert_source(source: str) -> ast.AST:
    """
    解析并重写用户脚本中的 assert 语句，保持语义同时补充结构化统计能力。
    """
    tree = ast.parse(source, mode="exec")
    transformer = StructuredPythonAssertTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    return new_tree


def exec_js(js_code_source: str, data: dict, logger: CustomStackLevelLogger = None):
    """
    执行自定义js脚本
    使用python库py_mini_racer实现，不依赖其他运行环境
    from py_mini_racer import py_mini_racer
    """
    result = data
    try:
        ctx = quickjs.Context()

        # ===== 注入 Python 能力到 JS =====

        def jmes_search(obj, expr):
            return jmespath.search(expr, obj)

        def jsonpath_query(obj, expr):
            return [m.value for m in jsonpath(obj, expr)]

        def http_get(url):
            # return requests.get(url).text

            # if not is_allowed_domain(url):
            #     raise Exception("Domain not allowed")

            with httpx.Client(timeout=3) as client:
                resp = client.get(url)
                return resp.text

        ctx.add_callable("py_jmes_search", jmes_search)
        ctx.add_callable("py_jsonpath_query", jsonpath_query)
        ctx.add_callable("py_http_get", http_get)

        ctx.eval("""
                var jmespath = { search: py_jmes_search };
                var jsonpath = { query: py_jsonpath_query };
                var http = { get: py_http_get };
            """)

        # 把 apt 注入 JS
        ctx.eval(f"var apt = {json.dumps(data)};")

        ctx.eval("""
        var console = {
            log: function(msg){
                apt.logs.info.push(String(msg));
            },
            error: function(msg){
                apt.logs.error.push(String(msg));
            }
        };
        """)

        # 注入日志容器
        ctx.eval("""
                        function logInfo(msg){ apt.logs.info.push(msg); }
                        function logError(msg){ apt.logs.error.push(msg); }

                        function assert(condition, successMsg, errorMsg){
                            if(!condition){
                                logError("断言失败：" + errorMsg + " >> " + condition);
                                apt.failed = true;
                            }else{
                                logInfo("断言成功：" + successMsg + " >> " + condition);
                            }
                        }
                        
                        var jmespath = {
                            search: function(obj, expr){
                                return py_jmes_search(obj, expr);
                            }
                        };
            
                        var jsonpath = {
                            query: function(obj, expr){
                                return py_jsonpath_query(obj, expr);
                            }
                        };
            
                        var http = {
                            get: function(url){
                                return py_http_get(url);
                            }
                        };
                    """)

        # 执行用户脚本
        ctx.eval(f"""
                try {{
                    {js_code_source}
                }} catch(err) {{
                    logError(err.message);
                    logError(err.stack);
                    apt.failed = true;
                }}
            """)

        # 回传结果
        # result = ctx.eval("apt")
        result = ctx.eval("JSON.stringify(apt)")
        result = json.loads(result)
        # logs = ctx.eval("apt_logs")
        # result["logs"] = logs
        # result = data
    except Exception as err:
        result["failed"] = True
        logger.error(f"自定义js脚本执行异常： {err}")
        logger.exception(err)

    return result


def exec_js_old(js_code_source: str, data, logger: CustomStackLevelLogger = None):
    """
    执行自定义js脚本
    使用python库PyExecJS==1.5.1实现，依赖安装
    import execjs
    """
    import execjs

    js_source = f"""
            
    
    function exec_test(apt) {{
    // let logs = [];
        function logInfo(message) {{
            apt.logs.info.push(message); // 保存日志到全局变量
        }}
        
        function logError(message) {{
            apt.logs.error.push(message); // 保存日志到全局变量
        }}
        
        
        console.log = logInfo; // 重定义 console.log
        
        function assert(condition, successMsg, errorMsg) {{
          if (!condition){{
            logError("断言失败：" + errorMsg + " >> " + condition);
            apt.failed = true;
          }}else{{
            logInfo("断言成功：" + successMsg + " >> " + condition);
          }}
        }}
        
        
        try{{
        var jmespath = require('jmespath');
        var jsonpath = require('jsonpath'); 
        {js_code_source}
        }}catch(err) {{
        console.log(err.message);
        console.log(err.stack);
        apt.failed = true;
        }}

        

        // apt.logs = logs;
        return apt;

      
    }}
    

"""
    result = data
    try:
        context = execjs.compile(js_source)
        result = context.call("exec_test", data)
    except Exception as err:
        result["failed"] = True
        logger.error(f"自定义js脚本执行异常： {err}")
        logger.exception(err)

    return result


def exec_python(python_code_source: str, apt: CustomHooksParams, logger: CustomStackLevelLogger = None):
    """
    执行自定义python脚本
    """

    def _get_hook_context():
        data = apt.data
        step_id = stringify_error_value(getattr(data, "step_id", ""))
        step_name = getattr(data, "name", "")
        if not step_name and getattr(data, "config", None):
            step_name = getattr(data.config, "name", "")
        if not step_name:
            step_name = getattr(data, "case_name", "")
        return step_id, step_name

    def _resolve_message(msg_factory, fallback_message: str = "") -> str:
        if msg_factory is None:
            return fallback_message
        try:
            return stringify_error_value(msg_factory())
        except Exception as msg_error:
            return f"{fallback_message} [message evaluate failed: {msg_error}]".strip()

    def _append_structured_assert_event(
        *,
        error_subtype: str,
        assert_name: str,
        check_key: str,
        expected_value=None,
        actual_value=None,
        error_message: str = "",
    ):
        step_id, step_name = _get_hook_context()
        apt.error_events.append(
            build_assertion_error_event(
                error_source='custom_python',
                error_subtype=error_subtype,
                assert_name=assert_name,
                check_key=check_key,
                expected_value=expected_value,
                actual_value=actual_value,
                error_message=error_message,
                step_id=step_id,
                step_name=step_name,
            )
        )

    def _raise_structured_assertion(
        *,
        error_subtype: str,
        assert_name: str,
        check_key: str,
        expected_value=None,
        actual_value=None,
        error_message: str = "",
    ):
        apt.logs.error.append(f"断言失败: {error_message}")
        apt.failed = True
        _append_structured_assert_event(
            error_subtype=error_subtype,
            assert_name=assert_name,
            check_key=check_key,
            expected_value=expected_value,
            actual_value=actual_value,
            error_message=error_message,
        )
        raise AssertionError(error_message)

    def _eval_compare_operator(operator_name: str, left_value, right_value) -> bool:
        if operator_name == "Eq":
            return left_value == right_value
        if operator_name == "NotEq":
            return left_value != right_value
        if operator_name == "Gt":
            return left_value > right_value
        if operator_name == "Lt":
            return left_value < right_value
        if operator_name == "GtE":
            return left_value >= right_value
        if operator_name == "LtE":
            return left_value <= right_value
        if operator_name == "In":
            return left_value in right_value
        if operator_name == "NotIn":
            return left_value not in right_value
        if operator_name == "Is":
            return left_value is right_value
        if operator_name == "IsNot":
            return left_value is not right_value
        raise AssertionError(f"当前断言运算符不支持：{operator_name}")

    def _build_assert_result(
        passed: bool,
        *,
        source: str,
        error_subtype: str,
        check_key: str,
        expected_value=None,
        actual_value=None,
        fallback_message: str = "",
    ):
        """
        组装统一的断言分析结果，供 bool/not 递归分析与最终抛错复用。
        """
        return {
            "passed": passed,
            "source": source,
            "error_subtype": error_subtype,
            "check_key": check_key,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "fallback_message": fallback_message,
        }

    def _analyze_condition_value(condition_value, assert_source: str):
        """
        分析普通 truthy/falsey 条件断言。
        """
        return _build_assert_result(
            bool(condition_value),
            source=assert_source,
            error_subtype='python_assert',
            check_key=assert_source,
            expected_value=True,
            actual_value=condition_value,
            fallback_message=f"assert {assert_source}",
        )

    def _analyze_compare_values(
        left_value,
        comparator_values,
        operator_names,
        left_source: str,
        comparator_sources,
        assert_source: str = "",
    ):
        """
        分析 compare 表达式，保持链式比较的逐段失败定位。
        """
        current_left = left_value
        current_left_source = left_source
        failed_operator = ""
        failed_right_value = None
        failed_right_source = ""

        for index, (operator_name, right_value) in enumerate(zip(operator_names, comparator_values)):
            if _eval_compare_operator(operator_name, current_left, right_value):
                current_left = right_value
                current_left_source = comparator_sources[index]
                continue
            failed_operator = operator_name
            failed_right_value = right_value
            failed_right_source = comparator_sources[index]
            break

        if not failed_operator:
            return _build_assert_result(
                True,
                source=assert_source or left_source,
                error_subtype='python_assert',
                check_key=assert_source or left_source,
                expected_value=True,
                actual_value=True,
                fallback_message=f"assert {assert_source or left_source}",
            )

        subtype, operator_label = COMPARE_OPERATOR_LABELS.get(
            getattr(ast, failed_operator, object),
            ("python_compare", failed_operator),
        )

        if failed_operator in {"In", "NotIn"}:
            check_key = failed_right_source
            actual_value = failed_right_value
            expected_value = current_left
        else:
            check_key = current_left_source
            actual_value = current_left
            expected_value = failed_right_value

        return _build_assert_result(
            False,
            source=assert_source or left_source,
            error_subtype=subtype,
            check_key=check_key,
            expected_value=expected_value,
            actual_value=actual_value,
            fallback_message=f"{check_key} {operator_label} {failed_right_source}",
        )

    def _analyze_assert_spec(spec):
        """
        递归分析 AST 断言规格，按 Python 短路语义返回最具体的失败子项。
        """
        kind = spec.get("kind")
        source = spec.get("source", "")

        if kind == "condition":
            return _analyze_condition_value(spec["value_factory"](), source)

        if kind == "compare":
            return _analyze_compare_values(
                spec["left_factory"](),
                (factory() for factory in spec["comparator_factories"]),
                spec["operator_names"],
                spec["left_source"],
                spec["comparator_sources"],
                source,
            )

        if kind == "boolop":
            op_name = spec.get("op_name")
            last_failure = None
            for child_spec in spec.get("children", []):
                child_result = _analyze_assert_spec(child_spec)
                if op_name == "And" and not child_result["passed"]:
                    return child_result
                if op_name == "Or" and child_result["passed"]:
                    return _build_assert_result(
                        True,
                        source=source,
                        error_subtype='python_assert',
                        check_key=source,
                        expected_value=True,
                        actual_value=True,
                        fallback_message=f"assert {source}",
                    )
                last_failure = child_result

            if op_name == "And":
                return _build_assert_result(
                    True,
                    source=source,
                    error_subtype='python_assert',
                    check_key=source,
                    expected_value=True,
                    actual_value=True,
                    fallback_message=f"assert {source}",
                )

            if op_name == "Or" and last_failure is not None:
                return last_failure

            raise AssertionError(f"当前布尔断言运算符不支持：{op_name}")

        if kind == "unary_not":
            operand_result = _analyze_assert_spec(spec["operand"])
            if not operand_result["passed"]:
                return _build_assert_result(
                    True,
                    source=source,
                    error_subtype='python_assert',
                    check_key=source,
                    expected_value=True,
                    actual_value=True,
                    fallback_message=f"assert {source}",
                )
            return _build_assert_result(
                False,
                source=source,
                error_subtype='python_not_assert',
                check_key=operand_result.get("check_key") or spec["operand"].get("source", source),
                expected_value=False,
                actual_value=operand_result.get("actual_value"),
                fallback_message=f"not {spec['operand'].get('source', source)}",
            )

        raise AssertionError(f"当前断言表达式不支持：{kind}")

    def _raise_from_assert_result(result, msg_factory=None, assert_source: str = ""):
        """
        把分析结果转换成统一日志与结构化错误事件。
        """
        if result["passed"]:
            apt.logs.info.append(f"断言成功: {assert_source or result['source']}")
            return
        fallback_message = result.get("fallback_message") or f"assert {assert_source or result['source']}"
        final_message = _resolve_message(msg_factory, fallback_message)
        _raise_structured_assertion(
            error_subtype=result["error_subtype"],
            assert_name='assert',
            check_key=result["check_key"],
            expected_value=result.get("expected_value"),
            actual_value=result.get("actual_value"),
            error_message=final_message,
        )

    def __ast_assert_expression__(spec, msg_factory=None, assert_source: str = ""):
        """
        统一处理用户 assert 表达式，支持 compare、and/or、not 递归拆解。
        """
        _raise_from_assert_result(_analyze_assert_spec(spec), msg_factory, assert_source)

    def __ast_assert_condition__(condition_value, assert_source: str, msg_factory=None):
        _raise_from_assert_result(
            _analyze_condition_value(condition_value, assert_source),
            msg_factory,
            assert_source,
        )

    def __ast_assert_compare__(
        left_value,
        comparator_values,
        operator_names,
        left_source: str,
        comparator_sources,
        msg_factory=None,
        assert_source: str = "",
    ):
        _raise_from_assert_result(
            _analyze_compare_values(
                left_value,
                comparator_values,
                operator_names,
                left_source,
                comparator_sources,
                assert_source,
            ),
            msg_factory,
            assert_source,
        )

    def __ast_raise_assertion__(msg_factory=None, assert_source: str = "AssertionError"):
        final_message = _resolve_message(msg_factory, assert_source)
        _raise_structured_assertion(
            error_subtype='python_assertion_error',
            assert_name='AssertionError',
            check_key=assert_source,
            error_message=final_message,
        )

    def assertC(
        condition,
        successMsg=None,
        errorMsg=None,
        expected=None,
        actual=None,
        field=None,
        subtype='custom_script_assert',
        message=None,
    ):
        if condition:
            apt.logs.info.append(f"断言成功: {str(successMsg or '')} >> {condition}")
        else:
            final_message = str(message or errorMsg or successMsg or '')
            apt.logs.error.append(f"断言失败: {final_message} >> {condition}")
            apt.failed = True
            apt.error_events.append(
                build_assertion_error_event(
                    error_source='custom_python',
                    error_subtype=subtype,
                    assert_name='assertC',
                    check_key=str(field or ''),
                    expected_value=expected,
                    actual_value=actual if actual is not None else condition,
                    error_message=final_message,
                    step_id=_get_hook_context()[0],
                    step_name=_get_hook_context()[1],
                )
            )

    sandbox_globals = {
        "apt": apt,
        "logger": logger,
        "assertC": assertC,
        "__ast_assert_expression__": __ast_assert_expression__,
        "__ast_assert_condition__": __ast_assert_condition__,
        "__ast_assert_compare__": __ast_assert_compare__,
        "__ast_raise_assertion__": __ast_raise_assertion__,
    }

    sandbox_globals.update(SANDBOX_GLOBALS)

    try:
        # global_namespace = globals()
        # local_namespace = locals()
        python_code_source = textwrap.dedent(python_code_source)
        code_tree = _transform_python_assert_source(python_code_source)
        code_obj = compile(code_tree, "<custom-hook>", "exec")
        exec(code_obj, sandbox_globals, None)
    except Exception:
        apt.failed = True
        raise
        # logger.error(f"自定义python执行异常： {err}")
        # logger.exception(err)


def get_script_name(data_type, script_type, is_before):
    """
    组装脚本名称方便打印日志以及其他显示使用
    """
    type_name = ""
    script_type_name = ""
    position_name = ""
    if script_type == CodeTypeEnum.js.value:
        script_type_name = CodeTypeEnum.js.name
    elif script_type == CodeTypeEnum.python.value:
        script_type_name = CodeTypeEnum.python.name

    if is_before:
        position_name = "setup_hook"
    else:
        position_name = "teardown_hook"

    if data_type == DataType.case.value:
        type_name = DataType.case.name
    else:
        type_name = "step"

    return f"{type_name}-{position_name}-自定义{script_type_name}回调脚本"


def exec_hook_script(
    hooks_info: HooksModel,
    logger: CustomStackLevelLogger,
    handler,
    data_obj,
    global_vars,
    case_vars,
    logs: StepLogs,
    result_obj: Result | None = None,
    is_before=True,
    data_type=DataType.case.value,
):
    """
    执行自定义回调脚本
    """
    script_name = ""
    step_data_obj: CustomHooksParams = None
    script_source = hooks_info.code_info.code_content
    exception_str = ""
    hook_exception = None
    try:
        if script_source:
            script_type = hooks_info.code_info.code_type
            script_name = get_script_name(data_type, script_type, is_before)

            if script_type == CodeTypeEnum.js.value:
                step_data_dict = {
                    "data": data_obj.model_dump(by_alias=True),
                    "globals": global_vars,
                    "caseVariables": key_value_dict(case_vars),
                    "logs": {"info": [], "error": []},
                    "failed": False,
                }
                new_step_data_dict = exec_js(script_source, step_data_dict, logger)
                step_data_obj = CustomHooksParams(**new_step_data_dict)

                if data_type == DataType.case.value:
                    data_obj = caseVoForRun.TestCase(**step_data_dict["data"])
                else:
                    data_obj = TStep(**step_data_dict["data"])
                step_data_obj.data = data_obj
                global_vars.update(step_data_obj.globals)
                update_or_extend_list(case_vars, dict2list(step_data_obj.case_variables))

            elif script_type == CodeTypeEnum.python.value:
                step_data_obj = CustomHooksParams(
                    globals=global_vars, caseVariables=key_value_dict(case_vars), failed=False
                )
                step_data_obj.data = data_obj
                exec_python(script_source, step_data_obj, logger)
                global_vars.update(step_data_obj.globals)
                update_or_extend_list(case_vars, dict2list(step_data_obj.case_variables))
    except Exception as e:
        logger.exception(e)
        exception_str = "".join(traceback.format_exception(e))
        hook_exception = e
        # raise TestFailError(f"{script_name}执行异常：{e}, 脚本: {script_source}") from e
    finally:
        if not script_source:
            return
        if isinstance(step_data_obj, dict):
            step_data_obj = CustomHooksParams(**step_data_obj)
        if step_data_obj and step_data_obj.logs:  # 处理回调中的日志
            for log in step_data_obj.logs.info:
                logger.info(f"{script_name}日志： {log}")

            if logs:
                info_log = handler.get_log()
                if is_before:
                    logs.before_request += info_log
                else:
                    logs.after_response += info_log

            for elog in step_data_obj.logs.error:
                logger.error(f"{script_name}日志： {elog}")
            if logs:
                error_log = handler.get_log()
                if is_before:
                    logs.before_request += error_log
                else:
                    logs.after_response += error_log
                logs.error += error_log

        if exception_str:  # 这里是脚本执行异常
            if logs:
                logs.error += f"{script_name}执行异常：{exception_str}"
            if result_obj:
                if isinstance(hook_exception, AssertionError) and not (step_data_obj and step_data_obj.error_events):
                    result_obj.error_events.append(
                        build_assertion_error_event(
                            error_source='hook_script',
                            error_subtype='hook_script_assert',
                            assert_name='AssertionError',
                            error_message=str(hook_exception),
                            error_stack=exception_str,
                        )
                    )
                elif not isinstance(hook_exception, AssertionError):
                    result_obj.error_events.append(
                        build_exception_error_event(
                            error_source='hook_script',
                            error_name=type(hook_exception).__name__ if hook_exception else 'HookScriptError',
                            error_message=str(hook_exception or script_name),
                            error_stack=exception_str,
                            error_subtype='hook_script_exception',
                        )
                    )
        if step_data_obj and step_data_obj.failed:
            if result_obj:
                if step_data_obj.error_events:
                    result_obj.error_events.extend(step_data_obj.error_events)

            raise AssertionError(f"{script_name}断言失败")


if __name__ == '__main__':
    a = eval("1>2")
    print(a)
