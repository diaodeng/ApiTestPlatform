from fastapi import APIRouter, Request

qtrServiceStatusController = APIRouter(prefix='/check')


# 健康检查接口1
@qtrServiceStatusController.get('/health')
def health(request: Request):
    return 'OK'


# 健康检查接口2
@qtrServiceStatusController.get('/ready')
def ready(request: Request):
    return 'OK'
