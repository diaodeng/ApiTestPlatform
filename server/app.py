import uvicorn
from server import app, AppConfig
from utils.log_util import logger


if __name__ == '__main__':
    try:
        logger.info("准备启动应用")
        uvicorn.run(
            app='app:app',
            host=AppConfig.app_host,
            port=AppConfig.app_port,
            root_path=AppConfig.app_root_path,
            reload=AppConfig.app_reload,
            workers=AppConfig.worker_num
        )
    except KeyboardInterrupt as e:
        logger.info("应用已停止")
