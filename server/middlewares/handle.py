from fastapi import FastAPI

from middlewares.cors_middleware import add_cors_middleware, register_request_log_middleware


def handle_middleware(app: FastAPI):
    """
    全局中间件处理
    """
    # 加载跨域中间件
    add_cors_middleware(app)
    register_request_log_middleware(app)
