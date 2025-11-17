

class ExistsError(Exception):
    pass

class DebugtalkError(Exception):
    pass

class DebugtalkRepeatedError(DebugtalkError):
    pass




""" failure type exceptions
    these exceptions will mark test as failure
"""


class MyBaseFailure(Exception):
    pass


class ParseTestsFailure(MyBaseFailure):
    pass


class ValidationFailure(MyBaseFailure):
    pass


class ExtractFailure(MyBaseFailure):
    pass


class SetupHooksFailure(MyBaseFailure):
    pass


class TeardownHooksFailure(MyBaseFailure):
    pass


""" error type exceptions
    these exceptions will mark test as error
"""


class MyBaseError(Exception):
    """应用程序异常基类"""

    def __init__(self, message=None, original_exception=None, error_code=None, **kwargs):
        self.message = message
        self.original_exception = original_exception
        self.error_code = error_code
        self.context = kwargs

        # 构建错误信息
        parts = []
        if error_code:
            parts.append(f"[错误码: {error_code}]")
        if message:
            parts.append(message)
        if original_exception:
            parts.append(f"原异常: {original_exception}")

        full_message = " ".join(parts) if parts else "服务异常"
        super().__init__(full_message)

    def to_dict(self):
        """将异常信息转换为字典"""
        return {
            'message': self.message,
            'error_code': self.error_code,
            'original_exception': str(self.original_exception) if self.original_exception else None,
            'context': self.context
        }


class FileFormatError(MyBaseError):
    pass


class TestCaseFormatError(FileFormatError):
    pass


class TestSuiteFormatError(FileFormatError):
    pass


class ParamsError(MyBaseError):
    pass


class NotFoundError(MyBaseError):
    pass


class FileNotFound(FileNotFoundError, NotFoundError):
    pass


class FunctionNotFound(NotFoundError):
    pass


class VariableNotFound(NotFoundError):
    pass


class EnvNotFound(NotFoundError):
    pass


class CSVNotFound(NotFoundError):
    pass


class ApiNotFound(NotFoundError):
    pass


class TestcaseNotFound(NotFoundError):
    pass


class SummaryEmpty(MyBaseError):
    """test result summary data is empty"""


class SqlMethodNotSupport(MyBaseError):
    pass


class TestFailError(MyBaseError):
    pass

class TestStepCustomScriptFailError(TestFailError):
    pass

class TestStepCustomFunctionFailError(TestFailError):
    pass

class TestStepSystemFunctionFailError(TestFailError):
    pass

class TestCaseCustomScriptFailError(TestFailError):
    pass

class TestCaseCustomFunctionFailError(TestFailError):
    pass

class TestCaseSystemFunctionFailError(TestFailError):
    pass