from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
# from .models import Base
from config.env import DataBaseConfig
from urllib.parse import quote_plus

# ASYNC_DATABASE_URL = "mysql+asyncmy://root:password@localhost:3306/testdb"
ASYNC_DATABASE_URL = f"mysql+asyncmy://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@" \
                     f"{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}"

engine_async = create_async_engine(ASYNC_DATABASE_URL,
                                   echo=DataBaseConfig.db_echo,
                                   pool_pre_ping=True,
                                   max_overflow=DataBaseConfig.db_max_overflow,
                                   pool_size=DataBaseConfig.db_pool_size,
                                   pool_recycle=DataBaseConfig.db_pool_recycle,
                                   pool_timeout=DataBaseConfig.db_pool_timeout)
SessionLocalAsync = async_sessionmaker(engine_async, expire_on_commit=False)

# from sqlalchemy import MetaData
# from sqlalchemy.orm import DeclarativeBase
#
# my_metadata = MetaData()
#
#
# class Base(DeclarativeBase):
#     metadata = my_metadata


# 初始化表（只需运行一次）
# async def init_async_db():
#     async with engine_async.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
