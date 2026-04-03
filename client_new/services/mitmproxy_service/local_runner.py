import asyncio
import os
import signal
import sys
from pathlib import Path

from loguru import logger
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster

# 直接脚本启动时，补齐项目根目录到 sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.config import MitmproxyConfig
from services.mitmproxy_service.mock_handle import MockHandle
from services.mitmproxy_service.runtime_config import RuntimeConfig


async def _run():
    config = MitmproxyConfig.read()
    RuntimeConfig.set(config)

    mode = [config.proxy_model] if config.proxy_model else []
    if config.proxy_model == "local":
        mode = [f"{config.proxy_model}:{config.proxy_model_value}"]

    config_dir = config.mitmproxy_config_dir
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir)

    opts = Options(
        listen_host="127.0.0.1",
        listen_port=config.port,
        ssl_insecure=True,
        mode=mode,
        confdir=config_dir or os.path.join(os.path.expanduser("~"), ".mitmproxy"),
    )
    master = DumpMaster(opts)
    master.addons.add(MockHandle())

    loop = asyncio.get_running_loop()

    def _shutdown():
        try:
            master.shutdown()
        except Exception:
            pass

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _shutdown())

    await master.run()


def main():
    try:
        asyncio.run(_run())
    except Exception as e:
        logger.exception(f"local runner 异常退出: {e}")


if __name__ == "__main__":
    main()
