from module_pressure.service.dag_validator.errors import InvalidGotoError
"""
核心规则（非常重要）

goto 只能跳到“同一 step 层级”的 request 节点

不能：

跳进 loop 内部

跳出当前 if / loop 结构
"""
def build_parent_map(dag):
    parent = {}

    def walk(nid, stack):
        parent[nid] = list(stack)
        for targets in dag.nodes[nid].edges.values():
            for t in targets:
                walk(t, stack + [nid])

    walk(dag.start.id, [])
    return parent


def check_goto(dag):
    parent_map = build_parent_map(dag)

    for node in dag.nodes.values():
        if node.meta.get("on_fail", {}).get("action") == "goto":
            target = node.meta["on_fail"]["target"]

            if target not in dag.name_map:
                raise InvalidGotoError(f"goto target {target} not found")

            src_scope = set(parent_map[node.id])
            dst_scope = set(parent_map[dag.name_map[target]])

            if src_scope != dst_scope:
                raise InvalidGotoError(
                    f"illegal goto from {node.name} to {target}"
                )
