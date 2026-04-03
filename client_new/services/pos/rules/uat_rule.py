from .base_rule import BaseRule, RuleResult


class UatNoLocalRule(BaseRule):
    def apply(self, ctx):
        if ctx.is_uat and not ctx.has_local:
            return RuleResult(
                need_confirm=True,
                message="是UAT环境，但没有本地配置（pos_params），是否继续？",
            )
        return RuleResult()
