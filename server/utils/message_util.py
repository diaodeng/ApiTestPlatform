import json
from functools import wraps

import requests
from sqlalchemy.orm import Session

from config.database import SessionLocal
from module_hrm.dao.push_dao import PushDao
from module_hrm.entity.do.report_do import HrmReport
from module_hrm.entity.vo.report_vo import ReportListModel
from module_hrm.enums.enums import PushTypeEnum, PushReminderEnum, CaseRunStatus
from config.env import FeishuBotConfig
from module_hrm.entity.vo.case_vo import CaseRunModel
from module_hrm.entity.vo.push_vo import FeishuRobotModel, PushModel
from module_hrm.utils.parser import parse_string
from utils.log_util import logger


def message_service(sms_code: str):
    logger.info(f"短信验证码为{sms_code}")


"""
https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot#132a114c
"""


class FeiShuHandler:
    def __init__(self, feishu_bot_config: FeishuRobotModel):
        token = feishu_bot_config.url if feishu_bot_config else None
        secret_key = feishu_bot_config.secret if feishu_bot_config else None

        self._token = token or FeishuBotConfig.feishu_bot_token
        self._secret_key = secret_key or FeishuBotConfig.feishu_bot_key

        logger.debug(f"FeiShuHandler token: {token}   secret_key: {secret_key}")
        logger.debug(f"FeiShuHandler FeishuBotConfig: {FeishuBotConfig.model_dump_json()}")
        logger.debug(f"FeiShuHandler self._token: {self._token}   self._secret_key: {self._secret_key}")

        self.config = feishu_bot_config
        self.config.push = FeishuBotConfig.feishu_bot_push

    def content_text(self, content):
        "消息卡片"
        at_info = ""
        if self.config.at_user_id:
            for user_id in self.config.at_user_id:
                at_info += f"<at id={user_id}>所有人</at> "
        else:
            if self.config.at_reminder == PushReminderEnum.reminder_all.value:
                at_info = "<at id=all>所有人</at>"

        param = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "template": "purple",
                    "title": {
                        "content": "【QTR测试】",
                        "tag": "plain_text"
                    }
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "content": content,
                            "tag": "lark_md"
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "elements": [
                            {
                                "content": "{}【{}】".format(at_info, self._secret_key),
                                "tag": "lark_md"
                            }
                        ],
                        "tag": "note"
                    }
                ]
            }
        }
        return param

    def content_post(self, content, chat_info=None):
        "富文本消息"
        param = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": "【{}】测试结果".format(self._secret_key),
                        "content": [
                            [
                                {
                                    "tag": "text",
                                    "text": content.descrption
                                },
                                {
                                    "tag": "a",
                                    "href": content.link,
                                    "text": "点击打开{}".format(
                                        "登录二维码" if content.link_type == "qrlink" else "登录地址")
                                },
                                {
                                    "tag": "at",
                                    "user_id": "all"
                                }
                            ]
                        ]
                    }
                }
            }
        }

        return param

    def push(self, content):
        if not self.config.push:
            logger.info(f"飞书推送配置关闭，不推送：push=={self.config.push}")
            return

        # 没配置参数则直接返回
        if not self._token or not self._secret_key:
            logger.info(f"没有飞书推送配置，不推送：token=={self._token}; secret_key=={self._secret_key}")
            return
        try:
            # logger.info("飞书机器人推送参数：token:{}, key:{}".format(self._token, self._secret_key))
            headers = {"content_type": "application/json"}
            json_str = self.content_text(content)
            logger.info("飞书机器人发送的内容：{}".format(json_str))
            res = requests.post(url="https://open.feishu.cn/open-apis/bot/v2/hook/{}".format(self._token),
                                headers=headers,
                                data=json.dumps(json_str),
                                verify=False)
            logger.info("飞书推送结果 {}：{}".format(res.status_code, res.text))
        except Exception as e:
            logger.error("==============飞书推送异常===========")
            logger.error(e, exc_info=True)

    def upload_image(self):
        pass


class MessageHandler:
    def __init__(self, push_info: PushModel = None, push_obj: dict = None):
        self.push_info = push_info
        self.push_obj = push_obj
        self.default_test_push_temp = "[${user}]于${start_at}开始执行的测试完成。\n总共：${total_count}条用例，成功：${success_count}条，失败：${failed_count};\n报告：【${report_id}】${report_name}"

    def _push_content_parse(self, content):
        return parse_string(content or self.default_test_push_temp, self.push_obj or {}, {}, False)

    def push(self, content=None, at_reminder: int = None):
        if self.push_info.type == PushTypeEnum.feishu_bot.value:
            feishu_push_config = FeishuRobotModel(**self.push_info.config_content or {})
            feishu_push_config.at_reminder = at_reminder
            FeiShuHandler(feishu_push_config).push(
                self._push_content_parse(content) if content else self._push_content_parse(feishu_push_config.content)
            )
        else:
            logger.warning(f"暂不支持推送类型：{self.push_info.type}")


class TestResultPushHandler:
    def __init__(self,
                 run_info: CaseRunModel,
                 report_info: ReportListModel | HrmReport,
                 user_name: str = None,
                 ):
        self.run_info = run_info
        self.report_info = report_info
        self.push_obj = {
            "user": user_name,
            "start_at": self.report_info.start_at.strftime("%Y-%m-%d %H:%M:%S") if self.report_info.start_at else None,
            "total_count": self.report_info.total,
            "success_count": self.report_info.success,
            "failed_count": self.report_info.total - self.report_info.success,
            "report_id": self.run_info.report_id,
            "report_name": self.report_info.report_name,
        }

    def push(self, content=None):

        if not self.run_info.push:
            return

        push = False
        at_reminder = PushReminderEnum.no_reminder.value
        status_desc = ""
        if self.report_info.status == CaseRunStatus.passed.value \
                and self.run_info.push_config.success.push:
            push = True
            at_reminder = self.run_info.push_config.success.reminder
            status_desc = "成功"

        elif self.report_info.status == CaseRunStatus.failed.value \
                and self.run_info.push_config.failed.push:
            push = True
            at_reminder = self.run_info.push_config.failed.reminder
            status_desc = "失败"

        if not push:
            return

        with SessionLocal() as query_db:
            for push_id in self.run_info.push_config.push_ids:
                detail = PushDao.get(query_db, push_id)
                if detail:
                    MessageHandler(PushModel.model_validate(detail),
                                   self.push_obj).push(content=content,
                                                       at_reminder=at_reminder)
                else:
                    logger.warning(f"用例执行{status_desc}，推送配置【{push_id}】不存在，不会推送消息")
