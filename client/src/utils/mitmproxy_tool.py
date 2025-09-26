import asyncio
import os
import sys
import socket
import platform
import re
import json
import threading
from collections import defaultdict
import requests


import psutil
# import psutil
from mitmproxy.addonmanager import Loader
from mitmproxy import ctx
from mitmproxy import tls
from mitmproxy.options import Options
from mitmproxy.tools.web.master import WebMaster, webaddons
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.http import HTTPFlow, Response
from loguru import logger

from model.config import MitmProxyConfigModel
from server.config import MitmproxyConfig


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        return f"无法获取 IP: {e}"


def get_all_macs():
    system = platform.system().lower()
    if system == "windows":
        cmd = "getmac"
    else:
        cmd = "ifconfig -a"

    output = os.popen(cmd).read()

    macs = re.findall(r"([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})", output)
    return ",".join([i.replace("-", "").lower() for i in set(macs) if i != "00-00-00-00-00-00"])

is_mock2 = False

class MockHandle:
    count = 0
    local_ip = get_local_ip()
    local_mac = get_all_macs()

    mock_server = "https://testautoapi.rta-os.com/hrm/mock"
    open_include = False
    open_exclude = False
    include = []
    exclude = []
    is_mock = True
    add_headers = dict()
    add_body = dict()
    def __init__(self):
        # self.client = httpx.AsyncClient(timeout=5)
        config = MitmproxyConfig.read()

        if config.add_headers:
            lines = config.add_headers.split("\n")
            for line in lines:
                line = line.strip().split("=", 1)
                if len(line) == 2:
                    MockHandle.add_headers[line[0]] = line[1]
        if config.add_body:
            lines = config.add_body.split("\n")
            for line in lines:
                line = line.strip().split("=", 1)
                if len(line) == 2:
                    MockHandle.add_body[line[0]] = line[1]


        MockHandle.is_mock = config.is_mock
        MockHandle.open_include = config.open_include
        MockHandle.open_exclude = config.open_exclude
        MockHandle.exclude = config.exclude.split(",")
        MockHandle.include = config.include.split(",")
        MockHandle.mock_server = config.mock_server

    def configure(self, updated: set[str]):
        try:
            if updated:
                old_config1 = MitmproxyConfig.read()
                for key in updated :
                    setattr(old_config1, key, getattr(ctx.options, key))
                MitmproxyConfig.write(old_config1)

            # if "mode" in updated:
            #     # logger.info(ctx.options.items())
            #     old_config = MitmproxyConfig.read()
            #     model_value = getattr(ctx.options, "mode")
            #     if model_value and model_value[0].startswith("local"):
            #         model_config = model_value[0].split(":", 1)
            #         old_config.proxy_model = model_config[0]
            #         old_config.proxy_model_value = model_config[1]
            #     elif model_value:
            #         old_config.proxy_model = model_value[0]
            #     else:
            #         old_config.proxy_model = ""
            #     MitmproxyConfig.write(old_config)
        except Exception as e:
            logger.error(f"回调配置更新失败： {e}")

    def load(self, loader: Loader):
        logger.info("load被调用")

    def tls_failed_client(self, data: tls.TlsData):
        logger.info("tls_failed_client")

    def tls_failed_server(data: tls.TlsData):
        logger.info("tls_failed_server")


    async def request(self, flow: HTTPFlow):
        logger.info(f"request: {flow.request.path}")
        logger.info(f"is_mock: {MockHandle.is_mock}, include: {MockHandle.include}, exclude: {MockHandle.exclude}")

        if not MockHandle.is_mock:
            logger.info(f"not mock: {flow.request.path}")
            return

        if MockHandle.open_include and flow.request.path not in MockHandle.include:
            logger.info(f"not include: {flow.request.path}")
            return

        if MockHandle.open_exclude and flow.request.path in MockHandle.exclude:
            logger.info(f"exclude: {flow.request.path}")
            return

        try:
            try:
                json_data = flow.request.json()
            except Exception as e:
                json_data = None
            logger.info(f"path: {flow.request.path}")

            headers = {
                "ip": MockHandle.local_ip,
                "mac": MockHandle.local_mac,
                **MockHandle.add_headers
            }
            result_data = requests.post(f"{MockHandle.mock_server}{flow.request.path}",
                                    json=json_data,
                                    data=dict(flow.request.urlencoded_form),
                                    headers=headers,
                                    timeout=3
                                    )
            if result_data.status_code == 200:
                logger.info(result_data.text)
                flow.response = Response.make(200,
                                              content=result_data.content,
                                              headers={"Content-Type": result_data.headers.get("Content-Type")},
                                              )
                return
            logger.info(f"mock error[{flow.request.path}]: {result_data.status_code}")
        except Exception as e:
            logger.exception(e)
            logger.error(f"request mock error[{flow.request.path}]: {e}")

    async def response(self, flow: HTTPFlow):
        pass


