import aiohttp

from ..base_executor.node_handler import NodeHandler as AsyncNodeHandler



class AsyncRequestHandler(AsyncNodeHandler):
    async def execute(self, node, ctx):
        try:
            # 示例：伪 HTTP 调用
            async with aiohttp.ClientSession() as session:
                async with session.request(
                        method=node.meta["method"],
                        url=node.meta["url"],
                        timeout=node.meta.get("timeout", 5)
                ) as resp:
                    body = await resp.text()
                    ctx.record_result(node.id, {
                        "status": resp.status,
                        "body": body
                    })

                    # 断言
                    for assert_expr in node.meta.get("asserts", []):
                        if not eval(assert_expr, {}, resp):
                            raise AssertionError(assert_expr)

            return True, "success"

        except Exception as e:
            ctx.record_error(node.id, e)
            return False, "fail"


class AsyncIfHandler(AsyncNodeHandler):
    async def execute(self, node, ctx):
        return super().execute(node, ctx)


class AsyncLoopHandler(AsyncNodeHandler):
    async def execute(self, node, ctx):
        return super().execute(node, ctx)


class AsyncRetryHandler(AsyncNodeHandler):
    async def execute(self, node, ctx):
        return super().execute(node, ctx)


class AsyncEndHandler(AsyncNodeHandler):
    async def execute(self, node, ctx):
        return super().execute(node, ctx)
