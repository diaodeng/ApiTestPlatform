from config.database import SessionLocal, Base, engine
from utils.log_util import logger



from typing import Any, Callable
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session


class AsyncSessionProxy:
    """把同步 SQLAlchemy Session 包装成可在 async 环境下调用的代理类"""

    def __init__(self, sync_session: Session):
        self._sync_session = sync_session

    def __getattr__(self, item: str) -> Callable[..., Any]:
        """拦截方法调用，自动转到 run_in_threadpool"""
        attr = getattr(self._sync_session, item)

        if callable(attr):
            async def async_attr(*args, **kwargs):
                return await run_in_threadpool(attr, *args, **kwargs)
            return async_attr
        else:
            return attr

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await run_in_threadpool(self._sync_session.close)


def get_db_pro():
    """
    每一个请求处理完毕后会关闭当前连接，不同的请求使用不同的连接
    :return:
    """
    current_db = SessionLocal()
    try:
        yield current_db
    finally:
        current_db.close()

async def async_get_db_pro():
    sync_session = SessionLocal()
    async with AsyncSessionProxy(sync_session) as session:
        yield session


async def init_create_table():
    """
    应用启动时初始化数据库连接
    :return:
    """
    logger.info("初始化数据库连接...")
    Base.metadata.create_all(bind=engine)
    logger.info("数据库连接成功")


get_db = get_db_pro
