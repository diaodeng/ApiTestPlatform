import aiohttp

from .execution_context import ExecutionContext

class NodeHandler:
    def execute(self, node, ctx: ExecutionContext):
        """
        返回：
          success: bool
          next_edge: str
        """
        raise NotImplementedError


class RequestHandler(NodeHandler):
    def execute(self, node, ctx):
        raise NotImplementedError


class IfHandler(NodeHandler):
    def execute(self, node, ctx):
        cond = node.meta["condition"]
        result = eval(cond, {}, ctx.vars)
        return True, "true" if result else "false"


class LoopHandler(NodeHandler):
    def execute(self, node, ctx):
        if not ctx.loop_stack or ctx.loop_stack[-1]["id"] != node.id:
            ctx.loop_stack.append({
                "id": node.id,
                "count": 0,
                "max": node.meta.get("times", 1)
            })

        loop = ctx.loop_stack[-1]
        if loop["count"] < loop["max"]:
            loop["count"] += 1
            return True, "enter"
        else:
            ctx.loop_stack.pop()
            return True, "exit"


class RetryHandler(NodeHandler):
    def execute(self, node, ctx):
        retry = node.meta.get("retry", 1)

        if not ctx.retry_stack or ctx.retry_stack[-1]["id"] != node.id:
            ctx.retry_stack.append({
                "id": node.id,
                "count": 0,
                "max": retry
            })

        r = ctx.retry_stack[-1]
        if r["count"] < r["max"]:
            r["count"] += 1
            return True, "retry"
        else:
            ctx.retry_stack.pop()
            return True, "fail"


class EndHandler(NodeHandler):
    def execute(self, node, ctx):
        return True, None
