import json
from functools import wraps

import requests

from config.env import FeishuBotConfig
from module_hrm.entity.vo.case_vo import CaseRunModel, FeishuRobotModel
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
    def __init__(self, run_info: CaseRunModel):
        logger.info(f"用例执行信息：{run_info.model_dump()}")
        self.is_push = run_info.push
        self.run_info = run_info

    def can_push(self):
        return self.run_info.push

    def feishu(self):
        return FeiShuHandler(self.run_info.feishu_robot)
