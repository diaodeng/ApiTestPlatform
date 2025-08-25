import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.env import AppConfig


def add_cors_middleware(app: FastAPI):
    # 前端页面url
    origins = [
        "http://localhost:80",
        "http://127.0.0.1:80"
    ]

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
