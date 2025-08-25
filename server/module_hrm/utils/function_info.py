import inspect
import sys


class Tmp(object):
    def __init__(self):
        pass

    def ycs(self, var2=3, *args, var1=1, **kwargs):
        pass

    def onlyarg(self, *args):
        pass

    def onlykwarg(self, **kwargs):
        pass

    def onlyvar(self, var1, var2):
        pass

    def onlyfuncdefault(self, var1="1111"):
        pass

    @classmethod
    def calssfunc(cls, classvar):
        pass

    @staticmethod
    def staticmethod(staticvar):
        pass


class FunctionInfo:
    @classmethod
    def is_function_or_method(cls, func):
        return inspect.isfunction(func) or inspect.ismethod(func)

    @classmethod
    def get_functions(cls, module):
        methods = inspect.getmembers(module, predicate=cls.is_function_or_method)
        functions_info = []
        for name, func in methods:
            if name.startswith("_"):
                continue
            func_info = FunctionInfo()
            sig = inspect.signature(func)
            parameters = sig.parameters
            for param_name, param in parameters.items():
                param_name = ""
                print(f"{name}: {param.name} : {param.kind} : {param.default}")
                continue
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    param_name = param_name.lstrip('_')
                    print("POSITIONAL_ONLY")
                elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                    param_name = param_name.lstrip('_')
                    print("KEYWORD_ONLY")
                elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                    param_name = param_name.lstrip('_')
                    print("VAR_POSITIONAL")
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    param_name = param_name.lstrip('_')
                    print("VAR_KEYWORD")
                elif param.default == inspect.Parameter.empty:
                    print("参数必填")
                elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                    param_name = param_name.lstrip('_')
                    print("POSITIONAL_OR_KEYWORD")
                else:
                    print("未知的")
                # print(param_name)



if __name__ == '__main__':
    FunctionInfo.get_functions(Tmp)