from ..base_executor.node_handler import NodeHandler

class RequestHandler(NodeHandler):
    def execute(self, node, ctx):
        try:
            # 示例：伪 HTTP 调用
            resp = {
                "status": 200,
                "body": "ok"
            }
            ctx.record_result(node.id, resp)

            # 断言
            for assert_expr in node.meta.get("asserts", []):
                if not eval(assert_expr, {}, resp):
                    raise AssertionError(assert_expr)

            return True, "success"

        except Exception as e:
            ctx.record_error(node.id, e)
            return False, "fail"


class IfHandler(NodeHandler):
    def execute(self, node, ctx):
        return super().execute(node, ctx)


class LoopHandler(NodeHandler):
    def execute(self, node, ctx):
        return super().execute(node, ctx)


class RetryHandler(NodeHandler):
    def execute(self, node, ctx):
        return super().execute(node, ctx)


class EndHandler(NodeHandler):
    def execute(self, node, ctx):
        return super().execute(node, ctx)
