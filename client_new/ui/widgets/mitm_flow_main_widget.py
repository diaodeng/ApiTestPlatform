# flow_main_widget.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from .mitm_flow_detail_widget import FlowDetailWidget
from .mitm_flow_table_widget import FlowTableWidget


class FlowMainWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.table = FlowTableWidget(self)
        self.detail = FlowDetailWidget(self)
        self._last_sizes = [900, 420]

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.detail)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setCollapsible(1, True)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes(self._last_sizes)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)
        self.setLayout(layout)

        self._bind()

    def _bind(self):
        self.table.flow_selected.connect(self._on_flow_selected)
        self.splitter.splitterMoved.connect(self._remember_sizes)

    def _on_flow_selected(self, item):
        if item is None:
            self.detail.clear()
            return
        self.detail.show_flow(item)

    def _remember_sizes(self, *_args):
        sizes = self.splitter.sizes()
        if len(sizes) == 2 and sizes[1] > 0:
            self._last_sizes = sizes

    def set_detail_visible(self, visible: bool):
        if visible:
            self.detail.show()
            self.splitter.setSizes(self._last_sizes)
            return

        sizes = self.splitter.sizes()
        if len(sizes) == 2 and sizes[1] > 0:
            self._last_sizes = sizes
        self.detail.hide()
        self.splitter.setSizes([sum(self._last_sizes), 0])

    def toggle_detail(self) -> bool:
        visible = self.detail.isVisible()
        self.set_detail_visible(not visible)
        return not visible

    def clear(self):
        self.table.clear()
        self.detail.clear()
