from module_hrm.entity.vo.case_vo import CaseRunModel
from utils.log_util import logger
from .message_way.feishu_bot import FeiShuHandler


class MessageHandler:
    def __init__(self, run_info: CaseRunModel):
        logger.info(f"用例执行信息：{run_info.model_dump()}")
        self.is_push = run_info.push
        self.run_info = run_info

    def can_push(self):
        return self.run_info.push

    def feishu(self):
        return FeiShuHandler(self.run_info.feishu_robot)