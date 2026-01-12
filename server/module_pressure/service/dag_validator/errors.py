class DagValidationError(Exception):
    pass


class DeadNodeError(DagValidationError):
    pass


class UnreachableEndError(DagValidationError):
    pass


class InvalidGotoError(DagValidationError):
    pass


class InfiniteLoopError(DagValidationError):
    pass


class PathExplosionError(DagValidationError):
    pass
