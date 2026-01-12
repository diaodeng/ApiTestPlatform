from module_pressure.service.dag_validator.errors import DagValidationError, DeadNodeError

"""
校验点

edge 指向的 node 必须存在

非 end 节点不能没有任何出边

"""

def check_structure(dag):
    for node in dag.nodes.values():
        for edge, targets in node.edges.items():
            for t in targets:
                if t not in dag.nodes:
                    raise DeadNodeError(
                        f"node {node.name} points to missing node {t}"
                    )

        if node.type != "end" and not node.edges:
            raise DeadNodeError(f"node {node.name} has no outgoing edges")
