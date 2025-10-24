from urllib.parse import quote_plus

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config.env import DataBaseConfig

SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@" \
                          f"{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=DataBaseConfig.db_echo,
    pool_pre_ping=True,
    max_overflow=DataBaseConfig.db_max_overflow,
    pool_size=DataBaseConfig.db_pool_size,
    pool_recycle=DataBaseConfig.db_pool_recycle,
    pool_timeout=DataBaseConfig.db_pool_timeout,
    connect_args={
        "connect_timeout": DataBaseConfig.db_connect_timeout,  # 建立连接超时
        "read_timeout": DataBaseConfig.db_read_timeout,     # 读超时
        "write_timeout": DataBaseConfig.db_write_timeout     # 写超时
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()


my_metadata = MetaData()


class Base(DeclarativeBase):
    metadata = my_metadata
