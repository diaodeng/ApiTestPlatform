class RuleResult:
    def __init__(
        self, continue_flow=True, need_confirm=False, message="", choice=False
    ):
        self.continue_flow = continue_flow
        self.need_confirm = need_confirm
        self.message = message
        self.choice = choice


class BaseRule:
    def apply(self, ctx):
        raise NotImplementedError
