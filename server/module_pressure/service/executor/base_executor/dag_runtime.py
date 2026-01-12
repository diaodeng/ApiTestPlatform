from state import ExecutionState, State
from .execution_context import ExecutionContext

class DagRuntime:
    def __init__(self, dag, handlers):
        self.dag = dag
        self.handlers = handlers

    def step(self, state: ExecutionState, ctx: ExecutionContext):
        raise NotImplementedError()
