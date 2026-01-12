from dag_runtime import SyncDagRuntime
from node_handler import RetryHandler
from node_handler import RequestHandler
from node_handler import IfHandler
from node_handler import LoopHandler
from node_handler import EndHandler
from ..base_executor.execution_context import ExecutionContext
from ..base_executor.state import ExecutionState, State

from gevent.pool import Pool
import gevent

class DagExecutor:
    def __init__(self, dag):
        self.runtime = SyncDagRuntime(dag, {
            "request": RequestHandler(),
            "if": IfHandler(),
            "loop": LoopHandler(),
            "retry": RetryHandler(),
            "end": EndHandler(),
        })

    def run(self, variables=None):
        ctx = ExecutionContext(variables)
        state = ExecutionState(self.runtime.dag.start.id)
        state.state = State.RUNNING

        try:
            while state.state == State.RUNNING:
                self.runtime.step(state, ctx)

        except Exception as e:
            state.state = State.FAILED
            ctx.record_error(state.current, e)

        return state, ctx




# locust中并发执行
def run_many_gevent(dag, cases, size=100):
    pool = Pool(size)
    executor = DagExecutor(dag)

    jobs = [
        pool.spawn(executor.run, vars)
        for vars in cases
    ]

    gevent.joinall(jobs)
    return [job.value for job in jobs]