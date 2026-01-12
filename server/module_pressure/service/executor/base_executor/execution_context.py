

class ExecutionContext:
    def __init__(self, variables=None):
        self.vars = variables or {}
        self.results = {}
        self.errors = []
        self.loop_stack = []
        self.retry_stack = []

    def get(self, key, default=None):
        return self.vars.get(key, default)

    def set(self, key, value):
        self.vars[key] = value

    def record_result(self, node_id, result):
        self.results[node_id] = result

    def record_error(self, node_id, error):
        self.errors.append((node_id, str(error)))
