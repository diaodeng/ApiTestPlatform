from module_pressure.service.dag_validator.errors import InfiniteLoopError
"""
规则（保守但安全）

retry 节点不能位于 loop 内

retry 回路中必须存在“非 retry 退出路径”
"""

def check_retry_safety(dag):
    for node in dag.nodes.values():
        if node.type == "retry":
            # retry 自身是否形成闭环
            visited = set()

            def dfs(nid):
                if nid in visited:
                    return False
                visited.add(nid)
                for targets in dag.nodes[nid].edges.values():
                    for t in targets:
                        if dag.nodes[t].type != "retry":
                            return True
                        if dfs(t):
                            return True
                return False

            if not dfs(node.id):
                raise InfiniteLoopError(
                    f"retry loop at {node.name} has no exit"
                )
