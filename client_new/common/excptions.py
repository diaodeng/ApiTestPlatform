class QTRClientBaseError(Exception):
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

        full_message = " ".join(parts) if parts else "客户端异常"
        super().__init__(full_message)

    def to_dict(self):
        """将异常信息转换为字典"""
        return {
            'message': self.message,
            'error_code': self.error_code,
            'original_exception': str(self.original_exception) if self.original_exception else None,
            'context': self.context
        }

class PosHandleException(QTRClientBaseError):
    def __init__(self, message: str, original_exception=None, error_code=None, **kwargs):
        super().__init__(message, original_exception, error_code, **kwargs)


class PosParamsException(QTRClientBaseError):
    def __init__(self, message: str, original_exception=None, error_code=None, **kwargs):
        super().__init__(message, original_exception, error_code, **kwargs)


class PosStartException(QTRClientBaseError):
    """POS 启动过程异常（启动前动作执行失败等），替代早期误用的 shutil.ExecError"""

    def __init__(self, message: str, original_exception=None, error_code=None, **kwargs):
        super().__init__(message, original_exception, error_code, **kwargs)


class ConfigFileException(QTRClientBaseError):
    """配置文件存在但内容损坏（JSON 解析失败/模型校验失败），不允许静默回退默认值"""

    def __init__(self, message: str, original_exception=None, error_code=None, **kwargs):
        super().__init__(message, original_exception, error_code, **kwargs)