import argparse
import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """
    应用配置
    """
    app_env: str = 'dev'
    app_name: str = 'QTestRunner'
    app_root_path: str = '/dev-api'
    app_host: str = '0.0.0.0'
    app_port: int = 9099
    app_version: str = '1.0.0'
    app_reload: bool = True
    app_ip_location_query: bool = True
    app_same_time_login: bool = True
    worker_num: int = 1
    app_origins: str = '[]'


class JwtSettings(BaseSettings):
    """
    Jwt配置
    """
    jwt_secret_key: str = 'b01c66dc2c58dc6a0aabfe2144256be36226de378bf87f72c0c795dda67f4d55'
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 7 * 24 * 60
    jwt_redis_expire_minutes: int = 7 * 24 * 60


class DataBaseSettings(BaseSettings):
    """
    数据库配置
    """
    db_type: str = 'mysql'
    db_url: str = ''
    db_sqlite_path: str = 'caches/qtr-dev.sqlite3'
    sqlite_auto_seed: bool = False
    sqlite_seed_sql_file: str = 'sql/apitest.sql'
    sqlite_seed_table_prefix: str = 'sys_'
    db_host: str = '127.0.0.1'
    db_port: int = 3306
    db_username: str = 'root'
    db_password: str = 'mysqlroot'
    db_database: str = 'ruoyi-fastapi'
    db_echo: bool = True
    db_max_overflow: int = 10
    db_pool_size: int = 50
    db_pool_recycle: int = 3600
    db_pool_timeout: int = 30
    db_connect_timeout: int = 10
    db_read_timeout: int = 30
    db_write_timeout: int = 30


class RedisSettings(BaseSettings):
    """
    Redis配置
    """
    cache_backend: str = 'redis'
    redis_host: str = '127.0.0.1'
    redis_port: int = 6379
    redis_username: str = ''
    redis_password: str = ''
    redis_database: int = 2
    redis_celery_database: int = 3


class MessageFeishuBotSettings(BaseSettings):
    """
    飞书消息通知相关配置
    """
    feishu_bot_token: str = ''
    feishu_bot_key: str = ''
    feishu_bot_push: bool = False


class MetricsSettings(BaseSettings):
    """
    数据采集配置
    """
    vm_url: str = ''
    vm_user: str = ''
    vm_password: str = ""
    vm_job:str = ""
    vm_instance:str = ""
    vm_merchant:str = ""

class UploadSettings:
    """
    上传配置
    """
    UPLOAD_PREFIX = '/profile'
    UPLOAD_PATH = 'vf_admin/upload_path'
    UPLOAD_MACHINE = 'A'
    DEFAULT_ALLOWED_EXTENSION = [
        # 图片
        "bmp", "gif", "jpg", "jpeg", "png",
        # word excel powerpoint
        "doc", "docx", "xls", "xlsx", "ppt", "pptx", "html", "htm", "txt",
        # 压缩文件
        "rar", "zip", "gz", "bz2",
        # 视频格式
        "mp4", "avi", "rmvb",
        # pdf
        "pdf"
    ]
    DOWNLOAD_PATH = 'vf_admin/download_path'

    def __init__(self):
        if not os.path.exists(self.UPLOAD_PATH):
            os.makedirs(self.UPLOAD_PATH)
        if not os.path.exists(self.DOWNLOAD_PATH):
            os.makedirs(self.DOWNLOAD_PATH)


class CachePathConfig:
    """
    缓存目录配置
    """
    PATH = os.path.join(os.path.abspath(os.getcwd()), 'caches')
    PATHSTR = 'caches'


class RedisInitKeyConfig:
    """
    系统内置Redis键名
    """
    ACCESS_TOKEN = {'key': 'access_token', 'remark': '登录令牌信息'}
    SYS_DICT = {'key': 'sys_dict', 'remark': '数据字典'}
    SYS_CONFIG = {'key': 'sys_config', 'remark': '配置信息'}
    CAPTCHA_CODES = {'key': 'captcha_codes', 'remark': '图片验证码'}
    ACCOUNT_LOCK = {'key': 'account_lock', 'remark': '用户锁定'}
    PASSWORD_ERROR_COUNT = {'key': 'password_error_count', 'remark': '密码错误次数'}
    SMS_CODE = {'key': 'sms_code', 'remark': '短信验证码'}


class GetConfig:
    """
    获取配置
    """

    def __init__(self):
        self.parse_cli_args()

    @lru_cache
    def get_app_config(self):
        """
        获取应用配置
        """
        # 实例化应用配置模型
        return AppSettings()

    @lru_cache
    def get_jwt_config(self):
        """
        获取Jwt配置
        """
        # 实例化Jwt配置模型
        return JwtSettings()

    @lru_cache
    def get_database_config(self):
        """
        获取数据库配置
        """
        # 实例化数据库配置模型
        return DataBaseSettings()

    @lru_cache
    def get_redis_config(self):
        """
        获取Redis配置
        """
        # 实例化Redis配置模型
        return RedisSettings()

    @lru_cache
    def get_upload_config(self):
        """
        获取数据库配置
        """
        # 实例上传配置
        return UploadSettings()

    @lru_cache
    def get_feishu_config(self):
        """
        获取数据库配置
        """
        # 实例上传配置
        return MessageFeishuBotSettings()

    @lru_cache
    def get_metrics_config(self):
        """
        获取数据采集配置
        """
        # 实例上传配置
        return MetricsSettings()

    @staticmethod
    def parse_cli_args():
        """
        解析命令行参数
        """
        # 只解析本项目支持的 --env 参数，其余参数交由外部命令（如 celery/uvicorn）自行处理。
        parser = argparse.ArgumentParser(description='命令行参数', add_help=False)
        parser.add_argument('--env', type=str, default='', help='运行环境')
        args, _ = parser.parse_known_args()
        if args.env:
            os.environ['APP_ENV'] = args.env
        elif not os.environ.get('APP_ENV'):
            os.environ['APP_ENV'] = 'dev'
        # 读取运行环境
        run_env = (os.environ.get('APP_ENV', '') or 'dev').strip()
        env_file = f'.env.{run_env}'
        # 加载配置

        if os.path.exists(env_file):
            load_dotenv(env_file)
        load_dotenv(".env.base")


# 实例化获取配置类
get_config = GetConfig()
# 应用配置
AppConfig = get_config.get_app_config()

# Jwt配置
JwtConfig = get_config.get_jwt_config()
# 数据库配置
DataBaseConfig = get_config.get_database_config()
# Redis配置
RedisConfig = get_config.get_redis_config()
# 上传配置
UploadConfig = get_config.get_upload_config()

FeishuBotConfig = get_config.get_feishu_config()
MetricsConfig = get_config.get_metrics_config()