class ProxyCore:
    def __init__(self, config_data=None):
        self.master: WebMaster = None
        self.loop: asyncio.AbstractEventLoop = None
        self.task: asyncio.Task = None
        self.process: threading.Thread = None
        self.old_process_info = defaultdict()

    @classmethod
    async def update_config(cls):
        config = MitmproxyConfig.read()

        if config.add_headers:
            lines = config.add_headers.split("\n")
            for line in lines:
                line = line.strip().split("=", 1)
                if len(line) == 2:
                    MockHandle.add_headers[line[0]] = line[1]
        if config.add_body:
            lines = config.add_body.split("\n")
            for line in lines:
                line = line.strip().split("=", 1)
                if len(line) == 2:
                    MockHandle.add_body[line[0]] = line[1]

        MockHandle.is_mock = config.is_mock
        MockHandle.open_include = config.open_include
        MockHandle.open_exclude = config.open_exclude
        MockHandle.exclude = config.exclude.split(",")
        MockHandle.include = config.include.split(",")
        MockHandle.mock_server = config.mock_server

    async def run(self,
                  config_data: MitmProxyConfigModel,
                  # mode=["local:CPOS-DF,df_sv,Launcher,java,Pos,CPOS-KH,ONENOTE,ONENOTEM,HttpServer"]
                  ):
        """
        web-port
        """
        logger.info("mitmproxy proxy start")
        mode = [config_data.proxy_model]
        if config_data.proxy_model == "local":
            mode = [f"{config_data.proxy_model}:{config_data.proxy_model_value}"]
        if not config_data.proxy_model:
            mode = []
        try:
            config_dir = config_data.mitmproxy_config_dir
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)
            opts = Options(listen_host="127.0.0.1",
                           listen_port=config_data.port,
                           confdir=config_dir or os.path.join(os.path.expanduser("~"), ".mitmproxy"),
                           # confdir="C:\\Users\\Administrator\\.mitmproxy",
                           mode=mode,
                           )

            # self.master = DumpMaster(opts, with_termlog=False, with_dumper=False)

            self.master = WebMaster(opts, with_termlog=True)

            self.master.addons.add(MockHandle())
            self.master.options.add_option("web_host", str, "127.0.0.1", "")
            self.master.options.add_option("web_port", int, config_data.web_port, "")
            self.master.options.add_option("web_open_browser", bool, config_data.web_open_browser, "")
        except Exception as e:
            logger.error(f"mitmproxy proxy error[{e}]")
            logger.exception(e)

        logger.info("mitmproxy proxy start ...")
        try:
            await self.master.run()
            # self.master.running()
        except KeyboardInterrupt:
            logger.info("mitmproxy stopped")
            self.master.shutdown()


    def start_loop(self, config_data: MitmProxyConfigModel):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run(config_data))


    def start(self, config_data: MitmProxyConfigModel):
        if self.process and self.process.is_alive():
            print("mitmproxy already running")
            return
        self.process = threading.Thread(
            target=self.start_loop, args=(config_data, ), daemon=True
        )
        self.process.start()
        print(f"mitmproxy started pid={self.process.name}")

    def stop(self):

        if self.master:
            # self.master.event_loop.stop()
            self.master.shutdown()

            logger.info(f"mitmproxy stopped")

        if self.task:
            try:
                self.task.cancel()
                self.task.done()
                # self.task.exception()

                logger.info(f"mitmproxy task cancelled")
            except Exception as e:
                logger.error(f"mitmproxy stop task error[{e}]")

        if self.loop:
            try:
                self.loop.stop()
                # self.loop.close()

                logger.info(f"mitmproxy loop stopped")
            except Exception as e:
                logger.error(f"mitmproxy stop loop error[{e}]")

        if self.process:
            try:
                self.process.join(timeout=2)

                logger.info(f"mitmproxy process stopped")
            except Exception as e:
                logger.error(f"mitmproxy stop thread error[{e}]")

        self.master = None
        self.task = None
        self.loop = None
        self.process = None

    def open_url(self):
        if self.master and isinstance(self.master, WebMaster):
            webaddons.open_browser(self.master.web_url)
        else:
            logger.info(f"只能在web模式下才能打开浏览器，{type(self.master)}")


    @classmethod
    def find_mitm_children(cls):
        p = psutil.Process(os.getpid())

        # 获取所有子孙进程（递归）
        descendants = p.children(recursive=True)
        for d in descendants:
            logger.info(f"后代 PID={d.pid}, 名称={d.name()}， 状态={d.status()}， 信息：{d.exe()}")
        logger.info(f"mitmproxy 后代进程获取完毕")
        return

        current_pid = os.getpid()
        children = []
        threads = []
        # 查找所有子进程
        for proc in psutil.process_iter(['pid', 'ppid', 'name', "exe"]):
            try:
                logger.debug(f"进程： {proc.info['name']}")
                if "mitm" in proc.info["name"].lower():
                    logger.info(f"这是啥：{proc}")

                if proc.info['ppid'] == current_pid:
                    # 查找当前进程的所有线程
                    parent = psutil.Process(current_pid)
                    threads.extend(parent.threads())
                    logger.info(proc)
                    logger.info(f"{proc.info['pid']}  mitmproxy threads: {[thread.id for thread in threads]}")

                    # if proc.info['name'] != "flet.exe":
                    #     proc.terminate()
                    # else:
                    #     pass

                    # 查找当前进程的所有线程
                    # for thread in threads:
                    #     logger.info(f"{current_pid} {thread}")
                    #     logger.debug(f"{dir(thread)}")

                    # if proc.info['name'] != "flet.exe":
                    #     proc.terminate()
                        # children.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return children, threads


    @classmethod
    def config_path(cls):
        return "mitmproxy"


if __name__ == "__main__":
    server_port = 8080
    web_prot = 8081
    if len(sys.argv) > 1:
        server_port = int(sys.argv[1])
        web_prot = int(sys.argv[2])
    proxy = ProxyCore()
    proxy.start_loop(server_port, web_prot)

