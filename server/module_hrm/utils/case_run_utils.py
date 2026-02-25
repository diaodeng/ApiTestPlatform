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
from module_hrm.entity.vo.case_vo_detail_for_handle import CustomHooksParams, HooksModel, StepLogs, TStep
from module_hrm.enums.enums import CodeTypeEnum, DataType
from module_hrm.utils.CaseRunLogHandle import CustomStackLevelLogger
from module_hrm.utils.common import dict2list, key_value_dict, update_or_extend_list
from module_hrm.utils.sandbox_globals import SANDBOX_GLOBALS

# 初始化一个 JS 运行环境（默认是 Node.js）
js_code = """
    console.log(apt)
    apt.a = 2
    apt.b = 3
"""


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

    def assertC(condition, successMsg, errorMsg):
        if condition:
            apt.logs.info.append(f"断言成功: {str(successMsg or '')} >> {condition}")
        else:
            apt.logs.error.append(f"断言失败: {str(errorMsg or '')} >> {condition}")
            apt.failed = True

    sandbox_globals = {
        "apt": apt,
        "logger": logger,
        "assertC": assertC,
    }

    sandbox_globals.update(SANDBOX_GLOBALS)

    try:
        # global_namespace = globals()
        # local_namespace = locals()
        python_code_source = textwrap.dedent(python_code_source)
        code_obj = compile(python_code_source, "<custom-hook>", "exec")
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
        # raise TestFailError(f"{script_name}执行异常：{e}, 脚本: {script_source}") from e
    finally:
        if not script_source:
            return
        if isinstance(step_data_obj, dict):
            step_data_obj = CustomHooksParams(**step_data_obj)
        if step_data_obj.logs:  # 处理回调中的日志
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

        if exception_str:
            logs.error += f"{script_name}执行异常：{exception_str}"
        if step_data_obj.failed:
            raise AssertionError(f"{script_name}断言失败")


if __name__ == '__main__':
    a = eval("1>2")
    print(a)
