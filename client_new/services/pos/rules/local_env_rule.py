from .base_rule import BaseRule, RuleResult


class LocalEnvRule(BaseRule):
    """
    本地环境硬校验：只检查 pos.ini 是否可识别环境。

    注意：本规则只负责 pos.ini（本地环境标识），缺 pos_params（本地业务参数）
    属于"提示可继续"场景，由引擎 _env_decision 的确认弹窗处理，两者必须区分：
    缺 pos.ini 时环境完全未知，后续 pos_init 会兜底打到 test 地址，必须阻断；
    缺 pos_params 时仍可确认后启动，全流程不允许硬阻断。
    """

    def apply(self, ctx):
        if not ctx.local_env_info:
            return RuleResult(
                continue_flow=False,
                need_confirm=False,
                message="POS 目录缺少 pos.ini（或未配置 pos_env），无法识别 POS 环境，已停止启动",
            )
        return RuleResult()
