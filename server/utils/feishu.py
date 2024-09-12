import json
import time
import requests
import hashlib
import base64
import hmac


# 飞书通知机器人
FeishuTalk_Robots = {
    "url": 'xxx',     # 机器人地址
    "keywords": ["", ""],   # 关键词
    "secret": "xxx",  # 签名
    "at_user_id": []  # @用户id，不配置默认all
}


class Feishu:
    def __init__(self, kwargs):
        self.robot = kwargs
        self.headers = {"Content-Type": "application/json; charset=utf8"}
        self.secret = self.robot.get('secret', None)
        self.user_ids = self.robot.get('at_user_id', ["all"])
        self.keywords = self.robot.get('keywords', "")

    def sendTextmessage(self, content):
        payload_message = {
            "msg_type": "text",
            "content": {
                "text": ""
            }
        }
        if self.secret:
            timestamp = int(time.time())
            payload_message.update({"timestamp": timestamp})
            # 飞书机器人签名
            payload_message.update({"sign": self.gen_sign(timestamp, self.secret)})
        if len(self.keywords) > 0:
            self.keywords = "".join(self.keywords)
        else:
            self.keywords = ""
        content_text = self._get_user_ids() + self.keywords + content
        payload_message['content'].update({"text": content_text})
        res = requests.post(url=self.robot['url'], data=json.dumps(payload_message), headers=self.headers)
        return res.json()

    def sendFuTextmessage(self, content):
        payload_message = {
            "msg_type": "post",
            "content": {
                "zh_cn": {
                    "title": "",
                    "content": [
                        {
                            "tag": "a",
                            "href": "http://www.baidu.com",
                            "text": "查看报告",
                            "style": ['bold', 'italic']
                         }
                    ]
                }
            }
        }

        if self.secret:
            timestamp = int(time.time())
            payload_message.update({"timestamp": timestamp})
            # 飞书机器人签名
            payload_message.update({"sign": self.gen_sign(timestamp, self.secret)})
        if len(self.keywords) > 0:
            self.keywords = "".join(self.keywords)
        else:
            self.keywords = ""
        content_text = self._get_user_ids() + self.keywords + content
        payload_message['content'].update({"text": content_text})
        res = requests.post(url=self.robot['url'], data=json.dumps(payload_message), headers=self.headers)
        return res.json()

    def _get_user_ids(self):
        """
        拼接要@的用户id
        """
        at_user_ids = ""
        if len(self.user_ids) == 0:
            self.user_ids = ['all']
        for user_id in self.user_ids:
            at_user_ids += f"<at user_id=\"{user_id}\"></at> "
        return at_user_ids

    def gen_sign(self, timestamp, secret):
        # 拼接timestamp和secret
        string_to_sign = '{}\n{}'.format(timestamp, secret)
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()

        # 对结果进行base64处理
        sign = base64.b64encode(hmac_code).decode('utf-8')

        return sign


if __name__ == '__main__':
    content = "路在脚下!"
    print(Feishu().sendTextmessage(content))
