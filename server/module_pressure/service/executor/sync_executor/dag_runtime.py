from ..base_executor.state import ExecutionState, State
from ..base_executor.execution_context import ExecutionContext
from ..base_executor.dag_runtime import DagRuntime

class SyncDagRuntime(DagRuntime):
    def __init__(self, dag, handlers):
        super().__init__(dag, handlers)

    def step(self, state: ExecutionState, ctx: ExecutionContext):
        node = self.dag.nodes[state.current]
        handler = self.handlers[node.type]

        success, edge = handler.execute(node, ctx)

        if edge is None:
            state.state = State.FINISHED
            return

        next_nodes = node.edges.get(edge)
        if not next_nodes:
            raise RuntimeError(
                f"no edge '{edge}' from node {node.name}"
            )

        state.move(next_nodes[0])
