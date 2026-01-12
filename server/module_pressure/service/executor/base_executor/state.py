from enum import Enum, auto


class State(Enum):
    READY = auto()
    RUNNING = auto()
    FAILED = auto()
    FINISHED = auto()
    STOPPED = auto()


class ExecutionState:
    def __init__(self, start_node_id):
        self.current = start_node_id
        self.state = State.READY
        self.steps = []  # 执行轨迹（node_id 序列）

    def move(self, node_id):
        self.current = node_id
        self.steps.append(node_id)
