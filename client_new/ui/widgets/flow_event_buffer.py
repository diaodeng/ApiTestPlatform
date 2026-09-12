from PySide6.QtCore import QObject, QTimer

# 默认批量刷新间隔（毫秒）：定时器制刷新，低频流量最多延迟一个间隔即显示
DEFAULT_FLUSH_INTERVAL_MS = 250
# 缓冲上限：极端流量下防止缓冲无限堆积，达到阈值立即落盘
MAX_PENDING_EVENTS = 500


class FlowEventBuffer(QObject):
    """
    流量事件缓冲层。

    在 flow_emitter 与 FlowTableModel 之间做定时批量写入：
    - 普通流量先入缓冲，定时器统一写入模型，避免高频流量逐条触发表格刷新、
      统计刷新和选中恢复，导致 UI 线程饱和；
    - 断点流量旁路缓冲立即写入，保证暂停中的请求第一时间展示、放行按钮即时可点；
      断点流量进入旁路前先落盘缓冲中的存量事件，保证插入与更新的先后顺序。
    """

    def __init__(
        self,
        model,
        flush_interval_ms: int = DEFAULT_FLUSH_INTERVAL_MS,
        parent=None,
    ):
        """
        :param model: FlowTableModel 实例，需支持 add_flow/add_flows/update_flow/update_flows
        :param flush_interval_ms: 批量刷新间隔毫秒
        :param parent: Qt 父对象
        """
        super().__init__(parent)
        self._model = model
        self._pending_new: list = []
        self._pending_update: dict = {}
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(max(int(flush_interval_ms), 50))
        self._flush_timer.timeout.connect(self._on_flush_timeout)
        self._flush_timer.start()

    def add_flow(self, item):
        """
        新流量入口：断点流量立即落库，普通流量进缓冲。
        :param item: FlowItem
        :return:
        """
        if self._is_breakpoint_priority(item):
            self.flush()
            self._model.add_flow(item)
            return

        self._pending_new.append(item)
        self._flush_if_overflow()

    def update_flow(self, item):
        """
        流量更新入口：断点流量立即落库，普通流量按 flow id 合并进缓冲（保留最新状态）。
        :param item: FlowItem
        :return:
        """
        if self._is_breakpoint_priority(item):
            self.flush()
            self._model.update_flow(item)
            return

        self._pending_update[item.id] = item
        self._flush_if_overflow()

    def flush(self):
        """
        把缓冲中的事件按“先新增后更新”的顺序一次性写入模型。
        :return:
        """
        pending_new = self._pending_new
        pending_update = self._pending_update
        if pending_new:
            self._pending_new = []
            self._model.add_flows(pending_new)
        if pending_update:
            self._pending_update = {}
            self._model.update_flows(list(pending_update.values()))

    def discard(self):
        """
        丢弃缓冲中的事件（清空流量列表时使用），定时器保持运行。
        :return:
        """
        self._pending_new = []
        self._pending_update = {}

    def _flush_if_overflow(self):
        if len(self._pending_new) + len(self._pending_update) >= MAX_PENDING_EVENTS:
            self.flush()

    def _on_flush_timeout(self):
        if self._pending_new or self._pending_update:
            self.flush()

    @staticmethod
    def _is_breakpoint_priority(item) -> bool:
        """
        断点流量需要即时展示与放行，旁路批量缓冲。
        :param item: FlowItem
        :return: 是否断点优先流量
        """
        return bool(getattr(item, "breakpoint_matched", False))
