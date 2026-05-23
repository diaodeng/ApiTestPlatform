import json
import time
import uuid

from config.env import AppConfig
from context.request_context import request_id_var
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger


def add_cors_middleware(app: FastAPI):
    # 前端页面url
    origins = ["http://localhost:80", "http://127.0.0.1:80"]

    if AppConfig.app_origins:
        custom_origins = json.loads(AppConfig.app_origins)
        origins.extend(custom_origins)

    # 后台api允许跨域
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def register_request_log_middleware(app):

    @app.middleware("http")
    async def request_log(request, call_next):

        request_id = str(uuid.uuid4())[:8]
        token = request_id_var.set(request_id)

        start_time = time.perf_counter()

        response = None

        try:
            response = await call_next(request)
            return response

        except Exception:
            logger.exception(f"[{request_id}] {request.method} {request.url.path} 请求异常")
            raise

        finally:
            process_time = (time.perf_counter() - start_time) * 1000

            status_code = response.status_code if response else 500

            log_msg = f"[{request_id}] [{status_code}] {request.method} {request.url.path} {process_time:.2f}ms"

            if process_time > 1000:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

            if response:
                response.headers["X-Request-Id"] = request_id
                response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

            request_id_var.reset(token)
