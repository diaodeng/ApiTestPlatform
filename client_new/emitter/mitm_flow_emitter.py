# flow_emitter.py
from PySide6.QtCore import QObject, Signal


class FlowEmitter(QObject):
    new_flow = Signal(object)  # FlowItem
    update_flow = Signal(object)


flow_emitter = FlowEmitter()
