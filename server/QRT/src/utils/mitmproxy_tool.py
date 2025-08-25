import os

import flet as ft
import threading
import asyncio
from mitmproxy.options import Options
from mitmproxy.tools.web.master import WebMaster

class ProxyCore:
    def __init__(self):
        self.master = None
        self.loop = None
        self.thread = None

    async def run(self, port=8080, web_port=8081, config_dir="mitmproxy", mode=["local:CPOS-DF.exe"]):
        """
        web-port
        """
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        opts = Options(listen_host="127.0.0.1", listen_port=port, confdir=config_dir, mode=mode)
        # opts.web_port = web_port
        # opts.web_host = "127.0.0.1"
        self.master = WebMaster(opts, with_termlog=True)
        await self.master.run()

    def _start_loop(self, port, web_port):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run(port, web_port))

    def start(self, port=8080, web_port=8081):
        if self.thread and self.thread.is_alive():
            print("Proxy already running")
            return
        self.thread = threading.Thread(target=self._start_loop, args=(port, web_port), daemon=True)
        self.thread.start()
        print(f"Proxy started: http://127.0.0.1:{port}, web: http://127.0.0.1:{web_port}")

    def stop(self):
        if self.master:
            self.master.shutdown()
            print("Proxy stopped")
            self.master = None
