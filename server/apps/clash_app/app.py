from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .clash.proxy import router as proxy_router
from .yacd import router as yacd_router

clash_admin_app = FastAPI(
    title="Clash Admin",
    docs_url=None,
    redoc_url=None
)

# API
clash_admin_app.include_router(api_router, prefix="/api")

# Clash API 代理
clash_admin_app.include_router(proxy_router, prefix="/clash")

# Yacd
clash_admin_app.include_router(yacd_router)

# UI
clash_admin_app.mount(
    "/",
    StaticFiles(directory="clash_app/page", html=True),
    name="ui"
)

# Yacd 静态资源
clash_admin_app.mount(
    "/yacd/assets",
    StaticFiles(directory="clash_app/yacd/dist/assets"),
    name="yacd-assets"
)
