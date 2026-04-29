from .base_rule import BaseRule, RuleResult


class LocalEnvRule(BaseRule):
    def apply(self, ctx):
        if not ctx.has_local:
            return RuleResult(
                continue_flow=False,
                need_confirm=False,
                message="没有获取到本地环境信息",
            )
        return RuleResult()
