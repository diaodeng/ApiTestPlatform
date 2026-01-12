from module_pressure.service.dag_validator.errors import PathExplosionError

"""
思路（不做完全路径枚举）

if：路径 ×2

loop：路径 × times（上限）

retry：路径 × (times + 1)
"""
MAX_PATHS = 10_000


def check_path_explosion(dag):
    def estimate(nid, visited):
        if nid in visited:
            return 1

        node = dag.nodes[nid]
        visited.add(nid)

        if node.type == "if":
            t = estimate(node.edges["true"][0], visited.copy())
            f = estimate(node.edges["false"][0], visited.copy())
            return t + f

        if node.type == "loop":
            times = int(node.meta.get("times", 1))
            body = estimate(node.edges["enter"][0], visited.copy())
            return body * times

        total = 1
        for targets in node.edges.values():
            for t in targets:
                total *= estimate(t, visited.copy())

        return total

    total = estimate(dag.start.id, set())

    if total > MAX_PATHS:
        raise PathExplosionError(
            f"path count {total} exceeds limit {MAX_PATHS}"
        )
