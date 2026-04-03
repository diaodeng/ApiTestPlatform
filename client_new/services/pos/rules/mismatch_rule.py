from .base_rule import BaseRule, RuleResult


class MismatchRule(BaseRule):
    def apply(self, ctx):
        if ctx.has_local and ctx.has_remote:
            l = ctx.local_pos_params
            r = ctx.remote_pos_params

            if l.venderNo != r.venderNo or l.orgNo != r.orgNo or l.posId != r.posId:
                return RuleResult(
                    need_confirm=True,
                    choice=True,
                    message=f"配置不一致：\n服务端：{ctx.remote_info}",
                )
        return RuleResult()
