class QTRBaseError(Exception):
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


class LoginException(Exception):
    """
    自定义登录异常LoginException
    """

    def __init__(self, data: str = None, message: str = None):
        self.data = data
        self.message = message


class AuthException(Exception):
    """
    自定义令牌异常AuthException
    """

    def __init__(self, data: str = None, message: str = None):
        self.data = data
        self.message = message


class PermissionException(Exception):
    """
    自定义权限异常PermissionException
    """

    def __init__(self, data: str = None, message: str = None):
        self.data = data
        self.message = message


class AgentForwardError(QTRBaseError):
    """
    agent转发异常
    """

    def __init__(self, message: str = None, original_exception=None):
        super().__init__(message=message, original_exception=original_exception)
