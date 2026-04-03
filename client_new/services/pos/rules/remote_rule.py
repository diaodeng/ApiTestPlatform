from .base_rule import BaseRule, RuleResult


class NoRemoteRule(BaseRule):
    def apply(self, ctx):
        if not ctx.has_remote and not ctx.start_config.change_pos:
            return RuleResult(
                need_confirm=True,
                message=f"服务端无机台信息，是否继续？\n{ctx.remote_info}",
            )
        return RuleResult()
