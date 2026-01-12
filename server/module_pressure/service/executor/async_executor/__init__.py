import asyncio

from dag_runtime import AsyncDagRuntime
from node_handler import AsyncRequestHandler, AsyncRetryHandler, AsyncIfHandler, AsyncLoopHandler, AsyncEndHandler
from ..base_executor.state import ExecutionState, State
from ..base_executor.execution_context import ExecutionContext

from gevent.pool import Pool
import gevent

class AsyncDagExecutor:
    def __init__(self, dag):
        self.runtime = AsyncDagRuntime(dag, {
            "request": AsyncRequestHandler(),
            "if": AsyncIfHandler(),
            "loop": AsyncLoopHandler(),
            "retry": AsyncRetryHandler(),
            "end": AsyncEndHandler(),
        })

    async def run(self, variables=None):
        ctx = ExecutionContext(variables)
        state = ExecutionState(self.runtime.dag.start.id)
        state.state = State.RUNNING

        try:
            while state.state == State.RUNNING:
                await self.runtime.step(state, ctx)

        except Exception as e:
            state.state = State.FAILED
            ctx.record_error(state.current, e)

        return state, ctx




# fastapi中并发执行
async def run_many(dag, cases):
    executor = AsyncDagExecutor(dag)

    tasks = [
        asyncio.create_task(executor.run(vars))
        for vars in cases
    ]

    return await asyncio.gather(*tasks)
