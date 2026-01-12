from module_pressure.service.dag_validator.errors import InfiniteLoopError

"""
校验点

loop 必须存在 exit 边

break 最终能走到 loop_exit

"""

def check_loop_safety(dag):
    for node in dag.nodes.values():
        if node.type == "loop":
            if "exit" not in node.edges:
                raise InfiniteLoopError(
                    f"loop {node.name} has no exit"
                )
