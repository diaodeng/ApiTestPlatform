from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

class AuthMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        # 保护 /clash-admin
        # if request.url.path.startswith("/clash-admin"):
        #     user = await authenticate(request)
        #     if not user:
        #         return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        #
        #     # 👇 关键：把用户信息放入 request.state
        #     request.state.user = user

        return await call_next(request)


async def authenticate(request: Request):
    # 示例：JWT / Cookie / Session
    token = request.cookies.get("access_token")
    if not token:
        return None

    # 你已有的校验逻辑
    return {
        "id": "u123",
        "username": "admin",
        "roles": ["admin"]
    }
