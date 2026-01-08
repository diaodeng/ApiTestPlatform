import os
import threading
import requests
import time
import random
from .container import MemoryCollector
from .container import CgroupCPU

from loguru import logger

from config.env import MetricsConfig


class PushDataToServer(threading.Thread):
    """
    发送数据都爱prometheus或者vm
    """
    def __init__(self, batch=100, interval=5):
        threading.Thread.__init__(self)
        self.data_lines = []
        self.batch = batch
        self.interval = interval
        self.current_time = time.time()
        self.vm_url = MetricsConfig.vm_url
        if not self.vm_url:
            logger.warning(f"vm_url未配置，不推送统计数据")
        self.daemon = True
        self.stopped = False
        self.cpu_info = CgroupCPU()
        self.mem_info = MemoryCollector()
        self.group = os.environ.get("SYM_GROUP", "stable")

    def run(self):
        logger.info(f"开始采集信息")
        while self.vm_url and not self.stopped:
            try:
                self.push_machine_metrics()
                time.sleep(1)
            except Exception as e:
                pass

    def stop(self):
        self.stopped = True
        self._push()
        self.data_lines = []

    def _push(self):
        # 将所有数据行合并，一次批量发送
        headers = {
            'Content-Type': 'text/plain',
        }
        metrics_data = "\n".join(self.data_lines)

        # print("推送的数据示例：\n", metrics_data)
        response = requests.post(self.vm_url,
                                 data=metrics_data,
                                 auth=(MetricsConfig.vm_user, MetricsConfig.vm_password),
                                 headers=headers,
                                 verify=False)
        if response.status_code == 204:
            pass
            # print("数据推送成功！")
        else:
            print("推送失败:", response.text)

    def push_machine_metrics(self):

        data = {}
        data.update(self.cpu_info.cpu_status())
        data.update(self.mem_info.snapshot())
        for key,value in data.items():
            labels = {
                "job": MetricsConfig.vm_job or "QTR",  # 标识这是一个来自Python应用的任务
                "instance": MetricsConfig.vm_instance or "TEST_ENV",  # 标识这是哪个具体的应用实例（主机:端口）
                "machine": MetricsConfig.vm_merchant or self.group,  # 您的业务标签
                "sensor": key  # 您的业务标签
            }
            timestamp = int(time.time() * 1000)

            # 将标签字典转换为Prometheus格式的字符串
            label_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
            line = f"{key}{{{label_str}}} {value} {timestamp}"

            self.data_lines.append(line)
        if len(self.data_lines) >= self.batch or (time.time() - self.current_time >= self.interval):
            self._push()
            self.data_lines = []
            self.current_time = time.time()