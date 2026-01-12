from module_pressure.service.dag_validator.errors import UnreachableEndError, DeadNodeError

"""
校验点

start 能否到达 end

是否存在 start 可达、但 end 不可达的节点
"""

def check_reachability(dag):
    visited = set()

    def dfs(nid):
        if nid in visited:
            return
        visited.add(nid)
        for targets in dag.nodes[nid].edges.values():
            for t in targets:
                dfs(t)

    dfs(dag.start.id)

    if dag.end.id not in visited:
        raise UnreachableEndError("end node is unreachable")

    for nid, node in dag.nodes.items():
        if nid not in visited and node.type != "end":
            raise DeadNodeError(f"node {node.name} is unreachable")
