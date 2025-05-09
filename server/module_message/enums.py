from enum import Enum


class PushTypeEnum(Enum):
    """
    推送类型
    """
    DISABLED = (1, "禁用")
    ALWAYS = (2, "始终推送")
    SUCCESS = (4, "仅成功")
    FAIL = (8, "仅失败")

    def __init__(self, value, desc):
        self._value_ = value  # 必须通过 _value_ 设置枚举值
        self.desc = desc  # 自定义描述字段

    @classmethod
    def get_choices(cls):
        """返回前端可用的选项列表（值 + 描述）"""
        return [{"value": member.value, "desc": member.desc} for member in cls]

    @classmethod
    def get_desc(cls, value):
        """根据值获取描述"""
        for member in cls:
            if member.value == value:
                return member.desc
        return None  # 或抛出 ValueError


class PushWayEnum(Enum):
    """
    推送方式
    """
    FEISHU_BOT = (1, "飞书机器人")
    FEISHU_APPLICATION = (2, "飞书应用")
    WECHAT_PUBLIC = (4, "微信公众号")
    ENTERPRISE_WECHAT = (8, "企业微信")
    EMAIL = (16, "邮箱")
    SMS = (32, "短信")
    DINGDING = (64, "钉钉")

    def __init__(self, value, desc):
        self._value_ = value  # 必须通过 _value_ 设置枚举值
        self.desc = desc  # 自定义描述字段

    @classmethod
    def get_choices(cls):
        """返回前端可用的选项列表（值 + 描述）"""
        return [{"value": member.value, "desc": member.desc} for member in cls]

    @classmethod
    def get_desc(cls, value):
        """根据值获取描述"""
        for member in cls:
            if member.value == value:
                return member.desc
        return None  # 或抛出 ValueError


if __name__ == "__main__":
    print(PushTypeEnum.SUCCESS.value)
    print(PushTypeEnum.FAIL.desc)