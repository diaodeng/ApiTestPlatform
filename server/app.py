import logging

import uvicorn

from config.env import AppConfig
from utils.log_util import logger

logging.getLogger("watchfiles.main").setLevel(logging.CRITICAL)


def main():
    logger.info("准备启动应用")
    uvicorn.run(
        app="server:app",
        host=AppConfig.app_host,
        port=AppConfig.app_port,
        root_path=AppConfig.app_root_path,
        reload=AppConfig.app_reload,
        workers=1 if AppConfig.app_reload else AppConfig.worker_num,
        log_config=None,
    )


if __name__ == "__main__":
    main()
