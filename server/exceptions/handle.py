from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from exceptions.exception import AuthException, PermissionException
from utils.response_util import ResponseUtil, JSONResponse, jsonable_encoder


def handle_exception(app: FastAPI):
    """
    全局异常处理
    """
    # 自定义token检验异常
    @app.exception_handler(AuthException)
    async def auth_exception_handler(request: Request, exc: AuthException):
        return ResponseUtil.unauthorized(data=exc.data, msg=exc.message)

    # 自定义权限检验异常
    @app.exception_handler(PermissionException)
    async def permission_exception_handler(request: Request, exc: PermissionException):
        return ResponseUtil.forbidden(data=exc.data, msg=exc.message)

    # 处理其他http请求异常
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            content=jsonable_encoder({"code": exc.status_code, "msg": exc.detail}),
            status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
            request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        捕捉422报错并进行自定义处理
        :param request:
        :param exc:
        :return:
        """
        x = exc.errors()
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": jsonable_encoder(exc.errors()), "msg": "参数或数据异常"},
        )

