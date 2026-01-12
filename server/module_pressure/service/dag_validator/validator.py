from module_pressure.service.dag_validator.rules.path import check_path_explosion
from module_pressure.service.dag_validator.rules.goto import check_goto
from module_pressure.service.dag_validator.rules.loop import check_loop_safety
from module_pressure.service.dag_validator.rules.reachability import check_reachability
from module_pressure.service.dag_validator.rules.retry import check_retry_safety
from module_pressure.service.dag_validator.rules.structure import check_structure

class DagValidator:
    def __init__(self, dag):
        self.dag = dag
        self.nodes = dag.nodes
        self.start = dag.start.id
        self.end = dag.end.id

    def validate(self):
        check_structure(self.dag)
        check_reachability(self.dag)
        check_goto(self.dag)
        check_loop_safety(self.dag)
        check_retry_safety(self.dag)
        check_path_explosion(self.dag)

