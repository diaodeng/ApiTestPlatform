import asyncio

from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster

from services.mitmproxy_service.runtime_config import RuntimeConfig


def run_proxy(config_queue, result_queue, port):

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    class IPCAddon:
        def request(self, flow):
            data = {
                "type": "request",
                "url": flow.request.pretty_url,
                "method": flow.request.method,
            }
            result_queue.put(data)

        def response(self, flow):
            data = {
                "type": "response",
                "url": flow.request.pretty_url,
                "status": flow.response.status_code,
            }
            result_queue.put(data)

    async def config_watcher():
        while True:
            config = await loop.run_in_executor(None, config_queue.get)
            RuntimeConfig.set(config)

    async def main():
        config = RuntimeConfig.get()
        opts = Options(
            listen_host="127.0.0.1",
            listen_port=port,
            ssl_insecure=bool(getattr(config, "ssl_insecure", True)),
        )

        master = DumpMaster(opts)
        master.addons.add(IPCAddon())

        asyncio.create_task(config_watcher())

        await master.run()

    loop.run_until_complete(main())
