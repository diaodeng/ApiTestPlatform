import uvicorn
from server import app, AppConfig
from loguru import logger
from asyncio.exceptions import CancelledError


if __name__ == '__main__':
    try:
        uvicorn.run(
            app='app:app',
            host=AppConfig.app_host,
            port=AppConfig.app_port,
            root_path=AppConfig.app_root_path,
            reload=AppConfig.app_reload,
            workers=AppConfig.worker_num
        )
    except (KeyboardInterrupt, CancelledError):
        logger.info("程序已停止[KeyboardInterrupt]")
    except CancelledError:
        logger.info("循环事件被停止")